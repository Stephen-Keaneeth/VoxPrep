/**
 * Shared score normalization helper.
 * Normalizes scores on the 1.0 - 10.0 backend scale into 0 - 100% integer percentages.
 * If the score is already on the 0 - 100 scale, preserves it.
 *
 * Formula: score <= 10 ? Math.round(score * 10) : Math.round(score)
 */
export function normalizeScore(score?: number | null, fallback = 0): number {
  if (score === undefined || score === null || isNaN(score)) {
    return fallback;
  }
  return score <= 10 ? Math.round(score * 10) : Math.round(score);
}

export default normalizeScore;
