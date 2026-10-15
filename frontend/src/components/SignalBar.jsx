/**
 * The one chart the report is built around.
 *
 * A single centre axis with frequency growing left and star cost growing right.
 * Reading across a list of themes, a long left arm with a short right arm means
 * "everyone mentions it, nobody downgrades over it" — and the reverse means
 * "rare but expensive". Two separate bar charts never make that trade visible.
 */
export default function SignalBar({ share, starCost, maxShare, maxCost }) {
  const width = 320;
  const height = 26;
  const axis = width / 2;
  const barHeight = 9;
  const y = (height - barHeight) / 2;

  const shareWidth = maxShare > 0 ? (share / maxShare) * (axis - 8) : 0;
  const cost = starCost === null || starCost === undefined ? 0 : Math.max(starCost, 0);
  const costWidth = maxCost > 0 ? (cost / maxCost) * (axis - 8) : 0;

  const costColour =
    cost >= 1 ? "var(--color-signal-high)" : cost >= 0.4 ? "var(--color-signal-mid)" : "var(--color-signal-low)";

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img"
         aria-label={`Mentioned in ${(share * 100).toFixed(1)} percent of reviews, costs ${cost.toFixed(2)} stars`}>
      <rect x={axis - shareWidth} y={y} width={shareWidth} height={barHeight} fill="var(--color-field)" />
      <rect x={axis} y={y} width={costWidth} height={barHeight} fill={costColour} />
      <line x1={axis} y1={2} x2={axis} y2={height - 2} stroke="var(--color-ink)" strokeWidth="1" />
    </svg>
  );
}
