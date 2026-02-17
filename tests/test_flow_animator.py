from __future__ import annotations

from datetime import date
from pathlib import Path

from family_tree.csv_parser import parse_csv
from family_tree.flow_animator import (
    ActionType,
    _merge_marriage_edges,
    build_action_sequence,
    create_flow_animation,
)
from family_tree.frame_drawer import FrameDrawer, _interpolate_points_along_path
from family_tree.graph_builder import build_graph_with_persons
from family_tree.layout_engine import extract_layout
from family_tree.models import Family, Person, Sex


def _build_two_gen_family() -> Family:
    """2世代のシンプルな家族。"""
    family = Family()
    family.add_person(
        Person(id=1, name="太郎", birth_date=date(1940, 1, 1), sex=Sex.M, spouse_id=2)
    )
    family.add_person(
        Person(id=2, name="花子", birth_date=date(1942, 1, 1), sex=Sex.F, spouse_id=1)
    )
    family.add_person(
        Person(
            id=3,
            name="一郎",
            birth_date=date(1965, 1, 1),
            sex=Sex.M,
            parent_ids=[1, 2],
        )
    )
    return family


def _get_layout(family: Family):
    all_ids = set(family.persons.keys())
    dot = build_graph_with_persons(family, all_ids)
    return extract_layout(dot)


class TestLayoutEngine:
    def test_extract_layout_has_nodes(self) -> None:
        family = _build_two_gen_family()
        layout = _get_layout(family)
        # 3人 + couple ノード
        assert "1" in layout.nodes
        assert "2" in layout.nodes
        assert "3" in layout.nodes
        assert layout.width > 0
        assert layout.height > 0

    def test_extract_layout_has_edges(self) -> None:
        family = _build_two_gen_family()
        layout = _get_layout(family)
        assert len(layout.edges) > 0


class TestInterpolatePath:
    def test_progress_zero(self) -> None:
        points = [(0.0, 0.0), (100.0, 0.0)]
        result = _interpolate_points_along_path(points, 0.0)
        assert len(result) == 1
        assert result[0] == (0.0, 0.0)

    def test_progress_one(self) -> None:
        points = [(0.0, 0.0), (100.0, 0.0)]
        result = _interpolate_points_along_path(points, 1.0)
        assert len(result) == 2
        assert result[-1] == (100.0, 0.0)

    def test_progress_half(self) -> None:
        points = [(0.0, 0.0), (100.0, 0.0)]
        result = _interpolate_points_along_path(points, 0.5)
        assert len(result) == 2
        assert abs(result[-1][0] - 50.0) < 0.01


class TestEdgeEndpointFix:
    def test_child_edge_reaches_child_node(self) -> None:
        """親子線の終点が子ノードの上端に到達していることを確認。"""
        family = _build_two_gen_family()
        layout = _get_layout(family)
        child_node = layout.nodes["3"]
        # couple_1_2 -> 3 のエッジを探す
        child_edges = [
            e for e in layout.edges if e.head == "3" and "couple" in e.tail
        ]
        assert len(child_edges) > 0
        for edge in child_edges:
            last_point = edge.points[-1]
            # 終点のY座標が子ノードの上端と一致
            assert abs(last_point[1] - child_node.top) < 1.0

    def test_marriage_edge_reaches_person_nodes(self) -> None:
        """婚姻線の端点が人物ノードの境界に到達していることを確認。"""
        family = _build_two_gen_family()
        layout = _get_layout(family)
        node1 = layout.nodes["1"]
        node2 = layout.nodes["2"]
        # person1 -> couple_1_2 のエッジ
        edges_from_1 = [
            e
            for e in layout.edges
            if e.tail == "1" and e.head == "couple_1_2"
        ]
        assert len(edges_from_1) > 0
        # 始点がperson1の右辺に一致
        assert abs(edges_from_1[0].points[0][0] - node1.right) < 1.0


class TestMergeMarriageEdges:
    def test_merge_produces_single_edge(self) -> None:
        """婚姻エッジの結合が1本のエッジを返す。"""
        family = _build_two_gen_family()
        layout = _get_layout(family)
        merged = _merge_marriage_edges(layout, 1, 2)
        assert len(merged) == 1

    def test_merged_edge_spans_both_persons(self) -> None:
        """結合エッジが person1 から person2 に渡る。"""
        family = _build_two_gen_family()
        layout = _get_layout(family)
        merged = _merge_marriage_edges(layout, 1, 2)
        edge = merged[0]
        assert edge.tail == "1"
        assert edge.head == "2"
        # ポイント数は元の2本の合計 - 1（重複除去）
        assert len(edge.points) > 2


class TestBuildActionSequence:
    def test_has_appear_actions(self) -> None:
        family = _build_two_gen_family()
        layout = _get_layout(family)
        actions = build_action_sequence(family, layout)
        appear_actions = [a for a in actions if a.action_type == ActionType.APPEAR]
        assert len(appear_actions) > 0

    def test_has_draw_line_actions(self) -> None:
        family = _build_two_gen_family()
        layout = _get_layout(family)
        actions = build_action_sequence(family, layout)
        line_actions = [a for a in actions if a.action_type == ActionType.DRAW_LINE]
        assert len(line_actions) > 0


class TestFrameDrawer:
    def test_draw_empty_frame(self) -> None:
        family = _build_two_gen_family()
        layout = _get_layout(family)
        drawer = FrameDrawer(layout, family)
        img = drawer.draw_frame(set(), [])
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_draw_frame_with_persons(self) -> None:
        family = _build_two_gen_family()
        layout = _get_layout(family)
        drawer = FrameDrawer(layout, family)
        img = drawer.draw_frame({1, 2}, [])
        assert img.size[0] > 0


class TestCreateFlowAnimation:
    def test_creates_mp4(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        output = tmp_path / "test_flow.mp4"
        result = create_flow_animation(
            family, output, line_duration=0.3, pause_duration=0.1, final_pause=0.5
        )
        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    def test_sample_csv(self, tmp_path: Path) -> None:
        """examples/sample.csv からフローアニメーションを正常に生成できる。"""
        family = parse_csv("examples/sample.csv")
        output = tmp_path / "sample_flow.mp4"
        create_flow_animation(
            family, output, line_duration=0.3, pause_duration=0.1, final_pause=0.5
        )
        assert output.exists()
        assert output.stat().st_size > 0

    def test_single_person(self, tmp_path: Path) -> None:
        """1人だけでもエラーにならない。"""
        family = Family()
        family.add_person(
            Person(id=1, name="単独者", birth_date=date(2000, 1, 1), sex=Sex.M)
        )
        output = tmp_path / "single_flow.mp4"
        create_flow_animation(
            family, output, line_duration=0.3, pause_duration=0.1, final_pause=0.5
        )
        assert output.exists()

    def test_auto_create_directory(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        output = tmp_path / "nested" / "dir" / "test_flow.mp4"
        create_flow_animation(
            family, output, line_duration=0.3, pause_duration=0.1, final_pause=0.5
        )
        assert output.exists()
