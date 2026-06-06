"""
Agent 共享基础设施

去掉 atomic-agents 依赖，直接用 instructor + Pydantic 实现：
- get_client(): 返回 instructor 包装的 DeepSeek 客户端
- run_agent(): 通用 Agent 执行函数（加载 YAML → 构建 prompt → 调用 LLM → 验证输出）
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import instructor
from pydantic import BaseModel

load_dotenv()

BASE_DIR = Path(__file__).parent.parent


def get_client():
    """创建 instructor 包装的 DeepSeek 客户端"""
    return instructor.from_openai(
        OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY", "sk-xxx"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
    )


def _render_template(template: str, variables: dict) -> str:
    """
    安全模板渲染：用变量值替换 {key} 占位符。

    使用 str.replace() 而非 str.format()，因为 prompt 模板中
    大量使用 {{ }} 表示 JSON 示例花括号，.format() 会错误解析。

    单次遍历替换，避免子串冲突（如 {weak_point} vs {weak_point_detail}）。
    """
    result = template
    for key, val in variables.items():
        result = result.replace("{" + key + "}", str(val))
    return result


def run_agent(
    prompt_yaml: str,
    output_model: type[BaseModel],
    user_vars: dict,
    model: str = "deepseek-chat",
    temperature: float = 0.3,
    max_tokens: int = 4096,
):
    """
    通用 Agent 执行函数。

    参数:
        prompt_yaml: YAML 文件路径（相对于 prompts/ 目录）
        output_model: Pydantic 输出模型（用于结构化输出验证）
        user_vars: 填充 user_template 的变量字典
        model: 模型名称
        temperature: 温度
        max_tokens: 最大 token 数

    返回:
        output_model 的实例（已验证的结构化输出）
    """
    import yaml

    prompt_path = BASE_DIR / "prompts" / prompt_yaml
    with open(prompt_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    system = config["system"]

    # 构建 system prompt
    system_prompt_parts = []
    if system.get("background"):
        bg = "\n".join(f"- {b}" for b in system["background"])
        system_prompt_parts.append(f"## 角色定位\n{bg}")
    if system.get("steps"):
        steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(system["steps"]))
        system_prompt_parts.append(f"## 执行步骤\n{steps}")
    if system.get("output_instructions"):
        oi = "\n".join(f"- {o}" for o in system["output_instructions"])
        system_prompt_parts.append(f"## 输出要求\n{oi}")

    system_prompt = "\n\n".join(system_prompt_parts)

    # 构建 user message — 使用 _render_template() 安全替换变量
    user_template = config.get("user_template", "")
    user_template = _render_template(user_template, user_vars)

    # 调用 LLM
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_model=output_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_template},
        ],
    )

    return response
