"""SQLite 数据层测试 — TDD RED 阶段"""
import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas import StudentProfile


# ============================================================
# RED: 测试在 data/db.py 不存在时应该失败
# ============================================================

def test_create_and_load_student():
    """创建学生 → 加载学生 → 数据一致"""
    from data.db import init_db, create_student, get_student

    db = init_db(":memory:")
    create_student(db, StudentProfile(id="s1", name="张三", grade=8, textbook="人教版"))

    loaded = get_student(db, "s1")
    assert loaded.name == "张三"
    assert loaded.grade == 8
    assert loaded.textbook == "人教版"


def test_student_not_found():
    """查询不存在的学生返回 None"""
    from data.db import init_db, get_student

    db = init_db(":memory:")
    result = get_student(db, "no-such-id")
    assert result is None


def test_list_all_students():
    """列出所有学生"""
    from data.db import init_db, create_student, list_students

    db = init_db(":memory:")
    create_student(db, StudentProfile(id="s1", name="张三", grade=8))
    create_student(db, StudentProfile(id="s2", name="李四", grade=9))

    all_students = list_students(db)
    assert len(all_students) == 2
    names = [s.name for s in all_students]
    assert "张三" in names
    assert "李四" in names


def test_save_and_load_exercise():
    """保存练习记录 → 加载历史 → 数据一致"""
    from data.db import init_db, create_student, save_exercise, get_exercise_history

    db = init_db(":memory:")
    create_student(db, StudentProfile(id="s1", name="张三", grade=8))

    save_exercise(
        db, student_id="s1", day=1, weak_point="一般现在时三单",
        accuracy=0.65, questions_json='[{"q_id":"Q1"}]',
        answers_json='[{"q_id":"Q1","student_answer":"go"}]',
        analysis_json='{"error_pattern":"三单忘变"}',
        prompt_version="v1.0"
    )
    save_exercise(
        db, student_id="s1", day=2, weak_point="一般现在时三单",
        accuracy=0.80, questions_json='[{"q_id":"Q2"}]',
        answers_json='[{"q_id":"Q2","student_answer":"goes"}]',
        analysis_json='{"error_pattern":"进步明显"}',
        prompt_version="v1.0"
    )

    history = get_exercise_history(db, "s1")
    assert len(history) == 2
    assert history[0]["day"] == 1
    assert history[0]["accuracy"] == 0.65
    assert history[1]["day"] == 2
    assert history[1]["accuracy"] == 0.80


def test_skill_progress_tracking():
    """更新和查询薄弱点熟练度"""
    from data.db import init_db, create_student, update_skill_progress, get_skill_progress

    db = init_db(":memory:")
    create_student(db, StudentProfile(id="s1", name="张三", grade=8))

    update_skill_progress(db, "s1", "一般现在时三单", 0.4, 5, 0.65)
    update_skill_progress(db, "s1", "现在完成时", 0.7, 3, 0.90)

    progress = get_skill_progress(db, "s1")
    assert "一般现在时三单" in progress
    assert progress["一般现在时三单"]["proficiency"] == 0.4
    assert progress["现在完成时"]["proficiency"] == 0.7
