"""小说视频生成系统 Pydantic schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── 小说来源（ai-novel-agent proxy） ──


class NovelSourceItem(BaseModel):
    slug: str
    title: str
    author: str | None = None
    category: str | None = None
    summary: str | None = None
    total_chapters: int = 0
    cover_url: str | None = None


class NovelSourceDetail(NovelSourceItem):
    chapters: list[dict[str, Any]] = []


class NovelChapterText(BaseModel):
    chapter_no: int
    title: str
    content: str


# ── NovelProject ──


class ProjectCreate(BaseModel):
    novel_slug: str
    narrator_voice_id: str | None = None
    visual_style: str | None = "电影质感，暖色调"
    video_orientation: str = "portrait"


class ProjectUpdate(BaseModel):
    narrator_voice_id: str | None = None
    visual_style: str | None = None
    default_bgm_id: int | None = None
    video_orientation: str | None = None
    status: str | None = None


class ProjectOut(BaseModel):
    id: int
    user_id: int
    novel_slug: str
    novel_title: str
    novel_author: str | None
    novel_intro: str | None
    cover_url: str | None
    narrator_voice_id: str | None
    visual_style: str | None
    default_bgm_id: int | None
    video_orientation: str
    status: str
    chapter_count: int = 0
    character_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── NovelCharacter ──


class CharacterCreate(BaseModel):
    name: str
    gender: str = "neutral"
    voice_id: str | None = None
    voice_sample_url: str | None = None
    personality: str | None = None
    appearance: str | None = None


class CharacterUpdate(BaseModel):
    name: str | None = None
    gender: str | None = None
    voice_id: str | None = None
    personality: str | None = None
    appearance: str | None = None


class CharacterOut(BaseModel):
    id: int
    project_id: int
    name: str
    gender: str
    voice_id: str | None
    personality: str | None
    appearance: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── NovelChapter ──


class ChapterImportRequest(BaseModel):
    chapter_nos: list[int] = Field(default_factory=list, description="要导入的章节号列表，空=全部")


class ChapterOut(BaseModel):
    id: int
    project_id: int
    chapter_no: int
    title: str
    script_status: str
    video_status: str
    estimated_duration: int | None
    actual_duration: float | None
    error: str | None
    output_path: str | None
    bgm_id: int | None
    bgm_volume: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterDetailOut(ChapterOut):
    raw_text: str | None
    script: dict | None
    script_review_notes: str | None
    video_review_notes: str | None
    audio_assets: dict | None
    visual_assets: dict | None


class ScriptEditRequest(BaseModel):
    script: dict


# ── Script Review ──


class ScriptReviewRequest(BaseModel):
    action: str = Field(description="approve / reject")
    notes: str | None = None


# ── Video Generation ──


class GenerateVideoRequest(BaseModel):
    bgm_id: int | None = None
    bgm_volume: float = 0.15


# ── Video Review ──


class ReviewItemIn(BaseModel):
    target_type: str  # scene_visual / scene_audio / bgm / subtitle / overall
    target_scene_id: int | None = None
    passed: bool = True
    notes: str | None = None
    action: str | None = None  # regenerate / replace_manual / adjust_params / skip


class VideoReviewRequest(BaseModel):
    action: str = Field(description="approve / reject")
    notes: str | None = None
    items: list[ReviewItemIn] = Field(default_factory=list)


class RegenerateSceneRequest(BaseModel):
    scene_ids: list[int]
    target: str = "all"  # all / visual / audio


# ── BGM ──


class BgmOut(BaseModel):
    id: int
    user_id: int | None
    name: str
    mood: str
    file_path: str
    duration_sec: float | None
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Review ──


class ReviewOut(BaseModel):
    id: int
    chapter_id: int
    review_stage: str
    review_round: int
    status: str
    notes: str | None
    items: list | None
    created_at: datetime

    model_config = {"from_attributes": True}
