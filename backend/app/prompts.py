"""Two-pass extraction.

Pass 1 pulls topics out of each review. Left alone it produces 300 near-identical
labels ("slow service", "service was slow", "waited too long") which makes any
frequency count meaningless. Pass 2 collapses them into canonical themes. The
second pass is the whole product; skipping it is what makes competing tools
produce word clouds instead of a work list.
"""

CATEGORIES = [
    "product_quality",
    "service_staff",
    "speed_wait_time",
    "price_value",
    "cleanliness_condition",
    "ordering_checkout",
    "delivery_shipping",
    "returns_refunds",
    "communication_support",
    "atmosphere_experience",
    "accuracy_expectations",
    "other",
]

EXTRACT_SYSTEM = f"""You extract structured topics from customer reviews for an operational audit.

For each review, list every distinct topic the customer actually comments on. A topic is a concrete thing the business controls, not a mood.

Rules:
- Write topic labels as short noun phrases in English, 2-5 words, lowercase, describing the specific thing: "wait time at pickup", "portion size", "checkout page errors". Never write vague labels like "bad service", "good experience", "quality".
- Only extract what is stated. Do not infer causes the customer did not mention.
- A review with no substantive content (e.g. "Great!", "5 stars") gets an empty topics list.
- sentiment is "positive", "negative" or "mixed" for that topic in that review.
- severity is 1-5 and applies to negative or mixed topics only (use 1 for positive): 1 minor nitpick, 3 real friction that annoys, 5 the customer says they will not return, lost money, or was unsafe.
- excerpt is a verbatim span from the review, max 20 words, that supports the topic. Copy it exactly, do not paraphrase.
- category must be one of: {", ".join(CATEGORIES)}

Return ONLY valid JSON, no markdown fences, no commentary, in this shape:
{{"results": [{{"id": <review id as given>, "topics": [{{"label": "...", "category": "...", "sentiment": "...", "severity": 3, "excerpt": "..."}}]}}]}}

Include an entry for every review id you were given, even if its topics list is empty."""


def extract_user_prompt(batch: list[dict], business_type: str) -> str:
    context = f"Business type: {business_type}\n\n" if business_type else ""
    lines = []
    for review in batch:
        rating = review["rating"] if review["rating"] is not None else "n/a"
        lines.append(f"[id={review['id']}] (rating: {rating}) {review['text']}")
    return context + "Reviews:\n\n" + "\n\n".join(lines)


CONSOLIDATE_SYSTEM = """You merge near-duplicate topic labels into canonical themes for a review audit.

You get a list of raw topic labels with the number of times each appeared. Group labels that describe the same underlying operational issue, even when worded differently ("slow service", "long wait", "waited 40 minutes" are one theme).

Rules:
- Merge aggressively on meaning, but never merge topics a business owner would fix differently. "cold food" and "slow delivery" stay separate even though both are about delivery.
- Never merge a positive theme with a negative one about the same subject. "friendly staff" and "rude staff" are two themes.
- Canonical labels: sentence case, 2-6 words, name the specific issue as an owner would put it on a task list. Good: "Wait time before seating", "Checkout page throws errors", "Staff friendliness". Bad: "Service issues", "Various complaints".
- Assign each canonical theme a category from the ones present in the input, and polarity ("negative" or "positive") based on how the underlying labels read.
- Every raw label must appear in exactly one theme's members list. Do not invent labels that were not in the input.
- Aim for 12-30 canonical themes. If the input is small, fewer is fine.

Return ONLY valid JSON, no markdown fences:
{"themes": [{"label": "...", "category": "...", "polarity": "negative", "members": ["raw label 1", "raw label 2"]}]}"""


def consolidate_user_prompt(label_counts: list[tuple[str, str, int]], business_type: str) -> str:
    context = f"Business type: {business_type}\n\n" if business_type else ""
    lines = [f"- {label} (category: {category}, seen {count}x)" for label, category, count in label_counts]
    return context + "Raw topic labels:\n" + "\n".join(lines)


SUMMARY_SYSTEM = """You write the opening page of a customer-review audit delivered to a business owner.

You get ranked themes with their metrics. Write for someone who has 90 seconds and wants to know what to fix on Monday.

Rules:
- No preamble, no "in conclusion", no praise for the business.
- Reference real numbers from the data (share of reviews, star cost, direction of trend).
- Be specific about the operational fix implied by each theme. If the data does not tell you the cause, say what to investigate rather than guessing.
- Do not invent facts that are not in the metrics you were given.

Return ONLY valid JSON, no markdown fences:
{"headline": "one sentence, max 20 words, the single most important finding",
 "situation": "2-3 sentences on the overall state of the review corpus",
 "priorities": [{"theme": "exact theme label", "why": "one sentence on cost to the business", "action": "one concrete next step"}],
 "strengths": ["what is working, 1-3 bullets, each under 15 words"]}

Include 3-5 priorities, ordered most urgent first."""
