"""Pillow を使って家系図のフレームを描画する。

レイアウト座標に基づいて人物ブロックと線を描画する。
線の部分描画（進捗率）をサポートし、アニメーションに利用できる。
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from family_tree.config import AppConfig
from family_tree.layout_engine import EdgeLayout, GraphLayout, NodeLayout
from family_tree.models import Family, Sex


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """フォントを取得する。システムフォントが見つからない場合はデフォルトを使用。"""
    # (パス, ttcインデックス) のリスト。None はデフォルトインデックス。
    font_candidates: list[tuple[str, int | None]] = [
        ("/System/Library/Fonts/ヒラギノ明朝 ProN.ttc", 2),  # W6（太字）
        ("/System/Library/Fonts/ヒラギノ明朝 ProN.ttc", None),  # W3
        ("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", None),
        ("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", None),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", None),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", None),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", None),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", None),
    ]
    for font_path, index in font_candidates:
        try:
            if index is not None:
                return ImageFont.truetype(font_path, size, index=index)
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _interpolate_point(
    start: tuple[float, float], end: tuple[float, float], t: float
) -> tuple[float, float]:
    """2点間を線形補間する。t=0で始点、t=1で終点。"""
    return (
        start[0] + (end[0] - start[0]) * t,
        start[1] + (end[1] - start[1]) * t,
    )


def _interpolate_points_along_path(
    points: list[tuple[float, float]], t: float
) -> list[tuple[float, float]]:
    """パス上の点列を進捗率 t まで補間する。

    Args:
        points: パスの制御点リスト
        t: 進捗率 (0.0〜1.0)

    Returns:
        描画すべき点列（始点から進捗位置まで）
    """
    if t <= 0 or len(points) < 2:
        return [points[0]] if points else []
    if t >= 1.0:
        return list(points)

    # 各セグメントの長さを計算
    segment_lengths: list[float] = []
    for i in range(len(points) - 1):
        dx = points[i + 1][0] - points[i][0]
        dy = points[i + 1][1] - points[i][1]
        segment_lengths.append((dx**2 + dy**2) ** 0.5)

    total_length = sum(segment_lengths)
    if total_length == 0:
        return [points[0]]

    target_length = total_length * t
    accumulated = 0.0
    result = [points[0]]

    for i, seg_len in enumerate(segment_lengths):
        if accumulated + seg_len >= target_length:
            # このセグメントの途中で止まる
            remaining = target_length - accumulated
            seg_t = remaining / seg_len if seg_len > 0 else 0
            result.append(_interpolate_point(points[i], points[i + 1], seg_t))
            break
        else:
            accumulated += seg_len
            result.append(points[i + 1])

    return result


class FrameDrawer:
    """家系図フレームの描画を管理するクラス。"""

    def __init__(self, layout: GraphLayout, family: Family, config: AppConfig) -> None:
        self.layout = layout
        self.family = family
        self.config = config
        self.font_name = _get_font(config.dimensions.font_size_name)
        # キャンバスサイズ (余白を含む)
        padding = config.dimensions.padding
        self.canvas_width = int(layout.width + padding * 2)
        self.canvas_height = int(layout.height + padding * 2)

    def draw_frame(
        self,
        visible_person_ids: set[int],
        visible_edges: list[tuple[EdgeLayout, float]],
    ) -> Image.Image:
        """1フレームを描画する。

        Args:
            visible_person_ids: 表示する人物のIDセット
            visible_edges: 表示するエッジと進捗率のリスト [(edge, progress), ...]
                           progress: 0.0〜1.0

        Returns:
            描画されたフレーム画像
        """
        img = Image.new("RGB", (self.canvas_width, self.canvas_height), self.config.colors.background)
        draw = ImageDraw.Draw(img)

        # エッジを先に描画（ノードの下に表示）
        for edge, progress in visible_edges:
            self._draw_edge(draw, edge, progress)

        # 人物ノードを描画
        for pid in visible_person_ids:
            node_name = str(pid)
            if node_name in self.layout.nodes:
                person = self.family.get_person(pid)
                if person is not None:
                    self._draw_person_node(draw, self.layout.nodes[node_name], person)

        return img

    def _draw_person_node(
        self, draw: ImageDraw.ImageDraw, node: NodeLayout, person: object
    ) -> None:
        """人物ブロックを描画する。"""
        from family_tree.models import Person

        if not isinstance(person, Person):
            return

        padding = self.config.dimensions.padding
        x0 = node.left + padding
        y0 = node.top + padding
        x1 = node.right + padding
        y1 = node.bottom + padding

        colors = self.config.colors
        dims = self.config.dimensions
        fill = colors.male_fill if person.sex == Sex.M else colors.female_fill
        border = colors.male_border if person.sex == Sex.M else colors.female_border

        # 角丸矩形を描画
        draw.rounded_rectangle(
            [x0, y0, x1, y1],
            radius=dims.corner_radius,
            fill=fill,
            outline=border,
            width=dims.border_width,
        )

        # 名前（中央揃え）
        name_text = person.name
        name_bbox = draw.textbbox((0, 0), name_text, font=self.font_name)
        name_w = name_bbox[2] - name_bbox[0]
        name_h = name_bbox[3] - name_bbox[1]
        name_x = (x0 + x1) / 2 - name_w / 2
        name_y = (y0 + y1) / 2 - name_h / 2

        draw.text((name_x, name_y), name_text, fill=colors.text, font=self.font_name)

    def _draw_edge(
        self, draw: ImageDraw.ImageDraw, edge: EdgeLayout, progress: float
    ) -> None:
        """エッジ（線）を描画する。progress=1.0で完全表示。"""
        if not edge.points or progress <= 0:
            return

        padding = self.config.dimensions.padding
        colors = self.config.colors
        dims = self.config.dimensions

        # PADDING オフセットを適用
        offset_points = [(p[0] + padding, p[1] + padding) for p in edge.points]

        # 進捗率に応じて描画する点列を計算
        draw_points = _interpolate_points_along_path(offset_points, progress)

        if len(draw_points) < 2:
            return

        # 婚姻線か親子線かを判定（couple_ ノードが含まれるか）
        is_marriage = edge.tail.startswith("couple_") or edge.head.startswith("couple_")
        # 婚姻線: tail/head が couple_ ノードと人物ノードの場合
        # 同じ rank の場合は婚姻線とみなす
        tail_node = self.layout.nodes.get(edge.tail)
        head_node = self.layout.nodes.get(edge.head)
        if tail_node and head_node:
            # Y座標がほぼ同じなら婚姻線
            if abs(tail_node.cy - head_node.cy) < 5:
                color = colors.marriage_line
                width = dims.line_width_marriage
            else:
                color = colors.child_line
                width = dims.line_width_child
        elif is_marriage:
            color = colors.marriage_line
            width = dims.line_width_marriage
        else:
            color = colors.child_line
            width = dims.line_width_child

        # 線を描画
        for i in range(len(draw_points) - 1):
            draw.line(
                [draw_points[i], draw_points[i + 1]],
                fill=color,
                width=width,
            )
