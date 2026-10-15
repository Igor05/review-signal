import { useEffect, useState } from "react";
import { api } from "../api";

export default function ThemePanel({ theme, onClose }) {
  const [reviews, setReviews] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    setReviews(null);
    setError(null);
    api
      .themeReviews(theme.id)
      .then((data) => active && setReviews(data))
      .catch((err) => active && setError(err.message));
    return () => {
      active = false;
    };
  }, [theme.id]);

  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="no-print fixed inset-0 z-50 flex justify-end">
      <button
        className="flex-1 bg-ink/25"
        aria-label="Close panel"
        onClick={onClose}
      />
      <aside className="w-full max-w-xl overflow-y-auto bg-card border-l border-rule">
        <header className="sticky top-0 flex items-start justify-between gap-4 border-b border-rule bg-card px-6 py-5">
          <div>
            <p className="eyebrow">{theme.category.replace(/_/g, " ")}</p>
            <h2 className="display mt-1 text-2xl">{theme.label}</h2>
            <p className="mt-1 font-mono text-xs text-graphite">
              {theme.mention_count} reviews · {(theme.share * 100).toFixed(1)}% of corpus
              {theme.star_cost !== null && ` · ${theme.star_cost > 0 ? "−" : "+"}${Math.abs(theme.star_cost).toFixed(2)}★`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 border border-rule px-3 py-1 font-mono text-xs hover:bg-field"
          >
            Close
          </button>
        </header>

        <div className="px-6 py-5">
          {error && <p className="font-mono text-sm text-signal-high">{error}</p>}
          {!reviews && !error && <p className="font-mono text-sm text-graphite">Loading reviews…</p>}
          {reviews?.length === 0 && <p className="font-mono text-sm text-graphite">No reviews attached.</p>}

          <ul className="space-y-5">
            {reviews?.map((review) => (
              <li key={review.id} className="border-b border-rule pb-5 last:border-0">
                <div className="flex items-center gap-3 font-mono text-[11px] text-graphite">
                  <span>{review.rating !== null ? `${review.rating}★` : "no rating"}</span>
                  <span>{review.review_date || "no date"}</span>
                  {review.source && <span>{review.source}</span>}
                  <span className="ml-auto">severity {review.severity}</span>
                </div>
                {review.excerpt && (
                  <p className="mt-2 border-l-2 border-signal-mid pl-3 text-sm italic">{review.excerpt}</p>
                )}
                <p className="mt-2 text-sm leading-relaxed text-ink/80">{review.text}</p>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
