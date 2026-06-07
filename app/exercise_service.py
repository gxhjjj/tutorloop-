"""
轻量应用函数层：CLI 和 Streamlit 共享的入口。

职责：
- 调用 Agent 生成练习草稿
- 校验老师编辑后的题目
- 导出 Markdown / HTML（学生版和教师版）

不负责：UI 渲染、文件读写、数据库操作（由调用方处理）。
"""
from datetime import datetime
from agents import run_exercise
from schemas import (
    ExerciseInput,
    DailyExercise,
    ExerciseRun,
    ExerciseStatus,
    ExerciseQuestion,
)


def generate_exercise_draft(
    student_id: str,
    student_name: str,
    grade: int,
    textbook: str,
    weak_point: str,
    weak_point_detail: str,
    day: int,
    previous_exercises: list[str] | None = None,
    previous_accuracy: float = 0.0,
) -> ExerciseRun:
    """
    调用 ExerciseAgent 生成一份练习草稿。

    返回 ExerciseRun（status=draft），调用方负责持久化。
    """
    prev_list = previous_exercises or []

    params = ExerciseInput(
        grade=grade,
        textbook=textbook,
        weak_point=weak_point,
        weak_point_detail=weak_point_detail,
        day=day,
        previous_exercises=prev_list,
        previous_accuracy=previous_accuracy,
    )

    result: DailyExercise = run_exercise(params)

    exercise_id = f"{student_id}_day{day}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return ExerciseRun(
        exercise_id=exercise_id,
        student_id=student_id,
        day=day,
        target=weak_point,
        draft_questions=[q.model_dump() for q in result.questions],
        approved_questions=[],
        status=ExerciseStatus.DRAFT,
        modified_count=0,
        created_at=datetime.now().isoformat(),
        prompt_version="v1.0",
    )


def validate_edited_questions(questions: list[dict]) -> DailyExercise | None:
    """
    校验老师编辑后的题目是否符合 DailyExercise 的 Schema。

    返回 validated DailyExercise 或 None（校验失败时）。
    校验失败的错误信息通过 Pydantic ValidationError 抛出，
    调用方负责捕获并展示给老师。
    """
    try:
        validated_questions = [ExerciseQuestion(**q) for q in questions]
        return DailyExercise(
            title="",
            weak_point="",
            day=0,
            daily_tip="",
            questions=validated_questions,
        )
    except Exception:
        return None


def compute_modifications(draft: list[dict], approved: list[dict]) -> int:
    """
    计算老师修改或删除的题目数量。

    以 draft 为基准：draft 中存在但 approved 中不存在的题目 = 删除数，
    draft 中与 approved 中同 q_id 但内容不同 = 修改数。
    """
    draft_by_id = {q.get("q_id", ""): q for q in draft}
    approved_by_id = {q.get("q_id", ""): q for q in approved}

    mod_count = 0
    for q_id, draft_q in draft_by_id.items():
        if q_id not in approved_by_id:
            mod_count += 1  # 删除了
        elif draft_q != approved_by_id[q_id]:
            mod_count += 1  # 修改了

    return mod_count


def export_markdown(exercise_run: ExerciseRun, mode: str = "student") -> str:
    """导出 Markdown 格式的练习。

    mode='student': 不含答案和解析
    mode='teacher': 含答案和解析
    """
    questions = exercise_run.approved_questions or exercise_run.draft_questions
    if not questions:
        return "*暂无题目*"

    lines = [
        f"# 每日练习 — Day {exercise_run.day}",
        "",
        f"**目标**：{exercise_run.target}",
        "",
        "---",
        "",
    ]

    for i, q in enumerate(questions, 1):
        q_id = q.get("q_id", f"Q{i}")
        section = q.get("section", "")
        content = q.get("content", "")
        options = q.get("options") or []

        lines.append(f"### {q_id} ({section})")
        lines.append("")
        lines.append(content)
        lines.append("")

        if options:
            for j, opt in enumerate(options):
                label = chr(65 + j)  # A, B, C, D
                lines.append(f"{label}. {opt}")
            lines.append("")

        if mode == "teacher":
            answer = q.get("answer", "")
            explanation = q.get("explanation", "")
            lines.append(f"> **答案**：{answer}")
            if explanation:
                lines.append(f"> **解析**：{explanation}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _render_student_html(questions: list[dict], day: int, target: str) -> str:
    parts = []
    for i, q in enumerate(questions, 1):
        q_id = q.get("q_id", f"Q{i}")
        section = q.get("section", "")
        content = q.get("content", "")
        options = q.get("options") or []

        parts.append(f'<div class="question"><h3>{q_id} <small>({section})</small></h3>')
        parts.append(f'<p class="content">{content}</p>')

        if options:
            parts.append('<ol class="options">')
            for opt in options:
                parts.append(f"<li>{opt}</li>")
            parts.append("</ol>")

        parts.append("</div>")

    body = "\n".join(parts)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>每日练习 — Day {day}</title>
<style>
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; max-width: 700px; margin: 20px auto; padding: 0 16px; line-height: 1.8; }}
h1 {{ font-size: 1.4em; }}
.target {{ color: #666; font-size: 0.95em; margin-bottom: 24px; }}
.question {{ background: #f9f9f9; padding: 16px; border-radius: 8px; margin-bottom: 16px; }}
.question h3 {{ margin-top: 0; font-size: 1em; }}
.question small {{ color: #999; font-weight: normal; }}
.options {{ margin: 8px 0 0; padding-left: 24px; }}
.options li {{ margin-bottom: 4px; }}
</style>
</head>
<body>
<h1>每日练习 — Day {day}</h1>
<p class="target">目标：{target}</p>
{body}
</body>
</html>"""


def _render_teacher_html(questions: list[dict], day: int, target: str) -> str:
    parts = []
    for i, q in enumerate(questions, 1):
        q_id = q.get("q_id", f"Q{i}")
        section = q.get("section", "")
        content = q.get("content", "")
        options = q.get("options") or []
        answer = q.get("answer", "")
        explanation = q.get("explanation", "")

        parts.append(f'<div class="question"><h3>{q_id} <small>({section})</small></h3>')
        parts.append(f'<p class="content">{content}</p>')

        if options:
            parts.append('<ol class="options">')
            for opt in options:
                parts.append(f"<li>{opt}</li>")
            parts.append("</ol>")

        parts.append(f'<p class="answer">答案：<strong>{answer}</strong></p>')
        if explanation:
            parts.append(f'<p class="explain">解析：{explanation}</p>')

        parts.append("</div>")

    body = "\n".join(parts)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>每日练习 — Day {day}（教师版）</title>
<style>
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; max-width: 700px; margin: 20px auto; padding: 0 16px; line-height: 1.8; }}
h1 {{ font-size: 1.4em; }}
.target {{ color: #666; font-size: 0.95em; margin-bottom: 24px; }}
.question {{ background: #f9f9f9; padding: 16px; border-radius: 8px; margin-bottom: 16px; }}
.question h3 {{ margin-top: 0; font-size: 1em; }}
.question small {{ color: #999; font-weight: normal; }}
.options {{ margin: 8px 0 0; padding-left: 24px; }}
.options li {{ margin-bottom: 4px; }}
.answer {{ color: #2a7d2a; margin: 8px 0 4px; }}
.explain {{ color: #555; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>每日练习 — Day {day}（教师版）</h1>
<p class="target">目标：{target}</p>
{body}
</body>
</html>"""


def export_html(exercise_run: ExerciseRun, mode: str = "student") -> str:
    """导出可打印/可微信发送的 HTML。

    mode='student': 不含答案和解析（发给学生）
    mode='teacher': 含答案和解析（老师自留）
    """
    questions = exercise_run.approved_questions or exercise_run.draft_questions
    if not questions:
        return "<p>暂无题目</p>"

    if mode == "student":
        return _render_student_html(questions, exercise_run.day, exercise_run.target)
    return _render_teacher_html(questions, exercise_run.day, exercise_run.target)
