// // spec: root-anchor-01, root-anchor-03
// DevGate scanner project-root contract — the single home for "which tree does
// a scanner operate on."
//
// The contract (external audit 2026-09-20):
//   A scanner resolves the project root by LAYOUT, never by walking up from an
//   ancestor looking for a marker file. The directory that CONTAINS `.devgate/`
//   is the project (submodule layout); when DevGate runs as its own repository
//   (standalone), DevGate itself IS the project.
//
// Why this replaced a marker walk-up: `findProjectRoot(resolve(devgateRoot,
// ".."))` started ABOVE the repo and returned the first ancestor holding a
// marker (package.json/.git/…). On a machine where the parent of the checkout
// is a shared directory (e.g. /mnt/data/git, which carries a package.json of its
// own), the walk-up settled on that shared directory and the scanner evaluated
// sibling repositories — semantic-scan reported thousands of foreign files, and
// run-tests discovered ZERO of DevGate's own tests yet still exited 0. A root
// chosen by "the nearest marker above me" is a root that can silently be the
// wrong tree; a root named by layout cannot be. This is the same contract
// guardrails-scan.mjs already uses, centralized so every scanner shares one
// definition and a future scanner cannot reintroduce the escape.
//
// devgateRoot is the caller's own directory (where its script lives), resolved
// the same way every scanner already resolves it:
//   join(dirname(fileURLToPath(import.meta.url)), "..")

import { basename, dirname } from "node:path";

export function projectRootFor(devgateRoot) {
	// basename/dirname strip trailing separators, and dirname("/") stays "/" —
	// the fresh-eyes audit (2026-09-20) of the first hand-rolled slice version
	// flagged "/" + "/.devgate" as its one boundary bug; node:path handles it.
	return basename(devgateRoot) === ".devgate" ? dirname(devgateRoot) : devgateRoot;
}
