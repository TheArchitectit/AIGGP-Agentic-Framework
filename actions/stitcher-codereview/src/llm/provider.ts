import type { Diff, Requirement } from '../types.js';

export type LLMMode = 'off' | 'auto' | 'require' | 'gap';

export interface RescoreResult {
  /** 0 = not implemented, 0.5 = partial, 1 = fully implemented */
  score: number;
  rationale: string;
}

/** Line-level gap finding from LLM requirement-gap analysis. */
export interface GapFinding {
  /** File path relative to repo root (must match a file in the diff). */
  file: string;
  /** Line number in the new file (added line). */
  line: number;
  /** Human-readable message describing the gap. */
  message: string;
  /** Optional executable fix or AI-agent prompt snippet. */
  suggestion?: string;
  /** Severity of the gap. */
  severity: 'blocker' | 'high' | 'medium' | 'low' | 'info';
  /** Which scenario/requirement this relates to. */
  requirementId?: string;
}

export interface LLMProvider {
  readonly name: string;
  rescore(req: Requirement, diffSlice: string, opts?: { lens?: string }): Promise<RescoreResult | null>;
  /** Analyze requirement vs diff for line-level gaps. Returns null if unavailable. */
  analyzeGaps(req: Requirement, diffSlice: string, opts?: { lens?: string }): Promise<GapFinding[] | null>;
}

/** Thresholds shared with the heuristic scorer: >=0.30 covered, >=0.12 partial. */
export const COVERED_AT = 0.3;
export const PARTIAL_AT = 0.12;

export function statusForScore(
  score: number,
  coveredAt: number = COVERED_AT,
  partialAt: number = PARTIAL_AT
): 'covered' | 'partial' | 'missing' {
  if (score >= coveredAt) return 'covered';
  if (score >= partialAt) return 'partial';
  return 'missing';
}

/** Weighted blend. llm=null means the provider was unavailable → heuristic stands. */
export function blendScores(heuristic: number, llm: number | null, weight: number): number {
  const w = Math.min(1, Math.max(0, weight));
  if (llm === null || Number.isNaN(llm)) return heuristic;
  return w * llm + (1 - w) * heuristic;
}

function clamp01(n: number): number {
  return Math.min(1, Math.max(0, n));
}

/**
 * Build a bounded diff excerpt biased toward files matching the requirement's
 * capability path, so the model judges relevant code instead of the whole diff.
 */
export function buildDiffSlice(req: Requirement, diff: Diff, maxChars = 8000): string {
  const capTokens = req.capability.toLowerCase().split(/[/_-]/).filter((t) => t.length > 2);
  const ranked = [...diff.files].sort((a, b) => {
    const sa = capTokens.some((t) => a.path.toLowerCase().includes(t)) ? 0 : 1;
    const sb = capTokens.some((t) => b.path.toLowerCase().includes(t)) ? 0 : 1;
    return sa - sb;
  });
  const out: string[] = [];
  let used = 0;
  for (const f of ranked) {
    for (const l of f.addedLines) {
      const row = `+++ ${f.path}:${l.n}: ${l.text}\n`;
      if (used + row.length > maxChars) return out.join('');
      out.push(row);
      used += row.length;
    }
  }
  return out.join('');
}

export function buildRequirementPrompt(
  req: Requirement,
  diffSlice: string,
  lens?: string
): { system: string; user: string } {
  const scenarios =
    req.scenarios.map((s) => `- ${s.name}: ${s.whenThen.join(' / ')}`).join('\n') || '(no scenarios)';
  const base =
    'You are a strict spec-compliance reviewer. Judge whether the code diff implements the requirement. ' +
    'Reply with a single JSON object: {"score": <0..1>, "rationale": "<one sentence>"}. ' +
    'Use 1.0 fully implemented, 0.5 partially (some scenarios missing), 0.0 not implemented. No other text.';
  return {
    system: lens ? `${base} Project context: ${lens}` : base,
    user:
      `Requirement [${req.operation}]: ${req.id}\n${req.text}\nScenarios:\n${scenarios}\n\nDiff excerpt (added lines):\n${diffSlice || '(empty diff)'}`
  };
}

/** Build prompt for line-level gap analysis. */
export function buildGapPrompt(
  req: Requirement,
  diffSlice: string,
  lens?: string
): { system: string; user: string } {
  const scenarios =
    req.scenarios.map((s) => `- ${s.name}: ${s.whenThen.join(' / ')}`).join('\n') || '(no scenarios)';
  const base =
    'You are a precise code reviewer. Analyze the diff against the requirement and identify specific gaps at the line level. ' +
    'Reply with a JSON array of gap findings. Each finding: {"file": "<path>", "line": <int>, "message": "<gap description>", "severity": "blocker|high|medium|low|info", "suggestion": "<optional fix or AI agent prompt>", "requirementId": "<req id>"}. ' +
    'Only include findings anchored to actual added lines in the diff. Use exact file paths and line numbers from the diff excerpt. ' +
    'If no gaps, return []. No other text.';
  return {
    system: lens ? `${base} Project context: ${lens}` : base,
    user:
      `Requirement [${req.operation}]: ${req.id}\n${req.text}\nScenarios:\n${scenarios}\n\nDiff excerpt (added lines):\n${diffSlice || '(empty diff)'}`
  };
}

/** Extract gap findings array from LLM response. */
export function extractGapFindings(text: string, maxItems = 50): GapFinding[] | null {
  if (typeof text !== 'string' || text.length > 500_000) return null;
  const m = text.match(/\[[\s\S]*?\]/);
  if (!m || m[0].length > 200_000) return null;
  try {
    const arr = JSON.parse(m[0]) as unknown[];
    if (!Array.isArray(arr)) return null;
    const out: GapFinding[] = [];
    const validSeverity = (s: string): s is 'blocker' | 'high' | 'medium' | 'low' | 'info' =>
      ['blocker', 'high', 'medium', 'low', 'info'].includes(s);
    for (const item of arr.slice(0, maxItems)) {
      if (typeof item !== 'object' || item === null) continue;
      const o = item as Record<string, unknown>;
      if (typeof o.file !== 'string' || typeof o.line !== 'number' || typeof o.message !== 'string' || typeof o.severity !== 'string') continue;
      if (!validSeverity(o.severity)) continue;
      if (o.file.length > 500 || o.message.length > 2000) continue;
      if (!Number.isInteger(o.line) || o.line < 1 || o.line > 10_000_000) continue;
      out.push({
        file: o.file,
        line: o.line,
        message: o.message.slice(0, 2000),
        severity: o.severity,
        suggestion: typeof o.suggestion === 'string' ? o.suggestion.slice(0, 2000) : undefined,
        requirementId: typeof o.requirementId === 'string' ? o.requirementId.slice(0, 200) : undefined
      });
    }
    return out;
  } catch {
    return null;
  }
}

function extractJsonScore(text: string): RescoreResult | null {
  if (typeof text !== 'string' || text.length > 200_000) return null;
  const m = text.match(/\{[\s\S]*?\}/);
  if (!m || m[0].length > 20_000) return null;
  try {
    const o = JSON.parse(m[0]) as { score?: unknown; rationale?: unknown };
    if (typeof o.score !== 'number') return null;
    return {
      score: clamp01(o.score),
      rationale: typeof o.rationale === 'string' ? o.rationale.slice(0, 300) : ''
    };
  } catch {
    return null;
  }
}

async function postJson(url: string, headers: Record<string, string>, body: unknown, timeoutMs: number): Promise<Response> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const raw = JSON.stringify(body);
    if (raw.length > 200_000) throw new Error('LLM request body too large');
    return await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...headers },
      body: raw,
      signal: ctrl.signal
    });
  } finally {
    clearTimeout(t);
  }
}

/**
 * Parse a hostname into IPv4 octets, accepting the forms attackers use to
 * obfuscate: dotted quad, decimal/hex/octal integer, A.B.C, A.B, per-part
 * hex/octal (0x7f.1, 0177.0.0.1). Returns null when not an IPv4 literal.
 */
function parseIPv4(raw: string): [number, number, number, number] | null {
  const part = (s: string): number | null => {
    if (/^0x[0-9a-f]+$/i.test(s)) return parseInt(s.slice(2), 16);
    if (/^0[0-7]+$/.test(s)) return parseInt(s.slice(1), 8);
    if (/^\d+$/.test(s)) return Number(s);
    return null;
  };
  const segs = raw.split('.');
  if (segs.length === 0 || segs.length > 4) return null;
  const nums: number[] = [];
  for (let i = 0; i < segs.length; i++) {
    const n = part(segs[i]);
    // WHATWG IPv4 parser: every part except the last must be <= 255; the last
    // may carry the remaining weight (256 ** (5 - length)).
    const cap = i < segs.length - 1 ? 255 : 256 ** (5 - segs.length);
    if (n === null || n < 0 || n > cap) return null;
    nums.push(n);
  }
  let value = 0;
  for (const n of nums) value = value * 256 + n;
  if (value > 0xffffffff) return null;
  return [(value >>> 24) & 255, (value >>> 16) & 255, (value >>> 8) & 255, value & 255];
}

/** Extract IPv4 octets from an IPv4-mapped IPv6 host in either canonical form. */
function mappedIpv4(host: string): [number, number, number, number] | null {
  const m = /^::ffff:(.+)$/i.exec(host);
  if (!m) return null;
  const rest = m[1];
  if (rest.includes('.')) return parseIPv4(rest); // ::ffff:169.254.169.254
  const groups = rest.split(':');
  if (groups.length === 2) {
    const hi = parseInt(groups[0], 16);
    const lo = parseInt(groups[1], 16);
    if (Number.isFinite(hi) && Number.isFinite(lo)) {
      return [(hi >>> 8) & 255, hi & 255, (lo >>> 8) & 255, lo & 255];
    }
  }
  return null;
}

/**
 * True when the host resolves to loopback, link-local/metadata, or RFC1918
 * space. Handles IPv4-mapped IPv6 (both canonical hex and dotted forms) and
 * every IPv4 literal encoding.
 */
export function isSensitiveHost(rawHost: string): 'loopback' | 'private' | null {
  let h = rawHost.toLowerCase().trim().replace(/^\[|\]$/g, '').replace(/\.+$/, '');
  if (h === '::1' || h === '::') return 'loopback';
  const mapped = mappedIpv4(h);
  if (mapped) h = mapped.join('.');
  if (h === 'localhost' || h.endsWith('.localhost')) return 'loopback';
  if (h === 'metadata' || h === 'metadata.google.internal' || h.endsWith('.internal')) return 'private';
  const v4 = parseIPv4(h);
  if (v4) {
    const [a, b] = v4;
    if (a === 127 || a === 0) return 'loopback';
    if (a === 169 && b === 254) return 'private';
    if (a === 10) return 'private';
    if (a === 192 && b === 168) return 'private';
    if (a === 172 && b >= 16 && b <= 31) return 'private';
    if (a === 100 && b >= 64 && b <= 127) return 'private';
  }
  return null;
}

/** Validate and normalize a base URL; throws on non-http(s) and SSRF-suspicious hosts. */
export function validateBaseUrl(raw: string): string {
  let u: URL;
  try {
    u = new URL(raw);
  } catch {
    throw new Error(`Invalid LLM base URL: ${raw}`);
  }
  if (u.protocol !== 'https:' && u.protocol !== 'http:') throw new Error(`LLM base URL must be http(s): ${raw}`);
  const kind = isSensitiveHost(u.hostname);
  if (kind === 'private') throw new Error(`LLM base URL host blocked (private/link-local/metadata): ${u.hostname}`);
  if (kind === 'loopback' && u.protocol !== 'http:') {
    throw new Error(`Local LLM base URL must use http: ${raw}`);
  }
  return raw.replace(/\/$/, '');
}

async function readJsonCapped(res: Response, maxBytes = 1_000_000): Promise<unknown> {
  const len = res.headers.get('content-length');
  if (len && Number(len) > maxBytes) throw new Error(`LLM response too large (${len} bytes)`);
  const text = await res.text();
  if (text.length > maxBytes) throw new Error(`LLM response too large (${text.length} chars)`);
  return JSON.parse(text);
}

/** Simple semaphore for concurrency control. */
export class Semaphore {
  private permits: number;
  private waiters: ((v: void) => void)[] = [];
  constructor(maxConcurrency: number) {
    const n = Math.floor(Number(maxConcurrency));
    this.permits = Number.isFinite(n) && n >= 1 ? Math.min(n, 32) : 1;
  }
  async acquire(): Promise<() => void> {
    if (this.permits > 0) {
      this.permits--;
      return () => this.release();
    }
    return new Promise<void>((resolve) => { // guardrails-allow SEMANTIC-001: the executor captures only `resolve` (no reject path), so this chain cannot reject; a .catch() would be unreachable dead code
      this.waiters.push(resolve);
    }).then(() => () => this.release());
  }
  private release() {
    this.permits++;
    if (this.waiters.length > 0) {
      this.permits--;
      this.waiters.shift()!();
    }
  }
}

/** Retry with exponential backoff. */
export async function withRetry<T>(fn: () => Promise<T>, maxRetries = 2, baseDelayMs = 500): Promise<T> {
  let lastErr: unknown;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (attempt < maxRetries) {
        const { randomBytes } = await import('node:crypto');
        const jitter = randomBytes(1)[0] / 255 * 100; // 0-100ms jitter
        const delay = baseDelayMs * 2 ** attempt + jitter;
        await new Promise((r) => setTimeout(r, delay));
      }
    }
  }
  throw lastErr;
}

/** OpenAI-compatible chat completions (OpenAI, OpenRouter, Ollama, vLLM, ...). */
export class OpenAICompatibleProvider implements LLMProvider {
  readonly name: string;
  constructor(
    private opts: { apiKey?: string; baseUrl: string; model: string; timeoutMs?: number }
  ) {
    this.name = `openai-compatible:${opts.model}`;
  }
  async rescore(req: Requirement, diffSlice: string, opts?: { lens?: string }): Promise<RescoreResult | null> {
    const { system, user } = buildRequirementPrompt(req, diffSlice, opts?.lens);
    const headers: Record<string, string> = {};
    if (this.opts.apiKey) headers.authorization = `Bearer ${this.opts.apiKey}`;
    try {
      const base = validateBaseUrl(this.opts.baseUrl);
      const res = await postJson(
        `${base}/chat/completions`,
        headers,
        { model: this.opts.model, temperature: 0, max_tokens: 400, messages: [{ role: 'system', content: system }, { role: 'user', content: user }] },
        this.opts.timeoutMs ?? 30_000
      );
      if (!res.ok) return null;
      const body = (await readJsonCapped(res)) as { choices?: { message?: { content?: string } }[] };
      const text = body.choices?.[0]?.message?.content ?? '';
      return extractJsonScore(text);
    } catch {
      return null; // fail-open: caller falls back to heuristic
    }
  }
  async analyzeGaps(req: Requirement, diffSlice: string, opts?: { lens?: string }): Promise<GapFinding[] | null> {
    const { system, user } = buildGapPrompt(req, diffSlice, opts?.lens);
    const headers: Record<string, string> = {};
    if (this.opts.apiKey) headers.authorization = `Bearer ${this.opts.apiKey}`;
    try {
      const base = validateBaseUrl(this.opts.baseUrl);
      const res = await postJson(
        `${base}/chat/completions`,
        headers,
        { model: this.opts.model, temperature: 0, max_tokens: 800, messages: [{ role: 'system', content: system }, { role: 'user', content: user }] },
        this.opts.timeoutMs ?? 30_000
      );
      if (!res.ok) return null;
      const body = (await readJsonCapped(res)) as { choices?: { message?: { content?: string } }[] };
      const text = body.choices?.[0]?.message?.content ?? '';
      return extractGapFindings(text);
    } catch {
      return null;
    }
  }
}

/** Anthropic Messages API. */
export class AnthropicProvider implements LLMProvider {
  readonly name: string;
  constructor(
    private opts: { apiKey: string; baseUrl?: string; model: string; timeoutMs?: number }
  ) {
    this.name = `anthropic:${opts.model}`;
  }
  async rescore(req: Requirement, diffSlice: string, opts?: { lens?: string }): Promise<RescoreResult | null> {
    const { system, user } = buildRequirementPrompt(req, diffSlice, opts?.lens);
    try {
      const base = validateBaseUrl(this.opts.baseUrl ?? 'https://api.anthropic.com');
      const res = await postJson(
        `${base}/v1/messages`,
        { 'x-api-key': this.opts.apiKey, 'anthropic-version': '2023-06-01' },
        { model: this.opts.model, max_tokens: 400, system, messages: [{ role: 'user', content: user }] },
        this.opts.timeoutMs ?? 30_000
      );
      if (!res.ok) return null;
      const body = (await readJsonCapped(res)) as { content?: { type?: string; text?: string }[] };
      const text = (body.content ?? []).filter((b) => b.type === 'text').map((b) => b.text ?? '').join('\n');
      return extractJsonScore(text);
    } catch {
      return null;
    }
  }
  async analyzeGaps(req: Requirement, diffSlice: string, opts?: { lens?: string }): Promise<GapFinding[] | null> {
    const { system, user } = buildGapPrompt(req, diffSlice, opts?.lens);
    try {
      const base = validateBaseUrl(this.opts.baseUrl ?? 'https://api.anthropic.com');
      const res = await postJson(
        `${base}/v1/messages`,
        { 'x-api-key': this.opts.apiKey, 'anthropic-version': '2023-06-01' },
        { model: this.opts.model, max_tokens: 800, system, messages: [{ role: 'user', content: user }] },
        this.opts.timeoutMs ?? 30_000
      );
      if (!res.ok) return null;
      const body = (await readJsonCapped(res)) as { content?: { type?: string; text?: string }[] };
      const text = (body.content ?? []).filter((b) => b.type === 'text').map((b) => b.text ?? '').join('\n');
      return extractGapFindings(text);
    } catch {
      return null;
    }
  }
}

export class OfflineProvider implements LLMProvider {
  readonly name = 'off';
  async rescore(): Promise<null> {
    return null;
  }
  async analyzeGaps(): Promise<null> {
    return null;
  }
}

export interface LLMConfig {
  mode: LLMMode;
  provider: LLMProvider;
  weight: number;
  maxConcurrency?: number;
  maxRetries?: number;
}

function parseWeight(raw: string | undefined, fallback: number): number {
  if (raw === undefined || raw === '') return fallback;
  const n = parseFloat(raw);
  return Number.isFinite(n) ? Math.min(1, Math.max(0, n)) : fallback;
}

/**
 * Resolve LLM config from CLI flags (overrides) falling back to env:
 * STITCHER_CODEREVIEW_LLM=off|auto|require, STITCHER_CODEREVIEW_LLM_PROVIDER=openai|anthropic|custom,
 * OPENAI_API_KEY / ANTHROPIC_API_KEY, STITCHER_CODEREVIEW_LLM_BASE_URL, STITCHER_CODEREVIEW_LLM_MODEL,
 * STITCHER_CODEREVIEW_LLM_WEIGHT.
 */
export function providerFromEnv(
  env: NodeJS.ProcessEnv,
  flags: { llm?: string; provider?: string; model?: string; weight?: string; baseUrl?: string; maxConcurrency?: string; maxRetries?: string } = {}
): LLMConfig {
  const mode = (flags.llm ?? env.STITCHER_CODEREVIEW_LLM ?? 'off').toLowerCase() as LLMMode;
  const weight = parseWeight(flags.weight ?? env.STITCHER_CODEREVIEW_LLM_WEIGHT, 0.5);
  const mcRaw = parseInt(flags.maxConcurrency ?? env.STITCHER_CODEREVIEW_LLM_MAX_CONCURRENCY ?? '3', 10);
  const mrRaw = parseInt(flags.maxRetries ?? env.STITCHER_CODEREVIEW_LLM_MAX_RETRIES ?? '2', 10);
  const maxConcurrency = Number.isFinite(mcRaw) ? Math.min(32, Math.max(1, mcRaw)) : 3;
  const maxRetries = Number.isFinite(mrRaw) ? Math.min(10, Math.max(0, mrRaw)) : 2;
  if (mode !== 'auto' && mode !== 'require' && mode !== 'gap') {
    return { mode: 'off', provider: new OfflineProvider(), weight, maxConcurrency, maxRetries };
  }
  const which = (flags.provider ?? env.STITCHER_CODEREVIEW_LLM_PROVIDER ?? '').toLowerCase();
  const openaiKey = env.OPENAI_API_KEY;
  const anthropicKey = env.ANTHROPIC_API_KEY;
  const baseUrl =
    flags.baseUrl ?? env.STITCHER_CODEREVIEW_LLM_BASE_URL ?? 'https://api.openai.com/v1';
  const model =
    flags.model ?? env.STITCHER_CODEREVIEW_LLM_MODEL ?? (which === 'anthropic' || (!which && anthropicKey && !openaiKey) ? 'claude-haiku-4-5' : 'gpt-4o-mini');

  if (which === 'anthropic' || (!which && anthropicKey && !openaiKey)) {
    if (!anthropicKey) return { mode, provider: new OfflineProvider(), weight, maxConcurrency, maxRetries };
    return { mode, provider: new AnthropicProvider({ apiKey: anthropicKey, model }), weight, maxConcurrency, maxRetries };
  }
  // default: OpenAI-compatible (also covers custom base URLs like Ollama without a key)
  if (!openaiKey && baseUrl === 'https://api.openai.com/v1') {
    return { mode, provider: new OfflineProvider(), weight, maxConcurrency, maxRetries };
  }
  return { mode, provider: new OpenAICompatibleProvider({ apiKey: openaiKey, baseUrl, model }), weight, maxConcurrency, maxRetries };
}
