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

        CREATE TABLE IF NOT EXISTS exercise_runs (
            exercise_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            day INTEGER NOT NULL,
            target TEXT NOT NULL,
            draft_questions_json TEXT NOT NULL DEFAULT '[]',
            approved_questions_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'draft',
            modified_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            sent_at TEXT,
            prompt_version TEXT NOT NULL DEFAULT 'v1.0',
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS exercise_results (
            exercise_id TEXT PRIMARY KEY,
            completed INTEGER NOT NULL DEFAULT 0,
            accuracy REAL,
            difficulty_notes TEXT DEFAULT '',
            parent_feedback TEXT DEFAULT '',
            next_action TEXT DEFAULT '',
            recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (exercise_id) REFERENCES exercise_runs(exercise_id)
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

def compute_weekly_stats(conn: sqlite3.Connection, student_id: str) -> dict:
    """计算一个学生本周的练习统计"""
    rows = conn.execute(
        """SELECT day, accuracy, weak_point FROM exercises
           WHERE student_id = ? ORDER BY day""",
        (student_id,),
    ).fetchall()

    if not rows:
        return {
            "day1_accuracy": 0.0,
            "last_accuracy": 0.0,
            "total_completed": 0,
            "total_assigned": 0,
            "accuracy_trend": "无数据",
            "weak_point": "",
        }

    accuracies = [r["accuracy"] for r in rows]
    day1_acc = accuracies[0]
    last_acc = accuracies[-1]

    if day1_acc < last_acc - 0.05:
        trend = "提升"
    elif last_acc < day1_acc - 0.05:
        trend = "波动"
    else:
        trend = "稳定"

    return {
        "day1_accuracy": day1_acc,
        "last_accuracy": last_acc,
        "total_completed": len(rows),
        "total_assigned": len(rows),
        "accuracy_trend": trend,
        "weak_point": rows[-1]["weak_point"] if rows else "",
    }


def ensure_db():
    """确保数据库文件存在并已初始化"""
    if not DEFAULT_DB_PATH.exists():
        return init_db()
    return sqlite3.connect(str(DEFAULT_DB_PATH))


# ============================================================
# 练习生命周期管理
# ============================================================

def save_exercise_run(conn: sqlite3.Connection, run) -> None:
    """保存一次练习运行记录（插入或替换）"""
    import json as _json
    conn.execute(
        """INSERT OR REPLACE INTO exercise_runs
           (exercise_id, student_id, day, target,
            draft_questions_json, approved_questions_json,
            status, modified_count, created_at, sent_at, prompt_version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run.exercise_id, run.student_id, run.day, run.target,
            _json.dumps(run.draft_questions, ensure_ascii=False),
            _json.dumps(run.approved_questions, ensure_ascii=False),
            run.status, run.modified_count,
            run.created_at, run.sent_at, run.prompt_version,
        ),
    )
    conn.commit()


def get_exercise_run(conn: sqlite3.Connection, exercise_id: str) -> dict | None:
    """按 ID 获取练习运行记录"""
    row = conn.execute(
        "SELECT * FROM exercise_runs WHERE exercise_id = ?", (exercise_id,)
    ).fetchone()
    if row is None:
        return None
    import json as _json
    data = dict(row)
    data["draft_questions"] = _json.loads(data.pop("draft_questions_json", "[]"))
    data["approved_questions"] = _json.loads(data.pop("approved_questions_json", "[]"))
    return data


def list_exercise_runs(conn: sqlite3.Connection, student_id: str) -> list[dict]:
    """按学生获取所有练习运行记录（按 day 排序）"""
    import json as _json
    rows = conn.execute(
        "SELECT * FROM exercise_runs WHERE student_id = ? ORDER BY day",
        (student_id,),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["draft_questions"] = _json.loads(d.pop("draft_questions_json", "[]"))
        d["approved_questions"] = _json.loads(d.pop("approved_questions_json", "[]"))
        result.append(d)
    return result


def get_latest_run(conn: sqlite3.Connection, student_id: str) -> dict | None:
    """获取学生最近一次练习运行"""
    row = conn.execute(
        "SELECT * FROM exercise_runs WHERE student_id = ? ORDER BY created_at DESC LIMIT 1",
        (student_id,),
    ).fetchone()
    if row is None:
        return None
    import json as _json
    data = dict(row)
    data["draft_questions"] = _json.loads(data.pop("draft_questions_json", "[]"))
    data["approved_questions"] = _json.loads(data.pop("approved_questions_json", "[]"))
    return data


def update_run_status(
    conn: sqlite3.Connection, exercise_id: str, status: str, sent_at: str = None,
) -> None:
    """更新练习运行状态（draft/approved/sent/completed）"""
    if sent_at:
        conn.execute(
            "UPDATE exercise_runs SET status = ?, sent_at = ? WHERE exercise_id = ?",
            (status, sent_at, exercise_id),
        )
    else:
        conn.execute(
            "UPDATE exercise_runs SET status = ? WHERE exercise_id = ?",
            (status, exercise_id),
        )
    conn.commit()


def save_approved_questions(
    conn: sqlite3.Connection, exercise_id: str,
    approved_questions: list[dict], modified_count: int,
) -> None:
    """保存老师审核确认后的题目并记录修改数"""
    import json as _json
    conn.execute(
        "UPDATE exercise_runs SET approved_questions_json = ?, modified_count = ?, status = ? WHERE exercise_id = ?",
        (_json.dumps(approved_questions, ensure_ascii=False), modified_count, "approved", exercise_id),
    )
    conn.commit()


# ============================================================
# 练习结果记录
# ============================================================

def save_exercise_result(conn: sqlite3.Connection, result) -> None:
    """保存学生完成练习后的结果"""
    conn.execute(
        """INSERT OR REPLACE INTO exercise_results
           (exercise_id, completed, accuracy, difficulty_notes,
            parent_feedback, next_action, recorded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            result.exercise_id,
            int(result.completed),
            result.accuracy,
            result.difficulty_notes,
            result.parent_feedback,
            result.next_action,
            result.recorded_at,
        ),
    )
    conn.commit()


def get_exercise_result(conn: sqlite3.Connection, exercise_id: str) -> dict | None:
    """获取一次练习的结果记录"""
    row = conn.execute(
        "SELECT * FROM exercise_results WHERE exercise_id = ?", (exercise_id,)
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["completed"] = bool(data["completed"])
    return data


def list_recent_results(conn: sqlite3.Connection, student_id: str, limit: int = 5) -> list[dict]:
    """获取学生最近 N 次练习结果（按记录时间倒序）"""
    rows = conn.execute(
        """SELECT r.* FROM exercise_results r
           JOIN exercise_runs e ON r.exercise_id = e.exercise_id
           WHERE e.student_id = ?
           ORDER BY r.recorded_at DESC LIMIT ?""",
        (student_id, limit),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["completed"] = bool(d["completed"])
        result.append(d)
    return result
