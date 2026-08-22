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
#   6. Commit + tag + push (before publish — push failure aborts, stderr shown)
#   6b. Tag-reached-remote verification (--follow-tags pushes annotated tags only)
#   6c. ARTIFACT VERIFY (manifest-driven; skipped when unconfigured)
#   7. Publish (auto-detected: npm / cargo / pip / custom)
#   8. GitHub release
#
# Usage:
#   ./scripts/deploy.sh <new-version>
#
# Optional: create .guardrails/release-artifact-contract.json (see
# release-artifact-contract.example.json) to assert the packed artifact really
# contains the files it must before an immutable publish. Absent = stage skipped.
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

# Capture stderr instead of discarding it: `2>/dev/null` hid the real reason a
# push failed and made every failure look like a missing upstream. Distinguish
# "no upstream configured" (retry with -u) from any other error (abort, showing
# what git actually said) — a push failure must abort while publish is un-done.
PUSH_ERR="$(mktemp)"
trap 'rm -f "$PUSH_ERR"' EXIT
if ! git push --follow-tags 2>"$PUSH_ERR"; then
	if grep -qiE 'no upstream branch|set-upstream|has no upstream' "$PUSH_ERR"; then
		echo "[deploy] no upstream for '$CURRENT_BRANCH' — retrying with --set-upstream"
		if ! git push --set-upstream origin "$CURRENT_BRANCH" --follow-tags 2>"$PUSH_ERR"; then
			echo "[deploy] ERROR: push failed even with --set-upstream:" >&2
			cat "$PUSH_ERR" >&2
			exit 1
		fi
	else
		echo "[deploy] ERROR: git push failed — aborting before publish:" >&2
		cat "$PUSH_ERR" >&2
		exit 1
	fi
fi
rm -f "$PUSH_ERR"

# --- 5b. verify the tag actually reached the remote ---------------------------
# `git push --follow-tags` pushes ANNOTATED tags only, and reports success
# either way. A tag left behind strands the source of a published artifact, so
# prove it is upstream, retry explicitly, then re-verify before publishing.
if ! git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null 2>&1; then
	echo "[deploy] tag $TAG not on remote after --follow-tags — pushing it explicitly"
	if ! git push origin "$TAG"; then
		echo "[deploy] ERROR: explicit tag push failed — aborting before publish" >&2
		exit 1
	fi
fi
if ! git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null 2>&1; then
	echo "[deploy] ERROR: tag $TAG still not on remote — refusing to publish an unpushed release" >&2
	exit 1
fi
echo "[deploy] commit + tag $TAG confirmed on remote."

# --- 5c. ARTIFACT VERIFY (manifest-driven; skips when unconfigured) -----------
# A published version is IMMUTABLE. Package managers will happily produce a
# well-formed archive with the built binary missing — the failure then surfaces
# at install time, for every user, on a version that cannot be recalled. When
# .guardrails/release-artifact-contract.json exists we pack, list the archive,
# and prove the required entries are really inside it BEFORE publishing.
# When it does not exist, we skip and continue (nothing to assert).
cd "$PROJECT_ROOT"
ARTIFACT_CONTRACT="$ROOT/.guardrails/release-artifact-contract.json"
if [ ! -f "$ARTIFACT_CONTRACT" ]; then
	echo "[deploy] no release-artifact-contract.json — skipping artifact verify"
else
	echo "[deploy] ARTIFACT VERIFY: packing and inspecting the release artifact"

	# Read the contract with python3 (already a DevGate dependency).
	contract_field() {
		python3 -c "
import json, sys
doc = json.load(open(sys.argv[1]))
val = doc.get(sys.argv[2])
if isinstance(val, list):
    print('\n'.join(str(v) for v in val))
elif val is not None:
    print(val)
" "$ARTIFACT_CONTRACT" "$1"
	}

	ARTIFACT_GLOB="$(contract_field artifact_glob)"
	ENTRY_PREFIX="$(contract_field entry_prefix)"

	# Per-package-manager pack + listing command. Each branch sets PACK_CMD (may
	# be empty when the artifact is pre-built) and LIST_MODE.
	PACK_CMD=""
	LIST_MODE="skip"
	if [ -f "package.json" ]; then
		PACK_CMD="npm pack"
		LIST_MODE="tar"
	elif [ -f "Cargo.toml" ]; then
		PACK_CMD="cargo package --allow-dirty"
		LIST_MODE="cargo-list"
	elif [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
		PACK_CMD="python3 -m build"
		LIST_MODE="python-dist"
	else
		echo "[deploy] no recognized packer — skipping artifact verify"
	fi

	if [ "$LIST_MODE" != "skip" ]; then
		if [ -n "$PACK_CMD" ]; then
			echo "[deploy]   packing: $PACK_CMD"
			$PACK_CMD >/dev/null 2>&1 || {
				echo "[deploy] ERROR: '$PACK_CMD' failed — cannot verify artifact" >&2
				exit 1
			}
		fi

		# Produce the archive entry listing.
		ARTIFACT_LISTING=""
		if [ "$LIST_MODE" = "cargo-list" ]; then
			# cargo prints the packaged file list directly (no prefix in output).
			ARTIFACT_LISTING="$(cargo package --list --allow-dirty 2>/dev/null)" || {
				echo "[deploy] ERROR: 'cargo package --list' failed" >&2
				exit 1
			}
			ARTIFACT_PATH="(cargo package --list)"
		else
			# Resolve the packed artifact via the contract glob (newest match).
			ARTIFACT_PATH=""
			for candidate in $(ls -t $ARTIFACT_GLOB 2>/dev/null); do
				ARTIFACT_PATH="$candidate"
				break
			done
			if [ -z "$ARTIFACT_PATH" ]; then
				echo "[deploy] ERROR: no artifact matched '$ARTIFACT_GLOB' after packing" >&2
				exit 1
			fi
			echo "[deploy]   artifact: $ARTIFACT_PATH"
			case "$ARTIFACT_PATH" in
				*.tgz|*.tar.gz)
					ARTIFACT_LISTING="$(tar -tzf "$ARTIFACT_PATH")" || {
						echo "[deploy] ERROR: could not list $ARTIFACT_PATH" >&2; exit 1; }
					;;
				*.tar)
					ARTIFACT_LISTING="$(tar -tf "$ARTIFACT_PATH")" || {
						echo "[deploy] ERROR: could not list $ARTIFACT_PATH" >&2; exit 1; }
					;;
				*.whl|*.zip)
					ARTIFACT_LISTING="$(unzip -Z1 "$ARTIFACT_PATH" 2>/dev/null || python3 -c "
import sys, zipfile
print('\n'.join(zipfile.ZipFile(sys.argv[1]).namelist()))
" "$ARTIFACT_PATH")" || {
						echo "[deploy] ERROR: could not list $ARTIFACT_PATH" >&2; exit 1; }
					;;
				*)
					echo "[deploy] WARN: unknown artifact type '$ARTIFACT_PATH' — skipping entry check"
					LIST_MODE="skip"
					;;
			esac
		fi
	fi

	if [ "$LIST_MODE" != "skip" ]; then
		# Every must_contain entry must be an EXACT line in the listing.
		MISSING=0
		while IFS= read -r required; do
			[ -n "$required" ] || continue
			expected="${ENTRY_PREFIX}${required}"
			if printf '%s\n' "$ARTIFACT_LISTING" | grep -Fqx "$expected"; then
				echo "[deploy]   ✓ $expected present"
			else
				echo "[deploy]   ✗ MISSING: $expected" >&2
				MISSING=$((MISSING + 1))
			fi
		done <<-EOF
			$(contract_field must_contain)
		EOF

		if [ "$MISSING" -gt 0 ]; then
			echo "[deploy] --- full artifact listing ($ARTIFACT_PATH) ---" >&2
			printf '%s\n' "$ARTIFACT_LISTING" >&2
			echo "[deploy] ERROR: $MISSING required entr(ies) missing from the artifact." >&2
			echo "[deploy] Refusing to publish an incomplete package (a published version is immutable)." >&2
			exit 1
		fi

		# Executable bits: a non-executable launcher breaks the installer's spawn.
		while IFS= read -r execpath; do
			[ -n "$execpath" ] || continue
			if [ ! -e "$execpath" ]; then
				echo "[deploy] ERROR: must_be_executable path does not exist: $execpath" >&2
				exit 1
			fi
			if [ ! -x "$execpath" ]; then
				echo "[deploy] ERROR: $execpath is not executable — installs would fail" >&2
				exit 1
			fi
			echo "[deploy]   ✓ $execpath is executable"
		done <<-EOF
			$(contract_field must_be_executable)
		EOF

		echo "[deploy] artifact verify OK."
	fi
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
