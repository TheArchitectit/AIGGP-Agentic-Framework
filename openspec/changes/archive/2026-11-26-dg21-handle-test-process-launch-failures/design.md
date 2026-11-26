# Per-file process launch error handling

The Node child-process `error` event can occur before the child launches. This
is a per-file execution failure. Capture its error name or code and settle the
file exactly once through cleanup, including temporary workspace and timers.
Keep the launch diagnostic in the normal per-file result so it remains visible
when workers run concurrently. Do not rethrow from the event callback.

The existing bounded solo pass is the adjudicator. A failed launch may clear
only if the solo run executes tests and exits cleanly. Record a persistent
failed launch in the final file list and return a nonzero overall exit.
Use a disposable fixture with a controlled process launch failure and an
independent healthy file. The fixture must exercise the actual runner process
and verify its output and exit. The fixture injects a launch failure under controlled local conditions.

The workflow runs the test process once. The first step streams the combined
output into a job-local file under `RUNNER_TEMP`. Its Bash pipeline preserves
any runner failure as a step failure. The non-vacuity step asserts a positive
file count in that specific run's completion line. Treat a missing or
unparseable report as a validation failure. Exercise both step bodies with a
stub command that records invocations and returns explicit counts and exits.
