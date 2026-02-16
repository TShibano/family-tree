from __future__ import annotations

import tempfile
from pathlib import Path

from moviepy import ImageClip, concatenate_videoclips
from PIL import Image

from family_tree.graph_builder import (
    build_graph_with_persons,
    compute_scene_order,
)
from family_tree.models import Family
from family_tree.renderer import render_graph

# 各シーンの表示秒数
SCENE_DURATION = 2.0
# 動画の FPS
FPS = 24


def generate_scene_frames(family: Family, tmp_dir: Path) -> list[Path]:
    """シーン順にフレーム画像（PNG）を累積的に生成する。

    Returns:
        各シーンの累積フレーム画像パスのリスト
    """
    scene_order = compute_scene_order(family)
    frames: list[Path] = []
    visible_ids: set[int] = set()

    for i, scene_ids in enumerate(scene_order):
        visible_ids.update(scene_ids)
        dot = build_graph_with_persons(family, visible_ids)
        frame_path = tmp_dir / f"scene_{i}.png"
        render_graph(dot, frame_path, fmt="png")
        frames.append(frame_path)

    return frames


def create_animation(
    family: Family,
    output_path: str | Path,
    scene_duration: float = SCENE_DURATION,
    fps: int = FPS,
) -> Path:
    """家系図のアニメーション動画（MP4）を生成する。

    シーン単位でカット切り替えで展開される。

    Args:
        family: Family オブジェクト
        output_path: 出力MP4ファイルパス
        scene_duration: 各シーンの表示秒数
        fps: 動画のフレームレート

    Returns:
        出力されたファイルのパス
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        frames = generate_scene_frames(family, Path(tmp_dir))

        if not frames:
            raise ValueError("フレームが生成されませんでした")

        # 最終フレーム（全員表示）のサイズを基準にする
        final_img = Image.open(frames[-1])
        target_w, target_h = final_img.size
        final_img.close()

        clips: list[ImageClip] = []
        for i, frame_path in enumerate(frames):
            # 各フレームを白背景でターゲットサイズに統一
            img = Image.open(frame_path)
            if img.size != (target_w, target_h):
                canvas = Image.new("RGB", (target_w, target_h), (255, 255, 255))
                offset_x = (target_w - img.width) // 2
                offset_y = (target_h - img.height) // 2
                canvas.paste(img, (offset_x, offset_y))
                resized_path = Path(tmp_dir) / f"scene_{i}_resized.png"
                canvas.save(str(resized_path))
                img.close()
                frame_path = resized_path
            else:
                img.close()

            clip = ImageClip(str(frame_path)).with_duration(scene_duration)
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose")
        video.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            logger=None,
        )
        video.close()

    return output_path
