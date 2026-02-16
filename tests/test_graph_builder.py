from __future__ import annotations

from datetime import date

import graphviz

from family_tree.csv_parser import parse_csv
from family_tree.graph_builder import (
    build_graph,
    compute_generations,
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
