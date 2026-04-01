"""图片评审服务。

AI 评审生成的图片是否满足提示词要求、是否存在错位/变形。
优先使用 DeepSeek 文本对比，备用 Gemini Vision。
"""
import base64
import json
import logging
import re
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.services.keyvault import get_provider_key_sync
from app.services.flow_log import log_sync

log = logging.getLogger(__name__)

MAX_REVIEW_ROUNDS = 3

REVIEW_SYSTEM_PROMPT = """\
你是专业的 AI 图片质量评审专家。请评审以下 AI 生成的图片是否满足要求。

评审标准：
1. 图片内容是否与提示词(visual_prompt)描述一致
2. 图片中是否存在明显错位（人物变形、肢体错乱、五官异常、多余手指等）
3. 图片风格是否与项目要求的视觉风格一致
4. 图片是否包含不该出现的水印或文字
5. 图片的构图和色调是否适合视频使用

由于你无法直接看到图片，请根据提供的图片文件信息（大小、分辨率）和提示词的合理性进行评审。
如果图片文件过小(< 10KB)或异常，视为生成失败。

请以纯 JSON 返回（不要 Markdown 代码块），格式：
{
  "overall_pass": true/false,
  "scenes": [
    {
      "scene_id": 1,
      "pass": true,
      "score": 85,
      "notes": "",
      "issues": [],
      "action": "keep"
    }
  ]
}

每个场景打分 0-100，70分以上为通过。
不通过时 issues 列出问题，action 设为 "regenerate"。
"""

VISION_REVIEW_PROMPT = """\
请评审这张 AI 生成的图片：

提示词要求: {prompt}
视觉风格: {style}

评审标准：
1. 图片是否与提示词描述一致
2. 是否有人物变形/错位/多余肢体
3. 风格是否统一
4. 构图是否合理

请以 JSON 返回: {{"pass": true/false, "score": 0-100, "issues": [], "notes": ""}}
"""


def review_images(
    db: Session,
    chapter_id: int,
    scene_images: dict[int, Path],
    scene_prompts: dict[int, str],
    visual_style: str = "",
) -> dict:
    """评审生成的图片是否满足提示词要求。"""
    gemini_key = get_provider_key_sync(db, "gemini_api_key")
    if gemini_key:
        return _review_with_gemini(db, chapter_id, scene_images, scene_prompts, visual_style, gemini_key)

    deepseek_key = get_provider_key_sync(db, "deepseek")
    if deepseek_key:
        return _review_with_deepseek(db, chapter_id, scene_images, scene_prompts, visual_style, deepseek_key)

    return _review_with_rules(db, chapter_id, scene_images, scene_prompts)


def _review_with_rules(
    db: Session,
    chapter_id: int,
    scene_images: dict[int, Path],
    scene_prompts: dict[int, str],
) -> dict:
    """基于规则的轻量评审（兜底方案）。"""
    scenes = []
    all_pass = True
    for sid, img_path in scene_images.items():
        issues = []
        score = 80

        if not img_path.exists():
            issues.append("图片文件不存在")
            score = 0
        elif img_path.stat().st_size < 5000:
            issues.append("图片文件过小，可能生成失败")
            score = 20
        elif img_path.stat().st_size < 10000:
            issues.append("图片文件较小，质量可能不佳")
            score = 50

        passed = score >= 70
        if not passed:
            all_pass = False

        scenes.append({
            "scene_id": sid,
            "pass": passed,
            "score": score,
            "notes": "; ".join(issues) if issues else "规则检查通过",
            "issues": issues,
            "action": "regenerate" if not passed else "keep",
        })

    log_sync(db, "novel_chapter", chapter_id, "image_review",
             f"图片评审(规则): {'通过' if all_pass else '未通过'}", "info")
    return {"overall_pass": all_pass, "scenes": scenes}


def _review_with_deepseek(
    db: Session,
    chapter_id: int,
    scene_images: dict[int, Path],
    scene_prompts: dict[int, str],
    visual_style: str,
    api_key: str,
) -> dict:
    """使用 DeepSeek 文本模型评审（基于文件元数据）。"""
    user_msg = f"## 视觉风格要求\n{visual_style or '默认'}\n\n## 待评审的场景图片\n"
    for sid, img_path in scene_images.items():
        prompt = scene_prompts.get(sid, "")
        size_kb = img_path.stat().st_size / 1024 if img_path.exists() else 0
        user_msg += f"- scene_id={sid}, prompt=\"{prompt}\", 文件大小={size_kb:.1f}KB, 文件={'存在' if img_path.exists() else '不存在'}\n"

    try:
        with httpx.Client(timeout=90) as c:
            r = c.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
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
        result = json.loads(content)

        if "scenes" not in result:
            result = {"overall_pass": True, "scenes": []}

        all_pass = all(s.get("pass", True) for s in result.get("scenes", []))
        result["overall_pass"] = all_pass

        log_sync(db, "novel_chapter", chapter_id, "image_review",
                 f"图片评审(DeepSeek): {'通过' if all_pass else '未通过'}", "info")
        return result

    except Exception as e:
        log.error("DeepSeek image review failed: %s", e)
        return _review_with_rules(db, chapter_id, scene_images, scene_prompts)


def _review_with_gemini(
    db: Session,
    chapter_id: int,
    scene_images: dict[int, Path],
    scene_prompts: dict[int, str],
    visual_style: str,
    api_key: str,
) -> dict:
    """使用 Gemini Vision API 进行多模态图片评审。"""
    scenes = []
    all_pass = True

    for sid, img_path in scene_images.items():
        prompt = scene_prompts.get(sid, "")
        if not img_path.exists() or img_path.stat().st_size < 5000:
            scenes.append({
                "scene_id": sid, "pass": False, "score": 0,
                "issues": ["图片不存在或过小"], "action": "regenerate", "notes": "",
            })
            all_pass = False
            continue

        try:
            img_data = base64.b64encode(img_path.read_bytes()).decode("utf-8")
            suffix = img_path.suffix.lower().lstrip(".")
            mime = f"image/{'jpeg' if suffix in ('jpg', 'jpeg') else suffix}"

            review_prompt = VISION_REVIEW_PROMPT.format(prompt=prompt, style=visual_style)
            with httpx.Client(timeout=60) as c:
                r = c.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                    json={
                        "contents": [{
                            "parts": [
                                {"inline_data": {"mime_type": mime, "data": img_data}},
                                {"text": review_prompt},
                            ]
                        }],
                        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 500},
                    },
                )
                r.raise_for_status()
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            scene_result = json.loads(text)
            scene_result["scene_id"] = sid
            if not scene_result.get("pass", True):
                scene_result["action"] = "regenerate"
                all_pass = False
            else:
                scene_result["action"] = "keep"
            scenes.append(scene_result)

        except Exception as e:
            log.warning("Gemini review failed for scene %d: %s", sid, e)
            score = 70 if img_path.stat().st_size > 50000 else 40
            passed = score >= 70
            if not passed:
                all_pass = False
            scenes.append({
                "scene_id": sid, "pass": passed, "score": score,
                "issues": [f"Gemini评审异常: {e}"], "action": "keep" if passed else "regenerate",
                "notes": "",
            })

    log_sync(db, "novel_chapter", chapter_id, "image_review",
             f"图片评审(Gemini): {'通过' if all_pass else '未通过'}, {len(scenes)}个场景", "info")
    return {"overall_pass": all_pass, "scenes": scenes}
