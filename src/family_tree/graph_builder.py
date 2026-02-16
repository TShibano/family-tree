from __future__ import annotations

from collections import deque

import graphviz

from family_tree.models import Family, Person, Sex

# 性別による色分け
COLOR_MALE = "lightblue"
COLOR_FEMALE = "lightpink"


def compute_generations(family: Family) -> dict[int, int]:
    """各人物の世代（depth）を算出する。

    親がいない人物を第0世代とし、トポロジカル順に子孫の世代を決定する。
    子の世代は全ての親の世代の最大値 + 1。
    配偶者は同じ世代に揃える（より深い方に合わせる）。

    Returns:
        person_id -> generation のマッピング
    """
    generations: dict[int, int] = {}

    # 親がいない人物（ルート）を世代0に設定
    for person in family.persons.values():
        if not person.parent_ids:
            generations[person.id] = 0

    # トポロジカル順に世代を決定（全員が確定するまで繰り返す）
    changed = True
    while changed:
        changed = False
        for person in family.persons.values():
            if not person.parent_ids:
                continue
            # 全ての親の世代が確定しているか確認
            parent_gens = [
                generations[pid]
                for pid in person.parent_ids
                if pid in generations
            ]
            if len(parent_gens) != len(person.parent_ids):
                continue
            new_gen = max(parent_gens) + 1
            if person.id not in generations or generations[person.id] != new_gen:
                generations[person.id] = new_gen
                changed = True

    # 配偶者を同じ世代に揃える（より深い方に合わせ、子を再計算）
    spouse_changed = True
    while spouse_changed:
        spouse_changed = False
        for person in family.persons.values():
            if person.spouse_id is None:
                continue
            sid = person.spouse_id
            if person.id in generations and sid in generations:
                max_gen = max(generations[person.id], generations[sid])
                if generations[person.id] != max_gen:
                    generations[person.id] = max_gen
                    spouse_changed = True
                if generations[sid] != max_gen:
                    generations[sid] = max_gen
                    spouse_changed = True

    return generations


def _get_node_color(person: Person) -> str:
    return COLOR_MALE if person.sex == Sex.M else COLOR_FEMALE


def _format_label(person: Person) -> str:
    return f"{person.name}\n{person.birth_date}"


def build_graph(family: Family) -> graphviz.Digraph:
    """Family データから Graphviz の Digraph オブジェクトを生成する。"""
    generations = compute_generations(family)

    dot = graphviz.Digraph(
        "family_tree",
        graph_attr={
            "rankdir": "TB",
            "splines": "ortho",
            "nodesep": "0.8",
            "ranksep": "1.0",
        },
        node_attr={
            "fontname": "Helvetica",
            "fontsize": "11",
            "shape": "box",
            "style": "filled,rounded",
        },
        edge_attr={
            "fontname": "Helvetica",
        },
    )

    # 人物ノードを追加
    for person in family.persons.values():
        dot.node(
            str(person.id),
            label=_format_label(person),
            fillcolor=_get_node_color(person),
        )

    # 婚姻関係の処理（重複回避のためペアを追跡）
    processed_couples: set[tuple[int, int]] = set()

    for person in family.persons.values():
        if person.spouse_id is None:
            continue

        couple = tuple(sorted((person.id, person.spouse_id)))
        if couple in processed_couples:
            continue
        processed_couples.add(couple)  # type: ignore[arg-type]

        spouse = family.get_person(person.spouse_id)
        if spouse is None:
            continue

        # 婚姻の中間ノード（不可視）
        mid_node = f"couple_{couple[0]}_{couple[1]}"
        dot.node(
            mid_node,
            label="",
            shape="point",
            width="0.01",
            height="0.01",
        )

        # 配偶者同士を同じ rank に配置
        with dot.subgraph() as s:
            s.attr(rank="same")
            s.node(str(couple[0]))
            s.node(mid_node)
            s.node(str(couple[1]))

        # 婚姻エッジ（矢印なし）
        dot.edge(
            str(couple[0]),
            mid_node,
            dir="none",
            color="darkred",
            penwidth="2",
        )
        dot.edge(
            mid_node,
            str(couple[1]),
            dir="none",
            color="darkred",
            penwidth="2",
        )

        # 子供へのエッジ（中間ノードから）
        children = _get_couple_children(family, couple[0], couple[1])
        for child in children:
            dot.edge(
                mid_node,
                str(child.id),
                color="gray30",
            )

    # 親が1人だけの子供のエッジ（婚姻ペアでカバーされないケース）
    couple_children = _get_all_couple_children_ids(family, processed_couples)
    for person in family.persons.values():
        if person.parent_ids and person.id not in couple_children:
            for pid in person.parent_ids:
                dot.edge(str(pid), str(person.id), color="gray30")

    # 世代ごとに rank を揃える
    gen_groups: dict[int, list[int]] = {}
    for pid, gen in generations.items():
        gen_groups.setdefault(gen, []).append(pid)

    for gen in sorted(gen_groups):
        with dot.subgraph() as s:
            s.attr(rank="same")
            for pid in gen_groups[gen]:
                s.node(str(pid))

    return dot


def _get_couple_children(
    family: Family, parent1_id: int, parent2_id: int
) -> list[Person]:
    """夫婦の共通の子供を返す。"""
    return [
        p
        for p in family.persons.values()
        if parent1_id in p.parent_ids and parent2_id in p.parent_ids
    ]


def _get_all_couple_children_ids(
    family: Family, couples: set[tuple[int, int]]
) -> set[int]:
    """すべての婚姻ペアの子供IDを集める。"""
    ids: set[int] = set()
    for c0, c1 in couples:
        for child in _get_couple_children(family, c0, c1):
            ids.add(child.id)
    return ids
