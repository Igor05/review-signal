import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import SignalBar from "../components/SignalBar";
import Sparkline from "../components/Sparkline";
import ThemePanel from "../components/ThemePanel";

export default function Report({ projectId, runId, onBack }) {
  const [report, setReport] = useState(null);
  const [summary, setSummary] = useState(null);
  const [summaryState, setSummaryState] = useState("idle");
  const [error, setError] = useState(null);
  const [openTheme, setOpenTheme] = useState(null);

  useEffect(() => {
    api.getReport(projectId, runId).then(setReport).catch((err) => setError(err.message));
  }, [projectId, runId]);

  const negatives = useMemo(
    () => report?.themes.filter((theme) => theme.polarity === "negative") || [],
    [report],
  );
  const positives = useMemo(
    () => report?.themes.filter((theme) => theme.polarity === "positive") || [],
    [report],
  );

  const maxShare = Math.max(...negatives.map((t) => t.share), 0.01);
  const maxCost = Math.max(...negatives.map((t) => Math.max(t.star_cost ?? 0, 0)), 0.2);

  const writeSummary = async () => {
    setSummaryState("loading");
    try {
      setSummary(await api.getSummary(projectId, runId));
      setSummaryState("done");
    } catch (err) {
      setError(err.message);
      setSummaryState("idle");
    }
  };

  if (error && !report) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-12">
        <button onClick={onBack} className="font-mono text-[11px] uppercase tracking-widest text-graphite">← Back</button>
        <p className="mt-6 font-mono text-sm text-signal-high">{error}</p>
      </div>
    );
  }
  if (!report) {
    return <div className="mx-auto max-w-5xl px-6 py-12 font-mono text-sm text-graphite">Building report…</div>;
  }

  const { project, totals, timeline } = report;
  const period =
    timeline.length > 0 ? `${timeline[0].month} — ${timeline[timeline.length - 1].month}` : "no dates in data";

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <div className="no-print flex items-center justify-between">
        <button onClick={onBack} className="font-mono text-[11px] uppercase tracking-widest text-graphite hover:text-ink">
          ← Back
        </button>
        <button
          onClick={() => window.print()}
          className="border border-forest px-4 py-1.5 font-mono text-xs uppercase tracking-widest hover:bg-forest hover:text-paper"
        >
          Print / save PDF
        </button>
      </div>

      <header className="mt-8 border-b-2 border-ink pb-6">
        <p className="eyebrow">Customer review audit</p>
        <h1 className="display mt-2 text-5xl">{project.name}</h1>
        <div className="mt-5 grid grid-cols-2 gap-6 sm:grid-cols-4">
          <Stat label="Reviews read" value={totals.reviews} />
          <Stat label="Average rating" value={totals.average_rating ? `${totals.average_rating.toFixed(2)}★` : "—"} />
          <Stat label="Themes found" value={totals.themes} />
          <Stat label="Period" value={period} mono />
        </div>
      </header>

      {!totals.has_ratings && (
        <p className="no-print mt-6 border-l-2 border-signal-mid bg-card px-4 py-3 font-mono text-xs">
          Star cost is unavailable: the upload had no usable rating column. Themes are ranked on frequency and severity only.
        </p>
      )}

      <section className="mt-10 print-block">
        <div className="flex items-baseline justify-between">
          <p className="eyebrow">Executive summary</p>
          {summaryState === "idle" && (
            <button onClick={writeSummary} className="no-print font-mono text-[11px] underline hover:text-forest">
              generate
            </button>
          )}
        </div>
        {summaryState === "loading" && <p className="mt-3 font-mono text-sm text-graphite">Writing…</p>}
        {summary && (
          <div className="mt-3">
            <p className="display text-2xl leading-snug">{summary.headline}</p>
            <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink/85">{summary.situation}</p>
            <ol className="mt-6 space-y-4">
              {summary.priorities?.map((item, index) => (
                <li key={index} className="flex gap-4 print-block">
                  <span className="mt-1 font-mono text-xs text-graphite">{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <p className="font-semibold">{item.theme}</p>
                    <p className="text-sm text-ink/80">{item.why}</p>
                    <p className="mt-1 text-sm text-forest">→ {item.action}</p>
                  </div>
                </li>
              ))}
            </ol>
            {summary.strengths?.length > 0 && (
              <div className="mt-6 border-l-2 border-signal-low pl-4">
                <p className="eyebrow">Keep doing</p>
                <ul className="mt-2 space-y-1 text-sm">
                  {summary.strengths.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {summaryState === "idle" && !summary && (
          <p className="mt-3 max-w-xl text-sm text-graphite">
            The narrative page is written from the numbers below. Generate it once the theme list looks right.
          </p>
        )}
      </section>

      <section className="mt-14">
        <p className="eyebrow">Work list · ranked by cost to the business</p>
        <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-1 font-mono text-[10px] text-graphite">
          <span>← share of reviews mentioning it</span>
          <span>rating lost when mentioned →</span>
        </div>

        <ul className="mt-5 divide-y divide-rule border-y border-rule">
          {negatives.map((theme, index) => (
            <li key={theme.id} className="print-block py-4">
              <button
                onClick={() => setOpenTheme(theme)}
                className="grid w-full grid-cols-1 items-center gap-3 text-left lg:grid-cols-[2.2rem_1fr_320px_5rem]"
              >
                <span className="font-mono text-xs text-graphite">{String(index + 1).padStart(2, "0")}</span>
                <span>
                  <span className="display text-lg">{theme.label}</span>
                  <span className="mt-0.5 block font-mono text-[11px] text-graphite">
                    {theme.mention_count} reviews · {(theme.share * 100).toFixed(1)}%
                    {theme.star_cost !== null && ` · −${Math.max(theme.star_cost, 0).toFixed(2)}★`}
                    {" · severity "}{theme.avg_severity.toFixed(1)}
                    {theme.trend_direction !== "unknown" && ` · ${theme.trend_direction}`}
                  </span>
                </span>
                <span className="hidden lg:block">
                  <SignalBar share={theme.share} starCost={theme.star_cost} maxShare={maxShare} maxCost={maxCost} />
                </span>
                <span className="hidden items-center gap-2 lg:flex">
                  <Sparkline points={theme.trend} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {positives.length > 0 && (
        <section className="mt-14 print-block">
          <p className="eyebrow">What customers praise</p>
          <ul className="mt-4 grid gap-x-8 gap-y-3 sm:grid-cols-2">
            {positives.map((theme) => (
              <li key={theme.id}>
                <button onClick={() => setOpenTheme(theme)} className="text-left">
                  <span className="font-semibold">{theme.label}</span>
                  <span className="ml-2 font-mono text-[11px] text-graphite">
                    {theme.mention_count} · {(theme.share * 100).toFixed(1)}%
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {timeline.length > 1 && (
        <section className="mt-14 print-block">
          <p className="eyebrow">Review volume and rating by month</p>
          <Timeline timeline={timeline} />
        </section>
      )}

      <footer className="mt-16 border-t border-rule pt-4 font-mono text-[10px] text-graphite">
        Themes extracted from {totals.reviews} reviews. Star cost is the difference in average rating
        between reviews that mention a theme and reviews that do not.
      </footer>

      {openTheme && <ThemePanel theme={openTheme} onClose={() => setOpenTheme(null)} />}
    </div>
  );
}

function Stat({ label, value, mono }) {
  return (
    <div>
      <p className="eyebrow">{label}</p>
      <p className={`mt-1 ${mono ? "font-mono text-sm" : "display text-2xl"}`}>{value}</p>
    </div>
  );
}

function Timeline({ timeline }) {
  const maxCount = Math.max(...timeline.map((point) => point.count), 1);
  const width = Math.max(timeline.length * 42, 300);
  const height = 120;

  return (
    <div className="mt-4 overflow-x-auto">
      <svg width={width} height={height + 24} viewBox={`0 0 ${width} ${height + 24}`}>
        {timeline.map((point, index) => {
          const barHeight = (point.count / maxCount) * (height - 30);
          const x = index * 42 + 8;
          const rating = point.average_rating;
          const shade =
            rating === null ? "var(--color-field)"
              : rating >= 4 ? "var(--color-signal-low)"
              : rating >= 3 ? "var(--color-signal-mid)"
              : "var(--color-signal-high)";
          return (
            <g key={point.month}>
              <rect x={x} y={height - barHeight} width={26} height={barHeight} fill={shade} />
              <text x={x + 13} y={height - barHeight - 6} textAnchor="middle"
                    fontSize="9" fontFamily="IBM Plex Mono" fill="var(--color-graphite)">
                {rating ? rating.toFixed(1) : ""}
              </text>
              <text x={x + 13} y={height + 14} textAnchor="middle"
                    fontSize="8" fontFamily="IBM Plex Mono" fill="var(--color-graphite)">
                {point.month.slice(2)}
              </text>
            </g>
          );
        })}
        <line x1="0" y1={height} x2={width} y2={height} stroke="var(--color-rule)" />
      </svg>
    </div>
  );
}
