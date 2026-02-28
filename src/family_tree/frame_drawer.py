"""Pillow を使って家系図のフレームを描画する。

レイアウト座標に基づいて人物ブロックと線を描画する。
線の部分描画（進捗率）をサポートし、アニメーションに利用できる。
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFont

from family_tree.config import AppConfig
from family_tree.layout_engine import EdgeLayout, GraphLayout, NodeLayout
from family_tree.models import Family, Sex


def _load_background(path: str, size: tuple[int, int]) -> Image.Image:
    """背景画像を読み込み、キャンバスサイズに合わせてリサイズして返す（RGBA）。"""
    img = Image.open(path).convert("RGBA")
    return img.resize(size, Image.LANCZOS)


def _draw_double_line(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    color: tuple[int, int, int],
    base_width: int,
) -> None:
    """2本の平行線（二重線）を描画する。"""
    single_width = max(3, base_width // 4)
    offset = base_width // 3  # 中心から各線までの距離

    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        # 線分に垂直な方向（正規化）
        px = -dy / length
        py = dx / length
        for sign in (-1, 1):
            ox = sign * offset * px
            oy = sign * offset * py
            draw.line(
                [(p1[0] + ox, p1[1] + oy), (p2[0] + ox, p2[1] + oy)],
                fill=color,
                width=single_width,
            )


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """#RRGGBB を (R, G, B) に変換する。"""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


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
        # 背景をキャッシュ（毎フレーム読み込みを避ける）
        canvas_size = (self.canvas_width, self.canvas_height)
        if config.colors.background_image is not None:
            self._cached_bg: Image.Image | None = _load_background(
                config.colors.background_image, canvas_size
            )
        elif config.colors.background is not None:
            self._cached_bg = Image.new("RGBA", canvas_size, (*config.colors.background, 255))
        else:
            self._cached_bg = None

    def draw_frame(
        self,
        visible_person_ids: dict[int, float],
        visible_edges: list[tuple[EdgeLayout, float]],
    ) -> Image.Image:
        """1フレームを描画する。

        Args:
            visible_person_ids: 表示する人物の ID → alpha (0.0〜1.0) マッピング
            visible_edges: 表示するエッジと進捗率のリスト [(edge, progress), ...]
                           progress: 0.0〜1.0

        Returns:
            描画されたフレーム画像
        """
        if self._cached_bg is not None:
            img = self._cached_bg.copy()
        else:
            img = Image.new("RGBA", (self.canvas_width, self.canvas_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # エッジを先に描画（ノードの下に表示）
        for edge, progress in visible_edges:
            self._draw_edge(draw, edge, progress)

        # alpha=1.0 の人物は直接描画（効率優先）
        for pid, alpha in visible_person_ids.items():
            if alpha >= 1.0:
                node_name = str(pid)
                if node_name in self.layout.nodes:
                    person = self.family.get_person(pid)
                    if person is not None:
                        self._draw_person_node(draw, self.layout.nodes[node_name], person)

        # alpha < 1.0 の人物はオーバーレイ経由でフェードイン合成
        # ImageDraw の RGBA 描画はバージョン依存のため、
        # 透明オーバーレイ → alpha スケール → alpha_composite で確実に合成する
        fading = [(pid, a) for pid, a in visible_person_ids.items() if 0.0 < a < 1.0]
        if fading:
            # 同じ alpha 値のノードは1枚のオーバーレイにまとめる
            alpha_groups: dict[float, list[int]] = {}
            for pid, a in fading:
                alpha_groups.setdefault(round(a, 4), []).append(pid)

            for alpha_val, pids in alpha_groups.items():
                overlay = Image.new("RGBA", (self.canvas_width, self.canvas_height), (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                for pid in pids:
                    node_name = str(pid)
                    if node_name in self.layout.nodes:
                        person = self.family.get_person(pid)
                        if person is not None:
                            self._draw_person_node(
                                overlay_draw, self.layout.nodes[node_name], person
                            )
                # アルファチャネルを alpha_val でスケールして合成
                r, g, b, a_ch = overlay.split()
                a_ch = a_ch.point(lambda v: int(v * alpha_val))  # noqa: B023
                overlay = Image.merge("RGBA", (r, g, b, a_ch))
                img.alpha_composite(overlay)

        return img

    def _draw_person_node(
        self, draw: ImageDraw.ImageDraw, node: NodeLayout, person: object
    ) -> None:
        """人物ブロックをフル不透明で描画する。フェードインは draw_frame() 側で制御する。"""
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
        default_fill = colors.male_fill if person.sex == Sex.M else colors.female_fill
        default_border = colors.male_border if person.sex == Sex.M else colors.female_border
        fill = _hex_to_rgb(person.fill_color) if person.fill_color else default_fill
        border = _hex_to_rgb(person.border_color) if person.border_color else default_border

        # 矩形を描画（フル不透明）
        draw.rectangle(
            [x0, y0, x1, y1],
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
        tail_node = self.layout.nodes.get(edge.tail)
        head_node = self.layout.nodes.get(edge.head)
        use_marriage_line = False
        if tail_node and head_node:
            # Y座標がほぼ同じなら婚姻線
            if abs(tail_node.cy - head_node.cy) < 5:
                use_marriage_line = True
                color = colors.marriage_line
                width = dims.line_width_marriage
            else:
                color = colors.child_line
                width = dims.line_width_child
        elif is_marriage:
            use_marriage_line = True
            color = colors.marriage_line
            width = dims.line_width_marriage
        else:
            color = colors.child_line
            width = dims.line_width_child

        # 線を描画（婚姻線は二重線）
        if use_marriage_line:
            _draw_double_line(draw, draw_points, color, width)
        else:
            for i in range(len(draw_points) - 1):
                draw.line(
                    [draw_points[i], draw_points[i + 1]],
                    fill=color,
                    width=width,
                )
