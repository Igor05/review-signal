import asyncio
import os

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from . import analyze, ingest, scoring  # noqa: E402  (env must load first)
from .db import cursor, init_db  # noqa: E402

app = FastAPI(title="Review Signal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


class ProjectIn(BaseModel):
    name: str
    business_type: str = ""


class PasteIn(BaseModel):
    text: str
    source: str = ""


def _row(query: str, params: tuple):
    with cursor() as conn:
        return conn.execute(query, params).fetchone()


@app.get("/api/health")
def health():
    return {"ok": True, "model": analyze.MODEL, "key_configured": bool(os.getenv("ANTHROPIC_API_KEY"))}


@app.get("/api/projects")
def list_projects():
    with cursor() as conn:
        rows = conn.execute(
            """SELECT p.*,
                      (SELECT COUNT(*) FROM reviews r WHERE r.project_id = p.id) AS review_count,
                      (SELECT id FROM runs WHERE project_id = p.id AND status = 'done'
                       ORDER BY id DESC LIMIT 1) AS latest_run_id
               FROM projects p ORDER BY p.id DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/projects")
def create_project(payload: ProjectIn):
    if not payload.name.strip():
        raise HTTPException(400, "Project name is required")
    with cursor() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, business_type, created_at) VALUES (?, ?, ?)",
            (payload.name.strip(), payload.business_type.strip(), ingest.today()),
        )
        return {"id": cur.lastrowid}


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int):
    with cursor() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return {"ok": True}


@app.get("/api/projects/{project_id}")
def get_project(project_id: int):
    project = _row("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not project:
        raise HTTPException(404, "Project not found")
    with cursor() as conn:
        count = conn.execute(
            "SELECT COUNT(*) c FROM reviews WHERE project_id = ?", (project_id,)
        ).fetchone()["c"]
        sample = conn.execute(
            "SELECT id, rating, review_date, source, text FROM reviews WHERE project_id = ? ORDER BY id LIMIT 8",
            (project_id,),
        ).fetchall()
        runs = conn.execute(
            "SELECT * FROM runs WHERE project_id = ? ORDER BY id DESC LIMIT 10", (project_id,)
        ).fetchall()
    return {
        "project": dict(project),
        "review_count": count,
        "sample": [dict(r) for r in sample],
        "runs": [dict(r) for r in runs],
    }


def _insert_reviews(project_id: int, rows: list[dict]) -> int:
    with cursor() as conn:
        before = conn.execute(
            "SELECT COUNT(*) c FROM reviews WHERE project_id = ?", (project_id,)
        ).fetchone()["c"]
        conn.executemany(
            """INSERT OR IGNORE INTO reviews
               (project_id, source, author, rating, text, review_date, fingerprint)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    project_id,
                    r["source"],
                    r["author"],
                    r["rating"],
                    r["text"],
                    r["review_date"],
                    ingest._fingerprint(r["text"], r["author"]),
                )
                for r in rows
            ],
        )
        after = conn.execute(
            "SELECT COUNT(*) c FROM reviews WHERE project_id = ?", (project_id,)
        ).fetchone()["c"]
    return after - before


@app.post("/api/projects/{project_id}/upload")
async def upload_reviews(
    project_id: int,
    file: UploadFile = File(...),
    source: str = Form(""),
):
    if not _row("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise HTTPException(404, "Project not found")
    raw = await file.read()
    try:
        rows, warnings = ingest.parse_upload(raw, file.filename or "upload.csv", source)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(400, f"Could not read that file: {exc}")

    added = _insert_reviews(project_id, rows)
    return {
        "parsed": len(rows),
        "added": added,
        "duplicates_skipped": len(rows) - added,
        "warnings": warnings,
    }


@app.post("/api/projects/{project_id}/paste")
def paste_reviews(project_id: int, payload: PasteIn):
    if not _row("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise HTTPException(404, "Project not found")
    rows = ingest.parse_pasted_text(payload.text, payload.source)
    if not rows:
        raise HTTPException(400, "Nothing to add. Separate each review with a blank line.")
    added = _insert_reviews(project_id, rows)
    return {"parsed": len(rows), "added": added, "duplicates_skipped": len(rows) - added, "warnings": []}


@app.delete("/api/projects/{project_id}/reviews")
def clear_reviews(project_id: int):
    with cursor() as conn:
        conn.execute("DELETE FROM reviews WHERE project_id = ?", (project_id,))
    return {"ok": True}


@app.post("/api/projects/{project_id}/analyze")
def start_analysis(project_id: int, background: BackgroundTasks):
    project = _row("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not project:
        raise HTTPException(404, "Project not found")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(400, "ANTHROPIC_API_KEY is not set on the server.")

    with cursor() as conn:
        running = conn.execute(
            "SELECT id FROM runs WHERE project_id = ? AND status = 'running'", (project_id,)
        ).fetchone()
        if running:
            return {"run_id": running["id"], "already_running": True}
        count = conn.execute(
            "SELECT COUNT(*) c FROM reviews WHERE project_id = ?", (project_id,)
        ).fetchone()["c"]
        if count == 0:
            raise HTTPException(400, "Add reviews before running an analysis.")
        cur = conn.execute(
            "INSERT INTO runs (project_id, status, stage, total, created_at, model) VALUES (?, 'running', 'queued', ?, ?, ?)",
            (project_id, count, ingest.today(), analyze.MODEL),
        )
        run_id = cur.lastrowid

    background.add_task(asyncio.run, analyze.run_analysis(run_id, project_id))
    return {"run_id": run_id, "already_running": False}


@app.get("/api/runs/{run_id}")
def run_status(run_id: int):
    run = _row("SELECT * FROM runs WHERE id = ?", (run_id,))
    if not run:
        raise HTTPException(404, "Run not found")
    return dict(run)


@app.get("/api/projects/{project_id}/report")
def get_report(project_id: int, run_id: int | None = None):
    if run_id is None:
        latest = _row(
            "SELECT id FROM runs WHERE project_id = ? AND status = 'done' ORDER BY id DESC LIMIT 1",
            (project_id,),
        )
        if not latest:
            raise HTTPException(404, "No completed analysis for this project yet.")
        run_id = latest["id"]
    try:
        return scoring.build_report(project_id, run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@app.post("/api/projects/{project_id}/summary")
async def get_summary(project_id: int, run_id: int | None = None):
    report = get_report(project_id, run_id)
    try:
        return await analyze.write_summary(project_id, report)
    except Exception as exc:
        raise HTTPException(502, f"Summary generation failed: {exc}")


@app.get("/api/themes/{theme_id}/reviews")
def theme_reviews(theme_id: int, limit: int = 50):
    with cursor() as conn:
        rows = conn.execute(
            """SELECT r.id, r.rating, r.review_date, r.author, r.source, r.text,
                      m.sentiment, m.severity, m.excerpt
               FROM mentions m JOIN reviews r ON r.id = m.review_id
               WHERE m.theme_id = ?
               ORDER BY m.severity DESC, r.review_date DESC
               LIMIT ?""",
            (theme_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]
