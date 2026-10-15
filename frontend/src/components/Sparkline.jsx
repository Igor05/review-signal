export default function Sparkline({ points, width = 76, height = 22 }) {
  if (!points || points.length < 2) {
    return <div style={{ width, height }} className="text-graphite font-mono text-[10px] leading-[22px]">—</div>;
  }

  const values = points.map((p) => p.count);
  const max = Math.max(...values, 1);
  const step = points.length > 1 ? (width - 2) / (points.length - 1) : 0;

  const path = points
    .map((p, i) => {
      const x = 1 + i * step;
      const y = height - 2 - (p.count / max) * (height - 4);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const last = points[points.length - 1];
  const lastX = 1 + (points.length - 1) * step;
  const lastY = height - 2 - (last.count / max) * (height - 4);

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={path} fill="none" stroke="var(--color-graphite)" strokeWidth="1.25" />
      <circle cx={lastX} cy={lastY} r="2" fill="var(--color-ink)" />
    </svg>
  );
}
