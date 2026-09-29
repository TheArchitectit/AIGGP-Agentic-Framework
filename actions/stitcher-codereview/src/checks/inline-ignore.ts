/** Check if a line contains an inline review ignore directive. */
export function hasReviewIgnoreDirective(line: string): boolean {
  return /\b(review|stitcher-codereview)\s*:\s*ignore\b/i.test(line);
}