"""混音等小工具（FFmpeg）。"""
from pathlib import Path

from app.services.tts_audio import run_ffmpeg


def mix_voice_and_bgm(
    voice_mp3: Path,
    bgm_path: Path,
    out_mp3: Path,
    *,
    voice_volume: float = 1.0,
    bgm_volume: float = 0.22,
) -> None:
    """将口播与人声背景音乐混合为单条音轨。"""
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    # amix：两路对齐到较短时长
    filt = (
        f"[0:a]volume={voice_volume}[a0];"
        f"[1:a]volume={bgm_volume}[a1];"
        f"[a0][a1]amix=inputs=2:duration=shortest:dropout_transition=0[aout]"
    )
    run_ffmpeg(
        [
            "-y",
            "-i",
            str(voice_mp3),
            "-i",
            str(bgm_path),
            "-filter_complex",
            filt,
            "-map",
            "[aout]",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(out_mp3),
        ]
    )


def loop_bgm_to_length(bgm_path: Path, duration_sec: float, out_audio: Path) -> None:
    """将 BGM 循环/截断到指定时长（用于纯 BGM 模式）。"""
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    dur = max(duration_sec, 1.0)
    run_ffmpeg(
        [
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(bgm_path),
            "-t",
            str(dur),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(out_audio),
        ]
    )
