"""简历库：SQLite 持久化。主流程只读最新版；本地用 resume.md，仓库提供 resume.template.md。"""

import hashlib
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

# 与 JD 库同目录 data/jd_db/
DB_PATH = Path("./data/jd_db/resume.sqlite")


def _fingerprint(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_versions (
            resume_id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            created_at TEXT NOT NULL,
            note TEXT DEFAULT ''
        )
        """
    )
    conn.commit()
    return conn


def save_resume(content: str, note: str = "") -> dict:
    """内容有变才入库，返回 {resume_id, fingerprint, created_at, is_new}。"""
    fp = _fingerprint(content)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT fingerprint FROM resume_versions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row and row["fingerprint"] == fp:
            latest = conn.execute(
                "SELECT resume_id, fingerprint, created_at FROM resume_versions "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            return {
                "resume_id": latest["resume_id"],
                "fingerprint": latest["fingerprint"],
                "created_at": latest["created_at"],
                "is_new": False,
            }

        resume_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO resume_versions (resume_id, content, fingerprint, created_at, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (resume_id, content, fp, created_at, note),
        )
        conn.commit()
        return {
            "resume_id": resume_id,
            "fingerprint": fp,
            "created_at": created_at,
            "is_new": True,
        }
    finally:
        conn.close()


def get_latest() -> dict | None:
    """返回最新版 {resume_id, content, fingerprint, created_at, note}。"""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT resume_id, content, fingerprint, created_at, note "
            "FROM resume_versions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def load_resume() -> dict:
    """从简历库读最新版（主入口），返回 {content, fingerprint, resume_id}。"""
    latest = get_latest()
    if not latest:
        raise RuntimeError(
            "简历库为空。请复制 resume.template.md 为 resume.md 并填写后重跑，"
            "或执行：python -m memory.resume_store init resume.md"
        )
    return {
        "content": latest["content"],
        "fingerprint": latest["fingerprint"],
        "resume_id": latest["resume_id"],
    }


def seed_from_file_if_empty(*paths: Path) -> str | None:
    """库为空时，按顺序尝试导入。返回实际使用的文件名，未导入则 None。"""
    if get_latest() is not None:
        return None
    for file_path in paths:
        if not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8")
        save_resume(content, note=f"首次导入 {file_path.name}")
        return file_path.name
    return None


def list_versions() -> list[dict]:
    """按时间倒序列出版本摘要（不含全文）。"""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT resume_id, fingerprint, created_at, note, LENGTH(content) AS char_count "
            "FROM resume_versions ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    # 用法: python -m memory.resume_store init resume.md
    if len(sys.argv) >= 3 and sys.argv[1] == "init":
        path = Path(sys.argv[2])
        content = path.read_text(encoding="utf-8")
        meta = save_resume(content, note=f"init {path.name}")
        print(f"已入库 fingerprint={meta['fingerprint']} is_new={meta['is_new']}")
    elif len(sys.argv) >= 2 and sys.argv[1] == "list":
        for v in list_versions():
            print(v)
    else:
        print("用法: python -m memory.resume_store init <简历.md>")
        print("      python -m memory.resume_store list")
