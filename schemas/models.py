"""
所有 Agent 的输入/输出 Pydantic 模型。

每个 Agent 函数签名:
    agent.run(input_schema_instance) -> output_schema_instance

Atomic Agents 自动验证输出是否符合 Schema，不符合则自动重试。
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ============================================================
# Agent 1: Diagnose — 诊断测试生成
# ============================================================

class DiagnoseInput(BaseModel):
    """DiagnoseAgent 的输入"""
    grade: int = Field(..., ge=1, le=12, description="年级，如 8 代表初二")
    textbook: str = Field(..., description="教材版本，如 人教版")
    student_type: str = Field(default="课内提高", description="学生类型：课内提高 / 自主招生 / 提优")
    parent_note: str = Field(default="", description="家长描述的问题，如'考试阅读扣分多'")
    grammar_focus: list[str] = Field(
        default_factory=lambda: ["一般现在时第三人称单数", "现在完成时", "被动语态", "宾语从句"],
        description="本次诊断覆盖的语法点"
    )


class Question(BaseModel):
    """单道诊断题"""
    q_id: str = Field(..., description="题号，如 Q1")
    part: str = Field(..., description="Part A/B/C")
    type: str = Field(..., description="单词拼写 / 语法选择 / 阅读理解")
    content: str = Field(..., description="题目内容")
    options: Optional[list[str]] = Field(default=None, description="选项（语法选择/阅读才有）")
    answer: str = Field(..., description="正确答案")
    test_point: str = Field(..., description="考察的知识点")
    weak_point_signal: str = Field(..., description="如果做错这道题，说明哪个能力可能薄弱")


class DiagnosticTest(BaseModel):
    """DiagnoseAgent 的完整输出"""
    title: str = Field(..., description="测试标题")
    grade: int
    textbook: str
    questions: list[Question] = Field(..., min_length=15, max_length=25, description="15-25道诊断题")
    answer_sheet: dict[str, str] = Field(..., description="{q_id: answer}")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# Agent 2: Analyze — 错题归因
# ============================================================

class AnalyzeInput(BaseModel):
    """AnalyzeAgent 的输入"""
    grade: int
    weak_point_focus: str = Field(..., description="当前正在诊断的薄弱点")
    questions: list[dict] = Field(..., description="[{q_id, content, test_point, correct_answer}]")
    student_answers: list[dict] = Field(..., description="[{q_id, student_answer}]")
    previous_summary: str = Field(default="", description="如果之前有归因记录，粘贴摘要")


class MistakeItem(BaseModel):
    """单题错题归因"""
    q_id: str
    test_point: str
    student_answer: str
    correct_answer: str
    mistake_type: str = Field(..., description="规则遗忘 / 规则混淆 / 审题失误 / 词汇不足 / 过度泛化")
    mistake_detail: str = Field(..., description="具体错因，一行话")
    skill_gap: str = Field(..., description="暴露的能力短板")


class AnalysisResult(BaseModel):
    """AnalyzeAgent 的完整输出"""
    mistakes: list[MistakeItem] = Field(..., description="错题列表")
    error_pattern: str = Field(..., description="2-3句话的错误模式总结")
    weak_point: str = Field(..., description="确定的优先薄弱点名称")
    start_accuracy: float = Field(..., ge=0, le=1, description="本次正确率")
    next_action: str = Field(..., description="继续当前薄弱点 / 可以换下一个薄弱点")
    recommendation: str = Field(..., description="明天练习重点建议")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# Agent 3: Exercise — 每日练习
# ============================================================

class ExerciseInput(BaseModel):
    """ExerciseAgent 的输入"""
    grade: int
    textbook: str
    weak_point: str = Field(..., description="本次练习的薄弱点")
    weak_point_detail: str = Field(..., description="薄弱点具体表现，如'she go to school 忘记变goes'")
    day: int = Field(..., ge=1, description="第几天")
    previous_exercises: list[str] = Field(default_factory=list, description="之前出过的题，防重复")
    previous_accuracy: float = Field(default=0.0, description="上次正确率")


class ExerciseQuestion(BaseModel):
    """单道练习题"""
    q_id: str
    section: str = Field(..., description="基础巩固 / 辨析训练 / 综合挑战")
    content: str
    options: Optional[list[str]] = None
    answer: str
    explanation: str = Field(..., description="一句话解析")


class DailyExercise(BaseModel):
    """ExerciseAgent 的完整输出"""
    title: str = Field(..., description="每日练习 — Day N")
    weak_point: str
    day: int
    daily_tip: str = Field(..., description="今日小提示，20字以内")
    questions: list[ExerciseQuestion] = Field(..., min_length=6, max_length=12)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# Agent 4: Report — 家长周报
# ============================================================

class ReportInput(BaseModel):
    """ReportAgent 的输入"""
    student_name: str
    week_start: str
    week_end: str
    total_assigned: int
    total_completed: int
    weak_point: str
    accuracy_day1: float
    accuracy_last: float
    latest_analysis: str = Field(..., description="最近一次归因摘要")
    teacher_note: str = Field(default="", description="老师的主观观察")


class ParentReport(BaseModel):
    """ReportAgent 的完整输出"""
    student_name: str
    week_label: str
    report_text: str = Field(..., max_length=150, description="≤150字，直接复制发家长")
    next_plan: str = Field(..., description="下周计划 1 句话")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 通用类型
# ============================================================

class StudentProfile(BaseModel):
    """学生档案"""
    id: str
    name: str
    grade: int
    textbook: str = "人教版"
    student_type: str = "课内提高"
    is_tutoring: bool = False
    sessions_per_week: int = 1
    start_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    notes: str = ""


class StudentAnswer(BaseModel):
    """学生提交的答案（你手动录入）"""
    student_id: str
    test_id: str
    answers: list[dict]
    submitted_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class PipelineRun(BaseModel):
    """一次完整 Pipeline 的运行记录"""
    student_id: str
    steps: list[str]
    agent_versions: dict[str, str]
    status: str = "running"
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


# ============================================================
# 实验记录：练习生命周期与结果
# ============================================================

class ExerciseStatus:
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"
    COMPLETED = "completed"


class ExerciseRun(BaseModel):
    """一次练习从生成到下发的完整记录"""
    exercise_id: str = Field(..., description="唯一 ID，格式：{student_id}_day{day}_{timestamp}")
    student_id: str
    day: int = Field(..., ge=1, description="该学生的第几天练习")
    target: str = Field(..., description="本次练习目标或薄弱点")
    draft_questions: list[dict] = Field(default_factory=list, description="AI 生成的原始题目草稿")
    approved_questions: list[dict] = Field(default_factory=list, description="老师审核确认后的题目")
    status: str = Field(default=ExerciseStatus.DRAFT, description="draft / approved / sent / completed")
    modified_count: int = Field(default=0, description="老师修改或删除的题目数量")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    sent_at: Optional[str] = None
    prompt_version: str = "v1.0"


class ExerciseResult(BaseModel):
    """学生完成练习后的结果记录"""
    exercise_id: str
    completed: bool = Field(default=False, description="学生是否完成了本次练习")
    accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="正确率（0.0-1.0）")
    difficulty_notes: str = Field(default="", description="学生的困难点")
    parent_feedback: str = Field(default="", description="家长反馈原话")
    next_action: str = Field(default="", description="老师对下一次练习的判断")
    recorded_at: str = Field(default_factory=lambda: datetime.now().isoformat())
