/** Generated or vendored content that heuristic checkers should never scan. */
export function isGenerated(path: string): boolean {
  return (
    /(^|\/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb)$/.test(path) ||
    /(^|\/)(dist|build|coverage|generated)\//.test(path) ||
    // Vendored dependency trees (JS + Python) — never review third-party code.
    /(^|\/)(node_modules|\.venv|venv|env|\.tox|site-packages)\//.test(path) ||
    /\.min\.js$/.test(path) ||
    /\.snap$/.test(path)
  );
}
