"""
Agent 1: 诊断测试生成器 (DiagnoseAgent)
"""
from schemas import DiagnoseInput, DiagnosticTest
from .base import run_agent

AGENT_VERSION = "v1.0"


def run_diagnose(params: DiagnoseInput) -> DiagnosticTest:
    grade_names = {7: "初一", 8: "初二", 9: "初三"}
    return run_agent(
        prompt_yaml="diagnose.yaml",
        output_model=DiagnosticTest,
        user_vars={
            "grade": params.grade,
            "grade_name": grade_names.get(params.grade, str(params.grade)),
            "textbook": params.textbook,
            "student_type": params.student_type,
            "parent_note": params.parent_note or "未提供",
            "grammar_focus": "、".join(params.grammar_focus),
        },
    )
