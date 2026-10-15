"""Turns raw mentions into the numbers that go on the report.

star_cost is the metric the whole deliverable hangs on: how much average rating
the business loses on reviews that mention a theme, versus reviews that don't.
It answers "what does this cost me", which frequency alone never does.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from .db import cursor

RECENT_WINDOW_DAYS = 120


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def _month(date_str: str | None) -> str | None:
    return date_str[:7] if date_str and len(date_str) >= 7 else None


def build_report(project_id: int, run_id: int) -> dict:
    with cursor() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        reviews = conn.execute(
            "SELECT id, rating, review_date, text, author, source FROM reviews WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        themes = conn.execute(
            "SELECT * FROM themes WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
        mentions = conn.execute(
            """SELECT m.* FROM mentions m
               JOIN themes t ON t.id = m.theme_id
               WHERE t.run_id = ?""",
            (run_id,),
        ).fetchall()

    if not project:
        raise ValueError("Project not found")

    review_by_id = {r["id"]: r for r in reviews}
    total_reviews = len(reviews)
    all_ratings = [r["rating"] for r in reviews if r["rating"] is not None]
    has_ratings = len(all_ratings) >= max(10, total_reviews * 0.3)
    has_dates = sum(1 for r in reviews if r["review_date"]) >= max(10, total_reviews * 0.3)

    dated = [r["review_date"] for r in reviews if r["review_date"]]
    cutoff = None
    if dated:
        try:
            newest = max(datetime.strptime(d, "%Y-%m-%d") for d in dated)
            cutoff = (newest - timedelta(days=RECENT_WINDOW_DAYS)).strftime("%Y-%m-%d")
        except ValueError:
            cutoff = None

    by_theme = defaultdict(list)
    for mention in mentions:
        by_theme[mention["theme_id"]].append(mention)

    corpus_average = _mean(all_ratings)
    results = []

    for theme in themes:
        theme_mentions = by_theme.get(theme["id"], [])
        if not theme_mentions:
            continue

        review_ids = {m["review_id"] for m in theme_mentions}
        count = len(review_ids)
        share = round(count / total_reviews, 4) if total_reviews else 0

        inside = [review_by_id[i]["rating"] for i in review_ids
                  if i in review_by_id and review_by_id[i]["rating"] is not None]
        outside = [r["rating"] for r in reviews
                   if r["id"] not in review_ids and r["rating"] is not None]

        avg_inside, avg_outside = _mean(inside), _mean(outside)
        star_cost = None
        if has_ratings and avg_inside is not None and avg_outside is not None and len(inside) >= 3:
            star_cost = round(avg_outside - avg_inside, 2)

        severities = [m["severity"] for m in theme_mentions if m["sentiment"] != "positive"]
        avg_severity = _mean(severities) or 1.0

        monthly = defaultdict(int)
        for review_id in review_ids:
            month = _month(review_by_id[review_id]["review_date"]) if review_id in review_by_id else None
            if month:
                monthly[month] += 1
        trend = [{"month": m, "count": monthly[m]} for m in sorted(monthly)]

        recent_share = None
        trend_direction = "unknown"
        if cutoff and has_dates:
            recent_ids = [i for i in review_ids
                          if i in review_by_id and (review_by_id[i]["review_date"] or "") >= cutoff]
            recent_reviews = [r for r in reviews if (r["review_date"] or "") >= cutoff]
            if len(recent_reviews) >= 10:
                recent_share = round(len(recent_ids) / len(recent_reviews), 4)
                if recent_share > share * 1.25:
                    trend_direction = "worsening"
                elif recent_share < share * 0.75:
                    trend_direction = "improving"
                else:
                    trend_direction = "steady"

        # Priority: how often it happens, how badly it lands, what it costs in stars,
        # and whether it is getting worse. Scaled to 0-100 for readability.
        cost_factor = max(star_cost, 0.05) if star_cost is not None else 0.35
        recency_factor = {"worsening": 1.35, "steady": 1.0, "improving": 0.7, "unknown": 1.0}[trend_direction]
        priority = round(share * 100 * (avg_severity / 3) * (cost_factor / 0.4) * recency_factor, 1)

        excerpts = [m["excerpt"] for m in theme_mentions if m["excerpt"]][:4]

        results.append({
            "id": theme["id"],
            "label": theme["label"],
            "category": theme["category"],
            "polarity": theme["polarity"],
            "mention_count": count,
            "share": share,
            "avg_severity": round(avg_severity, 2),
            "avg_rating_with": avg_inside,
            "avg_rating_without": avg_outside,
            "star_cost": star_cost,
            "recent_share": recent_share,
            "trend_direction": trend_direction,
            "trend": trend,
            "priority": priority if theme["polarity"] == "negative" else 0,
            "excerpts": excerpts,
            "review_ids": sorted(review_ids),
        })

    results.sort(key=lambda t: (t["polarity"] == "positive", -t["priority"], -t["mention_count"]))

    rating_histogram = {str(star): 0 for star in range(1, 6)}
    for rating in all_ratings:
        rating_histogram[str(int(round(rating)))] += 1

    monthly_volume = defaultdict(lambda: {"count": 0, "ratings": []})
    for review in reviews:
        month = _month(review["review_date"])
        if month:
            monthly_volume[month]["count"] += 1
            if review["rating"] is not None:
                monthly_volume[month]["ratings"].append(review["rating"])

    timeline = [
        {"month": m, "count": v["count"], "average_rating": _mean(v["ratings"])}
        for m, v in sorted(monthly_volume.items())
    ]

    return {
        "project": {
            "id": project["id"],
            "name": project["name"],
            "business_type": project["business_type"],
        },
        "run_id": run_id,
        "totals": {
            "reviews": total_reviews,
            "average_rating": corpus_average,
            "has_ratings": has_ratings,
            "has_dates": has_dates,
            "themes": len(results),
            "negative_themes": sum(1 for t in results if t["polarity"] == "negative"),
            "rating_histogram": rating_histogram,
        },
        "timeline": timeline,
        "themes": results,
    }
