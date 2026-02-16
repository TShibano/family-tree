from __future__ import annotations

from pathlib import Path

import graphviz


def render_graph(
    dot: graphviz.Digraph,
    output_path: str | Path,
    fmt: str = "png",
) -> Path:
    """Graphviz グラフを画像ファイルとして出力する。

    Args:
        dot: Graphviz Digraph オブジェクト
        output_path: 出力ファイルパス（例: output/tree.png）
        fmt: 出力形式（"png" または "svg"）

    Returns:
        出力されたファイルのパス
    """
    output_path = Path(output_path)

    # 出力先ディレクトリの自動作成
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # graphviz の render はソースファイルを保存してから変換する。
    # outfile を指定すると直接出力先にレンダリングされる。
    dot.render(
        outfile=str(output_path),
        format=fmt,
        cleanup=True,
        quiet=True,
    )

    return output_path
