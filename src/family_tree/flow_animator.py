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

from family_tree.frame_drawer import FrameDrawer
from family_tree.graph_builder import build_graph_with_persons
from family_tree.layout_engine import EdgeLayout, GraphLayout, extract_layout, scale_node_widths
from family_tree.models import Family

# デフォルトパラメータ
DEFAULT_FPS = 24
DEFAULT_LINE_DURATION = 0.5  # 線アニメーション秒数
DEFAULT_PAUSE_DURATION = 0.3  # シーン間の静止秒数
DEFAULT_FINAL_PAUSE = 2.0  # 最後の全体表示秒数


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


def _merge_marriage_edges(
    layout: GraphLayout, person_id: int, spouse_id: int
) -> list[EdgeLayout]:
    """婚姻関係の2本のエッジを1本の連続パスに結合して返す。

    person1 → couple_node → person2 の2本のエッジのポイント列を結合し、
    person1 側から person2 側へ伸びる1本の連続エッジを生成する。
    """
    p1 = min(person_id, spouse_id)
    p2 = max(person_id, spouse_id)
    couple_key = f"couple_{p1}_{p2}"

    # person1 → couple_node のエッジ
    edges_to_couple = _find_edges(layout, str(p1), couple_key)
    # couple_node → person2 のエッジ
    edges_from_couple = _find_edges(layout, couple_key, str(p2))

    if edges_to_couple and edges_from_couple:
        edge1 = edges_to_couple[0]
        edge2 = edges_from_couple[0]

        # edge1 のポイント列: person1 側 → couple_node 方向に並べる
        pts1 = list(edge1.points)
        # tail が couple_key の場合は逆順にする（person1 から始めたい）
        if edge1.tail == couple_key:
            pts1 = pts1[::-1]

        # edge2 のポイント列: couple_node → person2 方向に並べる
        pts2 = list(edge2.points)
        # tail が person2 の場合は逆順にする（couple_node から始めたい）
        if edge2.tail == str(p2):
            pts2 = pts2[::-1]

        # 結合（couple_node 付近の重複点を除去）
        merged_points = pts1 + pts2[1:]

        return [EdgeLayout(tail=str(p1), head=str(p2), points=merged_points)]

    # 結合できない場合は個別のエッジをそのまま返す
    return edges_to_couple + edges_from_couple


def _find_child_edges(
    layout: GraphLayout,
    parent1_id: int,
    parent2_id: int,
    child_id: int,
) -> list[EdgeLayout]:
    """親子関係のエッジを返す。"""
    p1 = min(parent1_id, parent2_id)
    p2 = max(parent1_id, parent2_id)
    couple_key = f"couple_{p1}_{p2}"
    # couple_node -> child のエッジ
    edges = _find_edges(layout, couple_key, str(child_id))
    if not edges:
        # couple_node がない場合は直接親からのエッジ
        edges.extend(_find_edges(layout, str(parent1_id), str(child_id)))
        edges.extend(_find_edges(layout, str(parent2_id), str(child_id)))
    return edges


def build_action_sequence(
    family: Family,
    layout: GraphLayout,
    line_duration: float = DEFAULT_LINE_DURATION,
    pause_duration: float = DEFAULT_PAUSE_DURATION,
) -> list[AnimAction]:
    """CSVの行順に1人ずつアニメーションアクション列を構築する。

    Returns:
        AnimAction のリスト（時系列順）
    """
    actions: list[AnimAction] = []
    shown: set[int] = set()

    for person in family.persons.values():
        pid = person.id

        # この人物を表示
        actions.append(
            AnimAction(
                action_type=ActionType.APPEAR,
                duration=0.0,  # 瞬間表示
                new_person_ids=[pid],
            )
        )
        shown.add(pid)

        # 関連する線をアニメーション
        edges_to_animate: list[EdgeLayout] = []

        # 配偶者との婚姻線（配偶者が既に表示済みの場合）
        if person.spouse_id is not None and person.spouse_id in shown:
            merged = _merge_marriage_edges(layout, pid, person.spouse_id)
            edges_to_animate.extend(merged)

        # 親からの親子線（両親が既に表示済みの場合）
        if person.parent_ids:
            parents_shown = all(p in shown for p in person.parent_ids)
            if parents_shown:
                child_edges = _find_child_edges(
                    layout,
                    person.parent_ids[0],
                    person.parent_ids[1]
                    if len(person.parent_ids) > 1
                    else person.parent_ids[0],
                    pid,
                )
                edges_to_animate.extend(child_edges)

        if edges_to_animate:
            actions.append(
                AnimAction(
                    action_type=ActionType.DRAW_LINE,
                    duration=line_duration,
                    anim_edges=edges_to_animate,
                )
            )

        # シーン間の静止
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
    line_duration: float = DEFAULT_LINE_DURATION,
    pause_duration: float = DEFAULT_PAUSE_DURATION,
    final_pause: float = DEFAULT_FINAL_PAUSE,
    fps: int = DEFAULT_FPS,
) -> Path:
    """フローアニメーション動画（MP4）を生成する。

    Args:
        family: Family オブジェクト
        output_path: 出力MP4ファイルパス
        line_duration: 線アニメーション秒数
        pause_duration: シーン間の静止秒数
        final_pause: 最後の全体表示秒数
        fps: 動画のフレームレート

    Returns:
        出力されたファイルのパス
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 全員表示のグラフでレイアウトを計算
    all_ids = set(family.persons.keys())
    full_dot = build_graph_with_persons(family, all_ids)
    layout = extract_layout(full_dot)
    scale_node_widths(layout, 1.2)

    # アクションシーケンスを構築
    actions = build_action_sequence(family, layout, line_duration, pause_duration)

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
    drawer = FrameDrawer(layout, family)

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
        return np.array(img)

    clip = VideoClip(make_frame, duration=total_duration)
    clip.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        logger=None,
    )
    clip.close()

    return output_path
