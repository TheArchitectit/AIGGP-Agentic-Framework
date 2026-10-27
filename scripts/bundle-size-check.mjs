#!/usr/bin/env node
/**
 * scripts/bundle-size-check.mjs — post-build chunk budget gate.
 *
 * Measures built assets against a per-file budget and fails when any one of
 * them is over. This is the build-output counterpart of the source line
 * limits in regression_sizes.py: those keep files small, this keeps the
 * bundle small. It never builds anything itself - run your build first and
 * point the gate at the output.
 *
 * Configuration surface (README overlay contract - never edit this file):
 *   <project>/.guardrails/bundle-size.json
 *     {
 *       "dist_dir": "dist",                  // build output, relative to the project
 *       "max_kb": 900,                       // per-file budget, KiB (bytes/1024)
 *       "include": [<globs matched under dist_dir>]
 *     }
 *   Every key is optional; the defaults are dist_dir "dist", max_kb 900,
 *   and include = every *.js and *.css file at any depth under dist_dir
 *   (glob syntax: a double star crosses directories, a single star does
 *   not). "max_kb" is the same unit vite uses for chunkSizeWarningLimit -
 *   the warning, made fatal.
 *
 * Exit-code contract (deploy.sh dispatches on these - do not collapse them):
 *   0 = the gate RAN and every measured asset passed
 *   1 = the gate ran and FAILED (an asset over budget), or the configuration
 *       is unusable (bad types), or - under a present config - dist_dir is
 *       missing or holds zero measurable assets
 *   2 = the gate was SKIPPED (no overlay file)
 * A skip and a pass must not share an exit code. A build that produced
 * nothing to measure FAILS: "no assets found" is never a pass.
 *
 * Usage: node scripts/bundle-size-check.mjs
 */

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const TAG = "[bundle-size-check]";

// --- project / config resolution (same layout contract as the other gates) ---
function projectRoot() {
	const devgateRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
	if (process.env.DEVGATE_PROJECT_ROOT) return resolve(process.env.DEVGATE_PROJECT_ROOT);
	return basename(devgateRoot) === ".devgate" ? resolve(devgateRoot, "..") : devgateRoot;
}

function loadConfig(root) {
	const cfgPath = join(root, ".guardrails", "bundle-size.json");
	if (!existsSync(cfgPath)) return null;
	try {
		const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
		if (typeof cfg !== "object" || cfg === null || Array.isArray(cfg)) {
			console.error(`${TAG} ERROR: ${cfgPath} must contain a JSON object`);
			process.exit(1);
		}
		return cfg;
	} catch (err) {
		console.error(`${TAG} ERROR: config file ${cfgPath} is not valid JSON: ${err?.message ?? err}`);
		process.exit(1);
	}
}

// Present keys must be usable; absent keys take the documented defaults.
function effectiveConfig(cfg) {
	const distDir = cfg.dist_dir === undefined ? "dist" : cfg.dist_dir;
	const maxKb = cfg.max_kb === undefined ? 900 : cfg.max_kb;
	const include = cfg.include === undefined ? ["**/*.js", "**/*.css"] : cfg.include;
	if (typeof distDir !== "string" || distDir.trim() === "") {
		fail("config: dist_dir must be a non-empty string");
	}
	if (typeof maxKb !== "number" || !Number.isFinite(maxKb) || maxKb <= 0) {
		fail("config: max_kb must be a positive number (KiB, bytes/1024)");
	}
	if (!Array.isArray(include) || include.length === 0 ||
		include.some((p) => typeof p !== "string" || p.trim() === "")) {
		fail("config: include must be a non-empty array of glob strings");
	}
	return { distDir, maxKb, include };
}

function fail(message) {
	console.error(`${TAG} ERROR: ${message}`);
	process.exit(1);
}

// Minimal glob: "**" crosses directories, "*" does not, "?" one char.
function globToRegExp(glob) {
	let re = "^";
	for (let i = 0; i < glob.length; ) {
		if (glob.startsWith("**/", i)) { re += "(?:.*/)?"; i += 3; }
		else if (glob.startsWith("**", i)) { re += ".*"; i += 2; }
		else if (glob[i] === "*") { re += "[^/]*"; i += 1; }
		else if (glob[i] === "?") { re += "[^/]"; i += 1; }
		else { re += glob[i].replace(/[.+^${}()|[\]\\]/g, "\\$&"); i += 1; }
	}
	return new RegExp(`${re}$`);
}

function walk(dir, out) {
	for (const entry of readdirSync(dir, { withFileTypes: true })) {
		const full = join(dir, entry.name);
		if (entry.isDirectory()) walk(full, out);
		else if (entry.isFile()) out.push(full);
	}
	return out;
}

// --- measure -----------------------------------------------------------------
const root = projectRoot();
const cfg = loadConfig(root);

if (cfg === null) {
	// Loud skip: the project never opted in. Exit 2, never 0.
	console.log(`${TAG} SKIP: no .guardrails/bundle-size.json - nothing is configured to enforce.`);
	console.log(`${TAG} add {"dist_dir": "dist", "max_kb": 900} to opt this project in.`);
	process.exit(2);
}

const { distDir, maxKb, include } = effectiveConfig(cfg);
const distPath = resolve(root, distDir);

if (!existsSync(distPath)) {
	fail(`dist_dir "${distDir}" does not exist under ${root} - run the build first (a missing build is not a pass)`);
}

const matchers = include.map(globToRegExp);
const assets = walk(distPath, [])
	.map((file) => ({ file, rel: relative(distPath, file).split(sep).join("/") }))
	.filter((a) => matchers.some((re) => re.test(a.rel)))
	.map((a) => ({ ...a, bytes: statSync(a.file).size }))
	.sort((x, y) => y.bytes - x.bytes);

if (assets.length === 0) {
	fail(`no assets matched include ${JSON.stringify(include)} under ${distDir} - a build with nothing measurable is not a pass`);
}

const toKb = (bytes) => bytes / 1024;
const over = assets.filter((a) => toKb(a.bytes) > maxKb);

if (over.length > 0) {
	for (const a of over) {
		console.error(`${TAG} VIOLATION: ${distDir}/${a.rel}: ${toKb(a.bytes).toFixed(2)} kB (limit ${maxKb} kB)`);
	}
	console.error(`${TAG} ${over.length} of ${assets.length} asset(s) exceed the ${maxKb} kB per-file budget.`);
	process.exit(1);
}

const largest = assets[0];
console.log(`${TAG} OK: ${assets.length} asset(s) within the ${maxKb} kB per-file budget.`);
console.log(`${TAG} largest: ${distDir}/${largest.rel} (${toKb(largest.bytes).toFixed(2)} kB)`);
process.exit(0);
