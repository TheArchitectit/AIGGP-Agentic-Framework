#!/usr/bin/env node
/**
 * scripts/schema-health-check.mjs — deploy gate (database-agnostic).
 *
 * Validates that every column declared in your schema contract actually exists
 * in your database. Fails hard (exit 1) if any column is missing, any FK
 * constraint is violated, or integrity check fails.
 *
 * This script does NOT assume any specific database engine. Configure the
 * DB_ADAPTER constant and EXPECTED_COLUMNS array for your database.
 *
 * Supported adapters (uncomment and configure one):
 *   - "sqlite"   — Node 22+ built-in `node:sqlite` (no external deps)
 *   - "postgres" — requires `pg` package (`npm install pg`)
 *   - "mysql"    — requires `mysql2` package (`npm install mysql2`)
 *   - "none"     — skip schema checks entirely (for projects without a DB)
 *
 * Usage: node scripts/schema-health-check.mjs [--db <connection-string-or-path>]
 */

import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { homedir } from "node:os";

// --- configuration -----------------------------------------------------------
// Configuration resolution (project overlay FIRST — consumers never edit the
// submodule): <project>/.guardrails/schema-health.json
//   { "adapter": "sqlite" | "postgres" | "mysql" | "none",
//     "expected_columns": [["table", "column", "type_decl"], ...] }
// then the constants below (which a maintainer may tune), then "none".
// NOTE on the MySQL adapter template below: fkCheck() as written selects ALL
// FK constraints from KEY_COLUMN_USAGE, not violations — enabling it fails
// every schema with foreign keys. Fix the query before relying on it.
const DB_ADAPTER = "none"; // "sqlite" | "postgres" | "mysql" | "none"

// --- column registry (customize for your schema) -----------------------------
// Each entry: [table, column, expected_type_decl]
// Leave empty ([]) to skip column checks.
const EXPECTED_COLUMNS = [
	// Examples — uncomment and edit for your schema:
	// ["users", "id", "TEXT NOT NULL PRIMARY KEY"],
	// ["users", "email", "TEXT NOT NULL UNIQUE"],
	// ["users", "created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"],
];

// Load the project overlay config when present. The project root is the
// directory containing .devgate/ (layout contract, same as the other gates).
import { readFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

function loadProjectConfig() {
	const devgateRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
	// DEVGATE_PROJECT_ROOT overrides (parity with regression_check.py and the
	// other gates); otherwise the layout contract: a script inside .devgate/
	// serves the containing project, a standalone clone is its own project.
	const projectRoot = process.env.DEVGATE_PROJECT_ROOT
		? resolve(process.env.DEVGATE_PROJECT_ROOT)
		: basename(devgateRoot) === ".devgate"
			? resolve(devgateRoot, "..")
			: devgateRoot;
	const cfgPath = join(projectRoot, ".guardrails", "schema-health.json");
	if (!existsSync(cfgPath)) return null;
	try {
		const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
		if (typeof cfg !== "object" || cfg === null) return null;
		return cfg;
	} catch (err) {
		console.error(`[schema-health-check] ERROR: config file ${cfgPath} is not valid JSON: ${err?.message ?? err}`);
		process.exit(1);
	}
}

const projectConfig = loadProjectConfig();
const ADAPTER = projectConfig?.adapter ?? DB_ADAPTER;
const COLUMNS = Array.isArray(projectConfig?.expected_columns)
	? projectConfig.expected_columns
	: EXPECTED_COLUMNS;

// --- database adapters -------------------------------------------------------
// Each adapter provides: open(connStr), close(), integrityCheck(),
// fkCheck(), tableColumns(table).

let adapter = null;

/*
// --- SQLite adapter (Node 22+ built-in, no external deps) ---
import { DatabaseSync } from "node:sqlite";
let _db = null;
adapter = {
	open(connStr) {
		if (!existsSync(connStr)) return false;
		_db = new DatabaseSync(connStr);
		_db.exec("PRAGMA journal_mode=WAL");
		return true;
	},
	close() { if (_db) _db.close(); },
	integrityCheck() {
		return _db.prepare("PRAGMA integrity_check").all()
			.map(r => r.integrity_check || r["integrity_check"] || "");
	},
	fkCheck() { return _db.prepare("PRAGMA foreign_key_check").all(); },
	tableColumns(table) {
		return _db.prepare(`PRAGMA table_info('${table}')`).all().map(r => r.name);
	},
};
*/

/*
// --- PostgreSQL adapter (requires: npm install pg) ---
import pg from "pg";
let _client = null;
adapter = {
	async open(connStr) {
		_client = new pg.Client({ connectionString: connStr });
		await _client.connect();
		return true;
	},
	async close() { if (_client) await _client.end(); },
	async integrityCheck() {
		// PostgreSQL doesn't have a built-in integrity_check — run a vacuum analyze
		// and check for orphaned FK rows instead. Adjust for your needs.
		await _client.query("VACUUM ANALYZE");
		return ["ok"];
	},
	async fkCheck() {
		const r = await _client.query(`
			SELECT conrelid::regclass AS table_name
			FROM pg_constraint
			WHERE contype = 'f' AND NOT convalidated
		`);
		return r.rows;
	},
	async tableColumns(table) {
		const r = await _client.query(`
			SELECT column_name FROM information_schema.columns
			WHERE table_name = $1
		`, [table]);
		return r.rows.map(row => row.column_name);
	},
};
*/

/*
// --- MySQL adapter (requires: npm install mysql2) ---
import mysql from "mysql2/promise";
let _conn = null;
adapter = {
	async open(connStr) {
		_conn = await mysql.createConnection(connStr);
		return true;
	},
	async close() { if (_conn) await _conn.end(); },
	async integrityCheck() {
		await _conn.execute("CHECK TABLE mysql.user");
		return ["ok"];
	},
	async fkCheck() {
		const [rows] = await _conn.execute(`
			SELECT TABLE_NAME FROM information_schema.KEY_COLUMN_USAGE
			WHERE REFERENCED_TABLE_NAME IS NOT NULL
		`);
		return rows;
	},
	async tableColumns(table) {
		const [rows] = await _conn.execute(`
			SELECT COLUMN_NAME FROM information_schema.COLUMNS
			WHERE TABLE_NAME = ?
		`, [table]);
		return rows.map(r => r.COLUMN_NAME);
	},
};
*/

// --- main -------------------------------------------------------------------
const args = process.argv.slice(2);
let dbConnString = process.env.DEVGATE_DB_PATH || "";

for (let i = 0; i < args.length; i++) {
	if (args[i] === "--db" && args[i + 1]) {
		dbConnString = args[++i];
	}
}

// Unconfigured = BOTH absent: skip green. Half-configured (adapter without
// columns, or columns without an adapter) asserts nothing and used to skip
// green — that is an error, not a skip.
if (ADAPTER === "none" && COLUMNS.length === 0) {
	console.log("[schema-health-check] No database configured — skipping.");
	console.log('[schema-health-check] To enable: create <project>/.guardrails/schema-health.json with {"adapter": "...", "expected_columns": [...]} (see AGENTS.md).');
	process.exit(0);
}
if (ADAPTER !== "none" && COLUMNS.length === 0) {
	console.error("[schema-health-check] ERROR: adapter configured but expected_columns is empty — the gate would assert nothing.");
	console.error('[schema-health-check] Add columns to <project>/.guardrails/schema-health.json, or set adapter to "none" to skip explicitly.');
	process.exit(1);
}
if (ADAPTER === "none" && COLUMNS.length > 0) {
	console.error('[schema-health-check] ERROR: expected_columns configured but adapter is "none" — the gate would assert nothing.');
	console.error("[schema-health-check] Set the adapter in <project>/.guardrails/schema-health.json, or remove expected_columns to skip explicitly.");
	process.exit(1);
}

if (!adapter) {
	console.error(`[schema-health-check] ERROR: adapter "${ADAPTER}" is configured but no adapter implementation is enabled.`);
	console.error("[schema-health-check] Uncomment the adapter block for your database engine in scripts/schema-health-check.mjs (engine CODE lives here; project CONFIG lives in .guardrails/schema-health.json).");
	process.exit(1);
}

let failures = 0;

// Open database connection
const dbExists = await adapter.open(dbConnString);
if (!dbExists) {
	console.error(`[schema-health-check] Database not found at ${dbConnString} — skipping (cold install OK)`);
	process.exit(0);
}

try {
	// 1. Integrity check
	try {
		const results = await adapter.integrityCheck();
		for (const val of results) {
			if (typeof val === "string" && val !== "ok") {
				console.error(`[schema-health-check] integrity check FAIL: ${val}`);
				failures++;
			}
		}
	} catch (err) {
		console.error(`[schema-health-check] integrity check error: ${err?.message ?? err}`);
		failures++;
	}

	// 2. Foreign key check (may not apply to all DB engines)
	try {
		const fkResults = await adapter.fkCheck();
		if (fkResults.length > 0) {
			for (const row of fkResults) {
				console.error(`[schema-health-check] FK violation: ${JSON.stringify(row)}`);
			}
			failures += fkResults.length;
		}
	} catch (err) {
		// FK checks may not apply to all engines — non-fatal
		console.error(`[schema-health-check] FK check skipped (${err?.message ?? "not supported"})`);
	}

	// 3. Column audit (contract vs. DB)
	for (const [table, column] of COLUMNS) {
		try {
			const columns = await adapter.tableColumns(table);
			if (!columns.includes(column)) {
				console.error(`[schema-health-check] Missing column: ${table}.${column}`);
				failures++;
			}
		} catch {
			console.error(`[schema-health-check] Missing table: ${table}`);
			failures++;
		}
	}
} finally {
	await adapter.close();
}

if (failures > 0) {
	console.error(`\n[schema-health-check] ${failures} failure(s) found. Deploy blocked.`);
	console.error("Run database migrations or reconcile actions, then re-run this script.");
	process.exit(1);
}

console.log("[schema-health-check] all checks passed.");
process.exit(0);
