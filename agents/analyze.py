"""
Agent 2: 错题归因分析器 (AnalyzeAgent)
"""
from schemas import AnalyzeInput, AnalysisResult
from .base import run_agent

AGENT_VERSION = "v1.0"


def run_analyze(params: AnalyzeInput) -> AnalysisResult:
    answer_lines = []
    for q in params.questions:
        qid = q["q_id"]
        sa = next((a["student_answer"] for a in params.student_answers if a["q_id"] == qid), "未作答")
        correct = q.get("correct_answer", q.get("answer", ""))
        marker = "❌" if sa != correct else "✅"
        answer_lines.append(
            f"{marker} {qid}: {q.get('content', qid)}\n"
            f"   学生答案: {sa} | 正确答案: {correct} | 考点: {q.get('test_point', '—')}"
        )
    answer_data = "\n".join(answer_lines)

    previous_context = ""
    if params.previous_summary:
        previous_context = f"## 之前的归因记录\n{params.previous_summary}"

    return run_agent(
        prompt_yaml="analyze.yaml",
        output_model=AnalysisResult,
        user_vars={
            "grade": params.grade,
            "weak_point_focus": params.weak_point_focus,
            "answer_data": answer_data,
            "previous_context": previous_context,
            "previous_summary": params.previous_summary,
        },
    )
