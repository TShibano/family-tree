"""Graphviz のレイアウトエンジンを利用してノード・エッジの座標を算出する。

Graphviz の ``plain`` 形式出力をパースし、Pillow 座標系 (Y軸下向き, ピクセル) に変換する。
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import graphviz

# Graphviz のポイント単位をピクセルに変換するスケール (432 DPI = 6x)
DPI = 432
SCALE = DPI  # 1 inch = 432 pixels


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

    layout = GraphLayout(
        width=graph_width,
        height=graph_height,
        nodes=nodes,
        edges=edges,
    )
    fix_edge_endpoints(layout)
    return layout


def scale_node_widths(layout: GraphLayout, factor: float) -> None:
    """全ノードの幅をスケールし、エッジ端点を再補正する。

    中心座標は変更せず、幅だけを拡大/縮小する。
    point ノード（couple ノード等）はスケールしない。
    """
    for node in layout.nodes.values():
        if node.width >= 2:  # point ノードを除外
            node.width *= factor
    fix_edge_endpoints(layout)


def fix_edge_endpoints(layout: GraphLayout) -> None:
    """エッジの端点をノード境界に補正する。

    Graphviz はノードを楕円形として端点を計算するため、
    矩形ノードとして描画する場合にずれが生じる。
    tail ノードの適切な境界点と head ノードの適切な境界点に端点を補正する。
    """
    for edge in layout.edges:
        tail_node = layout.nodes.get(edge.tail)
        head_node = layout.nodes.get(edge.head)

        if tail_node and edge.points:
            # tail の端点を補正
            edge.points[0] = _snap_to_node_border(
                tail_node, edge.points[1] if len(edge.points) > 1 else edge.points[0]
            )

        if head_node and edge.points:
            # head の端点を補正
            edge.points[-1] = _snap_to_node_border(
                head_node,
                edge.points[-2] if len(edge.points) > 1 else edge.points[-1],
            )


def _snap_to_node_border(
    node: NodeLayout, toward: tuple[float, float]
) -> tuple[float, float]:
    """ノードの境界上で、toward 方向に最も近い点を返す。

    矩形ノードの上下左右の辺のうち、toward からの方向に最も適切な辺の点を返す。
    point ノード (width/height が非常に小さい) の場合は中心を返す。
    """
    # point ノード（couple ノード等）の場合は中心を返す
    if node.width < 2 and node.height < 2:
        return (node.cx, node.cy)

    dx = toward[0] - node.cx
    dy = toward[1] - node.cy

    # 方向に応じてノードの適切な辺の中央を返す
    if abs(dy) > abs(dx):
        # 上または下方向
        if dy > 0:
            return (node.cx, node.bottom)  # 下辺
        else:
            return (node.cx, node.top)  # 上辺
    else:
        # 左または右方向
        if dx > 0:
            return (node.right, node.cy)  # 右辺
        else:
            return (node.left, node.cy)  # 左辺
