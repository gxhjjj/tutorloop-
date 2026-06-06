"""验证 Agent 系统完整性"""
import sys
from pathlib import Path

errors = []
oks = []

# 1. 验证文件存在
files = [
    "agents/diagnose.py", "agents/analyze.py", "agents/exercise.py", "agents/report.py",
    "agents/base.py", "agents/__init__.py",
    "schemas/models.py", "schemas/__init__.py",
    "prompts/diagnose.yaml", "prompts/analyze.yaml", "prompts/exercise.yaml", "prompts/report.yaml",
    "orchestrator.py", "config.yaml"
]
for f in files:
    p = Path(f)
    oks.append(f"FILE: {f}") if p.exists() else errors.append(f"MISSING: {f}")

# 2. 验证 YAML
import yaml
prompt_issues = []
for pf in ["diagnose.yaml", "analyze.yaml", "exercise.yaml", "report.yaml"]:
    path = Path("prompts") / pf
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    sys_cfg = cfg.get("system", {})
    bg = len(sys_cfg.get("background", []))
    st = len(sys_cfg.get("steps", []))
    oi = len(sys_cfg.get("output_instructions", []))
    ut = cfg.get("user_template", "")
    has_vars = "{" in ut and "}" in ut
    oks.append(f"PROMPT: {pf} (bg:{bg} steps:{st} out:{oi} vars:{has_vars})")
    if bg == 0 or st == 0 or oi == 0:
        prompt_issues.append(f"  WARN: {pf} has empty section")

# 3. 验证导入
try:
    from agents import run_diagnose, run_analyze, run_exercise, run_report
    oks.append("IMPORT: All 4 agents")
except Exception as e:
    errors.append(f"IMPORT FAIL: {e}")

try:
    from schemas import DiagnoseInput, DiagnosticTest, AnalyzeInput, AnalysisResult
    from schemas import ExerciseInput, DailyExercise, ReportInput, ParentReport
    oks.append("SCHEMA: 8 models (4 in/out pairs)")
except Exception as e:
    errors.append(f"SCHEMA FAIL: {e}")

# 4. 验证函数签名
import inspect
for name, fn in [("diagnose", run_diagnose), ("analyze", run_analyze), ("exercise", run_exercise), ("report", run_report)]:
    sig = inspect.signature(fn)
    params = list(sig.parameters.keys())
    oks.append(f"FUNC: {name}({', '.join(params)})")

# 结果
print("=" * 60)
print(f"PASS: {len(oks)} checks")
for o in oks:
    print(f"  [OK] {o}")
if errors:
    print(f"\nFAIL: {len(errors)} checks")
    for e in errors:
        print(f"  [!!] {e}")
if prompt_issues:
    for p in prompt_issues:
        print(f"  [?] {p}")

print(f"\nDocker: NOT INSTALLED (LangFuse requires Docker Desktop)")
print(f"DeepSeek API: NOT CONFIGURED (.env has placeholder key)")

sys.exit(1 if errors else 0)
