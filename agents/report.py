"""
Agent 4: 家长周报生成器 (ReportAgent)
"""
from schemas import ReportInput, ParentReport
from .base import run_agent

AGENT_VERSION = "v1.0"


def run_report(params: ReportInput) -> ParentReport:
    return run_agent(
        prompt_yaml="report.yaml",
        output_model=ParentReport,
        user_vars={
            "student_name": params.student_name,
            "week_start": params.week_start,
            "week_end": params.week_end,
            "total_assigned": params.total_assigned,
            "total_completed": params.total_completed,
            "weak_point": params.weak_point,
            "accuracy_day1_pct": f"{params.accuracy_day1:.0%}",
            "accuracy_last_pct": f"{params.accuracy_last:.0%}",
            "teacher_note": params.teacher_note or "无",
            "latest_analysis": params.latest_analysis,
        },
    )
