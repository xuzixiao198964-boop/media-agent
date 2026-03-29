import shutil
import tempfile
import textwrap
from pathlib import Path
import re

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


def _banner_png(lines: list[str], out_path: Path, width: int = 1080, height: int = 420) -> None:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 160))
    img.alpha_composite(overlay, (0, 0))
    font = _load_font(40)
    y = 24
    for line in lines:
        for sub in textwrap.wrap(line, width=16):
            draw.text((36, y), sub, fill=(255, 255, 255, 255), font=font)
            y += 48
            if y > height - 40:
                break
        if y > height - 40:
            break
    img.convert("RGB").save(out_path, format="PNG")


def _format_srt_time(sec: float) -> str:
    sec = max(0.0, sec)
    ms = int((sec - int(sec)) * 1000)
    s = int(sec) % 60
    m = (int(sec) // 60) % 60
    h = int(sec) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _split_subtitle_lines(text: str, max_chars: int = 18) -> list[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    chunks = re.split(r"[。！？!?；;，,]\s*", text)
    chunks = [c.strip() for c in chunks if c.strip()]
    out: list[str] = []
    for c in chunks:
        out.extend(textwrap.wrap(c, width=max_chars) or [c])
    return out


def _write_simple_srt(text: str, total_seconds: float, out_path: Path) -> bool:
    lines = _split_subtitle_lines(text)
    if not lines:
        return False
    total_seconds = max(total_seconds, 1.0)
    seg = total_seconds / max(len(lines), 1)
    rows: list[str] = []
    t = 0.0
    for i, line in enumerate(lines, start=1):
        start = t
        end = min(total_seconds, t + seg)
        t = end
        rows.append(str(i))
        rows.append(f"{_format_srt_time(start)} --> {_format_srt_time(end)}")
        rows.append(line)
        rows.append("")
    out_path.write_text("\n".join(rows), encoding="utf-8")
    return True


def render_short_video(
    input_video: Path,
    audio_mp3: Path,
    title: str,
    summary: str,
    subtitle_text: str,
    output_mp4: Path,
    max_seconds: float = 60.0,
) -> None:
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp_name:
        tdir = Path(tmp_name)
        banner = tdir / "banner.png"
        lines = [title[:80]]
        if summary:
            lines.append(summary[:200])
        _banner_png(lines, banner)

        scaled = tdir / "scaled.mp4"
        dur = ffprobe_duration(input_video)
        use_trim = bool(dur and dur > max_seconds)

        run_ffmpeg(
            [
                "-y",
                "-i",
                str(input_video),
                *([] if not use_trim else ["-t", str(max_seconds)]),
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-an",
                str(scaled),
            ]
        )

        overlaid = tdir / "with_banner.mp4"
        run_ffmpeg(
            [
                "-y",
                "-i",
                str(scaled),
                "-i",
                str(banner),
                "-filter_complex",
                "[0:v][1:v]overlay=0:main_h-overlay_h",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                str(overlaid),
            ]
        )

        subtitled = tdir / "with_subtitles.mp4"
        sub_file = tdir / "captions.srt"
        audio_dur = ffprobe_duration(audio_mp3) or max_seconds
        has_sub = _write_simple_srt(subtitle_text, audio_dur, sub_file)
        if has_sub:
            # 优先硬字幕，若运行环境缺少 libass 则降级为不加字幕继续出片，避免流水线中断。
            try:
                run_ffmpeg(
                    [
                        "-y",
                        "-i",
                        str(overlaid),
                        "-vf",
                        f"subtitles={str(sub_file)}:force_style='FontSize=16,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=1.2,MarginV=56,Alignment=2'",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "23",
                        str(subtitled),
                    ]
                )
            except Exception:
                shutil.copy2(overlaid, subtitled)
        else:
            shutil.copy2(overlaid, subtitled)

        with_audio = tdir / "with_audio.mp4"
        run_ffmpeg(
            [
                "-y",
                "-i",
                str(subtitled),
                "-i",
                str(audio_mp3),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(with_audio),
            ]
        )
        shutil.copy2(with_audio, output_mp4)
