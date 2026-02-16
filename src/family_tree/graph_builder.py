from __future__ import annotations


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
                generations[pid] for pid in person.parent_ids if pid in generations
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


def compute_scene_order(family: Family) -> list[list[int]]:
    """アニメーション用のシーン順序を算出する。

    幅優先（世代順）で以下のルールに従う:
    - ルート人物（親がいない & 配偶者の親もいない場合は先に登場する方）を1人ずつ
    - ルート人物の配偶者を1人ずつ
    - 以降、世代順に:
      - 各夫婦の子供（兄弟姉妹）をまとめて1シーン
      - 各子供の配偶者を1人ずつ1シーン

    Returns:
        各シーンに登場する person_id のリスト（累積ではなく、そのシーンで新規に登場する人物）
    """
    generations = compute_generations(family)
    scenes: list[list[int]] = []
    shown: set[int] = set()

    # ルート人物を特定（親がいない人物）
    roots: list[Person] = []
    root_spouses: list[Person] = []
    for person in family.persons.values():
        if not person.parent_ids:
            if person.spouse_id is not None:
                spouse = family.get_person(person.spouse_id)
                if spouse is not None and spouse.parent_ids:
                    # 配偶者に親がいる → 嫁入り/婿入り。後で配偶者シーンとして表示
                    continue
                if spouse is not None and not spouse.parent_ids:
                    # 両方とも親なし → ID が小さい方をルートとする
                    if person.id < person.spouse_id:
                        roots.append(person)
                    else:
                        root_spouses.append(person)
                    continue
            roots.append(person)

    # ルート人物を1人ずつ表示
    for person in sorted(roots, key=lambda p: p.id):
        scenes.append([person.id])
        shown.add(person.id)

    # ルート配偶者を1人ずつ表示
    for person in sorted(root_spouses, key=lambda p: p.id):
        scenes.append([person.id])
        shown.add(person.id)

    # 世代順に処理: 各世代の「完成した夫婦」から子供を出し、子供の配偶者を追加
    max_gen = max(generations.values()) if generations else 0
    for gen in range(max_gen + 1):
        # この世代で両方 shown な夫婦を集める
        couples_in_gen: list[tuple[int, int]] = []
        seen_couples: set[tuple[int, int]] = set()
        for person in family.persons.values():
            if generations.get(person.id) != gen:
                continue
            if person.id not in shown or person.spouse_id is None:
                continue
            if person.spouse_id not in shown:
                continue
            couple = tuple(sorted((person.id, person.spouse_id)))
            if couple not in seen_couples:
                couples_in_gen.append(couple)  # type: ignore[arg-type]
                seen_couples.add(couple)  # type: ignore[arg-type]

        # 各夫婦の子供（兄弟姉妹）を1シーンで表示
        new_children_ids: list[int] = []
        for c0, c1 in couples_in_gen:
            children = _get_couple_children(family, c0, c1)
            children_ids = sorted([c.id for c in children if c.id not in shown])
            if children_ids:
                scenes.append(children_ids)
                shown.update(children_ids)
                new_children_ids.extend(children_ids)

        # 新たに追加された子供の配偶者を1人ずつ表示
        for cid in new_children_ids:
            child = family.get_person(cid)
            if child is not None and child.spouse_id is not None:
                if child.spouse_id not in shown:
                    scenes.append([child.spouse_id])
                    shown.add(child.spouse_id)

    return scenes


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
            "splines": "polyline",
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


def build_graph_with_persons(family: Family, visible_ids: set[int]) -> graphviz.Digraph:
    """指定された人物のみを含む Graphviz Digraph を生成する。"""
    generations = compute_generations(family)

    dot = graphviz.Digraph(
        "family_tree",
        graph_attr={
            "rankdir": "TB",
            "splines": "polyline",
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

    for person in family.persons.values():
        if person.id not in visible_ids:
            continue
        dot.node(
            str(person.id),
            label=_format_label(person),
            fillcolor=_get_node_color(person),
        )

    processed_couples: set[tuple[int, int]] = set()

    for person in family.persons.values():
        if person.id not in visible_ids or person.spouse_id is None:
            continue
        if person.spouse_id not in visible_ids:
            continue

        couple = tuple(sorted((person.id, person.spouse_id)))
        if couple in processed_couples:
            continue
        processed_couples.add(couple)  # type: ignore[arg-type]

        mid_node = f"couple_{couple[0]}_{couple[1]}"
        dot.node(mid_node, label="", shape="point", width="0.01", height="0.01")

        with dot.subgraph() as s:
            s.attr(rank="same")
            s.node(str(couple[0]))
            s.node(mid_node)
            s.node(str(couple[1]))

        dot.edge(str(couple[0]), mid_node, dir="none", color="darkred", penwidth="2")
        dot.edge(mid_node, str(couple[1]), dir="none", color="darkred", penwidth="2")

        children = [
            c
            for c in _get_couple_children(family, couple[0], couple[1])
            if c.id in visible_ids
        ]
        for child in children:
            dot.edge(mid_node, str(child.id), color="gray30")

    couple_children = _get_all_couple_children_ids(family, processed_couples)
    for person in family.persons.values():
        if person.id not in visible_ids:
            continue
        if person.parent_ids and person.id not in couple_children:
            for pid in person.parent_ids:
                if pid in visible_ids:
                    dot.edge(str(pid), str(person.id), color="gray30")

    gen_groups: dict[int, list[int]] = {}
    for pid, gen in generations.items():
        if pid in visible_ids:
            gen_groups.setdefault(gen, []).append(pid)

    for gen in sorted(gen_groups):
        with dot.subgraph() as s:
            s.attr(rank="same")
            for pid in gen_groups[gen]:
                s.node(str(pid))

    return dot


def build_graph_up_to_generation(family: Family, max_gen: int) -> graphviz.Digraph:
    """指定した世代までの人物を含む Graphviz Digraph を生成する。"""
    generations = compute_generations(family)
    visible_ids = {pid for pid, gen in generations.items() if gen <= max_gen}
    return build_graph_with_persons(family, visible_ids)


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
