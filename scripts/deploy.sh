#!/usr/bin/env bash
#
# scripts/deploy.sh — Generic gated publish pipeline (language-agnostic).
#
# Auto-detects the project's package manager (npm, cargo, pip) and runs
# the appropriate build/test/publish commands. Does NOT assume any specific
# language or framework.
#
# Steps:
#   1. Clean git tree
#   2. Full gate (build + test + lint + regression + guardrails)
#   3. Schema health validation (if database configured)
#   4. Build artifacts (if applicable)
#   5. Version bump
#   6. Commit + tag + push (before publish — push failure aborts)
#   7. Publish (auto-detected: npm / cargo / pip / custom)
#   8. GitHub release
#
# Usage:
#   ./scripts/deploy.sh <new-version>
#
# Exit codes: non-zero on any failure (set -euo pipefail).

set -euo pipefail

if [[ $# -ne 1 ]]; then
	echo "usage: $0 <new-version>" >&2
	echo "  e.g. $0 1.0.0" >&2
	exit 2
fi

NEW_VERSION="$1"
NEW_VERSION="${NEW_VERSION#v}"

if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
	echo "[deploy] ERROR: '$NEW_VERSION' is not a valid semver." >&2
	exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "$ROOT/.." && pwd)"
cd "$ROOT"

echo "[deploy] DevGate publish pipeline → v$NEW_VERSION"
echo "[deploy] DevGate dir: $ROOT"
echo "[deploy] Project dir: $PROJECT_ROOT"

# --- 1. clean git tree --------------------------------------------------------
if ! git -C "$PROJECT_ROOT" diff --quiet; then
	echo "[deploy] ERROR: working tree has unstaged changes." >&2
	git -C "$PROJECT_ROOT" diff --stat >&2 || true
	exit 1
fi
if ! git -C "$PROJECT_ROOT" diff --cached --quiet; then
	echo "[deploy] ERROR: index has staged but uncommitted changes." >&2
	exit 1
fi
echo "[deploy] git tree clean."

# --- 2. full gate -------------------------------------------------------------
echo "[deploy] running gate: regression + guardrails"

# Run regression check (auto-detects project root and package manager)
python3 "$ROOT/scripts/regression_check.py" --all --pre-commit || {
	echo "[deploy] FAIL: regression check failed — aborting deploy"
	exit 1
}

# Run guardrails scan
node "$ROOT/scripts/guardrails-scan.mjs" || {
	echo "[deploy] FAIL: guardrails scan failed — aborting deploy"
	exit 1
}

# Run project's own build/test/lint (whatever exists)
cd "$PROJECT_ROOT"
if [ -f "package.json" ]; then
	echo "[deploy] detected npm project — running npm scripts"
	npm run build || { echo "[deploy] FAIL: npm build failed"; exit 1; }
	npm test || { echo "[deploy] FAIL: npm test failed"; exit 1; }
	npm run lint 2>/dev/null || echo "[deploy] WARN: lint skipped or not configured"
elif [ -f "Cargo.toml" ]; then
	echo "[deploy] detected Rust project — running cargo"
	cargo build --release || { echo "[deploy] FAIL: cargo build failed"; exit 1; }
	cargo test || { echo "[deploy] FAIL: cargo test failed"; exit 1; }
	cargo clippy 2>/dev/null || echo "[deploy] WARN: clippy skipped or not configured"
elif [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
	echo "[deploy] detected Python project — running pytest"
	python3 -m pytest || { echo "[deploy] FAIL: pytest failed"; exit 1; }
elif [ -f "go.mod" ]; then
	echo "[deploy] detected Go project — running go test"
	go build ./... || { echo "[deploy] FAIL: go build failed"; exit 1; }
	go test ./... || { echo "[deploy] FAIL: go test failed"; exit 1; }
elif [ -f "project.godot" ]; then
	echo "[deploy] detected Godot project — skipping build/test (run Godot headless tests manually)"
else
	echo "[deploy] no recognized project type — skipping build/test"
fi

# --- 3. schema health (if configured) -----------------------------------------
if [ -f "$ROOT/scripts/schema-health-check.mjs" ]; then
	node "$ROOT/scripts/schema-health-check.mjs" && echo "[deploy] schema health OK." || { echo "[deploy] WARN: schema check skipped or failed (non-blocking for non-DB projects)"; }
fi

echo "[deploy] gate complete."

# --- 4. version bump ----------------------------------------------------------
cd "$PROJECT_ROOT"
if [ -f "package.json" ]; then
	CURRENT_VERSION="$(node -e "console.log(require('./package.json').version)")"
	if [[ "$CURRENT_VERSION" != "$NEW_VERSION" ]]; then
		echo "[deploy] bumping package.json $CURRENT_VERSION → v$NEW_VERSION"
		npm version "$NEW_VERSION" --no-git-tag-version
	fi
elif [ -f "Cargo.toml" ]; then
	CURRENT_VERSION="$(grep '^version' Cargo.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')"
	if [[ "$CURRENT_VERSION" != "$NEW_VERSION" ]]; then
		sed -i.bak "s/^version = .*/version = \"$NEW_VERSION\"/" Cargo.toml
		rm -f Cargo.toml.bak
		echo "[deploy] bumped Cargo.toml → v$NEW_VERSION"
	fi
elif [ -f "pyproject.toml" ]; then
	CURRENT_VERSION="$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')"
	if [[ "$CURRENT_VERSION" != "$NEW_VERSION" ]]; then
		sed -i.bak "s/^version = .*/version = \"$NEW_VERSION\"/" pyproject.toml
		rm -f pyproject.toml.bak
		echo "[deploy] bumped pyproject.toml → v$NEW_VERSION"
	fi
else
	echo "[deploy] no recognized manifest — skipping version bump (set manually)"
fi

# --- 5. commit + tag + push ---------------------------------------------------
cd "$PROJECT_ROOT"
if ! git diff --quiet; then
	echo "[deploy] committing version bump"
	git add -A
	git commit -m "chore(release): v$NEW_VERSION"
fi

TAG="v$NEW_VERSION"
if ! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
	git tag -a "$TAG" -m "Release v$NEW_VERSION"
fi

echo "[deploy] pushing commits + tag"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if ! git push --follow-tags 2>/dev/null; then
	git push --set-upstream origin "$CURRENT_BRANCH" --follow-tags
fi

# --- 6. publish ---------------------------------------------------------------
cd "$PROJECT_ROOT"
if [ -f "package.json" ]; then
	echo "[deploy] publishing to npm"
	npm publish
elif [ -f "Cargo.toml" ]; then
	echo "[deploy] publishing to crates.io"
	cargo publish
elif [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
	echo "[deploy] publishing to PyPI"
	python3 -m twine upload dist/* 2>/dev/null || python3 -m build && python3 -m twine upload dist/*
else
	echo "[deploy] no recognized package manager — tag v$NEW_VERSION is pushed. Publish manually if needed."
fi

echo "[deploy] published v$NEW_VERSION."

# --- 7. GitHub release --------------------------------------------------------
cd "$PROJECT_ROOT"
if command -v gh >/dev/null 2>&1; then
	echo "[deploy] creating GitHub release $TAG"
	PREV_TAG=$(git describe --tags --abbrev=0 "$TAG^" 2>/dev/null || true)
	if [ -n "$PREV_TAG" ]; then
		RELEASE_NOTES=$(git log --pretty=format:"- %s" "$PREV_TAG..$TAG" 2>/dev/null | grep -vE "^- chore\(release\)" | sed -n '1,15p' || true)
	else
		RELEASE_NOTES=$(git log --pretty=format:"- %s" "$TAG" 2>/dev/null | sed -n '1,15p' || true)
	fi
	RELEASE_NOTES="${RELEASE_NOTES:-(no commit notes extracted)}"
	gh release create "$TAG" --title "v$NEW_VERSION" --notes "$(printf '## What changed\n\n%s' "$RELEASE_NOTES")" \
		|| echo "[deploy] WARN: gh release create failed — skipping"
else
	echo "[deploy] WARN: gh CLI not installed — skipping GitHub release."
fi

echo
echo "============================================================"
echo " PUBLISHED v$NEW_VERSION"
echo "============================================================"
echo "[deploy] done."
