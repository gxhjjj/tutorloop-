"""
Agent 3: 每日练习生成器 (ExerciseAgent)
"""
from schemas import ExerciseInput, DailyExercise
from .base import run_agent

AGENT_VERSION = "v1.0"


def run_exercise(params: ExerciseInput) -> DailyExercise:
    grade_names = {7: "初一", 8: "初二", 9: "初三"}

    prev_ex_text = (
        "\n".join(f"- {ex}" for ex in params.previous_exercises)
        if params.previous_exercises
        else "（无，这是第一次练习）"
    )
    acc_pct = f"{params.previous_accuracy:.0%}" if params.previous_accuracy > 0 else "首次练习，无历史数据"

    return run_agent(
        prompt_yaml="exercise.yaml",
        output_model=DailyExercise,
        user_vars={
            "grade": params.grade,
            "grade_name": grade_names.get(params.grade, str(params.grade)),
            "textbook": params.textbook,
            "weak_point": params.weak_point,
            "weak_point_detail": params.weak_point_detail,
            "day": params.day,
            "previous_accuracy_pct": acc_pct,
            "previous_exercises": prev_ex_text,
        },
    )
