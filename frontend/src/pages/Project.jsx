import { useEffect, useRef, useState } from "react";
import { api } from "../api";

const STAGE_LABELS = {
  queued: "Queued",
  extracting: "Reading reviews",
  consolidating: "Merging duplicate topics",
  writing: "Saving results",
  done: "Done",
  failed: "Failed",
};

export default function Project({ projectId, onBack, onReport }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [paste, setPaste] = useState("");
  const [source, setSource] = useState("");
  const [activeRun, setActiveRun] = useState(null);
  const fileInput = useRef(null);

  const load = () =>
    api.getProject(projectId).then(setData).catch((err) => setError(err.message));

  useEffect(() => {
    load();
  }, [projectId]);

  // Adopt any run that is still going after a page reload.
  useEffect(() => {
    const running = data?.runs?.find((run) => run.status === "running");
    if (running && !activeRun) setActiveRun(running);
  }, [data]);

  useEffect(() => {
    if (!activeRun || activeRun.status !== "running") return;
    const timer = setInterval(async () => {
      try {
        const run = await api.runStatus(activeRun.id);
        setActiveRun(run);
        if (run.status !== "running") {
          clearInterval(timer);
          load();
          if (run.status === "done") onReport(projectId, run.id);
        }
      } catch {
        clearInterval(timer);
      }
    }, 2500);
    return () => clearInterval(timer);
  }, [activeRun?.id, activeRun?.status]);

  const wrap = async (fn) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const upload = (file) =>
    wrap(async () => {
      const result = await api.uploadFile(projectId, file, source);
      const parts = [`${result.added} reviews added`];
      if (result.duplicates_skipped) parts.push(`${result.duplicates_skipped} duplicates skipped`);
      setNotice([...parts, ...result.warnings].join(" · "));
    });

  const addPasted = () =>
    wrap(async () => {
      const result = await api.pasteReviews(projectId, paste, source);
      setPaste("");
      setNotice(`${result.added} reviews added`);
    });

  const analyse = () =>
    wrap(async () => {
      const { run_id } = await api.startAnalysis(projectId);
      setActiveRun({ id: run_id, status: "running", stage: "queued", processed: 0, total: 0 });
    });

  const clear = () =>
    wrap(async () => {
      if (!window.confirm("Remove every review from this project?")) return;
      await api.clearReviews(projectId);
    });

  if (error && !data) return <Shell onBack={onBack}><p className="font-mono text-sm text-signal-high">{error}</p></Shell>;
  if (!data) return <Shell onBack={onBack}><p className="font-mono text-sm text-graphite">Loading…</p></Shell>;

  const { project, review_count, sample, runs } = data;
  const lastDone = runs.find((run) => run.status === "done");
  const running = activeRun?.status === "running";
  const progress = activeRun?.total ? Math.round((activeRun.processed / activeRun.total) * 100) : 0;

  return (
    <Shell onBack={onBack}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">{project.business_type || "no business type set"}</p>
          <h1 className="display mt-2 text-4xl">{project.name}</h1>
          <p className="mt-1 font-mono text-xs text-graphite">{review_count} reviews loaded</p>
        </div>
        {lastDone && (
          <button
            onClick={() => onReport(projectId, lastDone.id)}
            className="border border-forest px-5 py-2 font-mono text-xs uppercase tracking-widest hover:bg-forest hover:text-paper"
          >
            Open report
          </button>
        )}
      </div>

      {notice && <p className="mt-6 border-l-2 border-signal-low bg-card px-4 py-3 font-mono text-xs">{notice}</p>}
      {error && <p className="mt-6 border-l-2 border-signal-high bg-card px-4 py-3 font-mono text-xs text-signal-high">{error}</p>}

      <section className="mt-10 grid gap-6 lg:grid-cols-2">
        <div className="border border-rule bg-card p-6">
          <p className="eyebrow">1 · Load reviews</p>
          <input
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Source label, e.g. Google"
            className="mt-4 w-full border border-rule bg-paper px-3 py-2 text-sm outline-none focus:border-forest"
          />

          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const file = e.dataTransfer.files?.[0];
              if (file) upload(file);
            }}
            className="mt-4 border border-dashed border-rule px-4 py-8 text-center"
          >
            <p className="text-sm">Drop a CSV, XLSX or JSON export here</p>
            <button
              onClick={() => fileInput.current?.click()}
              disabled={busy}
              className="mt-3 border border-rule px-4 py-1.5 font-mono text-xs hover:bg-field disabled:opacity-40"
            >
              Choose file
            </button>
            <input
              ref={fileInput}
              type="file"
              accept=".csv,.xlsx,.xls,.json"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) upload(file);
                e.target.value = "";
              }}
            />
            <p className="mt-3 font-mono text-[10px] leading-relaxed text-graphite">
              Column names are detected automatically. A text column is required;
              rating and date columns unlock star cost and trends.
            </p>
          </div>

          <textarea
            value={paste}
            onChange={(e) => setPaste(e.target.value)}
            rows={4}
            placeholder="Or paste reviews, one per paragraph, separated by a blank line"
            className="mt-4 w-full border border-rule bg-paper px-3 py-2 text-sm outline-none focus:border-forest"
          />
          <div className="mt-2 flex gap-3">
            <button
              onClick={addPasted}
              disabled={busy || !paste.trim()}
              className="border border-rule px-4 py-1.5 font-mono text-xs hover:bg-field disabled:opacity-40"
            >
              Add pasted reviews
            </button>
            {review_count > 0 && (
              <button
                onClick={clear}
                disabled={busy}
                className="ml-auto font-mono text-[11px] uppercase tracking-widest text-graphite hover:text-signal-high"
              >
                Clear all
              </button>
            )}
          </div>
        </div>

        <div className="border border-rule bg-card p-6">
          <p className="eyebrow">2 · Run the analysis</p>
          <p className="mt-4 text-sm text-graphite">
            Every review is read once to pull out topics, then all topics are merged into
            canonical themes. Roughly one minute per 200 reviews.
          </p>

          <button
            onClick={analyse}
            disabled={busy || running || review_count === 0}
            className="mt-5 w-full bg-forest px-5 py-3 font-mono text-xs uppercase tracking-widest text-paper hover:bg-ink disabled:opacity-40"
          >
            {running ? "Analysis running" : review_count === 0 ? "Load reviews first" : "Analyse reviews"}
          </button>

          {activeRun && (
            <div className="mt-5">
              <div className="flex justify-between font-mono text-[11px] text-graphite">
                <span>{STAGE_LABELS[activeRun.stage] || activeRun.stage}</span>
                <span>{activeRun.total ? `${activeRun.processed}/${activeRun.total}` : ""}</span>
              </div>
              <div className="mt-2 h-1.5 bg-field">
                <div className="h-full bg-forest transition-all" style={{ width: `${progress}%` }} />
              </div>
              {activeRun.error && (
                <p className="mt-3 font-mono text-[11px] text-signal-high">{activeRun.error}</p>
              )}
            </div>
          )}

          {runs.length > 0 && (
            <ul className="mt-6 space-y-2 border-t border-rule pt-4">
              {runs.slice(0, 5).map((run) => (
                <li key={run.id} className="flex items-center gap-3 font-mono text-[11px] text-graphite">
                  <span className="w-12">#{run.id}</span>
                  <span className="w-16">{run.status}</span>
                  <span className="flex-1 truncate">{run.created_at}</span>
                  {run.status === "done" && (
                    <button onClick={() => onReport(projectId, run.id)} className="underline hover:text-ink">
                      view
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {sample.length > 0 && (
        <section className="mt-10">
          <p className="eyebrow">Loaded sample</p>
          <ul className="mt-3 divide-y divide-rule border-y border-rule">
            {sample.map((review) => (
              <li key={review.id} className="py-3">
                <div className="flex gap-3 font-mono text-[11px] text-graphite">
                  <span>{review.rating !== null ? `${review.rating}★` : "—"}</span>
                  <span>{review.review_date || "no date"}</span>
                  <span>{review.source || "—"}</span>
                </div>
                <p className="mt-1 truncate text-sm">{review.text}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </Shell>
  );
}

function Shell({ children, onBack }) {
  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <button onClick={onBack} className="font-mono text-[11px] uppercase tracking-widest text-graphite hover:text-ink">
        ← Clients
      </button>
      <div className="mt-6">{children}</div>
    </div>
  );
}
