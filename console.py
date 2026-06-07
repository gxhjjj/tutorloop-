"""
Streamlit 单页验证操作台 — 老师内部工具

四区域、四状态、P0/P1/P2 开发顺序。

运行: streamlit run console.py
目标: 10 分钟内完成 选择学生 → 生成 → 审核 → 导出 闭环。
"""
import json
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from schemas import ExerciseRun, ExerciseResult, ExerciseStatus
from app.exercise_service import (
    generate_exercise_draft,
    validate_edited_questions,
    compute_modifications,
    export_markdown,
    export_html,
)

DATA_DIR = Path(__file__).parent / "data" / "students"
OUTPUT_DIR = Path(__file__).parent / "output"

st.set_page_config(page_title="TutorLoop — 练习操作台", layout="wide")


def load_students() -> list[dict]:
    """从 JSON 和 SQLite 加载学生列表"""
    students = []
    if DATA_DIR.exists():
        for f in sorted(DATA_DIR.glob("*.json")):
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            students.append(data)
    return students


def load_latest_analysis(student_name: str) -> dict:
    """加载该学生最新的归因分析"""
    analysis_dir = OUTPUT_DIR / student_name
    if not analysis_dir.exists():
        return {}
    files = sorted(analysis_dir.glob("analyze_*.json"), reverse=True)
    if not files:
        return {}
    with open(files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def count_exercise_days(student_name: str) -> int:
    """统计已有练习天数"""
    student_dir = OUTPUT_DIR / student_name
    if not student_dir.exists():
        return 0
    return len(list(student_dir.glob("exercise_day*.json")))


def load_recent_exercises(student_name: str, count: int = 5) -> list[str]:
    """加载最近 N 次练习的题目内容（防重复）"""
    student_dir = OUTPUT_DIR / student_name
    if not student_dir.exists():
        return []
    files = sorted(student_dir.glob("exercise_day*.json"))[-count:]
    results = []
    for ef in files:
        with open(ef, "r", encoding="utf-8") as f:
            data = json.load(f)
            for q in data.get("questions", []):
                results.append(q.get("content", ""))
    return results


def save_exercise_json(run: ExerciseRun):
    """保存 ExerciseRun 到 JSON 和 SQLite"""
    student_dir = OUTPUT_DIR / run.student_id
    student_dir.mkdir(parents=True, exist_ok=True)
    path = student_dir / f"{run.exercise_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(run.model_dump(), f, ensure_ascii=False, indent=2)

    try:
        from data.db import ensure_db, save_exercise_run
        db = ensure_db()
        save_exercise_run(db, run)
    except Exception:
        pass


def save_result_json(result: ExerciseResult):
    """保存 ExerciseResult 到 JSON 和 SQLite"""
    if not OUTPUT_DIR.exists():
        return
    path = OUTPUT_DIR / result.exercise_id / "result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)

    try:
        from data.db import ensure_db, save_exercise_result
        db = ensure_db()
        save_exercise_result(db, result)
    except Exception:
        pass


# ============================================================
# Session State 初始化
# ============================================================
if "exercise_run" not in st.session_state:
    st.session_state.exercise_run = None
if "result_saved" not in st.session_state:
    st.session_state.result_saved = False


# ============================================================
# 页面标题
# ============================================================
st.title("TutorLoop — 练习操作台")
st.caption("单页闭环：选择学生 → 生成草稿 → 逐题审核 → 导出下发 → 记录结果")

# ============================================================
# 区域一：选择学生与本次目标
# ============================================================
st.header("1. 选择学生与练习目标")

students = load_students()
if not students:
    st.warning("暂未找到学生档案。请先在 CLI 运行 `python orchestrator.py --step init` 创建示例学生。")
    st.stop()

student_options = {s.get("name", s.get("id", "")): s for s in students}
selected_name = st.selectbox("选择学生", list(student_options.keys()))
student = student_options[selected_name]

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("年级", student.get("grade", "?"))
with col2:
    st.metric("教材", student.get("textbook", "?"))
with col3:
    st.metric("类型", student.get("student_type", "?"))

analysis = load_latest_analysis(selected_name)
current_weak_point = analysis.get("weak_point", "")
error_pattern = analysis.get("error_pattern", "")
day = count_exercise_days(selected_name) + 1

st.info(
    f"**最新归因**：{error_pattern or '暂无分析记录，请先在 CLI 运行 diagnose → analyze'}\n\n"
    f"**当前薄弱点**：{current_weak_point or '待诊断'}"
)

target = st.text_input(
    "本次练习目标（薄弱点）",
    value=current_weak_point or "",
    placeholder="例如：一般现在时第三人称单数",
)

col_gen1, col_gen2 = st.columns([1, 3])
with col_gen1:
    generate_clicked = st.button("生成练习草稿", type="primary", use_container_width=True)

if generate_clicked:
    if not target.strip():
        st.error("请输入练习目标（薄弱点）")
    else:
        with st.spinner("正在生成练习草稿（调用 AI Agent）..."):
            try:
                recent = load_recent_exercises(selected_name)
                exercise_run = generate_exercise_draft(
                    student_id=student.get("id", selected_name),
                    student_name=selected_name,
                    grade=student.get("grade", 8),
                    textbook=student.get("textbook", "人教版"),
                    weak_point=target.strip(),
                    weak_point_detail=error_pattern or target.strip(),
                    day=day,
                    previous_exercises=recent,
                    previous_accuracy=analysis.get("start_accuracy", 0.0),
                )
                st.session_state.exercise_run = exercise_run
                st.session_state.result_saved = False
                save_exercise_json(exercise_run)
                st.success(f"草稿已生成（Day {day}，{len(exercise_run.draft_questions)} 题）")
                st.rerun()
            except Exception as e:
                st.error(f"生成失败：{e}")
                st.info("请检查 DeepSeek API Key 配置（.env 文件）和网络连接后重试。")

# ============================================================
# 区域二：审核和修改练习
# ============================================================
st.header("2. 审核与修改练习")

run: ExerciseRun | None = st.session_state.exercise_run

if run is None:
    st.info("请先在区域一生成练习草稿。")
else:
    status = run.status
    status_labels = {"draft": "草稿", "approved": "已审核", "sent": "已下发", "completed": "已完成"}
    st.caption(f"当前状态：**{status_labels.get(status, status)}** | 练习 ID：`{run.exercise_id}`")

    if status == ExerciseStatus.DRAFT:
        questions = run.draft_questions
        approved_list = []

        col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
        with col_stats1:
            st.metric("总题数", len(questions))
        with col_stats2:
            checked = len(approved_list)
            st.metric("已检查", checked)
        with col_stats3:
            st.metric("待检查", len(questions) - checked)
        with col_stats4:
            st.metric("修改/删除", run.modified_count)

        st.divider()
        st.subheader("逐题审核")
        st.caption("编辑完成后点击题号旁的 ✓ 表示确认，所有题确认后点击底部「审核通过」。")

        approved_questions = []

        for i, q in enumerate(questions):
            q_id = q.get("q_id", f"Q{i+1}")
            section = q.get("section", "基础巩固")

            with st.expander(f"{q_id} ({section})", expanded=i < 4):
                c1, c2 = st.columns([3, 1])
                with c1:
                    content = st.text_area("题目", value=q.get("content", ""), key=f"content_{i}", height=68)
                with c2:
                    if q.get("options"):
                        opts_text = "\n".join(q.get("options", []))
                        new_opts = st.text_area("选项（每行一个）", value=opts_text, key=f"opts_{i}", height=68)
                        options_list = [o.strip() for o in new_opts.split("\n") if o.strip()]
                    else:
                        options_list = None

                c3, c4, c5 = st.columns(3)
                with c3:
                    answer = st.text_input("答案", value=q.get("answer", ""), key=f"ans_{i}")
                with c4:
                    explanation = st.text_input("解析", value=q.get("explanation", ""), key=f"exp_{i}")
                with c5:
                    section_edit = st.selectbox(
                        "层级",
                        ["基础巩固", "辨析训练", "综合挑战"],
                        index=0 if section == "基础巩固" else (1 if section == "辨析训练" else 2),
                        key=f"sec_{i}",
                    )

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    delete_key = f"del_{i}"
                    if delete_key not in st.session_state:
                        st.session_state[delete_key] = False

                    if st.button(f"删除 {q_id}", key=f"btn_del_{i}"):
                        st.session_state[delete_key] = True

                with col_btn2:
                    keep_key = f"keep_{i}"
                    if keep_key not in st.session_state:
                        st.session_state[keep_key] = True

                    keep = st.checkbox(f"确认 {q_id} 无误", value=st.session_state[keep_key], key=f"chk_{i}")

                if not st.session_state.get(delete_key, False):
                    approved_q = {
                        "q_id": q_id,
                        "section": section_edit,
                        "content": content,
                        "options": options_list,
                        "answer": answer,
                        "explanation": explanation,
                    }
                    approved_questions.append(approved_q)

        st.divider()

        st.caption(
            f"已确认 {len(approved_questions)}/{len(questions)} 题"
        )

        if st.button("审核通过", type="primary", disabled=len(approved_questions) == 0):
            try:
                validated = validate_edited_questions(approved_questions)
                if validated is None:
                    st.error("部分题目格式校验未通过，请检查是否有必填字段缺失。")
                else:
                    mods = compute_modifications(run.draft_questions, approved_questions)
                    st.session_state.exercise_run.approved_questions = approved_questions
                    st.session_state.exercise_run.status = ExerciseStatus.APPROVED
                    st.session_state.exercise_run.modified_count = mods
                    save_exercise_json(st.session_state.exercise_run)
                    st.success(f"审核通过！共 {len(approved_questions)} 题，修改/删除 {mods} 题。")
                    st.rerun()
            except Exception as e:
                st.error(f"校验异常：{e}")

    elif status == ExerciseStatus.APPROVED:
        st.success(f"已审核通过 | 共 {len(run.approved_questions)} 题")
        st.info("请进入区域三导出和下发。")

    elif status == ExerciseStatus.SENT:
        st.info("已下发，等待学生完成。请进入区域四记录结果。")

    elif status == ExerciseStatus.COMPLETED:
        st.success("本次练习已完成闭环。")
        if st.session_state.result_saved:
            st.balloons()

# ============================================================
# 区域三：导出和标记下发
# ============================================================
st.header("3. 导出与下发")

if run is None:
    st.info("请先生成并审核练习草稿。")
elif run.status == ExerciseStatus.DRAFT:
    st.warning("请先在区域二完成审核通过。")
elif run.status in (ExerciseStatus.APPROVED, ExerciseStatus.SENT, ExerciseStatus.COMPLETED):
    questions = run.approved_questions or run.draft_questions

    tab_student, tab_teacher = st.tabs(["学生版（不含答案）", "教师版（含答案）"])

    with tab_student:
        md_student = export_markdown(run, "student")
        st.markdown(md_student)

        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            st.download_button(
                "下载 Markdown（学生版）",
                md_student,
                file_name=f"exercise_day{run.day}_student.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_exp2:
            html_student = export_html(run, "student")
            st.download_button(
                "下载 HTML（学生版，可打印）",
                html_student,
                file_name=f"exercise_day{run.day}_student.html",
                mime="text/html",
                use_container_width=True,
            )

    with tab_teacher:
        md_teacher = export_markdown(run, "teacher")
        st.markdown(md_teacher)

        col_exp3, col_exp4 = st.columns(2)
        with col_exp3:
            st.download_button(
                "下载 Markdown（教师版）",
                md_teacher,
                file_name=f"exercise_day{run.day}_teacher.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_exp4:
            html_teacher = export_html(run, "teacher")
            st.download_button(
                "下载 HTML（教师版）",
                html_teacher,
                file_name=f"exercise_day{run.day}_teacher.html",
                mime="text/html",
                use_container_width=True,
            )

    st.divider()

    if run.status == ExerciseStatus.APPROVED:
        st.caption("完成导出后点击下方按钮标记已下发。")
        if st.button("已通过微信或线下方式下发", type="primary"):
            st.session_state.exercise_run.status = ExerciseStatus.SENT
            st.session_state.exercise_run.sent_at = datetime.now().isoformat()
            save_exercise_json(st.session_state.exercise_run)
            st.success("已标记为已下发。")
            st.rerun()
    elif run.status == ExerciseStatus.SENT:
        st.info(f"已于 {run.sent_at} 下发。请进入区域四记录结果。")
    elif run.status == ExerciseStatus.COMPLETED:
        st.success("已完成闭环。")

# ============================================================
# 区域四：记录真实结果
# ============================================================
st.header("4. 记录完成结果")

if run is None:
    st.info("请先完成练习的下发。")
elif run.status == ExerciseStatus.DRAFT:
    st.warning("请先完成审核。")
elif run.status == ExerciseStatus.APPROVED:
    st.warning("请先在区域三标记已下发。")
elif run.status in (ExerciseStatus.SENT, ExerciseStatus.COMPLETED):
    if run.status == ExerciseStatus.COMPLETED and st.session_state.result_saved:
        st.success("结果已记录，本次实验完成！")

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        completed = st.checkbox("学生已完成练习", value=True, key="result_completed")
        accuracy = st.slider("正确率", 0.0, 1.0, 0.5, 0.05, key="result_accuracy",
                             help="0.0 = 全错，1.0 = 全对")
    with col_r2:
        difficulty = st.text_area("学生的困难点", placeholder="例如：三单时态在否定句中仍会出错", key="result_difficulty")
        parent_feedback = st.text_area("家长反馈原话", placeholder="例如：妈妈说孩子愿意做这些题", key="result_parent")

    next_action = st.text_input(
        "下一次练习建议",
        placeholder="例如：继续巩固三单，增加疑问句练习",
        key="result_next",
    )

    if st.button("保存结果", type="primary"):
        result = ExerciseResult(
            exercise_id=run.exercise_id,
            completed=completed,
            accuracy=accuracy if completed else None,
            difficulty_notes=difficulty,
            parent_feedback=parent_feedback,
            next_action=next_action,
            recorded_at=datetime.now().isoformat(),
        )

        try:
            save_result_json(result)
            st.session_state.exercise_run.status = ExerciseStatus.COMPLETED
            save_exercise_json(st.session_state.exercise_run)
            st.session_state.result_saved = True
            st.success("结果已保存！")
            st.rerun()
        except Exception as e:
            st.error(f"保存失败：{e}")

    if run.status == ExerciseStatus.COMPLETED:
        st.divider()
        st.subheader("实验摘要")
        result_qs = run.approved_questions or run.draft_questions
        st.write(f"- 练习天数：第 {run.day} 天")
        st.write(f"- 目标薄弱点：{run.target}")
        st.write(f"- 题目数：{len(result_qs)}")
        st.write(f"- 老师修改/删除数：{run.modified_count}")
        if run.sent_at:
            st.write(f"- 下发时间：{run.sent_at}")
