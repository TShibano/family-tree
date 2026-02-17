"""Pillow を使って家系図のフレームを描画する。

レイアウト座標に基づいて人物ブロックと線を描画する。
線の部分描画（進捗率）をサポートし、アニメーションに利用できる。
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from family_tree.layout_engine import EdgeLayout, GraphLayout, NodeLayout
from family_tree.models import Family, Sex

# 描画色
COLOR_MALE_FILL = (173, 216, 230)  # lightblue
COLOR_FEMALE_FILL = (255, 182, 193)  # lightpink
COLOR_MALE_BORDER = (100, 149, 237)  # cornflowerblue
COLOR_FEMALE_BORDER = (219, 112, 147)  # palevioletred
COLOR_MARRIAGE_LINE = (139, 0, 0)  # darkred
COLOR_CHILD_LINE = (77, 77, 77)  # gray30
COLOR_TEXT = (30, 30, 30)
COLOR_BG = (255, 255, 255)

# 描画パラメータ
PADDING = 40  # グラフ周囲の余白 (px)
LINE_WIDTH_MARRIAGE = 3
LINE_WIDTH_CHILD = 2
BORDER_WIDTH = 2

# フォントサイズ
FONT_SIZE_NAME = 14
FONT_SIZE_DATE = 11


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """フォントを取得する。システムフォントが見つからない場合はデフォルトを使用。"""
    font_candidates = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for font_path in font_candidates:
        try:
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

    def __init__(self, layout: GraphLayout, family: Family) -> None:
        self.layout = layout
        self.family = family
        self.font_name = _get_font(FONT_SIZE_NAME)
        self.font_date = _get_font(FONT_SIZE_DATE)
        # キャンバスサイズ (余白を含む)
        self.canvas_width = int(layout.width + PADDING * 2)
        self.canvas_height = int(layout.height + PADDING * 2)

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
        img = Image.new("RGB", (self.canvas_width, self.canvas_height), COLOR_BG)
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

        x0 = node.left + PADDING
        y0 = node.top + PADDING
        x1 = node.right + PADDING
        y1 = node.bottom + PADDING

        fill = COLOR_MALE_FILL if person.sex == Sex.M else COLOR_FEMALE_FILL
        border = COLOR_MALE_BORDER if person.sex == Sex.M else COLOR_FEMALE_BORDER

        # 矩形を描画
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=border, width=BORDER_WIDTH)

        # テキストを描画
        name_text = person.name
        date_text = str(person.birth_date)

        # 名前（中央揃え）
        name_bbox = draw.textbbox((0, 0), name_text, font=self.font_name)
        name_w = name_bbox[2] - name_bbox[0]
        name_x = (x0 + x1) / 2 - name_w / 2
        name_y = y0 + (y1 - y0) * 0.2

        # 生年月日（中央揃え）
        date_bbox = draw.textbbox((0, 0), date_text, font=self.font_date)
        date_w = date_bbox[2] - date_bbox[0]
        date_x = (x0 + x1) / 2 - date_w / 2
        date_y = y0 + (y1 - y0) * 0.55

        draw.text((name_x, name_y), name_text, fill=COLOR_TEXT, font=self.font_name)
        draw.text((date_x, date_y), date_text, fill=COLOR_TEXT, font=self.font_date)

    def _draw_edge(
        self, draw: ImageDraw.ImageDraw, edge: EdgeLayout, progress: float
    ) -> None:
        """エッジ（線）を描画する。progress=1.0で完全表示。"""
        if not edge.points or progress <= 0:
            return

        # PADDING オフセットを適用
        offset_points = [(p[0] + PADDING, p[1] + PADDING) for p in edge.points]

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
                color = COLOR_MARRIAGE_LINE
                width = LINE_WIDTH_MARRIAGE
            else:
                color = COLOR_CHILD_LINE
                width = LINE_WIDTH_CHILD
        elif is_marriage:
            color = COLOR_MARRIAGE_LINE
            width = LINE_WIDTH_MARRIAGE
        else:
            color = COLOR_CHILD_LINE
            width = LINE_WIDTH_CHILD

        # 線を描画
        for i in range(len(draw_points) - 1):
            draw.line(
                [draw_points[i], draw_points[i + 1]],
                fill=color,
                width=width,
            )
