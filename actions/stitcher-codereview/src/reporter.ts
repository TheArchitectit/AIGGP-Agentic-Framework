import type { Finding, ReviewResult, Severity, Verdict } from './types.js';

const RANK: Record<Severity, number> = { blocker: 0, high: 1, medium: 2, low: 3, info: 4 };

export function sortFindings(fs: Finding[]): Finding[] {
  return [...fs].sort((a, b) => RANK[a.severity] - RANK[b.severity]);
}

export function decideVerdict(findings: Finding[]): Verdict {
  return findings.some((f) => f.severity === 'blocker' || f.severity === 'high') ? 'CHANGES_REQUESTED' : 'PASS';
}

export function toMarkdown(r: ReviewResult): string {
  const icon = r.verdict === 'PASS' ? '✅' : '🔁';
  const lines: string[] = [];
  lines.push(`## ${icon} stitcher-codereview: ${r.verdict} — \`${r.change}\``);
  lines.push('');
  lines.push(r.summary);
  lines.push('');
  lines.push(`**Stats:** ${r.stats.filesChanged} files, +${r.stats.linesAdded} lines, ${r.stats.requirementsCovered}/${r.stats.requirementsTotal} requirements covered.`);
  lines.push(`**Template:** ${r.template.label} (\`${r.template.id}\`) — ${r.template.reason}`);
  lines.push('');
  if (r.requirementCoverage.length > 0) {
    lines.push('### Spec coverage');
    lines.push('| Requirement | Op | Status | Evidence |');
    lines.push('|---|---|---|---|');
    for (const c of r.requirementCoverage) {
      const dot = c.status === 'covered' ? '🟢' : c.status === 'partial' ? '🟡' : c.status === 'missing' ? '🔴' : '🟣';
      lines.push(`| ${c.requirementId} (${c.capability}) | ${c.operation} | ${dot} ${c.status} | ${(c.evidence[0] ?? '—').replace(/\|/g, '\\|')} |`);
    }
    lines.push('');
    // Evidence trace table: requirement ↔ code locations
    const hasLocations = r.requirementCoverage.some((c) => c.locations && c.locations.length > 0);
    if (hasLocations) {
      lines.push('### Evidence trace');
      lines.push('| Requirement | Capability | Files (lines) |');
      lines.push('|---|---|---|');
      for (const c of r.requirementCoverage) {
        if (!c.locations || c.locations.length === 0) continue;
        const shown = c.locations.slice(0, 5);
        const more = c.locations.length > 5 ? ` …+${c.locations.length - 5} more` : '';
        const locStr = shown.map((l) => `\`${l.file}:${l.startLine}-${l.endLine}\``).join(', ') + more;
        lines.push(`| ${c.requirementId} | ${c.capability} | ${locStr} |`);
      }
      lines.push('');
    }
  }
  const groups: Severity[] = ['blocker', 'high', 'medium', 'low', 'info'];
  for (const sev of groups) {
    const fs = r.findings.filter((f) => f.severity === sev);
    if (fs.length === 0) continue;
    lines.push(`### ${sev.toUpperCase()} (${fs.length})`);
    for (const f of fs) {
      const loc = f.file ? ` \`${f.file}${f.line ? ':' + f.line : ''}\`` : '';
      const req = f.requirementId ? ` [req: ${f.requirementId}]` : '';
      lines.push(`- **[${f.category}]**${req} ${f.message}${loc}`);
      if (f.suggestion) lines.push(`  - 💡 ${f.suggestion}`);
    }
    lines.push('');
  }
  if (r.findings.length === 0) lines.push('_No findings._');
  return lines.join('\n');
}

export function toJson(r: ReviewResult): string {
  return JSON.stringify(r, null, 2);
}
