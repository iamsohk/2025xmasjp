"""
蘇蘇 AI 秘書 — Research Agent
使用 Claude API 做 research，結果寫入 Notion
"""
import os
import json
import anthropic
from datetime import datetime


SYSTEM_PROMPT = """你係蘇蘇嘅 AI 秘書。蘇蘇係一個香港人，鍾意用廣東話溝通。
你嘅工作係幫蘇蘇做 research 同比較，令佢只需要 approve 最後決定。

輸出格式要求：
1. 用廣東話寫摘要（簡短清晰）
2. 用表格比較選項（如適用）
3. 列出你嘅推薦同理由
4. 標明資料來源（如有）
5. 列出蘇蘇需要自己做嘅最後步驟

保持簡潔——蘇蘇唔得閒，重點先。"""


def research_task(task_name: str, task_description: str = "") -> dict:
    """
    輸入任務，返回 research 結果
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_message = f"""任務：{task_name}

{f'補充資料：{task_description}' if task_description else ''}

請幫我做 research 同整理，格式要方便我 review + approve。"""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    result_text = response.content[0].text

    return {
        "task": task_name,
        "description": task_description,
        "research_result": result_text,
        "model": response.model,
        "timestamp": datetime.now().isoformat(),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


def research_and_compare(items: list[str], criteria: str = "") -> dict:
    """
    比較多個選項（例如保險計劃、旅遊目的地）
    items: 要比較嘅選項列表
    criteria: 比較標準
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    items_str = "\n".join(f"- {item}" for item in items)
    user_message = f"""請幫我比較以下選項：

{items_str}

{f'比較標準：{criteria}' if criteria else ''}

用表格整理，然後俾我一個推薦同理由。"""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return {
        "type": "comparison",
        "items": items,
        "criteria": criteria,
        "research_result": response.content[0].text,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    # 測試
    result = research_task(
        task_name="搵旅遊保險",
        task_description="下個月去日本7日，兩個人，需要涵蓋行李遺失同醫療",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
