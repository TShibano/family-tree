"""フローアニメーション生成モジュール。

線が動きながら描画されるアニメーション動画を生成する。
- 人物ブロックは瞬間表示
- 婚姻線は伸びるアニメーション
- 親子線は上から下に伸びるアニメーション
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np
from moviepy import VideoClip
from family_tree.frame_drawer import FrameDrawer
from family_tree.graph_builder import build_graph_with_persons, compute_scene_order
from family_tree.layout_engine import EdgeLayout, GraphLayout, extract_layout
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
    # DRAW_LINE: アニメーションするエッジのインデックス (全体レイアウトの edges 内)
    edge_indices: list[int] = field(default_factory=list)


def _find_edge_indices(layout: GraphLayout, tail: str, head: str) -> list[int]:
    """レイアウト内で指定した tail/head に一致するエッジのインデックスを返す。"""
    indices = []
    for i, edge in enumerate(layout.edges):
        if edge.tail == tail and edge.head == head:
            indices.append(i)
        elif edge.tail == head and edge.head == tail:
            indices.append(i)
    return indices


def _find_marriage_edges(
    layout: GraphLayout, person_id: int, spouse_id: int
) -> list[int]:
    """婚姻関係のエッジインデックスを返す（person - couple_node - spouse）。"""
    couple_key = f"couple_{min(person_id, spouse_id)}_{max(person_id, spouse_id)}"
    indices: list[int] = []
    indices.extend(_find_edge_indices(layout, str(person_id), couple_key))
    indices.extend(_find_edge_indices(layout, couple_key, str(spouse_id)))
    return indices


def _find_child_edges(
    layout: GraphLayout,
    parent1_id: int,
    parent2_id: int,
    child_id: int,
) -> list[int]:
    """親子関係のエッジインデックスを返す。"""
    couple_key = f"couple_{min(parent1_id, parent2_id)}_{max(parent1_id, parent2_id)}"
    # couple_node -> child のエッジ
    indices = _find_edge_indices(layout, couple_key, str(child_id))
    if not indices:
        # couple_node がない場合は直接親からのエッジ
        indices.extend(_find_edge_indices(layout, str(parent1_id), str(child_id)))
        indices.extend(_find_edge_indices(layout, str(parent2_id), str(child_id)))
    return indices


def build_action_sequence(
    family: Family,
    layout: GraphLayout,
    line_duration: float = DEFAULT_LINE_DURATION,
    pause_duration: float = DEFAULT_PAUSE_DURATION,
) -> list[AnimAction]:
    """シーン順序からアニメーションアクション列を構築する。

    Returns:
        AnimAction のリスト（時系列順）
    """
    scene_order = compute_scene_order(family)
    actions: list[AnimAction] = []
    shown: set[int] = set()

    for scene_ids in scene_order:
        if not scene_ids:
            continue

        # この人物たちを表示
        actions.append(
            AnimAction(
                action_type=ActionType.APPEAR,
                duration=0.0,  # 瞬間表示
                new_person_ids=list(scene_ids),
            )
        )

        new_ids = set(scene_ids)
        shown.update(new_ids)

        # 新たに表示された人物に関連する線をアニメーション
        edge_indices_to_animate: list[int] = []

        for pid in scene_ids:
            person = family.get_person(pid)
            if person is None:
                continue

            # 配偶者との婚姻線（配偶者が既に表示済みの場合）
            if person.spouse_id is not None and person.spouse_id in shown:
                marriage_edges = _find_marriage_edges(layout, pid, person.spouse_id)
                edge_indices_to_animate.extend(marriage_edges)

            # 親からの親子線（両親が既に表示済みの場合）
            if person.parent_ids:
                for parent_id in person.parent_ids:
                    if parent_id in shown:
                        child_edges = _find_child_edges(
                            layout,
                            person.parent_ids[0]
                            if len(person.parent_ids) > 0
                            else parent_id,
                            person.parent_ids[1]
                            if len(person.parent_ids) > 1
                            else parent_id,
                            pid,
                        )
                        edge_indices_to_animate.extend(child_edges)
                        break  # 一度見つけたら十分

        # 重複を除去
        edge_indices_to_animate = list(dict.fromkeys(edge_indices_to_animate))

        if edge_indices_to_animate:
            actions.append(
                AnimAction(
                    action_type=ActionType.DRAW_LINE,
                    duration=line_duration,
                    edge_indices=edge_indices_to_animate,
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
        completed_edges: set[int] = set()  # 完了済みエッジ
        animating_edges: list[tuple[int, float]] = []  # (エッジインデックス, 進捗率)

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
                    completed_edges.update(action.edge_indices)
                else:
                    # アニメーション中
                    elapsed = t - action_start
                    progress = elapsed / action.duration if action.duration > 0 else 1.0
                    progress = min(max(progress, 0.0), 1.0)
                    for ei in action.edge_indices:
                        animating_edges.append((ei, progress))

        # 描画するエッジリストを構築
        visible_edge_list: list[tuple[EdgeLayout, float]] = []
        for ei in completed_edges:
            if 0 <= ei < len(layout.edges):
                visible_edge_list.append((layout.edges[ei], 1.0))
        for ei, progress in animating_edges:
            if 0 <= ei < len(layout.edges) and ei not in completed_edges:
                visible_edge_list.append((layout.edges[ei], progress))

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
