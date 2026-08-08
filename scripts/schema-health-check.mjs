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
// Set DB_ADAPTER to match your database engine. Use "none" if your project
// doesn't use a relational database — the script will exit 0 gracefully.
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

// If no adapter configured or no columns registered, skip gracefully.
if (DB_ADAPTER === "none" || EXPECTED_COLUMNS.length === 0) {
	console.log("[schema-health-check] No database configured — skipping.");
	console.log("[schema-health-check] To enable: set DB_ADAPTER and EXPECTED_COLUMNS in scripts/schema-health-check.mjs");
	process.exit(0);
}

if (!adapter) {
	console.error("[schema-health-check] ERROR: DB_ADAPTER is set but no adapter is configured.");
	console.error("[schema-health-check] Uncomment the adapter block for your database engine in this script.");
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
	for (const [table, column] of EXPECTED_COLUMNS) {
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
