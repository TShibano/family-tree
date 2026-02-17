"""Graphviz のレイアウトエンジンを利用してノード・エッジの座標を算出する。

Graphviz の ``plain`` 形式出力をパースし、Pillow 座標系 (Y軸下向き, ピクセル) に変換する。
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import graphviz

# Graphviz のポイント単位をピクセルに変換するスケール (72 DPI)
DPI = 72
SCALE = DPI  # 1 inch = 72 points = 72 pixels


@dataclass
class NodeLayout:
    """ノードのレイアウト情報。"""

    name: str
    cx: float  # 中心X (px)
    cy: float  # 中心Y (px)
    width: float  # 幅 (px)
    height: float  # 高さ (px)

    @property
    def left(self) -> float:
        return self.cx - self.width / 2

    @property
    def right(self) -> float:
        return self.cx + self.width / 2

    @property
    def top(self) -> float:
        return self.cy - self.height / 2

    @property
    def bottom(self) -> float:
        return self.cy + self.height / 2


@dataclass
class EdgeLayout:
    """エッジのレイアウト情報。"""

    tail: str
    head: str
    points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class GraphLayout:
    """グラフ全体のレイアウト情報。"""

    width: float  # グラフ全体の幅 (px)
    height: float  # グラフ全体の高さ (px)
    nodes: dict[str, NodeLayout] = field(default_factory=dict)
    edges: list[EdgeLayout] = field(default_factory=list)


def extract_layout(dot: graphviz.Digraph) -> GraphLayout:
    """Graphviz Digraph からレイアウト座標を抽出する。

    Graphviz の ``plain`` 形式出力をパースし、ピクセル座標に変換して返す。

    Args:
        dot: Graphviz Digraph オブジェクト

    Returns:
        GraphLayout オブジェクト
    """
    # Digraph のソースを一時ファイルに書き出して dot コマンドで plain 出力を得る
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gv", delete=False) as f:
        f.write(dot.source)
        gv_path = Path(f.name)

    try:
        result = subprocess.run(
            ["dot", "-Tplain", str(gv_path)],
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        gv_path.unlink(missing_ok=True)

    return _parse_plain(result.stdout)


def _parse_plain(plain_text: str) -> GraphLayout:
    """Graphviz plain 形式のテキストをパースする。

    plain 形式:
        graph scale width height
        node name x y width height label style shape color fillcolor
        edge tail head n x1 y1 ... xn yn [label xl yl] style color
        stop
    座標は inch 単位、Y軸上向き。ピクセル (Y軸下向き) に変換する。
    """
    graph_width = 0.0
    graph_height = 0.0
    nodes: dict[str, NodeLayout] = {}
    edges: list[EdgeLayout] = []

    for line in plain_text.strip().splitlines():
        parts = line.split()
        if not parts:
            continue

        if parts[0] == "graph":
            # graph scale width height
            graph_width = float(parts[2]) * SCALE
            graph_height = float(parts[3]) * SCALE

        elif parts[0] == "node":
            # node name x y width height label ...
            name = parts[1]
            x = float(parts[2]) * SCALE
            y = float(parts[3]) * SCALE
            w = float(parts[4]) * SCALE
            h = float(parts[5]) * SCALE
            # Y軸反転: y_pixel = graph_height - y_graphviz
            cy = graph_height - y
            nodes[name] = NodeLayout(name=name, cx=x, cy=cy, width=w, height=h)

        elif parts[0] == "edge":
            # edge tail head n x1 y1 ... xn yn [label xl yl] style color
            tail = parts[1]
            head = parts[2]
            n = int(parts[3])
            points: list[tuple[float, float]] = []
            for j in range(n):
                px = float(parts[4 + 2 * j]) * SCALE
                py = graph_height - float(parts[4 + 2 * j + 1]) * SCALE
                points.append((px, py))
            edges.append(EdgeLayout(tail=tail, head=head, points=points))

        elif parts[0] == "stop":
            break

    return GraphLayout(
        width=graph_width,
        height=graph_height,
        nodes=nodes,
        edges=edges,
    )
