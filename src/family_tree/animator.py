from __future__ import annotations

import tempfile
from pathlib import Path

from moviepy import CompositeVideoClip, ImageClip, vfx

from family_tree.graph_builder import (
    build_graph_up_to_generation,
    compute_generations,
)
from family_tree.models import Family
from family_tree.renderer import render_graph

# 各世代の表示秒数
GENERATION_DURATION = 3.0
# フェードイン秒数
FADE_DURATION = 1.0
# 動画の FPS
FPS = 24


def generate_generation_frames(family: Family, tmp_dir: Path) -> list[Path]:
    """世代ごとにフレーム画像（PNG）を生成する。

    Returns:
        世代0から順に、累積的に人物が追加されたPNG画像パスのリスト
    """
    generations = compute_generations(family)
    max_gen = max(generations.values()) if generations else 0

    frames: list[Path] = []
    for gen in range(max_gen + 1):
        dot = build_graph_up_to_generation(family, gen)
        frame_path = tmp_dir / f"gen_{gen}.png"
        render_graph(dot, frame_path, fmt="png")
        frames.append(frame_path)

    return frames


def create_animation(
    family: Family,
    output_path: str | Path,
    generation_duration: float = GENERATION_DURATION,
    fade_duration: float = FADE_DURATION,
    fps: int = FPS,
) -> Path:
    """家系図のアニメーション動画（MP4）を生成する。

    古い世代から順にフェードインしながら表示される。

    Args:
        family: Family オブジェクト
        output_path: 出力MP4ファイルパス
        generation_duration: 各世代の表示秒数
        fade_duration: フェードインの秒数
        fps: 動画のフレームレート

    Returns:
        出力されたファイルのパス
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        frames = generate_generation_frames(family, Path(tmp_dir))

        if not frames:
            raise ValueError("フレームが生成されませんでした")

        # 全フレーム画像のサイズを最大に統一するため、最終フレーム（全世代）のサイズを基準にする
        from PIL import Image

        final_img = Image.open(frames[-1])
        target_w, target_h = final_img.size
        final_img.close()

        clips: list[ImageClip] = []
        for i, frame_path in enumerate(frames):
            # 各フレームを白背景でターゲットサイズに統一
            img = Image.open(frame_path)
            if img.size != (target_w, target_h):
                canvas = Image.new("RGB", (target_w, target_h), (255, 255, 255))
                # 中央に配置
                offset_x = (target_w - img.width) // 2
                offset_y = (target_h - img.height) // 2
                canvas.paste(img, (offset_x, offset_y))
                resized_path = Path(tmp_dir) / f"gen_{i}_resized.png"
                canvas.save(str(resized_path))
                img.close()
                frame_path = resized_path
            else:
                img.close()

            start_time = i * generation_duration
            clip = (
                ImageClip(str(frame_path))
                .with_duration(generation_duration + fade_duration)
                .with_start(start_time)
                .with_effects([vfx.CrossFadeIn(fade_duration)])
            )
            clips.append(clip)

        video = CompositeVideoClip(clips, size=(target_w, target_h))
        video.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            logger=None,
        )
        video.close()

    return output_path
