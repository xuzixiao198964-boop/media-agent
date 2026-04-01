"""图片提示词评审服务。

AI 自动评审分镜脚本中的 visual_prompt 是否满足小说场景需求。
"""
import json
import logging
import re

import httpx
from sqlalchemy.orm import Session

from app.services.keyvault import get_provider_key_sync
from app.services.flow_log import log_sync

log = logging.getLogger(__name__)

MAX_REVIEW_ROUNDS = 3

REVIEW_SYSTEM_PROMPT = """\
你是专业的影视画面评审专家。请评审以下分镜脚本的画面描述(visual_prompt)，
检查每个场景的提示词是否准确描述了小说原文中的场景。

评审标准：
1. 场景描述是否与小说原文一致（环境、时间、氛围）
2. 涉及角色的外貌特征是否包含在提示词中
3. 提示词细节是否充足（光线、色调、构图、动作）
4. 各场景之间是否连贯、风格是否统一
5. 是否包含了不合适的现代元素（古代小说场景中出现现代物品等）

请以纯 JSON 返回（不要 Markdown 代码块），格式：
{
  "overall_pass": true/false,
  "scenes": [
    {
      "scene_id": 1,
      "pass": true,
      "score": 85,
      "notes": "描述准确",
      "suggested_prompt": ""
    }
  ]
}

每个场景打分 0-100，70分以上为通过。
不通过的场景必须给出改进后的 suggested_prompt。
"""

REGEN_SYSTEM_PROMPT = """\
你是专业的影视画面描述专家。请根据评审意见重新生成一个更准确的场景画面描述(visual_prompt)。

要求：
1. 准确反映小说原文描述的场景
2. 包含环境细节（场所、时间、天气、光线）
3. 如果涉及角色，包含其外貌特征
4. 适合 AI 图片生成模型使用
5. 中英文混合描述，以英文为主（AI 生图模型理解更好）

直接返回新的提示词文本，不要包裹代码块或 JSON。
"""


def review_prompts(
    db: Session,
    chapter_id: int,
    scenes: list[dict],
    raw_text: str,
    visual_style: str = "",
    characters: dict[str, str] | None = None,
) -> dict:
    """AI 评审分镜脚本中所有 scene 的 visual_prompt。"""
    key = get_provider_key_sync(db, "deepseek")
    if not key:
        log.warning("DeepSeek API Key 未配置，跳过提示词评审，直接通过")
        return {
            "overall_pass": True,
            "scenes": [{"scene_id": s.get("scene_id", i), "pass": True, "score": 100, "notes": "跳过评审"} for i, s in enumerate(scenes)],
        }

    user_msg = f"## 视觉风格\n{visual_style or '默认风格'}\n\n"
    if characters:
        user_msg += "## 角色外貌\n"
        for name, appearance in characters.items():
            user_msg += f"- {name}: {appearance}\n"
        user_msg += "\n"

    user_msg += f"## 小说原文（节选前3000字）\n{raw_text[:3000]}\n\n"
    user_msg += "## 待评审的场景提示词\n"
    for s in scenes:
        sid = s.get("scene_id", "?")
        vp = s.get("visual_prompt", "")
        mood = s.get("mood", "neutral")
        user_msg += f"- scene_id={sid}, mood={mood}, visual_prompt=\"{vp}\"\n"

    try:
        with httpx.Client(timeout=90) as c:
            r = c.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()

        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            last_brace = content.rfind("}")
            if last_brace > 0:
                result = json.loads(content[:last_brace + 1])
            else:
                raise

        if "scenes" not in result:
            result = {"overall_pass": True, "scenes": []}

        all_pass = all(s.get("pass", True) for s in result.get("scenes", []))
        result["overall_pass"] = all_pass

        log_sync(db, "novel_chapter", chapter_id, "prompt_review",
                 f"提示词评审完成: {'通过' if all_pass else '未通过'}, {len(result['scenes'])}个场景", "info")
        return result

    except Exception as e:
        log_sync(db, "novel_chapter", chapter_id, "prompt_review_fail", str(e), "error")
        log.error("Prompt review failed: %s", e)
        return {
            "overall_pass": True,
            "scenes": [{"scene_id": s.get("scene_id", i), "pass": True, "score": 60, "notes": f"评审异常，默认通过: {e}"} for i, s in enumerate(scenes)],
        }


def regenerate_prompt(
    db: Session,
    scene: dict,
    review_notes: str,
    raw_text: str,
    visual_style: str = "",
    character_appearance: str = "",
) -> str:
    """根据评审意见重新生成单个 scene 的 visual_prompt。"""
    key = get_provider_key_sync(db, "deepseek")
    if not key:
        return scene.get("visual_prompt", "")

    user_msg = f"## 当前提示词\n{scene.get('visual_prompt', '')}\n\n"
    user_msg += f"## 评审意见\n{review_notes}\n\n"
    user_msg += f"## 视觉风格\n{visual_style}\n\n"
    if character_appearance:
        user_msg += f"## 角色外貌\n{character_appearance}\n\n"
    user_msg += f"## 小说原文片段\n{raw_text[:1500]}\n"

    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": REGEN_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.6,
                    "max_tokens": 500,
                },
            )
            r.raise_for_status()
            new_prompt = r.json()["choices"][0]["message"]["content"].strip()
            new_prompt = re.sub(r"^```\s*", "", new_prompt)
            new_prompt = re.sub(r"\s*```$", "", new_prompt)
            return new_prompt
    except Exception as e:
        log.warning("Prompt regeneration failed: %s", e)
        return scene.get("suggested_prompt", scene.get("visual_prompt", ""))
