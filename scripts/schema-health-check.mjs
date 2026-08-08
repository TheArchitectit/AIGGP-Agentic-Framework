#!/usr/bin/env node
/**
 * scripts/schema-health-check.mjs — deploy gate.
 *
 * Validates that every column declared in the schema contract actually exists
 * in the live SQLite schema. Fails hard (exit 1) if any column is missing,
 * any FK constraint is violated, or integrity_check fails.
 *
 * Usage: node scripts/schema-health-check.mjs [--db <path>]
 *
 * Default DB: ~/.devgate/sqlite.db
 * Configure EXPECTED_COLUMNS for your own schema.
 */

import { DatabaseSync } from "node:sqlite";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { homedir } from "node:os";

// --- column registry (customize for your schema) -----------------------------
// Each module that owns tables declares them here as:
//   [table, column, expected SQL type decl]
const EXPECTED_COLUMNS = [
	// Add your schema columns here, e.g.:
	// ["users", "id", "TEXT NOT NULL PRIMARY KEY"],
	// ["users", "email", "TEXT NOT NULL UNIQUE"],
	// ["users", "created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"],
];

// --- main -------------------------------------------------------------------
const args = process.argv.slice(2);
let dbPath = resolve(homedir(), ".devgate", "sqlite.db");

for (let i = 0; i < args.length; i++) {
	if (args[i] === "--db" && args[i + 1]) {
		dbPath = args[++i];
	}
}

if (!existsSync(dbPath)) {
	console.error(`[schema-health-check] DB not found at ${dbPath} — skipping (cold install OK)`);
	process.exit(0);
}

if (EXPECTED_COLUMNS.length === 0) {
	console.log("[schema-health-check] No columns registered — skipping (configure EXPECTED_COLUMNS for your schema)");
	process.exit(0);
}

let failures = 0;
const db = new DatabaseSync(dbPath);
db.exec("PRAGMA journal_mode=WAL");

// 1. integrity_check
try {
	const rows = db.prepare("PRAGMA integrity_check").all();
	for (const row of rows) {
		const val = row.integrity_check ?? row["integrity_check"] ?? "";
		if (val !== "ok") {
			console.error(`[schema-health-check] integrity_check FAIL: ${val}`);
			failures++;
		}
	}
} catch (err) {
	console.error(`[schema-health-check] integrity_check error: ${err?.message ?? err}`);
	failures++;
}

// 2. FK check
try {
	const rows = db.prepare("PRAGMA foreign_key_check").all();
	if (rows.length > 0) {
		for (const row of rows) {
			console.error(`[schema-health-check] FK violation: table=${row.table} rowid=${row.rowid} parent=${row.parent} fkid=${row.fkid}`);
		}
		failures += rows.length;
	}
} catch (err) {
	console.error(`[schema-health-check] FK check error: ${err?.message ?? err}`);
	failures++;
}

// 3. Column audit
for (const [table, column] of EXPECTED_COLUMNS) {
	try {
		const rows = db.prepare(`PRAGMA table_info('${table}')`).all();
		const found = rows.some((r) => r.name === column);
		if (!found) {
			console.error(`[schema-health-check] Missing column: ${table}.${column}`);
			failures++;
		}
	} catch {
		console.error(`[schema-health-check] Missing table: ${table}`);
		failures++;
	}
}

db.close();

if (failures > 0) {
	console.error(`\n[schema-health-check] ${failures} failure(s) found. Deploy blocked.`);
	process.exit(1);
}

console.log("[schema-health-check] all checks passed.");
process.exit(0);
