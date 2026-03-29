"""小说章节视频合成 — FFmpeg 组装。

将各 scene 的音频+图片素材拼接为完整章节视频。
"""
import shutil
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.tts_audio import ffprobe_duration, run_ffmpeg


def _load_font(size: int):
    for p in (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "C:\\Windows\\Fonts\\msyh.ttc",
    ):
        fp = Path(p)
        if fp.is_file():
            try:
                return ImageFont.truetype(str(fp), size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_scene_image(
    visual_prompt: str,
    mood: str,
    out_path: Path,
    width: int = 1080,
    height: int = 1920,
    speaker: str | None = None,
    text: str | None = None,
) -> None:
    """生成场景占位图（PIL 文字卡）。后续可替换为 SiliconFlow AI 生图。"""
    mood_colors = {
        "melancholy": (40, 50, 80),
        "sad": (50, 50, 70),
        "happy": (80, 120, 60),
        "tense": (100, 30, 30),
        "peaceful": (60, 100, 90),
        "romantic": (120, 60, 80),
        "epic": (80, 60, 30),
        "comedy": (120, 110, 40),
        "mysterious": (30, 30, 60),
        "neutral": (60, 60, 60),
        "ambitious": (70, 70, 40),
        "curious": (50, 80, 80),
        "warm": (90, 70, 50),
        "heroic": (90, 60, 30),
    }
    bg_color = mood_colors.get(mood, (60, 60, 60))
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    title_font = _load_font(42)
    body_font = _load_font(32)
    sub_font = _load_font(28)

    y = height // 3
    for line in textwrap.wrap(visual_prompt[:200], width=18):
        draw.text((60, y), line, fill=(255, 255, 255), font=title_font)
        y += 52

    if speaker and speaker != "narrator":
        y += 30
        draw.text((60, y), f"【{speaker}】", fill=(255, 220, 100), font=body_font)
        y += 42

    if text:
        y += 10
        for line in textwrap.wrap(text[:120], width=22):
            draw.text((60, y), line, fill=(220, 220, 220), font=sub_font)
            y += 38

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path), format="PNG")


def image_to_video(image_path: Path, duration: float, out_path: Path) -> None:
    """将静态图片转为指定时长的视频（Ken Burns 缩放效果）。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dur = max(duration, 1.0)
    run_ffmpeg([
        "-y", "-loop", "1", "-i", str(image_path),
        "-vf", f"zoompan=z='min(zoom+0.0008,1.15)':d={int(dur*25)}:s=1080x1920:fps=25",
        "-t", str(dur),
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(out_path),
    ])


def _generate_silence(duration: float, out_path: Path) -> None:
    """生成指定时长的静音 MP3。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
        "-t", str(max(duration, 0.5)),
        "-c:a", "libmp3lame", "-q:a", "9",
        str(out_path),
    ])


def compose_chapter_video(
    scene_videos: list[Path],
    scene_audios: list[Path],
    bgm_path: Path | None,
    bgm_volume: float,
    output_path: Path,
    title_text: str = "",
    subtitle_texts: list[str] | None = None,
) -> None:
    """将所有 scene 视频+音频拼接为完整章节视频。

    策略：先分别拼接视频和音频轨道，再合并+混BGM，避免部分 scene 无音轨导致的问题。
    """
    import tempfile

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # 1) 为无音频的 scene 生成静音
        fixed_audios: list[Path] = []
        for i, (vid, aud) in enumerate(zip(scene_videos, scene_audios)):
            if aud.is_file() and aud.stat().st_size > 100:
                fixed_audios.append(aud)
            else:
                vid_dur = ffprobe_duration(vid) or 3.0
                silence = tmp / f"silence_{i:03d}.mp3"
                _generate_silence(vid_dur, silence)
                fixed_audios.append(silence)

        # 2) 每个 segment 合成为带音轨的 mp4
        segments: list[Path] = []
        for i, (vid, aud) in enumerate(zip(scene_videos, fixed_audios)):
            seg = tmp / f"seg_{i:03d}.mp4"
            run_ffmpeg([
                "-y", "-i", str(vid), "-i", str(aud),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(seg),
            ])
            segments.append(seg)

        # 3) concat 所有 segments
        concat_list = tmp / "concat.txt"
        lines = [f"file '{seg}'" for seg in segments]
        concat_list.write_text("\n".join(lines), encoding="utf-8")

        concat_out = tmp / "concat.mp4"
        run_ffmpeg([
            "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy",
            str(concat_out),
        ])

        # 4) 混入 BGM
        if bgm_path and bgm_path.is_file():
            final = tmp / "with_bgm.mp4"
            filt = (
                f"[1:a]volume={bgm_volume}[bgm];"
                f"[0:a]volume=1.0[voice];"
                f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            run_ffmpeg([
                "-y", "-i", str(concat_out),
                "-stream_loop", "-1", "-i", str(bgm_path),
                "-filter_complex", filt,
                "-map", "0:v:0", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(final),
            ])
            shutil.copy2(final, output_path)
        else:
            shutil.copy2(concat_out, output_path)
