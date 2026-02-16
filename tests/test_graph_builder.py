from __future__ import annotations

from datetime import date

import graphviz

from family_tree.csv_parser import parse_csv
from family_tree.graph_builder import (
    build_graph,
    compute_generations,
    compute_scene_order,
    _get_couple_children,
)
from family_tree.models import Family, Person, Sex


def _make_person(
    id: int,
    name: str = "テスト",
    sex: Sex = Sex.M,
    parent_ids: list[int] | None = None,
    spouse_id: int | None = None,
) -> Person:
    return Person(
        id=id,
        name=name,
        birth_date=date(2000, 1, 1),
        sex=sex,
        parent_ids=parent_ids or [],
        spouse_id=spouse_id,
    )


def _build_simple_family() -> Family:
    """3世代のシンプルな家族を構築する。

    世代0: 1(太郎) -- 2(花子)
    世代1: 3(一郎, 親:1,2)
    """
    family = Family()
    family.add_person(_make_person(1, "太郎", Sex.M, spouse_id=2))
    family.add_person(_make_person(2, "花子", Sex.F, spouse_id=1))
    family.add_person(_make_person(3, "一郎", Sex.M, parent_ids=[1, 2]))
    return family


class TestComputeGenerations:
    def test_roots_are_generation_zero(self) -> None:
        family = _build_simple_family()
        gens = compute_generations(family)
        assert gens[1] == 0
        assert gens[2] == 0

    def test_child_generation(self) -> None:
        family = _build_simple_family()
        gens = compute_generations(family)
        assert gens[3] == 1

    def test_spouse_same_generation(self) -> None:
        """配偶者は同じ世代に揃えられる。"""
        family = Family()
        family.add_person(_make_person(1, "祖父", Sex.M, spouse_id=2))
        family.add_person(_make_person(2, "祖母", Sex.F, spouse_id=1))
        family.add_person(_make_person(3, "父", Sex.M, parent_ids=[1, 2], spouse_id=4))
        # 配偶者4は親がないが、spouse_idにより世代1に揃う
        family.add_person(_make_person(4, "母", Sex.F, spouse_id=3))
        gens = compute_generations(family)
        assert gens[3] == gens[4]

    def test_multiple_generations(self) -> None:
        """4世代の家系でdepthが正しい。"""
        family = Family()
        family.add_person(_make_person(1, "祖父", Sex.M, spouse_id=2))
        family.add_person(_make_person(2, "祖母", Sex.F, spouse_id=1))
        family.add_person(_make_person(3, "父", Sex.M, parent_ids=[1, 2], spouse_id=4))
        family.add_person(_make_person(4, "母", Sex.F, spouse_id=3))
        family.add_person(_make_person(5, "子", Sex.M, parent_ids=[3, 4]))
        gens = compute_generations(family)
        assert gens[1] == 0
        assert gens[3] == 1
        assert gens[5] == 2

    def test_no_parents_all_zero(self) -> None:
        """親のいない人物は全員世代0。"""
        family = Family()
        family.add_person(_make_person(1, "A", Sex.M))
        family.add_person(_make_person(2, "B", Sex.F))
        gens = compute_generations(family)
        assert gens[1] == 0
        assert gens[2] == 0


class TestGetCoupleChildren:
    def test_couple_children(self) -> None:
        family = _build_simple_family()
        children = _get_couple_children(family, 1, 2)
        assert len(children) == 1
        assert children[0].id == 3

    def test_no_children(self) -> None:
        family = Family()
        family.add_person(_make_person(1, "A", Sex.M, spouse_id=2))
        family.add_person(_make_person(2, "B", Sex.F, spouse_id=1))
        children = _get_couple_children(family, 1, 2)
        assert children == []


class TestBuildGraph:
    def test_returns_digraph(self) -> None:
        family = _build_simple_family()
        dot = build_graph(family)
        assert isinstance(dot, graphviz.Digraph)

    def test_graph_contains_person_nodes(self) -> None:
        family = _build_simple_family()
        dot = build_graph(family)
        source = dot.source
        # 各人物のノードが存在する（ラベルで確認）
        assert "太郎" in source
        assert "花子" in source
        assert "一郎" in source

    def test_graph_contains_labels(self) -> None:
        family = _build_simple_family()
        dot = build_graph(family)
        source = dot.source
        assert "太郎" in source
        assert "花子" in source
        assert "一郎" in source

    def test_graph_contains_couple_node(self) -> None:
        """婚姻の中間ノードが生成される。"""
        family = _build_simple_family()
        dot = build_graph(family)
        source = dot.source
        assert "couple_1_2" in source

    def test_gender_colors(self) -> None:
        family = _build_simple_family()
        dot = build_graph(family)
        source = dot.source
        assert "lightblue" in source
        assert "lightpink" in source

    def test_marriage_edges_no_arrow(self) -> None:
        """婚姻エッジは矢印なし（dir=none）。"""
        family = _build_simple_family()
        dot = build_graph(family)
        source = dot.source
        assert "dir=none" in source

    def test_rankdir_is_tb(self) -> None:
        family = _build_simple_family()
        dot = build_graph(family)
        source = dot.source
        assert "rankdir=TB" in source

    def test_sample_csv_builds_graph(self) -> None:
        """examples/sample.csv から正常にグラフが構築できる。"""
        family = parse_csv("examples/sample.csv")
        dot = build_graph(family)
        source = dot.source
        # 12人分のノードが存在
        assert "山田 太郎" in source
        assert "山田 さくら" in source

    def test_single_person_no_error(self) -> None:
        """1人だけの家系でもエラーにならない。"""
        family = Family()
        family.add_person(_make_person(1, "単独者", Sex.M))
        dot = build_graph(family)
        assert "単独者" in dot.source


class TestComputeSceneOrder:
    def test_simple_family(self) -> None:
        """太郎+花子→一郎 の3人家族。"""
        family = _build_simple_family()
        scenes = compute_scene_order(family)
        # シーン1: 太郎(1), シーン2: 花子(2), シーン3: 一郎(3)
        assert scenes[0] == [1]
        assert scenes[1] == [2]
        assert scenes[2] == [3]
        assert len(scenes) == 3

    def test_sample_csv_scene_order(self) -> None:
        """sample.csv のシーン展開が期待通り。"""
        family = parse_csv("examples/sample.csv")
        scenes = compute_scene_order(family)
        # シーン1: 太郎(1)
        assert scenes[0] == [1]
        # シーン2: 花子(2)
        assert scenes[1] == [2]
        # シーン3: 一郎(3), 次郎(5) - 兄弟
        assert scenes[2] == [3, 5]
        # シーン4: 美咲(4) - 一郎の配偶者
        assert scenes[3] == [4]
        # シーン5: 由美(6) - 次郎の配偶者
        assert scenes[4] == [6]
        # シーン6: 翔太(7), 愛(8) - 一郎+美咲の子
        assert scenes[5] == [7, 8]
        # シーン7: 健太(9) - 次郎+由美の子
        assert scenes[6] == [9]
        # シーン8: 真理(10) - 健太の配偶者
        assert scenes[7] == [10]
        # シーン9: 大輝(11), さくら(12) - 健太+真理の子
        assert scenes[8] == [11, 12]
        assert len(scenes) == 9

    def test_all_persons_included(self) -> None:
        """全ての人物がシーンに含まれる。"""
        family = parse_csv("examples/sample.csv")
        scenes = compute_scene_order(family)
        all_ids = set()
        for scene in scenes:
            all_ids.update(scene)
        assert all_ids == set(family.persons.keys())

    def test_single_person(self) -> None:
        """1人だけの場合。"""
        family = Family()
        family.add_person(_make_person(1, "単独者", Sex.M))
        scenes = compute_scene_order(family)
        assert scenes == [[1]]

    def test_no_duplicate_ids(self) -> None:
        """同一人物が複数シーンに登場しない。"""
        family = parse_csv("examples/sample.csv")
        scenes = compute_scene_order(family)
        seen: set[int] = set()
        for scene in scenes:
            for pid in scene:
                assert pid not in seen, f"ID {pid} が重複"
                seen.add(pid)
