"""小说视频生成 API 路由。"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.deps import get_current_user
from app.database import get_db
from app.models import (
    BgmLibrary, ChapterReview, NovelChapter, NovelCharacter, NovelProject, User,
)
from app.schemas.novel import (
    BgmOut, ChapterDetailOut, ChapterImportRequest, ChapterOut,
    CharacterCreate, CharacterOut, CharacterUpdate,
    GenerateVideoRequest, NovelSourceDetail, NovelSourceItem,
    ProjectCreate, ProjectOut, ProjectUpdate,
    RegenerateSceneRequest, ReviewOut,
    ScriptEditRequest, ScriptReviewRequest,
    VideoReviewRequest,
)
from app.services import novel_client
from app.services.tts_audio import ffprobe_duration

router = APIRouter(prefix="/novel", tags=["novel"])
settings = get_settings()


# ━━ 小说来源（proxy ai-novel-agent） ━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/source/novels")
async def list_source_novels(page: int = 1, per_page: int = 20):
    try:
        return novel_client.list_novels(page, per_page)
    except Exception as e:
        raise HTTPException(502, f"ai-novel-agent 不可达: {e}")


@router.get("/source/novels/{slug}")
async def get_source_novel(slug: str):
    try:
        return novel_client.get_novel_detail(slug)
    except Exception as e:
        raise HTTPException(502, f"ai-novel-agent 不可达: {e}")


@router.get("/source/novels/{slug}/chapter/{chapter_no}")
async def get_source_chapter(slug: str, chapter_no: int):
    try:
        return novel_client.get_chapter_text(slug, chapter_no)
    except Exception as e:
        raise HTTPException(502, f"ai-novel-agent 不可达: {e}")


# ━━ 项目 CRUD ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/projects", response_model=ProjectOut)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        detail = novel_client.get_novel_detail(body.novel_slug)
    except Exception as e:
        raise HTTPException(502, f"从 ai-novel-agent 获取小说失败: {e}")

    proj = NovelProject(
        user_id=user.id,
        novel_slug=body.novel_slug,
        novel_title=detail.get("title", body.novel_slug),
        novel_author=detail.get("author"),
        novel_intro=detail.get("summary") or detail.get("description"),
        cover_url=detail.get("cover_url"),
        narrator_voice_id=body.narrator_voice_id,
        visual_style=body.visual_style,
        video_orientation=body.video_orientation,
    )
    db.add(proj)
    await db.commit()
    await db.refresh(proj)
    return _project_out(proj)


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(NovelProject).where(NovelProject.user_id == user.id).order_by(NovelProject.created_at.desc())
    )).scalars().all()
    results = []
    for p in rows:
        results.append(await _project_out_async(db, p))
    return results


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    proj = await _get_project(db, project_id, user.id)
    return await _project_out_async(db, proj)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    proj = await _get_project(db, project_id, user.id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(proj, k, v)
    await db.commit()
    await db.refresh(proj)
    return await _project_out_async(db, proj)


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    proj = await _get_project(db, project_id, user.id)
    await db.delete(proj)
    await db.commit()
    return {"detail": "已删除"}


# ━━ 角色 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/projects/{project_id}/characters", response_model=list[CharacterOut])
async def list_characters(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_project(db, project_id, user.id)
    rows = (await db.execute(
        select(NovelCharacter).where(NovelCharacter.project_id == project_id)
    )).scalars().all()
    return rows


@router.post("/projects/{project_id}/characters", response_model=CharacterOut)
async def add_character(
    project_id: int,
    body: CharacterCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_project(db, project_id, user.id)
    ch = NovelCharacter(project_id=project_id, **body.model_dump())
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    return ch


@router.patch("/characters/{char_id}", response_model=CharacterOut)
async def update_character(
    char_id: int,
    body: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ch = await db.get(NovelCharacter, char_id)
    if not ch:
        raise HTTPException(404, "角色不存在")
    await _get_project(db, ch.project_id, user.id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(ch, k, v)
    await db.commit()
    await db.refresh(ch)
    return ch


@router.delete("/characters/{char_id}")
async def delete_character(
    char_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ch = await db.get(NovelCharacter, char_id)
    if not ch:
        raise HTTPException(404, "角色不存在")
    await _get_project(db, ch.project_id, user.id)
    await db.delete(ch)
    await db.commit()
    return {"detail": "已删除"}


# ━━ 章节 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/projects/{project_id}/import-chapters")
async def import_chapters(
    project_id: int,
    body: ChapterImportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    proj = await _get_project(db, project_id, user.id)

    try:
        detail = novel_client.get_novel_detail(proj.novel_slug)
    except Exception as e:
        raise HTTPException(502, f"ai-novel-agent 不可达: {e}")

    chapters_info = detail.get("chapters", [])
    if not chapters_info:
        raise HTTPException(400, "该小说没有章节数据")

    existing = set(
        (await db.execute(
            select(NovelChapter.chapter_no).where(NovelChapter.project_id == project_id)
        )).scalars().all()
    )

    targets = body.chapter_nos if body.chapter_nos else [c.get("chapter_no", i + 1) for i, c in enumerate(chapters_info)]
    imported = 0

    for no in targets:
        if no in existing:
            continue
        try:
            ch_data = novel_client.get_chapter_text(proj.novel_slug, no)
        except Exception:
            continue

        title = ch_data.get("title", f"第{no}章")
        content = ch_data.get("content", "")
        if not content:
            continue

        chapter = NovelChapter(
            project_id=project_id,
            chapter_no=no,
            title=title,
            raw_text=content,
        )
        db.add(chapter)
        imported += 1

    await db.commit()
    return {"imported": imported, "total_available": len(chapters_info)}


@router.get("/projects/{project_id}/chapters", response_model=list[ChapterOut])
async def list_chapters(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_project(db, project_id, user.id)
    rows = (await db.execute(
        select(NovelChapter)
        .where(NovelChapter.project_id == project_id)
        .order_by(NovelChapter.chapter_no)
    )).scalars().all()
    return rows


@router.get("/chapters/{chapter_id}", response_model=ChapterDetailOut)
async def get_chapter(
    chapter_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ch = await db.get(NovelChapter, chapter_id)
    if not ch:
        raise HTTPException(404, "章节不存在")
    await _get_project(db, ch.project_id, user.id)
    return ch


# ━━ 脚本生成与审核 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/chapters/{chapter_id}/generate-script")
async def generate_script(
    chapter_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ch = await db.get(NovelChapter, chapter_id)
    if not ch:
        raise HTTPException(404, "章节不存在")
    await _get_project(db, ch.project_id, user.id)

    if ch.script_status in ("generating",):
        raise HTTPException(409, "脚本正在生成中，请稍候")

    ch.script_status = "generating"
    await db.commit()

    from app.novel_tasks import generate_novel_script_task
    generate_novel_script_task.delay(chapter_id)
    return {"detail": "脚本生成任务已提交", "chapter_id": chapter_id}


@router.patch("/chapters/{chapter_id}/script")
async def edit_script(
    chapter_id: int,
    body: ScriptEditRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ch = await db.get(NovelChapter, chapter_id)
    if not ch:
        raise HTTPException(404, "章节不存在")
    await _get_project(db, ch.project_id, user.id)
    ch.script = body.script
    if ch.script_status in ("pending", "rejected"):
        ch.script_status = "draft"
    await db.commit()
    return {"detail": "脚本已更新"}


@router.post("/chapters/{chapter_id}/script-review")
async def review_script(
    chapter_id: int,
    body: ScriptReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ch = await db.get(NovelChapter, chapter_id)
    if not ch:
        raise HTTPException(404, "章节不存在")
    await _get_project(db, ch.project_id, user.id)

    if body.action == "approve":
        ch.script_status = "approved"
        ch.script_review_notes = body.notes
    elif body.action == "reject":
        ch.script_status = "rejected"
        ch.script_review_notes = body.notes

    round_no = await _next_review_round(db, chapter_id, "script")
    review = ChapterReview(
        chapter_id=chapter_id,
        review_stage="script",
        review_round=round_no,
        status="approved" if body.action == "approve" else "rejected",
        reviewer_id=user.id,
        notes=body.notes,
    )
    db.add(review)
    await db.commit()
    return {"detail": f"脚本已{body.action}", "script_status": ch.script_status}


# ━━ 视频生成 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/chapters/{chapter_id}/generate-video")
async def generate_video(
    chapter_id: int,
    body: GenerateVideoRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ch = await db.get(NovelChapter, chapter_id)
    if not ch:
        raise HTTPException(404, "章节不存在")
    await _get_project(db, ch.project_id, user.id)

    if ch.script_status != "approved":
        raise HTTPException(400, "脚本未通过审核，请先审核通过")
    if ch.video_status in ("generating", "compositing"):
        raise HTTPException(409, "视频正在生成中，请稍候")

    if body.bgm_id is not None:
        ch.bgm_id = body.bgm_id
    ch.bgm_volume = body.bgm_volume
    ch.video_status = "generating"
    await db.commit()

    from app.novel_tasks import generate_chapter_video_task
    generate_chapter_video_task.delay(chapter_id)
    return {"detail": "视频生成任务已提交", "chapter_id": chapter_id}


# ━━ 成片审核 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/chapters/{chapter_id}/video-review")
async def review_video(
    chapter_id: int,
    body: VideoReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ch = await db.get(NovelChapter, chapter_id)
    if not ch:
        raise HTTPException(404, "章节不存在")
    await _get_project(db, ch.project_id, user.id)

    round_no = await _next_review_round(db, chapter_id, "video")
    items_json = [item.model_dump() for item in body.items] if body.items else None

    if body.action == "approve":
        ch.video_status = "approved"
        ch.video_review_notes = body.notes
    elif body.action == "reject":
        ch.video_status = "rejected"
        ch.video_review_notes = body.notes

    review = ChapterReview(
        chapter_id=chapter_id,
        review_stage="video",
        review_round=round_no,
        status="approved" if body.action == "approve" else "rejected",
        reviewer_id=user.id,
        notes=body.notes,
        items=items_json,
    )
    db.add(review)
    await db.commit()
    return {"detail": f"成片已{body.action}", "video_status": ch.video_status}


@router.post("/chapters/{chapter_id}/regenerate-scenes")
async def regenerate_scenes(
    chapter_id: int,
    body: RegenerateSceneRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ch = await db.get(NovelChapter, chapter_id)
    if not ch:
        raise HTTPException(404, "章节不存在")
    await _get_project(db, ch.project_id, user.id)

    if not body.scene_ids:
        raise HTTPException(400, "请指定要重做的场景 ID")

    ch.video_status = "generating"
    await db.commit()

    from app.novel_tasks import regenerate_scene_assets_task
    regenerate_scene_assets_task.delay(chapter_id, body.scene_ids, body.target)
    return {"detail": "增量重做任务已提交", "scene_ids": body.scene_ids}


# ━━ 审核记录 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/chapters/{chapter_id}/reviews", response_model=list[ReviewOut])
async def list_reviews(
    chapter_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ch = await db.get(NovelChapter, chapter_id)
    if not ch:
        raise HTTPException(404, "章节不存在")
    await _get_project(db, ch.project_id, user.id)
    rows = (await db.execute(
        select(ChapterReview)
        .where(ChapterReview.chapter_id == chapter_id)
        .order_by(ChapterReview.created_at.desc())
    )).scalars().all()
    return rows


# ━━ BGM 库 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/bgm", response_model=list[BgmOut])
async def list_bgm(
    mood: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(BgmLibrary)
    if mood:
        q = q.where(BgmLibrary.mood == mood)
    rows = (await db.execute(q.order_by(BgmLibrary.created_at.desc()))).scalars().all()
    return rows


@router.post("/bgm", response_model=BgmOut)
async def upload_bgm(
    name: str = Query(...),
    mood: str = Query("peaceful"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    bgm_dir = Path(settings.novel_assets_dir) / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)

    fname = f"bgm_{user.id}_{file.filename}"
    dest = bgm_dir / fname
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    dur = ffprobe_duration(dest)
    bgm = BgmLibrary(
        user_id=user.id,
        name=name,
        mood=mood,
        file_path=str(dest),
        duration_sec=dur,
        source="custom",
    )
    db.add(bgm)
    await db.commit()
    await db.refresh(bgm)
    return bgm


@router.delete("/bgm/{bgm_id}")
async def delete_bgm(
    bgm_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    bgm = await db.get(BgmLibrary, bgm_id)
    if not bgm:
        raise HTTPException(404, "BGM 不存在")
    if bgm.user_id and bgm.user_id != user.id:
        raise HTTPException(403, "无权删除")
    await db.delete(bgm)
    await db.commit()
    return {"detail": "已删除"}


# ━━ 辅助函数 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _get_project(db: AsyncSession, project_id: int, user_id: int) -> NovelProject:
    proj = await db.get(NovelProject, project_id)
    if not proj:
        raise HTTPException(404, "项目不存在")
    if proj.user_id != user_id:
        raise HTTPException(403, "无权访问")
    return proj


async def _next_review_round(db: AsyncSession, chapter_id: int, stage: str) -> int:
    n = await db.scalar(
        select(func.count()).where(
            ChapterReview.chapter_id == chapter_id,
            ChapterReview.review_stage == stage,
        )
    )
    return (n or 0) + 1


def _project_out(proj: NovelProject) -> ProjectOut:
    return ProjectOut(
        id=proj.id,
        user_id=proj.user_id,
        novel_slug=proj.novel_slug,
        novel_title=proj.novel_title,
        novel_author=proj.novel_author,
        novel_intro=proj.novel_intro,
        cover_url=proj.cover_url,
        narrator_voice_id=proj.narrator_voice_id,
        visual_style=proj.visual_style,
        default_bgm_id=proj.default_bgm_id,
        video_orientation=proj.video_orientation,
        status=proj.status,
        chapter_count=0,
        character_count=0,
        created_at=proj.created_at,
        updated_at=proj.updated_at,
    )


async def _project_out_async(db: AsyncSession, proj: NovelProject) -> ProjectOut:
    ch_count = await db.scalar(
        select(func.count()).where(NovelChapter.project_id == proj.id)
    ) or 0
    char_count = await db.scalar(
        select(func.count()).where(NovelCharacter.project_id == proj.id)
    ) or 0
    out = _project_out(proj)
    out.chapter_count = ch_count
    out.character_count = char_count
    return out
