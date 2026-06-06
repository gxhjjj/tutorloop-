"""Agent 错误处理 + 重试测试"""
import pytest
from pathlib import Path
import sys
from pydantic import BaseModel, ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))


class FakeOutput(BaseModel):
    name: str
    score: int


def test_retry_on_pydantic_validation_error(mocker):
    """LLM 返回格式不对时自动重试，最终成功"""
    from agents.base import _call_with_retry

    # Mock: 前 2 次返回无效（不受 FakeOutput 约束），第 3 次返回 FakeOutput
    call_count = [0]

    def mock_create(**kwargs):
        call_count[0] += 1
        if call_count[0] < 3:
            raise ValidationError.from_exception_data(
                title="FakeOutput",
                line_errors=[{"type": "missing", "loc": ("name",), "msg": "Field required"}],
            )
        return FakeOutput(name="test", score=100)

    mock_client = mocker.MagicMock()
    mock_openai = mocker.MagicMock()
    mock_openai.chat.completions.create = mock_create
    mock_client.chat.completions.create = mock_create

    result = _call_with_retry(mock_client, [], FakeOutput)
    assert result.name == "test"
    assert result.score == 100
    assert call_count[0] == 3


def test_retry_exhaustion_raises_runtime_error(mocker):
    """重试耗尽后抛出 RuntimeError 而非裸异常"""
    from agents.base import _call_with_retry

    def always_fail(**kwargs):
        raise ValidationError.from_exception_data(
            title="FakeOutput",
            line_errors=[{"type": "missing", "loc": ("name",), "msg": "Field required"}],
        )

    mock_client = mocker.MagicMock()
    mock_client.chat.completions.create = always_fail

    with pytest.raises(RuntimeError, match="LLM 输出格式验证失败"):
        _call_with_retry(mock_client, [], FakeOutput, max_retries=2)


def test_network_error_caught(mocker):
    """网络异常被捕获并包装为 RuntimeError"""
    from agents.base import _call_with_retry

    mock_client = mocker.MagicMock()
    mock_client.chat.completions.create.side_effect = ConnectionError("Connection refused")

    with pytest.raises(RuntimeError, match="LLM 调用失败"):
        _call_with_retry(mock_client, [], FakeOutput, max_retries=1)
