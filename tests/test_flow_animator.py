from __future__ import annotations

from datetime import date
from pathlib import Path

from family_tree.config import AppConfig, AnimationConfig
from family_tree.csv_parser import parse_csv
from family_tree.flow_animator import (
    ActionType,
    _collect_groups,
    _get_marriage_edges_toward_center,
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


class TestMarriageEdgesTowardCenter:
    def test_returns_two_edges(self) -> None:
        """婚姻エッジが2本（各人物→中心点）返る。"""
        family = _build_two_gen_family()
        layout = _get_layout(family)
        edges = _get_marriage_edges_toward_center(layout, 1, 2)
        assert len(edges) == 2

    def test_both_edges_point_toward_couple_node(self) -> None:
        """2本とも couple_node に向かうエッジである。"""
        family = _build_two_gen_family()
        layout = _get_layout(family)
        edges = _get_marriage_edges_toward_center(layout, 1, 2)
        couple_key = "couple_1_2"
        for edge in edges:
            assert edge.head == couple_key
            assert len(edge.points) >= 2


def _build_grouped_family() -> Family:
    """グループ設定ありの2世代家族。
    group="1": 太郎(1), 花子(2)
    group="2": 一郎(3)
    """
    family = Family()
    family.add_person(
        Person(id=1, name="太郎", birth_date=date(1940, 1, 1), sex=Sex.M, spouse_id=2, group="1")
    )
    family.add_person(
        Person(id=2, name="花子", birth_date=date(1942, 1, 1), sex=Sex.F, spouse_id=1, group="1")
    )
    family.add_person(
        Person(
            id=3,
            name="一郎",
            birth_date=date(1965, 1, 1),
            sex=Sex.M,
            parent_ids=[1, 2],
            group="2",
        )
    )
    return family


class TestCollectGroups:
    def test_groups_collected_in_csv_order(self) -> None:
        """グループがCSV登場順に収集される。"""
        family = _build_grouped_family()
        groups_order, groups_map = _collect_groups(family)
        assert groups_order == ["1", "2"]
        assert [p.id for p in groups_map["1"]] == [1, 2]
        assert [p.id for p in groups_map["2"]] == [3]

    def test_ungrouped_person_gets_solo_key(self) -> None:
        """group 未設定の人物は __solo_{id}__ キーで個別グループ扱い。"""
        family = _build_two_gen_family()  # group=None
        groups_order, groups_map = _collect_groups(family)
        assert "__solo_1__" in groups_order
        assert "__solo_2__" in groups_order
        assert "__solo_3__" in groups_order

    def test_mixed_grouped_and_ungrouped(self) -> None:
        """グループありとグループなしが混在する場合。"""
        family = Family()
        family.add_person(
            Person(id=1, name="A", birth_date=date(1940, 1, 1), sex=Sex.M, group="g1")
        )
        family.add_person(
            Person(id=2, name="B", birth_date=date(1942, 1, 1), sex=Sex.F, group="g1")
        )
        family.add_person(
            Person(id=3, name="C", birth_date=date(1965, 1, 1), sex=Sex.M)
        )
        groups_order, groups_map = _collect_groups(family)
        assert groups_order[0] == "g1"
        assert "__solo_3__" in groups_order
        assert len(groups_map["g1"]) == 2


class TestGroupedActionSequence:
    def test_group_members_appear_together(self) -> None:
        """同グループの人物が1つの APPEAR アクションにまとまる。"""
        family = _build_grouped_family()
        layout = _get_layout(family)
        actions = build_action_sequence(family, layout)
        appear_actions = [a for a in actions if a.action_type == ActionType.APPEAR]
        # グループ "1" の APPEAR に 太郎(1) と 花子(2) が含まれる
        first_appear = appear_actions[0]
        assert set(first_appear.new_person_ids) == {1, 2}

    def test_child_line_before_marriage_line(self) -> None:
        """同グループ内で親子線アクションが婚姻線アクションより先に来る。"""
        family = _build_grouped_family()
        layout = _get_layout(family)
        actions = build_action_sequence(family, layout)

        # グループ "2"（一郎）の処理: 親子線 → 婚姻線 の順を確認
        # 一郎は親がいるので親子線あり、配偶者なしなので婚姻線なし
        # グループ "1" は親なし・配偶者あり → 婚姻線のみ
        draw_actions = [a for a in actions if a.action_type == ActionType.DRAW_LINE]
        assert len(draw_actions) >= 2

        # 婚姻線（group=1）はグループ"1"処理時。親子線（group=2）はグループ"2"処理時。
        # グループ"1" の APPEAR の後にある DRAW_LINE は婚姻線
        appear_indices = [i for i, a in enumerate(actions) if a.action_type == ActionType.APPEAR]
        # group="1" の APPEAR は index 0 のはず
        group1_appear_idx = appear_indices[0]
        group2_appear_idx = appear_indices[1]
        # group="1" 処理後の DRAW_LINE（婚姻線）が group="2" の APPEAR より前
        draw_after_group1 = [
            i
            for i, a in enumerate(actions)
            if a.action_type == ActionType.DRAW_LINE
            and group1_appear_idx < i < group2_appear_idx
        ]
        assert len(draw_after_group1) == 1  # 婚姻線のみ（親子線なし）

    def test_no_duplicate_marriage_edges(self) -> None:
        """同グループ内の配偶者ペアで婚姻線が重複しない。"""
        family = _build_grouped_family()
        layout = _get_layout(family)
        actions = build_action_sequence(family, layout)
        draw_actions = [a for a in actions if a.action_type == ActionType.DRAW_LINE]
        # グループ"1"処理後の婚姻線アクションのエッジ数を確認
        # _get_marriage_edges_toward_center は2本返すので、重複なければ2本
        # 婚姻線は head が couple_（中心点に向かう）
        # 親子線の comb は tail が couple_（中心点から出る）
        marriage_draws = [a for a in draw_actions if any(
            e.head.startswith("couple_")
            for e in a.anim_edges
        )]
        assert len(marriage_draws) == 1
        assert len(marriage_draws[0].anim_edges) == 2  # 2本（重複なし）

    def test_ungrouped_still_works(self) -> None:
        """グループ未設定でも正常に動作する（後方互換性）。"""
        family = _build_two_gen_family()
        layout = _get_layout(family)
        actions = build_action_sequence(family, layout)
        appear_actions = [a for a in actions if a.action_type == ActionType.APPEAR]
        # グループなし → 1人ずつ APPEAR
        assert len(appear_actions) == 3
        for a in appear_actions:
            assert len(a.new_person_ids) == 1


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
        drawer = FrameDrawer(layout, family, AppConfig())
        img = drawer.draw_frame(set(), [])
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_draw_frame_with_persons(self) -> None:
        family = _build_two_gen_family()
        layout = _get_layout(family)
        drawer = FrameDrawer(layout, family, AppConfig())
        img = drawer.draw_frame({1, 2}, [])
        assert img.size[0] > 0


def _fast_config() -> AppConfig:
    """テスト用の短時間設定。"""
    cfg = AppConfig()
    cfg.animation.line_duration = 0.3
    cfg.animation.pause_duration = 0.1
    cfg.animation.final_pause = 0.5
    return cfg


class TestCreateFlowAnimation:
    def test_creates_mp4(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        output = tmp_path / "test_flow.mp4"
        result = create_flow_animation(family, output, _fast_config())
        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    def test_sample_csv(self, tmp_path: Path) -> None:
        """examples/sample.csv からフローアニメーションを正常に生成できる。"""
        family = parse_csv("examples/sample.csv")
        output = tmp_path / "sample_flow.mp4"
        create_flow_animation(family, output, _fast_config())
        assert output.exists()
        assert output.stat().st_size > 0

    def test_single_person(self, tmp_path: Path) -> None:
        """1人だけでもエラーにならない。"""
        family = Family()
        family.add_person(
            Person(id=1, name="単独者", birth_date=date(2000, 1, 1), sex=Sex.M)
        )
        output = tmp_path / "single_flow.mp4"
        create_flow_animation(family, output, _fast_config())
        assert output.exists()

    def test_auto_create_directory(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        output = tmp_path / "nested" / "dir" / "test_flow.mp4"
        create_flow_animation(family, output, _fast_config())
        assert output.exists()

    def test_line_duration_override(self, tmp_path: Path) -> None:
        """line_duration 引数が config より優先される。"""
        family = _build_two_gen_family()
        output = tmp_path / "override_flow.mp4"
        cfg = _fast_config()
        cfg.animation.line_duration = 999.0  # 上書きされるべき値
        create_flow_animation(family, output, cfg, line_duration=0.3)
        assert output.exists()
