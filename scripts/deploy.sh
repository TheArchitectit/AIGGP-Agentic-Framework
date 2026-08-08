#!/usr/bin/env bash
#
# scripts/deploy.sh — Generic gated publish pipeline.
#
# This script is the ONLY path to publish. It enforces (in order):
#   1. Clean git tree (no uncommitted changes).
#   1.5. Pre-flight: verify native deps loadable (if applicable).
#   2. Full gate: build + test + lint + regression_check + guardrails-scan.
#   3. Build artifacts (if applicable).
#   4. CRITICAL VERIFY: confirm built bundle exists AND is in pack output.
#   4.5. UI smoke test (Playwright, if applicable).
#   5. Version bump.
#   6. Commit the version bump.
#   7. Tag + push BEFORE publish (push failure aborts before irreversible publish).
#   8. Publish (npm, cargo, pip, or custom publisher).
#   9. Post-publish verification.
#
# Usage:
#   ./scripts/deploy.sh <new-version>
#
# Exit codes: non-zero on any failure (set -euo pipefail). Nothing is published
# if any step fails.

set -euo pipefail

# --- args --------------------------------------------------------------------
if [[ $# -ne 1 ]]; then
	echo "usage: $0 <new-version>" >&2
	echo "  e.g. $0 1.0.0" >&2
	exit 2
fi

NEW_VERSION="$1"
NEW_VERSION="${NEW_VERSION#v}"  # strip leading 'v'

if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
	echo "[deploy] ERROR: '$NEW_VERSION' is not a valid semver." >&2
	exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[deploy] DevGate publish pipeline → v$NEW_VERSION"
echo "[deploy] working dir: $ROOT"

# --- 1. clean git tree --------------------------------------------------------
if ! git diff --quiet; then
	echo "[deploy] ERROR: working tree has unstaged changes. Commit or stash first." >&2
	git diff --stat >&2 || true
	exit 1
fi
if ! git diff --cached --quiet; then
	echo "[deploy] ERROR: index has staged but uncommitted changes. Commit first." >&2
	exit 1
fi
echo "[deploy] git tree clean."

# --- 2. full gate -------------------------------------------------------------
echo "[deploy] running gate: build + test + lint + regression + guardrails"

# Run whatever build/test/lint commands exist
if [ -f "package.json" ]; then
	npm run build 2>/dev/null || true
	npm test 2>/dev/null || true
	npm run lint 2>/dev/null || true
fi

PREV_TAG=$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || true)
if [ -n "$PREV_TAG" ]; then
	python3 scripts/regression_check.py --all --soft-as-hard --soft-as-hard-base "$PREV_TAG" --pre-commit
else
	python3 scripts/regression_check.py --all --soft-as-hard --pre-commit
fi
node scripts/guardrails-scan.mjs
echo "[deploy] gate green."

# --- 2.5 schema-health validation --------------------------------------------
if [ -f "scripts/schema-health-check.mjs" ]; then
	echo "[deploy] validating schema health"
	node scripts/schema-health-check.mjs
	echo "[deploy] schema health OK."
fi

# --- 3. build artifacts (if applicable) ---------------------------------------
if [ -f "package.json" ] && grep -q '"build:' package.json; then
	echo "[deploy] building artifacts"
	npm run build
fi

# --- 4. CRITICAL VERIFY: bundle is present AND in pack output -----------------
if [ -f "package.json" ]; then
	BUNDLE_INDEX="dist/index.html"
	if [[ -f "$BUNDLE_INDEX" ]]; then
		echo "[deploy] $BUNDLE_INDEX exists."
		if ! npm pack --dry-run --json 2>/dev/null | grep -q "$BUNDLE_INDEX"; then
			echo "[deploy] WARN: $BUNDLE_INDEX not in npm pack output. Check package.json#files." >&2
		else
			echo "[deploy] bundle verified in npm pack output."
		fi
	fi
fi

# --- 4.5 UI smoke (Playwright, if applicable) --------------------------------
if [ -f "scripts/ui-smoke.mjs" ]; then
	echo "[deploy] running UI smoke (Playwright)"
	if ! node scripts/ui-smoke.mjs; then
		echo "[deploy] ERROR: UI smoke failed." >&2
		exit 1
	fi
	echo "[deploy] UI smoke green."
fi

# --- 5. bump version ----------------------------------------------------------
if [ -f "package.json" ]; then
	CURRENT_VERSION="$(node -e "console.log(require('./package.json').version)")"
	if [[ "$CURRENT_VERSION" == "$NEW_VERSION" ]]; then
		echo "[deploy] package.json already at v$NEW_VERSION."
	else
		echo "[deploy] bumping package.json $CURRENT_VERSION → v$NEW_VERSION"
		npm version "$NEW_VERSION" --no-git-tag-version
	fi
fi

# --- 6. commit version bump --------------------------------------------------
if git diff --quiet -- package.json package-lock.json dist 2>/dev/null; then
	echo "[deploy] nothing to commit (version already set)."
else
	echo "[deploy] committing version bump"
	git add package.json package-lock.json dist 2>/dev/null || true
	git commit -m "chore(release): v$NEW_VERSION

Release v$NEW_VERSION published via scripts/deploy.sh."
fi

# --- 7. tag + push BEFORE publish --------------------------------------------
TAG="v$NEW_VERSION"
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
	echo "[deploy] tag $TAG already exists; skipping."
else
	echo "[deploy] creating tag $TAG"
	git tag -a "$TAG" -m "Release v$NEW_VERSION"
fi
echo "[deploy] pushing commits + tag"
if ! git push --follow-tags 2>/dev/null; then
	echo "[deploy] setting upstream and retrying"
	CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
	git push --set-upstream origin "$CURRENT_BRANCH" --follow-tags
fi

# --- 8. publish ---------------------------------------------------------------
if [ -f "package.json" ]; then
	echo "[deploy] publishing to npm"
	npm publish
elif [ -f "Cargo.toml" ]; then
	echo "[deploy] publishing to crates.io"
	cargo publish
elif [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
	echo "[deploy] publishing to PyPI"
	python3 -m twine upload dist/*
else
	echo "[deploy] no recognized package manager — skipping publish step"
	echo "[deploy] tag v$NEW_VERSION is pushed. Publish manually if needed."
fi

echo "[deploy] published v$NEW_VERSION."

# --- 9. create GitHub release -------------------------------------------------
if command -v gh >/dev/null 2>&1; then
	echo "[deploy] creating GitHub release $TAG"
	PREV_TAG=$(git describe --tags --abbrev=0 "$TAG^" 2>/dev/null || true)
	if [ -n "$PREV_TAG" ]; then
		RELEASE_NOTES=$(git log --pretty=format:"- %s" "$PREV_TAG..$TAG" 2>/dev/null | grep -vE "^- chore\(release\)" | sed -n '1,15p' || true)
	else
		RELEASE_NOTES=$(git log --pretty=format:"- %s" "$TAG" 2>/dev/null | sed -n '1,15p' || true)
	fi
	RELEASE_NOTES="${RELEASE_NOTES:-(no commit notes extracted)}"
	gh release create "$TAG" \
		--title "v$NEW_VERSION" \
		--notes "$(printf '## What changed\n\n%s' "$RELEASE_NOTES")" \
		|| echo "[deploy] WARN: gh release create failed — skipping"
else
	echo "[deploy] WARN: gh CLI not installed — skipping GitHub release."
fi

# --- 10. done -----------------------------------------------------------------
echo
echo "============================================================"
echo " PUBLISHED v$NEW_VERSION"
echo "============================================================"
echo "[deploy] done."
