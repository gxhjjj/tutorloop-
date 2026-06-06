# Test fixtures
import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas import StudentProfile


@pytest.fixture
def test_db():
    """内存 SQLite 数据库，测试完自动销毁"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def sample_student():
    """示例学生档案"""
    return StudentProfile(
        id="stu_001",
        name="测试学生",
        grade=8,
        textbook="人教版",
        student_type="课内提高",
    )
