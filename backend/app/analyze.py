import asyncio
import json
import os
import re
from collections import Counter

from anthropic import AsyncAnthropic

from . import prompts
from .db import cursor
from .ingest import today

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "4"))

def make_client() -> AsyncAnthropic:
    """A fresh client per run.

    The underlying httpx client binds to the event loop it was created in, and
    every background run gets its own loop via asyncio.run. Caching one globally
    works on the first run and fails on the second.
    """
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.")
    return AsyncAnthropic(api_key=key)


def _strip_json(raw: str) -> str:
    """Models occasionally wrap JSON in fences despite instructions."""
    cleaned = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    start = min([i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1], default=0)
    return cleaned[start:]


async def _call(client: AsyncAnthropic, system: str, user: str,
                max_tokens: int = 16000, retries: int = 2) -> dict:
    # Current models think before answering by default, and thinking tokens count
    # against max_tokens. A tight cap truncates the JSON mid-string.
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            if response.stop_reason in ("max_tokens", "refusal"):
                raise RuntimeError(f"Model stopped early: stop_reason={response.stop_reason}")
            text = "".join(block.text for block in response.content if block.type == "text")
            return json.loads(_strip_json(text))
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            await asyncio.sleep(1 + attempt * 2)
        except Exception as exc:  # network, rate limit, overload
            last_error = exc
            await asyncio.sleep(2 + attempt * 4)
    raise RuntimeError(f"Model call failed after {retries + 1} attempts: {last_error}")


def _set_run(run_id: int, **fields):
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    with cursor() as conn:
        conn.execute(f"UPDATE runs SET {assignments} WHERE id = ?", (*fields.values(), run_id))


def _bump_processed(run_id: int, amount: int):
    with cursor() as conn:
        conn.execute("UPDATE runs SET processed = processed + ? WHERE id = ?", (amount, run_id))


async def run_analysis(run_id: int, project_id: int):
    try:
        with cursor() as conn:
            project = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            reviews = [
                dict(row) for row in conn.execute(
                    "SELECT id, text, rating FROM reviews WHERE project_id = ? ORDER BY id",
                    (project_id,),
                ).fetchall()
            ]

        if not reviews:
            raise RuntimeError("This project has no reviews yet.")

        business_type = project["business_type"] if project else ""
        batches = [reviews[i:i + BATCH_SIZE] for i in range(0, len(reviews), BATCH_SIZE)]
        _set_run(run_id, stage="extracting", total=len(reviews), processed=0, model=MODEL)

        client = make_client()
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def process(batch):
            async with semaphore:
                data = await _call(
                    client,
                    prompts.EXTRACT_SYSTEM,
                    prompts.extract_user_prompt(batch, business_type),
                )
                _bump_processed(run_id, len(batch))
                return data.get("results", [])

        extracted: list[dict] = []
        failed_reviews = 0
        first_error = None
        chunks = await asyncio.gather(*(process(b) for b in batches), return_exceptions=True)
        for batch, chunk in zip(batches, chunks):
            if isinstance(chunk, Exception):
                # One bad batch should not sink a 900-review run, but a report built
                # on a fraction of the corpus would be silently wrong.
                failed_reviews += len(batch)
                first_error = first_error or chunk
                continue
            extracted.extend(chunk)

        if not extracted:
            raise RuntimeError(f"Extraction produced no results. Check the API key and model name. ({first_error})")
        if failed_reviews > len(reviews) * 0.25:
            raise RuntimeError(
                f"Extraction failed for {failed_reviews} of {len(reviews)} reviews: {first_error}"
            )

        # Flatten into (review_id, topic) pairs, dropping anything malformed.
        valid_ids = {r["id"] for r in reviews}
        raw_topics: list[dict] = []
        for entry in extracted:
            try:
                review_id = int(entry["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if review_id not in valid_ids:
                continue
            for topic in entry.get("topics") or []:
                label = str(topic.get("label", "")).strip().lower()
                if not label:
                    continue
                sentiment = topic.get("sentiment", "negative")
                if sentiment not in ("positive", "negative", "mixed"):
                    sentiment = "negative"
                try:
                    severity = max(1, min(5, int(topic.get("severity", 3))))
                except (TypeError, ValueError):
                    severity = 3
                raw_topics.append({
                    "review_id": review_id,
                    "label": label,
                    "category": str(topic.get("category", "other")).strip() or "other",
                    "sentiment": sentiment,
                    "severity": severity,
                    "excerpt": str(topic.get("excerpt", ""))[:400],
                })

        if not raw_topics:
            raise RuntimeError("No topics were extracted. The reviews may be too short to analyse.")

        _set_run(run_id, stage="consolidating")

        counts = Counter((t["label"], t["category"]) for t in raw_topics)
        label_counts = [(label, category, n) for (label, category), n in counts.most_common()]

        # Very large label sets blow the context. Consolidate in slices, then merge names.
        themes_spec: list[dict] = []
        SLICE = 220
        for i in range(0, len(label_counts), SLICE):
            data = await _call(
                client,
                prompts.CONSOLIDATE_SYSTEM,
                prompts.consolidate_user_prompt(label_counts[i:i + SLICE], business_type),
            )
            themes_spec.extend(data.get("themes", []))

        # Merge themes that came back with the same canonical label from different slices.
        merged: dict[str, dict] = {}
        for spec in themes_spec:
            label = str(spec.get("label", "")).strip()
            if not label:
                continue
            key = label.lower()
            if key not in merged:
                merged[key] = {
                    "label": label,
                    "category": str(spec.get("category", "other")) or "other",
                    "polarity": spec.get("polarity", "negative"),
                    "members": [],
                }
            merged[key]["members"].extend(
                str(m).strip().lower() for m in (spec.get("members") or [])
            )

        label_to_theme: dict[str, str] = {}
        for key, theme in merged.items():
            for member in theme["members"]:
                label_to_theme.setdefault(member, key)

        # Anything the consolidation pass forgot keeps its own raw label as a theme,
        # so no mention is silently dropped from the counts.
        for topic in raw_topics:
            if topic["label"] not in label_to_theme:
                key = topic["label"]
                merged.setdefault(key, {
                    "label": topic["label"].capitalize(),
                    "category": topic["category"],
                    "polarity": "positive" if topic["sentiment"] == "positive" else "negative",
                    "members": [topic["label"]],
                })
                label_to_theme[topic["label"]] = key

        # Polarity comes from what reviewers actually said, not from the consolidation
        # pass, which sometimes files praise ("best carbonara") under a negative theme
        # and pushes it into the work list.
        sentiments: dict[str, Counter] = {}
        for topic in raw_topics:
            sentiments.setdefault(label_to_theme[topic["label"]], Counter())[topic["sentiment"]] += 1
        for key, counts in sentiments.items():
            merged[key]["polarity"] = "positive" if counts["positive"] > sum(counts.values()) / 2 else "negative"

        _set_run(run_id, stage="writing")

        with cursor() as conn:
            theme_ids: dict[str, int] = {}
            for key, theme in merged.items():
                cur = conn.execute(
                    "INSERT INTO themes (run_id, project_id, label, category, polarity) VALUES (?, ?, ?, ?, ?)",
                    (run_id, project_id, theme["label"], theme["category"], theme["polarity"]),
                )
                theme_ids[key] = cur.lastrowid

            conn.executemany(
                "INSERT INTO mentions (theme_id, review_id, sentiment, severity, excerpt) VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        theme_ids[label_to_theme[t["label"]]],
                        t["review_id"],
                        t["sentiment"],
                        t["severity"],
                        t["excerpt"],
                    )
                    for t in raw_topics
                    if label_to_theme.get(t["label"]) in theme_ids
                ],
            )

            # Drop themes that ended up with nothing attached.
            conn.execute(
                "DELETE FROM themes WHERE run_id = ? AND id NOT IN (SELECT theme_id FROM mentions)",
                (run_id,),
            )

        _set_run(run_id, status="done", stage="done", finished_at=today())

    except Exception as exc:
        _set_run(run_id, status="failed", stage="failed", error=str(exc)[:1000], finished_at=today())


async def write_summary(project_id: int, report: dict) -> dict:
    """Optional narrative page. Called separately so a failed summary never kills a run."""
    payload = {
        "business_type": report["project"]["business_type"],
        "total_reviews": report["totals"]["reviews"],
        "average_rating": report["totals"]["average_rating"],
        "themes": [
            {
                "label": t["label"],
                "share_of_reviews": t["share"],
                "star_cost": t["star_cost"],
                "avg_severity": t["avg_severity"],
                "trend": t["trend_direction"],
                "polarity": t["polarity"],
            }
            for t in report["themes"][:18]
        ],
    }
    return await _call(
        make_client(),
        prompts.SUMMARY_SYSTEM,
        json.dumps(payload, ensure_ascii=False),
    )
