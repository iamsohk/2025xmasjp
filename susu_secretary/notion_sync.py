"""
蘇蘇 AI 秘書 — Notion 同步模組
負責將 research 結果寫入 Notion，同讀取任務
"""
import os
import json
import requests
from datetime import datetime


NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
TASK_INBOX_DB = os.environ.get("NOTION_TASK_INBOX_DB", "a1289e90-d065-4647-b5b3-c66766a41bd7")
RESEARCH_DB = os.environ.get("NOTION_RESEARCH_DB", "")
REMINDER_DB = os.environ.get("NOTION_REMINDER_DB", "")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def get_pending_tasks() -> list[dict]:
    """從任務收件箱取得所有「待處理」任務"""
    url = f"https://api.notion.com/v1/databases/{TASK_INBOX_DB}/query"
    payload = {
        "filter": {
            "property": "狀態",
            "select": {"equals": "📥 待處理"},
        }
    }
    resp = requests.post(url, headers=HEADERS, json=payload)
    resp.raise_for_status()
    results = resp.json().get("results", [])

    tasks = []
    for page in results:
        props = page["properties"]
        task_name = ""
        if props.get("任務") and props["任務"].get("title"):
            task_name = "".join(t["text"]["content"] for t in props["任務"]["title"])
        description = ""
        if props.get("描述") and props["描述"].get("rich_text"):
            description = "".join(t["text"]["content"] for t in props["描述"]["rich_text"])
        tasks.append({
            "page_id": page["id"],
            "task": task_name,
            "description": description,
            "priority": props.get("優先級", {}).get("select", {}).get("name", "🟢 普通"),
            "type": props.get("類型", {}).get("select", {}).get("name", "Research"),
        })
    return tasks


def update_task_status(page_id: str, status: str):
    """更新任務狀態"""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "狀態": {"select": {"name": status}}
        }
    }
    resp = requests.patch(url, headers=HEADERS, json=payload)
    resp.raise_for_status()


def save_research_result(task_name: str, research_text: str, task_page_id: str = "") -> str:
    """將 research 結果寫入 Research 結果庫，返回新頁面 URL"""
    if not RESEARCH_DB:
        print("⚠️ NOTION_RESEARCH_DB 未設定，跳過寫入")
        return ""

    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": RESEARCH_DB},
        "properties": {
            "標題": {"title": [{"text": {"content": task_name}}]},
            "審批狀態": {"select": {"name": "⏳ 待 Review"}},
            "原始任務": {"rich_text": [{"text": {"content": task_page_id}}]},
        },
        "children": [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "🤖 AI Research 結果"}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": research_text[:2000]}}]
                },
            },
            {
                "object": "block",
                "type": "divider",
                "divider": {},
            },
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"text": {"content": "📋 你嘅決定"}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": "（在此填寫你嘅決定同下一步行動）"}}]
                },
            },
        ],
    }
    resp = requests.post(url, headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json().get("url", "")


def get_overdue_reminders() -> list[dict]:
    """取得今日到期或過期嘅提醒"""
    if not REMINDER_DB:
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://api.notion.com/v1/databases/{REMINDER_DB}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "狀態", "select": {"equals": "🟡 待辦"}},
                {"property": "提醒日期", "date": {"on_or_before": today}},
            ]
        }
    }
    resp = requests.post(url, headers=HEADERS, json=payload)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    reminders = []
    for page in results:
        props = page["properties"]
        name = ""
        if props.get("事項") and props["事項"].get("title"):
            name = "".join(t["text"]["content"] for t in props["事項"]["title"])
        reminders.append({"page_id": page["id"], "name": name})
    return reminders


if __name__ == "__main__":
    tasks = get_pending_tasks()
    print(f"待處理任務：{len(tasks)} 個")
    for t in tasks:
        print(f"  - [{t['priority']}] {t['task']}")
