"""Agents base 模块测试 — TDD RED 阶段

测试目标:
1. 模板替换不会出现子串冲突 (weak_point vs weak_point_detail)
2. 模板替换后 JSON 花括号 {{}} 不受影响
3. 未提供的变量保留占位符
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# T0.1: 模板替换 bug 测试
# ============================================================

def test_template_no_substring_collision():
    """weak_point 和 weak_point_detail 不会互相污染"""
    from agents.base import _render_template

    template = "练习重点: {weak_point}。具体表现: {weak_point_detail}"
    variables = {"weak_point": "一般现在时三单", "weak_point_detail": "动词忘加-s"}

    result = _render_template(template, variables)
    assert result == "练习重点: 一般现在时三单。具体表现: 动词忘加-s"


def test_template_json_braces_preserved():
    """JSON 示例中的 {{}} 花括号不受影响"""
    from agents.base import _render_template

    template = '输出格式: {{"name": "{student_name}", "score": {score}}}'
    variables = {"student_name": "张三", "score": "85"}

    result = _render_template(template, variables)
    # JSON 花括号 {{ }} 应该保持原样，只有单花括号被替换
    assert '{"name": "张三"' in result
    assert '"score": 85}' in result


def test_template_missing_var_keeps_placeholder():
    """未提供的变量保留原占位符，不崩溃"""
    from agents.base import _render_template

    template = "年级: {grade}, 教材: {textbook}, 备注: {notes}"
    result = _render_template(template, {"grade": "8"})

    assert "年级: 8" in result
    assert "{textbook}" in result
    assert "{notes}" in result
