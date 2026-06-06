"""
Orchestrator — 串联 4 个 Agent 的主控脚本

用法:
    python orchestrator.py --student 张三 --step diagnose
    python orchestrator.py --student 张三 --step analyze
    python orchestrator.py --student 张三 --step exercise
    python orchestrator.py --student 张三 --step report
    python orchestrator.py --student 张三 --step all      # 一键跑全程
"""
import argparse
import json
import yaml
from pathlib import Path
from datetime import datetime

from agents import run_diagnose, run_analyze, run_exercise, run_report
from schemas import (
    StudentProfile,
    DiagnoseInput,
    DiagnosticTest,
    AnalyzeInput,
    AnalysisResult,
    ExerciseInput,
    DailyExercise,
    ReportInput,
    ParentReport,
    StudentAnswer,
    PipelineRun,
)

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR = BASE_DIR / "data" / "students"

# ============================================================
# 学生档案读写
# ============================================================

def load_student(name: str) -> StudentProfile:
    """从 JSON 文件加载学生档案"""
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"学生 '{name}' 不存在。先在 data/students/ 创建 {name}.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return StudentProfile(**data)


def save_student(profile: StudentProfile):
    """保存学生档案"""
    path = DATA_DIR / f"{profile.name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile.model_dump(), f, ensure_ascii=False, indent=2)


def save_output(student_name: str, step: str, data):
    """保存 Agent 输出到 output/{学生}/{step}_{timestamp}.json"""
    student_dir = OUTPUT_DIR / student_name
    student_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = student_dir / f"{step}_{timestamp}.json"

    if hasattr(data, "model_dump"):
        content = data.model_dump()
    elif hasattr(data, "dict"):
        content = data.dict()
    else:
        content = data

    with open(path, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    return path


# ============================================================
# 各步骤执行
# ============================================================

def step_diagnose(profile: StudentProfile):
    """Step 1: 生成诊断测试"""
    print(f"\n[DiagnoseAgent] Generating diagnostic test for {profile.name}...")

    with open(BASE_DIR / "config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    grammar_focus = [
        "一般现在时第三人称单数",
        "现在完成时",
        "一般过去时与现在完成时辨析",
        "被动语态",
        "宾语从句",
    ]

    params = DiagnoseInput(
        grade=profile.grade,
        textbook=profile.textbook,
        student_type=profile.student_type,
        parent_note=profile.notes,
        grammar_focus=grammar_focus,
    )

    result: DiagnosticTest = run_diagnose(params)
    out_path = save_output(profile.name, "diagnose", result)

    print(f"   Test generated: {out_path}")
    print(f"   Total: {len(result.questions)} questions (Part A/B/C)")
    print(f"   Answer key: {len(result.answer_sheet)} entries")
    return result


def step_analyze(profile: StudentProfile):
    """Step 2: 错题归因分析"""
    print(f"\n[AnalyzeAgent] Analyzing answers for {profile.name}...")

    # 找最新的诊断测试
    diagnose_files = sorted((OUTPUT_DIR / profile.name).glob("diagnose_*.json"), reverse=True)
    if not diagnose_files:
        print("ERROR: No diagnostic test found. Please run --step diagnose first.")
        return None

    with open(diagnose_files[0], "r", encoding="utf-8") as f:
        diag_data = json.load(f)

    # 手动录入学生答案
    print("\nPlease enter student answers (q_id: student_answer, blank line to finish):")
    print("   Example: Q1: goes")
    student_answers = []
    while True:
        line = input("   > ").strip()
        if not line:
            break
        if ":" in line:
            qid, ans = line.split(":", 1)
            student_answers.append({"q_id": qid.strip(), "student_answer": ans.strip()})

    questions = [{"q_id": q["q_id"], "content": q["content"], "test_point": q["test_point"], "correct_answer": q["answer"]} for q in diag_data["questions"]]

    params = AnalyzeInput(
        grade=profile.grade,
        weak_point_focus="综合诊断",
        questions=questions,
        student_answers=student_answers,
    )

    result: AnalysisResult = run_analyze(params)
    out_path = save_output(profile.name, "analyze", result)

    print(f"\nAnalysis complete: {out_path}")
    print(f"   Error pattern: {result.error_pattern}")
    print(f"   Priority weak point: {result.weak_point}")
    print(f"   Starting accuracy: {result.start_accuracy:.0%}")
    print(f"   Next action: {result.next_action}")
    print(f"   Recommendation: {result.recommendation}")
    return result


def step_exercise(profile: StudentProfile):
    """Step 3: 生成每日练习"""
    print(f"\n[ExerciseAgent] Generating daily exercise for {profile.name}...")

    # 找最新的分析结果
    analyze_files = sorted((OUTPUT_DIR / profile.name).glob("analyze_*.json"), reverse=True)
    if not analyze_files:
        print("ERROR: No analysis results found. Please run --step analyze first.")
        return None

    with open(analyze_files[0], "r", encoding="utf-8") as f:
        analysis = json.load(f)

    # 找之前的练习记录
    exercise_files = sorted((OUTPUT_DIR / profile.name).glob("exercise_*.json"))
    day = len(exercise_files) + 1
    previous_exercises = []
    for ef in exercise_files[-5:]:  # 最近5次
        with open(ef, "r", encoding="utf-8") as f:
            ex_data = json.load(f)
            for q in ex_data.get("questions", []):
                previous_exercises.append(q.get("content", ""))

    params = ExerciseInput(
        grade=profile.grade,
        textbook=profile.textbook,
        weak_point=analysis.get("weak_point", "综合巩固"),
        weak_point_detail=analysis.get("error_pattern", ""),
        day=day,
        previous_exercises=previous_exercises,
        previous_accuracy=analysis.get("start_accuracy", 0.0),
    )

    result: DailyExercise = run_exercise(params)
    out_path = save_output(profile.name, f"exercise_day{day}", result)

    print(f"   Daily exercise saved: {out_path}")
    print(f"   Topic: {result.weak_point} | Questions: {len(result.questions)}")
    print(f"   Sections: basic={sum(1 for q in result.questions if q.section=='基础巩固')} + compare={sum(1 for q in result.questions if q.section=='辨析训练')} + challenge={sum(1 for q in result.questions if q.section=='综合挑战')}")
    print(f"   Tip: {result.daily_tip}")
    return result


def step_report(profile: StudentProfile):
    """Step 4: 生成家长周报"""
    print(f"\n[ReportAgent] Generating weekly report for {profile.name}...")

    # 找本周的练习记录
    exercise_files = list(sorted((OUTPUT_DIR / profile.name).glob("exercise_day*.json")))

    if not exercise_files:
        print("ERROR: No exercise records this week.")
        return None

    # 找最近的分析
    analyze_files = sorted((OUTPUT_DIR / profile.name).glob("analyze_*.json"), reverse=True)
    latest_analysis = ""
    if analyze_files:
        with open(analyze_files[0], "r", encoding="utf-8") as f:
            analysis = json.load(f)
        latest_analysis = analysis.get("error_pattern", "")
        weak_point = analysis.get("weak_point", "")
    else:
        weak_point = "综合练习"

    # 统计
    day1_acc = 0.0
    last_acc = 0.0
    for ef in exercise_files:
        with open(ef, "r", encoding="utf-8") as f:
            ex_data = json.load(f)
        # 读取关联的分析结果获取正确率
        ex_name = ef.stem

    week_start = exercise_files[0].stem.split("_")[-1][:8] if exercise_files else datetime.now().strftime("%Y%m%d")
    week_end = exercise_files[-1].stem.split("_")[-1][:8] if exercise_files else datetime.now().strftime("%Y%m%d")

    params = ReportInput(
        student_name=profile.name,
        week_start=week_start,
        week_end=week_end,
        total_assigned=len(exercise_files),
        total_completed=len(exercise_files),  # 简化：假设全部完成
        weak_point=weak_point,
        accuracy_day1=day1_acc,
        accuracy_last=last_acc,
        latest_analysis=latest_analysis,
    )

    result: ParentReport = run_report(params)
    out_path = save_output(profile.name, "report", result)

    print(f"\nWeekly report saved: {out_path}")
    print("\n" + "=" * 50)
    print("*** Copy and send to parent: ***\n")
    print(result.report_text)
    print(f"\nNext week plan: {result.next_plan}")
    print("=" * 50)
    return result


# ============================================================
# 示例学生档案
# ============================================================

def create_example_student():
    """创建示例学生档案（亲戚孩子）"""
    name = "亲戚孩子"
    path = DATA_DIR / f"{name}.json"
    if path.exists():
        print(f"Student profile '{name}' already exists.")
        return

    profile = StudentProfile(
        id="relative_001",
        name=name,
        grade=8,
        textbook="人教版",
        student_type="课内提高",
        is_tutoring=False,
        sessions_per_week=0,
        notes="亲戚的孩子，初二，想看看AI出题有没有用",
    )
    save_student(profile)
    print(f"Created example student: {name}")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="英语家教 AI Agent 系统")
    parser.add_argument("--student", type=str, required=True, help="学生姓名")
    parser.add_argument("--step", type=str, default="diagnose",
                       choices=["diagnose", "analyze", "exercise", "report", "all", "init"],
                       help="执行步骤 (默认: diagnose)")
    args = parser.parse_args()

    if args.step == "init":
        create_example_student()
        return

    profile = load_student(args.student)

    steps = [args.step] if args.step != "all" else ["diagnose", "analyze", "exercise", "report"]

    run_record = PipelineRun(
        student_id=profile.id,
        steps=steps,
        agent_versions={
            "diagnose": "v1.0",
            "analyze": "v1.0",
            "exercise": "v1.0",
            "report": "v1.0",
        },
    )

    for step_name in steps:
        if step_name == "diagnose":
            result = step_diagnose(profile)
        elif step_name == "analyze":
            result = step_analyze(profile)
        elif step_name == "exercise":
            result = step_exercise(profile)
        elif step_name == "report":
            result = step_report(profile)

        if result is None and step_name != "report":
            print(f"Step {step_name} failed. Pipeline stopped.")
            break

    run_record.status = "completed"
    run_record.completed_at = datetime.now().isoformat()
    save_output(profile.name, "pipeline_run", run_record)


if __name__ == "__main__":
    main()
