"""フローアニメーション生成モジュール。

線が動きながら描画されるアニメーション動画を生成する。
- 人物ブロックは瞬間表示
- 婚姻線は伸びるアニメーション（1本の連続線として描画）
- 親子線は上から下に伸びるアニメーション
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np
from moviepy import VideoClip
from PIL import Image

from family_tree.config import AppConfig
from family_tree.frame_drawer import FrameDrawer
from family_tree.graph_builder import build_graph_with_persons
from family_tree.layout_engine import EdgeLayout, GraphLayout, extract_layout, scale_node_widths
from family_tree.models import Family


class ActionType(Enum):
    """アニメーションアクションの種類。"""

    APPEAR = "appear"  # 人物ブロックの瞬間表示
    DRAW_LINE = "draw_line"  # 線が伸びるアニメーション
    PAUSE = "pause"  # 静止


@dataclass
class AnimAction:
    """1つのアニメーションアクション。"""

    action_type: ActionType
    duration: float  # 秒数
    # APPEAR: 新たに表示する人物ID
    new_person_ids: list[int] = field(default_factory=list)
    # DRAW_LINE: アニメーションするエッジ (EdgeLayout オブジェクトを直接保持)
    anim_edges: list[EdgeLayout] = field(default_factory=list)


def _find_edges(layout: GraphLayout, tail: str, head: str) -> list[EdgeLayout]:
    """レイアウト内で指定した tail/head に一致するエッジを返す。"""
    results = []
    for edge in layout.edges:
        if edge.tail == tail and edge.head == head:
            results.append(edge)
        elif edge.tail == head and edge.head == tail:
            results.append(edge)
    return results


def _get_marriage_edges_toward_center(
    layout: GraphLayout, person_id: int, spouse_id: int
) -> list[EdgeLayout]:
    """婚姻関係のエッジを2本（各人物→中心点）返す。

    person1 側と person2 側それぞれから couple_node（仮想中心点）に向かう
    エッジを生成し、両側から同時にアニメーションする。
    """
    p1 = min(person_id, spouse_id)
    p2 = max(person_id, spouse_id)
    couple_key = f"couple_{p1}_{p2}"

    edges_to_couple = _find_edges(layout, str(p1), couple_key)
    edges_from_couple = _find_edges(layout, couple_key, str(p2))

    if not edges_to_couple or not edges_from_couple:
        return edges_to_couple + edges_from_couple

    edge1 = edges_to_couple[0]
    edge2 = edges_from_couple[0]

    # Edge 1: person1 → couple_node（person1 側から中心点へ）
    pts1 = list(edge1.points)
    if edge1.tail == couple_key:
        pts1 = pts1[::-1]

    # Edge 2: person2 → couple_node（person2 側から中心点へ）
    pts2 = list(edge2.points)
    if edge2.tail == couple_key:
        pts2 = pts2[::-1]  # couple_node→person2 を逆順に: person2→couple_node

    return [
        EdgeLayout(tail=str(p1), head=couple_key, points=pts1),
        EdgeLayout(tail=str(p2), head=couple_key, points=pts2),
    ]


def _build_comb_child_edge(
    layout: GraphLayout,
    parent1_id: int,
    parent2_id: int,
    child_id: int,
) -> list[EdgeLayout]:
    """子供への櫛（くし）形エッジを生成する。

    couple_node から child へ向かう L字パス:
      (couple_cx, couple_cy) → (couple_cx, bar_y) → (child_cx, bar_y) → (child_cx, child_top)

    bar_y は couple_node と子供の上辺の中間点。
    """
    p1 = min(parent1_id, parent2_id)
    p2 = max(parent1_id, parent2_id)
    couple_key = f"couple_{p1}_{p2}"

    couple_node = layout.nodes.get(couple_key)
    child_node = layout.nodes.get(str(child_id))

    if couple_node is None or child_node is None:
        # フォールバック: 既存エッジを返す
        edges = _find_edges(layout, couple_key, str(child_id))
        if not edges:
            edges.extend(_find_edges(layout, str(parent1_id), str(child_id)))
            edges.extend(_find_edges(layout, str(parent2_id), str(child_id)))
        return edges

    # bar_y: couple_node と子供の上辺の中間
    bar_y = (couple_node.cy + child_node.top) / 2

    points = [
        (couple_node.cx, couple_node.cy),
        (couple_node.cx, bar_y),
        (child_node.cx, bar_y),
        (child_node.cx, child_node.top),
    ]

    return [EdgeLayout(tail=couple_key, head=str(child_id), points=points)]


def _collect_groups(
    family: Family,
) -> tuple[list[str], dict[str, list[Person]]]:
    """CSVの登場順を維持しながら、グループ別に人物をまとめる。

    group 未設定の人物は "__solo_{id}__" という内部キーで個別グループ扱い。

    Returns:
        (groups_order, groups_map)
        - groups_order: グループキーの登場順リスト
        - groups_map:   グループキー -> 人物リスト
    """
    groups_order: list[str] = []
    groups_map: dict[str, list[Person]] = {}
    for person in family.persons.values():
        key = person.group if person.group else f"__solo_{person.id}__"
        if key not in groups_map:
            groups_order.append(key)
            groups_map[key] = []
        groups_map[key].append(person)
    return groups_order, groups_map


def build_action_sequence(
    family: Family,
    layout: GraphLayout,
    line_duration: float = 0.5,
    pause_duration: float = 0.3,
) -> list[AnimAction]:
    """グループ単位でアニメーションアクション列を構築する。

    各グループに対して:
      1. APPEAR   : グループ全員を同時瞬間表示
      2. DRAW_LINE: 親子線（両親が表示済みの場合、グループ全員分まとめて）
      3. DRAW_LINE: 婚姻線（配偶者が表示済みの場合、グループ全員分まとめて）
      4. PAUSE    : 静止

    group 未設定の人物は1人ずつ個別グループとして処理する。

    Returns:
        AnimAction のリスト（時系列順）
    """
    actions: list[AnimAction] = []
    shown: set[int] = set()

    groups_order, groups_map = _collect_groups(family)

    for group_key in groups_order:
        persons_in_group = groups_map[group_key]

        # 1. APPEAR（グループ全員を同時瞬間表示）
        group_ids = [p.id for p in persons_in_group]
        actions.append(
            AnimAction(
                action_type=ActionType.APPEAR,
                duration=0.0,
                new_person_ids=group_ids,
            )
        )
        shown.update(group_ids)

        # 2. DRAW_LINE: 親子線（グループ全員分をまとめて1アクション）
        child_edges: list[EdgeLayout] = []
        for person in persons_in_group:
            if person.parent_ids and all(pid in shown for pid in person.parent_ids):
                p1 = person.parent_ids[0]
                p2 = person.parent_ids[1] if len(person.parent_ids) > 1 else p1
                child_edges.extend(_build_comb_child_edge(layout, p1, p2, person.id))
        if child_edges:
            actions.append(
                AnimAction(
                    action_type=ActionType.DRAW_LINE,
                    duration=line_duration,
                    anim_edges=child_edges,
                )
            )

        # 3. DRAW_LINE: 婚姻線（同グループ内の重複を除去）
        marriage_edges: list[EdgeLayout] = []
        processed_marriages: set[tuple[int, int]] = set()
        for person in persons_in_group:
            if person.spouse_id is not None and person.spouse_id in shown:
                pair = (min(person.id, person.spouse_id), max(person.id, person.spouse_id))
                if pair not in processed_marriages:
                    processed_marriages.add(pair)
                    marriage_edges.extend(
                        _get_marriage_edges_toward_center(layout, person.id, person.spouse_id)
                    )
        if marriage_edges:
            actions.append(
                AnimAction(
                    action_type=ActionType.DRAW_LINE,
                    duration=line_duration,
                    anim_edges=marriage_edges,
                )
            )

        # 4. PAUSE
        actions.append(
            AnimAction(
                action_type=ActionType.PAUSE,
                duration=pause_duration,
            )
        )

    return actions


def create_flow_animation(
    family: Family,
    output_path: str | Path,
    config: AppConfig,
    line_duration: float | None = None,
) -> Path:
    """フローアニメーション動画（MP4）を生成する。

    Args:
        family: Family オブジェクト
        output_path: 出力MP4ファイルパス
        config: アプリケーション設定
        line_duration: 線アニメーション秒数。None の場合は config の値を使用。

    Returns:
        出力されたファイルのパス
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    anim = config.animation
    effective_line_duration = line_duration if line_duration is not None else anim.line_duration
    pause_duration = anim.pause_duration
    final_pause = anim.final_pause
    fps = anim.fps

    # 全員表示のグラフでレイアウトを計算
    all_ids = set(family.persons.keys())
    full_dot = build_graph_with_persons(family, all_ids, config.colors.background)
    layout = extract_layout(full_dot, dpi=config.dimensions.dpi)
    scale_node_widths(layout, 1.2)

    # アクションシーケンスを構築
    actions = build_action_sequence(family, layout, effective_line_duration, pause_duration)

    # 最後の全体表示を追加
    actions.append(AnimAction(action_type=ActionType.PAUSE, duration=final_pause))

    # 各アクションの開始時刻を計算
    action_starts: list[float] = []
    t = 0.0
    for action in actions:
        action_starts.append(t)
        t += action.duration
    total_duration = t

    if total_duration <= 0:
        raise ValueError("アニメーションの長さが0です")

    # フレーム描画器
    drawer = FrameDrawer(layout, family, config)

    # 状態管理: 各時刻での描画状態を計算する関数
    def make_frame(t: float) -> np.ndarray:
        """時刻 t でのフレームを生成する。"""
        visible_persons: set[int] = set()
        completed_edges: list[EdgeLayout] = []
        animating_edges: list[tuple[EdgeLayout, float]] = []

        for i, action in enumerate(actions):
            action_start = action_starts[i]
            action_end = action_start + action.duration

            if action_start > t:
                break

            if action.action_type == ActionType.APPEAR:
                visible_persons.update(action.new_person_ids)

            elif action.action_type == ActionType.DRAW_LINE:
                if t >= action_end:
                    # アニメーション完了
                    completed_edges.extend(action.anim_edges)
                else:
                    # アニメーション中
                    elapsed = t - action_start
                    progress = elapsed / action.duration if action.duration > 0 else 1.0
                    progress = min(max(progress, 0.0), 1.0)
                    for edge in action.anim_edges:
                        animating_edges.append((edge, progress))

        # 描画するエッジリストを構築
        visible_edge_list: list[tuple[EdgeLayout, float]] = []
        for edge in completed_edges:
            visible_edge_list.append((edge, 1.0))
        for edge, progress in animating_edges:
            visible_edge_list.append((edge, progress))

        img = drawer.draw_frame(visible_persons, visible_edge_list)
        # MP4 (H.264) はアルファ非対応のため RGBA を RGB へ変換する
        # 背景画像/色が設定済みならすでに不透明なので直接変換、透明なら白で合成
        if config.colors.background_image is not None or config.colors.background is not None:
            return np.array(img.convert("RGB"))
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return np.array(bg)

    clip = VideoClip(make_frame, duration=total_duration)
    clip.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        logger=None,
    )
    clip.close()

    return output_path
