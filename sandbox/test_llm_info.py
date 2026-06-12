"""
LLM 信息返回能力测试 (sandbox/test_llm_info.py)

测试覆盖：
1. 长文本中文回答（风控报告风格）
2. JSON 结构化输出
3. 思考标签清洗（deepseek-v4-flash 应输出 <think>...</think>）
4. 多轮上下文

运行：
    python sandbox/test_llm_info.py
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.utils.llm_client import AquaLLM


def banner(title: str):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def test_long_text():
    """测试 1：长文本风控报告（中文 ~250 字）"""
    banner("[1/4] 长文本中文回答")
    llm = AquaLLM()
    prompt = (
        "请用中文写一段约 200 字的'双均线策略'风控要点，"
        "覆盖：策略逻辑、适合行情、潜在风险、参数建议。"
    )
    out = llm.generate_report(prompt)
    print(f"返回长度: {len(out)} 字符\n")
    print(out)
    return len(out) >= 50


def test_json_output():
    """测试 2：JSON 结构化输出 + 容错解析"""
    banner("[2/4] JSON 结构化输出")
    llm = AquaLLM()
    prompt = (
        "请输出一段 JSON，描述一个名为 'rsi_reversal' 的策略，"
        "包含字段: name (str), timeframe (str, e.g. 'D'), "
        "entry (list[str]), exit (list[str]), risk_pct (float)。"
        "只输出 JSON，不要任何解释。"
    )
    raw = llm.generate_code(prompt)
    print(f"原始返回:\n{raw}\n")
    # 尝试解析
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:] if lines and lines[0].strip().startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    try:
        data = json.loads(cleaned)
        print(f"解析成功: {json.dumps(data, ensure_ascii=False, indent=2)}")
        return True
    except json.JSONDecodeError as e:
        print(f"[WARN] 解析失败: {e}")
        return False


def test_think_tag_cleaning():
    """测试 3：deepseek 思考标签是否被 _clean_code 清除"""
    banner("[3/4] 思考标签清洗（deepseek 风格）")
    llm = AquaLLM()
    # 用一个容易触发思考链的 prompt
    prompt = "计算 123 * 456 + 789，并说明步骤。只输出一行答案。"
    out = llm.generate_code(prompt)
    print(f"返回:\n{out}\n")
    has_think = "<think>" in out.lower() or "思考过程" in out or "推理过程" in out
    has_md = "```" in out
    if has_think:
        print("[WARN] 思考标签未被清洗")
    if has_md:
        print("[WARN] Markdown 标记未清洗")
    if not has_think and not has_md:
        print("[OK] 思考标签 + Markdown 均已清洗")
    return not (has_think or has_md)


def test_stream_long():
    """测试 4：流式输出长文本，验证 SSE 通道"""
    banner("[4/4] 流式输出（实时打印）")
    llm = AquaLLM()
    prompt = "用 3 句话介绍量化交易中的'夏普比率'，每句话不超过 20 字。"
    parts = []
    for chunk in llm.generate_report_stream(prompt):
        print(chunk, end="", flush=True)
        parts.append(chunk)
    print()
    text = "".join(parts).strip()
    print(f"\n累计 {len(text)} 字符")
    return text and not text.startswith("[ERROR]")


def main():
    print("LLM 信息返回能力测试")
    print(f"模型: {__import__('config.config', fromlist=['Config']).Config.LLM_MODEL_NAME}")

    results = {
        "long_text": test_long_text(),
        "json_output": test_json_output(),
        "think_clean": test_think_tag_cleaning(),
        "stream": test_stream_long(),
    }

    banner("测试结果汇总")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")

    if all(results.values()):
        print("\n全部通过 ✅")
    else:
        print("\n存在异常 ❌")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
