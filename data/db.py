"""
SQLite 数据层：学生档案 + 练习记录 + 薄弱点进度 + 错题库

所有数据库操作通过此模块完成，替代分散的 JSON 文件。
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from schemas import StudentProfile

BASE_DIR = Path(__file__).parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "agent.db"


def init_db(path: str = None) -> sqlite3.Connection:
    """初始化数据库并创建所有表"""
    db_path = path if path else str(DEFAULT_DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            grade INTEGER NOT NULL,
            textbook TEXT NOT NULL DEFAULT '人教版',
            student_type TEXT NOT NULL DEFAULT '课内提高',
            is_tutoring INTEGER NOT NULL DEFAULT 0,
            sessions_per_week INTEGER NOT NULL DEFAULT 1,
            start_date TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            day INTEGER NOT NULL,
            weak_point TEXT NOT NULL,
            accuracy REAL NOT NULL DEFAULT 0.0,
            questions_json TEXT NOT NULL DEFAULT '[]',
            answers_json TEXT NOT NULL DEFAULT '[]',
            analysis_json TEXT NOT NULL DEFAULT '{}',
            prompt_version TEXT NOT NULL DEFAULT 'v1.0',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS skill_progress (
            student_id TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            proficiency REAL NOT NULL DEFAULT 0.0,
            exercises_done INTEGER NOT NULL DEFAULT 0,
            last_accuracy REAL NOT NULL DEFAULT 0.0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (student_id, skill_name),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS mistake_bank (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            question TEXT NOT NULL,
            student_answer TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            test_point TEXT NOT NULL,
            mistake_type TEXT NOT NULL,
            reused_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );
    """)
    conn.commit()
    return conn


# ============================================================
# 学生 CRUD
# ============================================================

def create_student(conn: sqlite3.Connection, profile: StudentProfile):
    """创建或替换学生档案"""
    conn.execute(
        """INSERT OR REPLACE INTO students
           (id, name, grade, textbook, student_type, is_tutoring,
            sessions_per_week, start_date, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            profile.id, profile.name, profile.grade, profile.textbook,
            profile.student_type, int(profile.is_tutoring),
            profile.sessions_per_week, profile.start_date, profile.notes,
        ),
    )
    conn.commit()


def get_student(conn: sqlite3.Connection, student_id: str) -> Optional[StudentProfile]:
    """按 ID 加载学生档案"""
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if row is None:
        return None
    return StudentProfile(
        id=row["id"], name=row["name"], grade=row["grade"],
        textbook=row["textbook"], student_type=row["student_type"],
        is_tutoring=bool(row["is_tutoring"]),
        sessions_per_week=row["sessions_per_week"],
        start_date=row["start_date"], notes=row["notes"] or "",
    )


def list_students(conn: sqlite3.Connection) -> list[StudentProfile]:
    """返回所有学生"""
    rows = conn.execute("SELECT * FROM students ORDER BY created_at").fetchall()
    return [
        StudentProfile(
            id=r["id"], name=r["name"], grade=r["grade"],
            textbook=r["textbook"], student_type=r["student_type"],
            is_tutoring=bool(r["is_tutoring"]),
            sessions_per_week=r["sessions_per_week"],
            start_date=r["start_date"], notes=r["notes"] or "",
        )
        for r in rows
    ]


# ============================================================
# 练习记录
# ============================================================

def save_exercise(
    conn: sqlite3.Connection, *, student_id: str, day: int,
    weak_point: str, accuracy: float,
    questions_json: str, answers_json: str, analysis_json: str,
    prompt_version: str = "v1.0",
):
    """保存一次练习记录"""
    conn.execute(
        """INSERT INTO exercises
           (student_id, day, weak_point, accuracy,
            questions_json, answers_json, analysis_json, prompt_version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (student_id, day, weak_point, accuracy,
         questions_json, answers_json, analysis_json, prompt_version),
    )
    conn.commit()


def get_exercise_history(conn: sqlite3.Connection, student_id: str) -> list[dict]:
    """获取学生所有练习记录（按 day 排序）"""
    rows = conn.execute(
        "SELECT * FROM exercises WHERE student_id = ? ORDER BY day",
        (student_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# 薄弱点熟练度
# ============================================================

def update_skill_progress(
    conn: sqlite3.Connection, student_id: str,
    skill_name: str, proficiency: float,
    exercises_done: int, last_accuracy: float,
):
    """更新某个薄弱点的熟练度"""
    conn.execute(
        """INSERT OR REPLACE INTO skill_progress
           (student_id, skill_name, proficiency, exercises_done, last_accuracy, updated_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))""",
        (student_id, skill_name, proficiency, exercises_done, last_accuracy),
    )
    conn.commit()


def get_skill_progress(conn: sqlite3.Connection, student_id: str) -> dict[str, dict]:
    """获取学生所有薄弱点熟练度"""
    rows = conn.execute(
        "SELECT * FROM skill_progress WHERE student_id = ?",
        (student_id,),
    ).fetchall()
    return {
        r["skill_name"]: {
            "proficiency": r["proficiency"],
            "exercises_done": r["exercises_done"],
            "last_accuracy": r["last_accuracy"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    }


# ============================================================
# 数据库初始化（首次运行）
# ============================================================

def ensure_db():
    """确保数据库文件存在并已初始化"""
    if not DEFAULT_DB_PATH.exists():
        return init_db()
    return sqlite3.connect(str(DEFAULT_DB_PATH))
