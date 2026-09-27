import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { createHmac, timingSafeEqual } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { join } from 'node:path';
import { stat as statP } from 'node:fs/promises';
import { loadChange, loadConventions } from './spec/loader.js';
import { getDiffRange } from './diff/git.js';
import { runReview, runReviewAsync } from './engine.js';
import { providerFromEnv } from './llm/provider.js';
import { loadConfig } from './config.js';
import { resolveTemplate } from './templates/detect.js';
import { builtinTemplates } from './templates/registry.js';
import { loadCustomTemplates } from './templates/parser.js';
import { getVcsProvider, ghRunner, glabRunner, partitionInline, buildReviewBody, findingKey, decodeMarker, type MrContext, type VcsProvider, type VcsRunner } from './vcs.js';
import { GitLabProvider } from './gitlab.js';
import type { ReviewOptions } from './engine.js';
import type { ReviewResult, Severity } from './types.js';
import type { ProjectTemplate } from './templates/types.js';

const execFileP = promisify(execFile);

// ---- Serve-mode caches: config/templates are re-read on EVERY webhook;
// mtime-keyed caching keeps them fresh on edits while cutting per-webhook
// syscalls. Remote detection is TTL-cached (git config rarely changes). ----
const CACHE_TTL_MS = 30_000;

interface CacheEntry<T> { key: string; value: T }
const configCache = new Map<string, CacheEntry<Awaited<ReturnType<typeof loadConfig>>>>();
const templatesCache = new Map<string, CacheEntry<{ customs: ProjectTemplate[]; template: Awaited<ReturnType<typeof resolveTemplate>> }>>();
const remoteCache = new Map<string, CacheEntry<string>>();

async function cachedRemote(root: string): Promise<string> {
  const hit = remoteCache.get(root);
  if (hit && Date.now() - Number(hit.key) < CACHE_TTL_MS) return hit.value;
  const value = await detectRemote(root);
  remoteCache.set(root, { key: String(Date.now()), value });
  return value;
}

async function fsKey(root: string, rel: string): Promise<string> {
  try {
    const st = await statP(join(root, rel));
    return String(st.mtimeMs);
  } catch {
    return 'absent';
  }
}

async function cachedConfig(root: string): Promise<Awaited<ReturnType<typeof loadConfig>>> {
  const key = await fsKey(root, join('openspec', 'review.yaml'));
  const hit = configCache.get(root);
  if (hit && hit.key === key) return hit.value;
  const value = await loadConfig(root, 'auto');
  configCache.set(root, { key, value });
  return value;
}

async function cachedTemplates(root: string): Promise<{ customs: ProjectTemplate[]; template: Awaited<ReturnType<typeof resolveTemplate>> }> {
  const key = await fsKey(root, join('openspec', 'review-templates'));
  const hit = templatesCache.get(root);
  if (hit && hit.key === key) return hit.value;
  const { templates: customs } = await loadCustomTemplates(root);
  const template = await resolveTemplate(root, 'auto', [...builtinTemplates(), ...customs]);
  const value = { customs, template };
  templatesCache.set(root, { key, value });
  return value;
}

export interface ServeOptions {
  port: number;
  host: string;
  /** Webhook secret — required by default (fail-closed); pass insecureDev to allow local dev without one. */
  secret?: string;
  /** Allow running without a secret (local dev only). Never use in production. */
  insecureDev?: boolean;
  /** Fail-closed secret enforcement (default true). */
  requireSecret?: boolean;
  /** Absolute per-request deadline in ms (default 30s). Kills slowloris-style trickles that keep the socket idle-timeout fed. */
  requestTimeoutMs?: number;
  /** Max concurrently RUNNING reviews before the server answers 503 instead of 202 (default 4). */
  maxParallelReviews?: number;
  root: string;
  /** Test seam: bypass gh/glab with a recorded provider + runner. */
  vcsOverride?: { provider: VcsProvider; run: VcsRunner };
  /** Test seam: use this change name instead of deriving it from the PR branch. */
  changeNameOverride?: string;
}

export interface WebhookPayload {
  action?: string;
  pull_request?: {
    number: number;
    head: { sha: string; ref?: string };
    base: { sha: string };
  };
  object_attributes?: {
    iid?: number;
    action?: string;
    sha?: string;
    source_branch?: string;
  };
  repository?: { full_name?: string };
  project?: { id?: number; path_with_namespace?: string };
}

type Provider = 'github' | 'gitlab';

/** Extract provider/event/payload from headers + raw body. Returns null if unsupported. */
export function parseWebhookEvent(
  headers: IncomingMessage['headers'],
  body: string
): { provider: Provider; event: string; action: string; payload: WebhookPayload } | null {
  const githubEvent = headers['x-github-event'] as string | undefined;
  const gitlabEvent = headers['x-gitlab-event'] as string | undefined;
  let payload: WebhookPayload;
  try {
    payload = JSON.parse(body) as WebhookPayload;
  } catch {
    return null;
  }
  if (typeof payload !== 'object' || payload === null) return null;

  if (githubEvent) {
    // Precedence note: a request carrying BOTH provider headers is treated as
    // GitHub. Both valid signatures share one secret by design; mixed-header
    // requests only occur from misconfigured proxies, never real providers.
    if (githubEvent !== 'pull_request') return null;
    if (!payload.pull_request?.number) return null;
    return { provider: 'github', event: githubEvent, action: payload.action ?? '', payload };
  }
  if (gitlabEvent) {
    // GitLab sends e.g. "Merge Request Hook"
    if (!/merge request/i.test(gitlabEvent)) return null;
    if (!payload.object_attributes?.iid) return null;
    return { provider: 'gitlab', event: gitlabEvent, action: payload.object_attributes.action ?? '', payload };
  }
  return null;
}

function safeEqual(a: Buffer, b: Buffer): boolean {
  return a.length === b.length && timingSafeEqual(a, b);
}

/** Verify the webhook signature for the given provider. */
export function verifySignature(
  provider: Provider,
  headers: IncomingMessage['headers'],
  rawBody: string,
  secret: string
): boolean {
  if (provider === 'github') {
    const sig = headers['x-hub-signature-256'] as string | undefined;
    if (!sig?.startsWith('sha256=')) return false;
    const digest = createHmac('sha256', secret).update(rawBody).digest('hex');
    return safeEqual(Buffer.from(sig.slice(7), 'utf8'), Buffer.from(digest, 'utf8'));
  }
  const token = headers['x-gitlab-token'] as string | undefined;
  if (!token) return false;
  return safeEqual(Buffer.from(token, 'utf8'), Buffer.from(secret, 'utf8')); // guardrails-allow PREVENT-003: constant-time compare of a request header token against the configured secret; no hardcoded credential
}

const REVIEWABLE_ACTIONS = new Set([
  'opened', 'synchronize', 'reopened', // GitHub
  'open', 'update', 'reopen' // GitLab
]);

/** Only open/synchronize/reopen deserve a fresh review. */
export function isReviewableAction(action: string): boolean {
  return REVIEWABLE_ACTIONS.has(action);
}

/** Serialized execution per key — concurrent webhooks for one repo queue up. */
export function createKeyedMutex(): <T>(key: string, fn: () => Promise<T>) => Promise<T> {
  const chains = new Map<string, Promise<unknown>>();
  return <T>(key: string, fn: () => Promise<T>): Promise<T> => {
    const prev = chains.get(key) ?? Promise.resolve();
    const next = prev.then(fn, fn);
    chains.set(key, next.catch(() => { /* keep chain rejection-free */ }));
    return next;
  };
}

/** Route path without query string (proxies may append delivery params). */
export function routePath(url: string | undefined): string {
  if (!url) return '';
  const q = url.indexOf('?');
  return q === -1 ? url : url.slice(0, q);
}

/**
 * Derive a change name from a branch slug. Full slug (not last segment, which
 * collides) sanitized for path safety; `..`/`.` segments collapse so a
 * hostile branch name cannot escape openspec/changes/.
 */
export function changeNameFromBranch(branch: string | undefined): string {
  if (!branch) return 'serve';
  const safe = branch.replace(/[^A-Za-z0-9._/-]/g, '-').replace(/^\/+|\/+$/g, '');
  const parts = safe.split('/').filter((p) => p !== '' && p !== '.' && p !== '..');
  return parts.length > 0 ? parts.join('/') : 'serve';
}

/** Remote PR/MR head ref name on the origin remote. */
export function prRemoteRef(provider: Provider, n: number): string {
  return provider === 'github' ? `refs/pull/${n}/head` : `refs/merge-requests/${n}/head`;
}

/** Local tracking ref the PR/MR head is fetched into (no checkout needed). */
export function prLocalRef(provider: Provider, n: number): string {
  return provider === 'github' ? `refs/remotes/origin/pr/${n}/head` : `refs/remotes/origin/mr/${n}/head`;
}

/** Detect the default remote name (usually "origin"). Falls back to "origin". */
async function detectRemote(root: string): Promise<string> {
  try {
    const { stdout } = await execFileP('git', ['remote'], { cwd: root, maxBuffer: 4 * 1024 * 1024, timeout: 10_000 });
    const remotes = stdout.split('\n').map((s) => s.trim()).filter(Boolean);
    if (remotes.includes('origin')) return 'origin';
    return remotes[0] ?? 'origin';
  } catch {
    return 'origin';
  }
}

/** Verify a remote URL belongs to the expected owner/repo (fork-safety). */
async function remoteUrlMatches(root: string, remote: string, owner: string, repo: string): Promise<boolean> {
  try {
    const { stdout } = await execFileP('git', ['config', '--get', `remote.${remote}.url`], { cwd: root, timeout: 10_000 });
    const url = stdout.trim().toLowerCase();
    if (!url) return true; // no URL configured — don't block local dev
    return url.includes(`${owner.toLowerCase()}/${repo.toLowerCase()}`);
  } catch {
    return true;
  }
}

/** Run a promise with a hard timeout (for detached background reviews). */
function withTimeout<T>(p: Promise<T>, ms: number, label: string): Promise<T> {
  let t: ReturnType<typeof setTimeout>;
  const timeout = new Promise<never>((_, reject) => {
    t = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
  });
  return Promise.race([p, timeout]).finally(() => clearTimeout(t!)) as Promise<T>;
}

/** Fetch the PR/MR head into a local tracking ref so we can diff without checkout. */
async function fetchPrRef(root: string, provider: Provider, n: number): Promise<void> {
  const remote = await detectRemote(root);
  await execFileP('git', ['fetch', '--force', remote, `+${prRemoteRef(provider, n)}:${prLocalRef(provider, n)}`], {
    cwd: root,
    maxBuffer: 16 * 1024 * 1024,
    timeout: 60_000
  });
}

function contextFromPayload(provider: Provider, payload: WebhookPayload): MrContext | null {
  if (provider === 'github') {
    const pr = payload.pull_request;
    const fullName = payload.repository?.full_name ?? '';
    const [owner, repo] = fullName.split('/');
    if (!pr || !owner || !repo) return null;
    return { provider, owner, repo, mrNumber: pr.number, headSha: pr.head.sha };
  }
  const attrs = payload.object_attributes;
  const path = payload.project?.path_with_namespace ?? '';
  const parts = path.split('/');
  const repo = parts.pop() ?? '';
  const owner = parts.join('/');
  if (!attrs?.iid || !owner || !repo) return null;
  return { provider, owner, repo, mrNumber: attrs.iid, headSha: attrs.sha, projectId: payload.project?.id };
}

/** Run the full review for one PR/MR event and post results. */
export async function handleReviewEvent(
  provider: Provider,
  payload: WebhookPayload,
  options: ServeOptions
): Promise<{ verdict: ReviewResult['verdict']; posted: number } | null> {
  const vcs = options.vcsOverride?.provider ?? await getVcsProvider(provider);
  const run = options.vcsOverride?.run ?? (provider === 'github' ? ghRunner(process.env.GITHUB_TOKEN) : glabRunner(process.env.GITLAB_TOKEN));
  const ctx = contextFromPayload(provider, payload);
  if (!ctx) return null;

  // Resolve diff refs — GitHub gets base from the payload; GitLab via MR API.
  let baseSha: string | undefined;
  if (provider === 'github') {
    baseSha = payload.pull_request?.base?.sha;
  } else {
    try {
      baseSha = (await (vcs as GitLabProvider).resolveDiffRefs(ctx, run)).base_sha;
    } catch {
      return null;
    }
  }
  if (!baseSha) return null;

  // Fetch the PR head so we can diff it without checking out.
  // Fork-safety: forks are allowed, but warn if the local remote doesn't match the webhook repo.
  try {
    const remote = await cachedRemote(options.root);
    const matches = await withTimeout(remoteUrlMatches(options.root, remote, ctx.owner, ctx.repo), 10_000, 'remoteUrlMatches');
    if (!matches) {
      console.error(`stitcher-codereview: warning: remote "${remote}" URL does not match ${ctx.owner}/${ctx.repo}; fetching anyway (fork PR).`);
    }
    await withTimeout(fetchPrRef(options.root, provider, ctx.mrNumber), 60_000, 'fetchPrRef');
  } catch (err) {
    console.error(`stitcher-codereview: failed to fetch ${prRemoteRef(provider, ctx.mrNumber)}: ${(err as Error).message}`);
    return null;
  }

  // Derive change name from the full branch slug (not just the last path segment,
  // which collides for `feature/foo` vs `other/foo`). Sanitize for path safety.
  const rawBranch = provider === 'github' ? payload.pull_request?.head?.ref : payload.object_attributes?.source_branch;
  const changeName = options.changeNameOverride ?? changeNameFromBranch(rawBranch);
  // Load policy first: config baselines feed loadChange, and the engine
  // policy below. Single load keeps serve + CLI precedence identical.
  const { config: fileCfg } = await cachedConfig(options.root);
  const change = await loadChange(options.root, changeName, fileCfg.baselines).catch(() => null);
  if (!change) {
    console.error(`stitcher-codereview: no change "${changeName}" for PR/MR #${ctx.mrNumber}; skipping.`);
    return null;
  }

  const diff = await withTimeout(getDiffRange(options.root, baseSha, prLocalRef(provider, ctx.mrNumber)), 60_000, 'getDiffRange');
  const conventions = await loadConventions(options.root);
  const { template } = await cachedTemplates(options.root);
  const categories = new Set(['all']);
  const engineOpts: ReviewOptions = {
    categories,
    template,
    base: baseSha,
    root: options.root,
    config: {
      disable: fileCfg.disable,
      severities: fileCfg.severities as Partial<Record<string, Severity>> | undefined,
      ignore: fileCfg.ignore,
      include: fileCfg.include,
      rules: fileCfg.rules,
      maxLineLength: fileCfg['max-line-length'] as number | undefined,
      coveredAt: fileCfg['covered-at'] as number | undefined,
      partialAt: fileCfg['partial-at'] as number | undefined,
      maxFindings: fileCfg['max-findings'] as number | undefined
    }
  };
  const llm = providerFromEnv(process.env, {
    llm: fileCfg.llm?.mode ?? 'off',
    provider: fileCfg.llm?.provider,
    model: fileCfg.llm?.model,
    weight: fileCfg.llm?.weight !== undefined ? String(fileCfg.llm.weight) : '0.5',
    baseUrl: fileCfg.llm?.['base-url'],
    maxConcurrency: fileCfg.llm?.maxConcurrency?.toString(),
    maxRetries: fileCfg.llm?.maxRetries?.toString()
  });
  const result = llm.mode !== 'off'
    ? await withTimeout(runReviewAsync(change, diff, conventions, engineOpts, llm), 120_000, 'runReviewAsync')
    : await withTimeout(runReview(change, diff, conventions, engineOpts), 120_000, 'runReview');

  const { comments, bodyOnly } = partitionInline(result, diff);
  const existing = new Set(await vcs.listPostedKeys(ctx, run));
  const fresh = comments.filter((c) => !decodeMarker(c.body).some((k) => existing.has(k)));
  const currentKeys = new Set(result.findings.map((f) => findingKey(f)));
  const stale = [...existing].filter((k) => !currentKeys.has(k)).length;

  if (fresh.length === 0 && bodyOnly.length === 0 && stale === 0) {
    console.error(`stitcher-codereview: ${provider} PR/MR #${ctx.mrNumber} — all findings already posted.`);
    return { verdict: result.verdict, posted: 0 };
  }
  const body = buildReviewBody(result, bodyOnly, stale);
  await vcs.postReview(ctx, { body, comments: fresh, commitId: ctx.headSha, run });
  console.error(`stitcher-codereview: posted ${fresh.length} inline comment(s) to ${provider} PR/MR #${ctx.mrNumber}.`);
  return { verdict: result.verdict, posted: fresh.length };
}

/** Maximum webhook request body size (1 MB). */
const MAX_BODY_BYTES = 1 * 1024 * 1024;

/** Request timeout in milliseconds (30 seconds). */
const REQUEST_TIMEOUT_MS = 30_000;

/** Simple per-IP token-bucket rate limiter (30 req/min by default). */
export function createRateLimiter(maxPerMinute = 30): (ip: string) => boolean {
  const hits = new Map<string, number[]>();
  return (ip: string): boolean => {
    const now = Date.now();
    const windowStart = now - 60_000;
    const arr = (hits.get(ip) ?? []).filter((t) => t > windowStart);
    if (arr.length >= maxPerMinute) {
      hits.set(ip, arr);
      return false;
    }
    arr.push(now);
    hits.set(ip, arr);
    // Evict stale entries to avoid unbounded growth.
    if (hits.size > 10_000) {
      for (const [k, v] of hits) {
        if (v.length === 0 || v[v.length - 1] < windowStart) hits.delete(k);
      }
    }
    return true;
  };
}

/** Build the HTTP server (exported for tests). */
export function createServeServer(options: ServeOptions): ReturnType<typeof createServer> {
  const mutex = createKeyedMutex();
  const allow = createRateLimiter();
  const maxParallel = options.maxParallelReviews ?? 4;
  const requestTimeoutMs = options.requestTimeoutMs ?? REQUEST_TIMEOUT_MS;
  let active = 0;

  return createServer(async (req: IncomingMessage, res: ServerResponse) => {
    // Idle-socket guard: dead peers that never finish their request.
    req.socket.setTimeout(REQUEST_TIMEOUT_MS, () => {
      if (!res.headersSent) {
        res.writeHead(408);
        res.end('Request Timeout');
      }
      req.destroy();
    });
    // Absolute wall-clock deadline: a slowloris peer dribbling bytes every
    // <30s would keep the idle timer fed forever; this cannot be fed.
    const deadline = setTimeout(() => {
      if (!res.headersSent) {
        res.writeHead(408);
        res.end('Request Timeout');
      }
      req.destroy();
    }, requestTimeoutMs);
    res.on('finish', () => clearTimeout(deadline));
    res.on('close', () => clearTimeout(deadline));

    if (req.method === 'GET' && routePath(req.url) === '/health') {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ ok: true }));
      return;
    }
    if (req.method !== 'POST' || routePath(req.url) !== '/webhook') {
      res.writeHead(404);
      res.end('Not Found');
      return;
    }

    const chunks: Buffer[] = [];
    let totalBytes = 0;
    try {
      for await (const chunk of req) {
        chunks.push(chunk as Buffer);
        totalBytes += (chunk as Buffer).length;
        if (totalBytes > MAX_BODY_BYTES) {
          res.writeHead(413);
          res.end('Payload Too Large');
          req.destroy();
          return;
        }
      }
    } catch {
      // Client disconnected or read error.
      if (!res.headersSent) {
        res.writeHead(400);
        res.end('Bad Request');
      }
      return;
    }
    const rawBody = Buffer.concat(chunks).toString('utf8');

    // Rate-limit before HMAC (cheap reject). Behind a reverse proxy the
    // immediate peer is the proxy — operators should also rate-limit there.
    const peer = req.socket.remoteAddress ?? 'unknown';
    if (!allow(peer)) {
      res.writeHead(429, { 'retry-after': '60' });
      res.end('Too Many Requests');
      return;
    }

    const parsed = parseWebhookEvent(req.headers, rawBody);
    if (!parsed) {
      res.writeHead(400);
      res.end('Bad Request: unsupported webhook');
      return;
    }
    // Fail-closed by default: a configured secret is required. The caller may
    // explicitly opt into insecure local dev via `insecureDev`.
    const effectiveSecret = options.secret ?? process.env.STITCHER_WEBHOOK_SECRET;
    const requireSecret = options.requireSecret ?? true;
    if (requireSecret && !effectiveSecret && !options.insecureDev) {
      res.writeHead(500);
      res.end('Server misconfigured: webhook secret required (pass --serve-secret or STITCHER_WEBHOOK_SECRET, or --insecure-dev for local dev only)');
      return;
    }
    if (effectiveSecret && !verifySignature(parsed.provider, req.headers, rawBody, effectiveSecret)) {
      res.writeHead(401);
      res.end('Unauthorized: invalid signature');
      return;
    }
    if (!effectiveSecret && !options.insecureDev) {
      // requireSecret === false path: still warn loudly.
      console.warn('Warning: webhook signature verification disabled (no secret). Local dev only.');
    }
    if (!isReviewableAction(parsed.action)) {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ ok: true, ignored: `action "${parsed.action}"` }));
      return;
    }
    // Capacity check BEFORE the 202 ack: a 202 followed by a silent drop is a
    // phantom success — the provider would never redeliver. Refusing with 503
    // lets GitHub/GitLab retry later. The slot is reserved synchronously (not
    // inside the deferred mutex) so concurrent acknowledgements cannot
    // overshoot the cap.
    if (active >= maxParallel) {
      res.writeHead(503, { 'retry-after': '30' });
      res.end('Service Unavailable: review capacity reached');
      return;
    }
    active++;

    // Ack immediately; review runs serialized per repo.
    res.writeHead(202, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ ok: true, queued: true }));

    const repoKey = parsed.payload.project?.path_with_namespace ?? parsed.payload.repository?.full_name ?? `unknown:${peer}`;
    void mutex(`${repoKey}#${parsed.provider}`, async () => {
      try {
        await withTimeout(handleReviewEvent(parsed.provider, parsed.payload, options), 180_000, 'handleReviewEvent');
      } catch (err) {
        console.error('stitcher-codereview: background review failed:', (err as Error).message);
      } finally {
        active--;
      }
    });
  });
}

/** Start the webhook server and wire graceful shutdown. */
export async function startServe(options: ServeOptions): Promise<void> {
  const effectiveSecret = options.secret ?? process.env.STITCHER_WEBHOOK_SECRET;
  const requireSecret = options.requireSecret ?? true;
  if (!effectiveSecret && !options.insecureDev && requireSecret) {
    throw new Error('Webhook secret required: pass --serve-secret <s> or STITCHER_WEBHOOK_SECRET. For local dev only, pass --insecure-dev (never in production).');
  }
  if (!effectiveSecret) {
    console.warn('Warning: No webhook secret provided. Signature verification disabled. Local dev only — never expose to the internet.');
  }
  if (options.host === '0.0.0.0' || options.host === '::') {
    console.warn('Warning: listening on all interfaces without in-process TLS. Run behind a TLS-terminating reverse proxy and enforce https (x-forwarded-proto).');
  }
  const server = createServeServer(options);
  server.listen(options.port, options.host, () => {
    console.log(`stitcher-codereview serve listening on ${options.host}:${options.port}`);
    console.log('Webhook endpoint: POST /webhook   Health: GET /health');
  });
  const shutdown = (signal: string) => {
    console.error(`stitcher-codereview: ${signal} received, shutting down.`);
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(1), 5000).unref();
  };
  process.once('SIGINT', () => shutdown('SIGINT'));
  process.once('SIGTERM', () => shutdown('SIGTERM'));
}
