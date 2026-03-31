"""DeepSeek AI 分镜脚本生成。

将小说章节原文拆解为结构化 scene 列表。
"""
import json
import re

import httpx
from sqlalchemy.orm import Session

from app.services.keyvault import get_provider_key_sync
from app.services.flow_log import log_sync

SYSTEM_PROMPT = """\
你是一位专业的影视编剧。你的任务是将小说章节原文拆解成一系列「分镜场景」(scenes)，
用于后续自动生成配音+画面的视频。

## 输出要求
请以**纯 JSON**返回（不要 Markdown、不要代码块包裹），格式如下：
{
  "summary": "本章概要（50字以内）",
  "estimated_duration_sec": 180,
  "scenes": [
    {
      "scene_id": 1,
      "type": "narration",
      "speaker": "narrator",
      "text": "旁白文本20~60字",
      "visual_prompt": "场景画面描述",
      "mood": "neutral",
      "duration_hint": 8
    }
  ]
}

## 规则
1. **旁白(narration)**: speaker 固定为 "narrator"
2. **对话(dialogue)**: speaker 必须是角色名
3. **独白(monologue)**: 角色内心独白
4. **转场(transition)**: 无台词，text 为 null，仅有 visual_prompt
5. 每个 scene 的 text 控制在 20~60 字，节奏要好
6. duration_hint 单位为秒，旁白 5~10s，对话 3~6s，转场 1~2s
7. 按原文顺序拆分，保留关键剧情，**场景总数控制在 8~12 个**
8. mood 标签要准确反映该场景的情绪
9. 如出现新角色，speaker 使用原文中的名字
10. **重要：必须输出完整合法的 JSON，不要截断**\
"""


def generate_script(
    db: Session,
    chapter_title: str,
    chapter_no: int,
    raw_text: str,
    existing_characters: list[str] | None = None,
    review_notes: str | None = None,
) -> dict:
    key = get_provider_key_sync(db, "deepseek")
    if not key:
        raise RuntimeError("DeepSeek API Key 未配置，无法生成分镜脚本")

    truncated = raw_text[:4000]
    user_msg = f"## 章节信息\n- 标题：第{chapter_no}章 {chapter_title}\n"
    if existing_characters:
        user_msg += f"- 已知角色：{', '.join(existing_characters)}\n"
    if review_notes:
        user_msg += f"\n## 审核意见（本次重写需满足）\n{review_notes}\n"
    user_msg += f"\n## 原文（节选前4000字）\n{truncated}\n"

    try:
        with httpx.Client(timeout=120) as c:
            r = c.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.5,
                    "max_tokens": 3000,
                },
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()

        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

        try:
            script = json.loads(content)
        except json.JSONDecodeError:
            last_brace = content.rfind("}")
            if last_brace > 0:
                script = json.loads(content[:last_brace + 1])
            else:
                raise

        if "scenes" not in script:
            raise ValueError("AI 返回的 JSON 中缺少 scenes 字段")

        script["chapter_no"] = chapter_no
        script["title"] = chapter_title

        log_sync(db, "novel_chapter", None, "script_gen", f"第{chapter_no}章脚本生成成功，{len(script['scenes'])}个场景", "info")
        return script
    except json.JSONDecodeError as e:
        log_sync(db, "novel_chapter", None, "script_gen_fail", f"JSON 解析失败: {e}", "error")
        raise RuntimeError(f"AI 返回格式异常，无法解析 JSON: {e}")
    except Exception as e:
        log_sync(db, "novel_chapter", None, "script_gen_fail", str(e), "error")
        raise


def extract_characters_from_script(script: dict) -> list[str]:
    """从脚本中提取所有出现的角色名。"""
    names = set()
    for scene in script.get("scenes", []):
        speaker = scene.get("speaker")
        if speaker and speaker != "narrator":
            names.add(speaker)
    return sorted(names)
