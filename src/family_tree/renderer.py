from __future__ import annotations

from pathlib import Path

import graphviz
from PIL import Image

from family_tree.config import AppConfig


def render_graph(
    dot: graphviz.Digraph,
    output_path: str | Path,
    fmt: str = "png",
    config: AppConfig | None = None,
) -> Path:
    """Graphviz グラフを画像ファイルとして出力する。

    Args:
        dot: Graphviz Digraph オブジェクト
        output_path: 出力ファイルパス（例: output/tree.png）
        fmt: 出力形式（"png" または "svg"）
        config: アプリケーション設定（背景画像の合成に使用）

    Returns:
        出力されたファイルのパス
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dot.render(
        outfile=str(output_path),
        format=fmt,
        cleanup=True,
        quiet=True,
    )

    # PNG 出力時、背景画像または背景色が設定されていれば合成する
    if fmt == "png" and config is not None:
        bg_image_path = config.colors.background_image
        bg_color = config.colors.background
        if bg_image_path is not None or bg_color is not None:
            fg = Image.open(output_path).convert("RGBA")
            if bg_image_path is not None:
                bg = Image.open(bg_image_path).convert("RGBA")
                bg = bg.resize(fg.size, Image.LANCZOS).convert("RGB")
            else:
                bg = Image.new("RGB", fg.size, bg_color)  # type: ignore[arg-type]
            bg.paste(fg, mask=fg.split()[3])
            bg.save(str(output_path))

    return output_path
