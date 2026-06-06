"""周报正确率测试 — 确认不再永远是 0%"""
import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas import StudentProfile


def test_compute_weekly_stats_accuracy_not_zero():
    """从 SQLite 数据计算周统计，正确率不再是 0%"""
    from data.db import init_db, create_student, save_exercise
    from data.db import compute_weekly_stats

    db = init_db(":memory:")
    create_student(db, StudentProfile(id="s1", name="测试", grade=8))

    # 模拟 3 次练习：正确率 0.4 → 0.6 → 0.8
    for day, acc in [(1, 0.4), (2, 0.6), (3, 0.8)]:
        save_exercise(
            db, student_id="s1", day=day, weak_point="三单",
            accuracy=acc, questions_json="[]", answers_json="[]",
            analysis_json="{}", prompt_version="v1.0",
        )

    stats = compute_weekly_stats(db, "s1")
    assert stats["day1_accuracy"] == 0.4
    assert stats["last_accuracy"] == 0.8
    assert stats["total_completed"] == 3
    assert stats["accuracy_trend"] == "提升"


def test_weekly_stats_empty_student():
    """没有练习记录的学生返回空统计"""
    from data.db import init_db, create_student, compute_weekly_stats

    db = init_db(":memory:")
    create_student(db, StudentProfile(id="s2", name="空记录", grade=8))

    stats = compute_weekly_stats(db, "s2")
    assert stats["day1_accuracy"] == 0.0
    assert stats["total_completed"] == 0


def test_weekly_stats_correct_trend():
    """正确率趋势判断正确"""
    from data.db import init_db, create_student, save_exercise
    from data.db import compute_weekly_stats

    db = init_db(":memory:")
    create_student(db, StudentProfile(id="s3", name="趋势", grade=8))

    # 下降趋势
    for day, acc in [(1, 0.9), (2, 0.7), (3, 0.5)]:
        save_exercise(
            db, student_id="s3", day=day, weak_point="三单",
            accuracy=acc, questions_json="[]", answers_json="[]",
            analysis_json="{}", prompt_version="v1.0",
        )

    stats = compute_weekly_stats(db, "s3")
    assert stats["accuracy_trend"] == "波动"
