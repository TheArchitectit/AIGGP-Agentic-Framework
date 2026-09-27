import type { Diff, Finding, OpenSpecChange } from '../types.js';
import { keywords } from '../spec/parser.js';

export function checkTasks(change: OpenSpecChange, diff: Diff): Finding[] {
  const findings: Finding[] = [];
  if (change.tasks.length === 0) {
    findings.push({
      severity: 'low',
      category: 'tasks',
      checkId: 'no-tasks-file',
      message: 'No tasks.md checklist found — cannot verify task-to-code traceability.',
      suggestion: 'Add tasks.md via `/opsx:propose` so reviewers can tick off implementation steps.'
    });
    return findings;
  }
  const hay = diff.evidenceText.toLowerCase();
  for (const t of change.tasks) {
    const keys = [...keywords(`${t.text}`)];
    const hits = keys.filter((k) => hay.includes(k)).length;
    const ratio = keys.length === 0 ? 0 : hits / keys.length;
    if (t.done && ratio < 0.1) {
      findings.push({
        severity: 'medium',
        category: 'tasks',
        checkId: 'task-done-no-evidence',
        message: `Task ${t.id} [x] "${t.text.slice(0, 100)}" is marked done but has little diff evidence.`,
        suggestion: 'Uncheck it or point to the implementing file in the PR body.'
      });
    } else if (!t.done && ratio >= 0.3) {
      findings.push({
        severity: 'low',
        category: 'tasks',
        checkId: 'task-undone-with-evidence',
        message: `Task ${t.id} [ ] "${t.text.slice(0, 100)}" looks implemented but is unchecked.`,
        suggestion: 'Tick the box in tasks.md.'
      });
    }
  }
  const done = change.tasks.filter((t) => t.done).length;
  if (done < change.tasks.length) {
    findings.push({
      severity: 'info',
      category: 'tasks',
      checkId: 'task-progress',
      message: `Progress: ${done}/${change.tasks.length} tasks checked.`
    });
  }
  return findings;
}
