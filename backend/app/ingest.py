"""Reads whatever the client exported and turns it into normalised review rows."""

import hashlib
import io
import re
from datetime import datetime

import pandas as pd

# Column names seen in the wild across Google Takeout, Judge.me, Loox, Yotpo,
# Trustpilot and hand-made spreadsheets. Order matters: first match wins.
COLUMN_ALIASES = {
    "text": [
        "text", "review", "review_text", "body", "content", "comment",
        "comments", "review body", "message", "description", "otzyv",
        "отзыв", "текст", "текст отзыва", "комментарий",
    ],
    "rating": [
        "rating", "stars", "star_rating", "score", "review_rating",
        "star rating", "оценка", "рейтинг", "звезды",
    ],
    "author": [
        "author", "name", "reviewer", "reviewer_name", "customer",
        "customer_name", "user", "display_name", "автор", "имя",
    ],
    "date": [
        "date", "created_at", "review_date", "time", "timestamp",
        "published", "published_at", "submitted_at", "дата",
    ],
    "source": ["source", "platform", "site", "channel", "источник"],
}

WORD_RATINGS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "1 star": 1, "2 stars": 2, "3 stars": 3, "4 stars": 4, "5 stars": 5,
}


def _normalise_header(name: str) -> str:
    return re.sub(r"[^a-zа-я0-9 ]+", " ", str(name).strip().lower()).strip()


def _map_columns(df: pd.DataFrame) -> dict:
    lookup = {_normalise_header(c): c for c in df.columns}
    mapping = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = _normalise_header(alias)
            if key in lookup:
                mapping[field] = lookup[key]
                break
    return mapping


def _parse_rating(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        rating = float(value)
    else:
        raw = str(value).strip().lower()
        if raw in WORD_RATINGS:
            return float(WORD_RATINGS[raw])
        match = re.search(r"\d+(?:[.,]\d+)?", raw)
        if not match:
            return None
        rating = float(match.group().replace(",", "."))
    # Some exports use a 0-100 or 0-10 scale. Rescale to 1-5.
    if rating > 10:
        rating = rating / 20
    elif rating > 5:
        rating = rating / 2
    return round(max(1.0, min(5.0, rating)), 2)


def _parse_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
    except Exception:
        return None
    if parsed is None or pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


def _fingerprint(text: str, author: str) -> str:
    key = re.sub(r"\s+", " ", f"{author}|{text}".strip().lower())
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def parse_upload(raw: bytes, filename: str, default_source: str = "") -> tuple[list[dict], list[str]]:
    """Returns (rows, warnings). Never raises on a single bad row."""
    warnings: list[str] = []
    name = filename.lower()

    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(raw))
    elif name.endswith(".json"):
        df = pd.read_json(io.BytesIO(raw))
    else:
        # CSV exports arrive in three encodings and two separators, routinely.
        text = None
        for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("Could not decode the file. Save it as UTF-8 CSV and retry.")
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python")

    mapping = _map_columns(df)
    if "text" not in mapping:
        raise ValueError(
            "No review text column found. Rename the column holding review text "
            "to 'text' and upload again. Columns seen: " + ", ".join(map(str, df.columns))
        )

    rows, seen = [], set()
    for _, record in df.iterrows():
        text = str(record[mapping["text"]]).strip()
        if not text or text.lower() in ("nan", "none", "null"):
            continue
        if len(text) < 3:
            continue

        author = str(record[mapping["author"]]).strip() if "author" in mapping else ""
        if author.lower() in ("nan", "none", "null"):
            author = ""

        source = default_source
        if "source" in mapping:
            candidate = str(record[mapping["source"]]).strip()
            if candidate and candidate.lower() not in ("nan", "none", "null"):
                source = candidate

        fingerprint = _fingerprint(text, author)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)

        rows.append({
            "text": text[:8000],
            "rating": _parse_rating(record[mapping["rating"]]) if "rating" in mapping else None,
            "author": author[:120],
            "review_date": _parse_date(record[mapping["date"]]) if "date" in mapping else None,
            "source": source[:60],
        })

    if "rating" not in mapping:
        warnings.append("No rating column found. Star-cost scoring will be unavailable.")
    if "date" not in mapping:
        warnings.append("No date column found. Trend charts will be unavailable.")
    if not rows:
        raise ValueError("File parsed, but no usable review rows were found.")

    return rows, warnings


def parse_pasted_text(blob: str, default_source: str = "") -> list[dict]:
    """One review per paragraph. For when the client just emails you a wall of text."""
    chunks = [c.strip() for c in re.split(r"\n\s*\n", blob) if c.strip()]
    rows, seen = [], set()
    for chunk in chunks:
        if len(chunk) < 3:
            continue
        fingerprint = _fingerprint(chunk, "")
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        rows.append({
            "text": chunk[:8000],
            "rating": None,
            "author": "",
            "review_date": None,
            "source": default_source,
        })
    return rows


def today() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")
