# TODO_07: グループ単位のアニメーション制御

## 概要

CSVの `group` カラムでグループを指定し、同グループの人物を同時表示した後、
親子線 → 婚姻線の順でアニメーションするよう制御する。

## 背景・要件

現在の `animate-flow` は人物を1人ずつ順に表示する。
ユーザーは「同一グループの人をまとめて表示 → 親子線 → 婚姻線」という演出を望んでいる。

### アニメーション順序（グループ単位）

```
[グループ1]
  1. APPEAR   : グループ内の全員を同時に瞬間表示
  2. DRAW_LINE: グループ内の全員の親子線（両親が表示済みの場合）を同時アニメーション
  3. DRAW_LINE: グループ内の全員の婚姻線（配偶者が表示済みの場合）を同時アニメーション
  4. PAUSE    : 静止
[グループ2]
  ... 同様
```

- `group` 未設定の人物は1人ずつ個別グループとして扱う（既存動作に近い）
- グループの処理順 = CSV上での最初の登場順
- 同グループ内に配偶者がいる場合は婚姻線の重複描画を防ぐ

### CSVフォーマット（追加カラム）

```csv
id,name,birth_date,sex,parent_ids,spouse_id,fill_color,border_color,group
1,山田 太郎,1940-03-15,M,,2,,,1
2,山田 花子,1942-07-22,F,,1,,,1
3,山田 一郎,1965-01-10,M,"1,2",4,,,2
4,山田 美咲,1967-05-30,F,,3,,,2
...
```

- `group`: 任意の文字列（数字でも文字でも可）。空欄 = グループなし（個別表示）

---

## 変更ファイルと実装詳細

### 1. `src/family_tree/models.py`

`Person` に `group` フィールドを追加する。

```python
@dataclass
class Person:
    ...
    fill_color: str | None = None
    border_color: str | None = None
    group: str | None = None          # ← 追加
    metadata: dict[str, str] = field(default_factory=dict)
```

### 2. `src/family_tree/csv_parser.py`

- `GROUP_COLUMNS = {"group"}` を追加し、`extra_columns`（metadata）から除外する
- `_parse_row()` で `group` カラムをパース（空文字列 → `None`）

```python
GROUP_COLUMNS = {"group"}

# parse_csv() 内:
extra_columns = headers - REQUIRED_COLUMNS - COLOR_COLUMNS - GROUP_COLUMNS

# _parse_row() 内:
group_str = (row.get("group") or "").strip()
group: str | None = group_str if group_str else None

return Person(
    ...
    group=group,
    ...
)
```

### 3. `src/family_tree/flow_animator.py`

`build_action_sequence()` を全面的に書き直す。

#### グループ集約ロジック

```python
def _collect_groups(family: Family) -> tuple[list[str], dict[str, list[Person]]]:
    """CSVの登場順を維持しながら、グループ別に人物をまとめる。

    group 未設定の人物は "__solo_{id}__" という内部キーで個別グループ扱いにする。
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
```

#### build_action_sequence() の構造

```python
def build_action_sequence(...):
    groups_order, groups_map = _collect_groups(family)
    shown: set[int] = set()

    for group_key in groups_order:
        persons_in_group = groups_map[group_key]

        # 1. APPEAR（グループ全員を同時表示）
        group_ids = [p.id for p in persons_in_group]
        actions.append(AnimAction(APPEAR, duration=0.0, new_person_ids=group_ids))
        shown.update(group_ids)

        # 2. DRAW_LINE: 親子線（グループ全員分をまとめて1アクション）
        child_edges = []
        for person in persons_in_group:
            if person.parent_ids and all(pid in shown for pid in person.parent_ids):
                p1 = person.parent_ids[0]
                p2 = person.parent_ids[1] if len(person.parent_ids) > 1 else p1
                child_edges.extend(_build_comb_child_edge(layout, p1, p2, person.id))
        if child_edges:
            actions.append(AnimAction(DRAW_LINE, duration=line_duration, anim_edges=child_edges))

        # 3. DRAW_LINE: 婚姻線（同グループ内の重複を除去）
        marriage_edges = []
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
            actions.append(AnimAction(DRAW_LINE, duration=line_duration, anim_edges=marriage_edges))

        # 4. PAUSE
        actions.append(AnimAction(PAUSE, duration=pause_duration))
```

### 4. `examples/sample.csv`

`group` カラムを追加する。配偶者ペアを同一グループに設定する例：

| group | 人物 |
|-------|------|
| 1 | 山田太郎, 山田花子（祖父母） |
| 2 | 山田一郎, 山田美咲（長男夫婦） |
| 3 | 山田次郎, 山田由美（次男夫婦） |
| 4 | 山田翔太, 山田愛（第3世代・長男家） |
| 5 | 山田健太, 佐藤真理（第3世代・次男家） |
| 6 | 山田大輝, 山田さくら（第4世代） |

### 5. `tests/test_flow_animator.py`

既存テストの更新と新規テストの追加：

#### 既存テストへの影響
- `TestBuildActionSequence` のテストは `group` 未指定でも動作するため基本的にそのまま
- ただし、`_build_two_gen_family()` が `group` なしなので個別扱いになり動作は変わらない

#### 新規テスト: `TestGroupedActionSequence`

```python
class TestGroupedActionSequence:
    def test_group_members_appear_together(self):
        """同グループの人物が1つの APPEAR アクションにまとまる。"""

    def test_child_line_before_marriage_line(self):
        """親子線アクションが婚姻線アクションより先に来る。"""

    def test_ungrouped_person_appears_individually(self):
        """group 未設定の人物は個別に APPEAR する。"""

    def test_no_duplicate_marriage_edges(self):
        """同グループの配偶者ペアで婚姻線が重複しない。"""
```

---

## 動作例（sample.csv のアニメーション順）

```
[group=1] APPEAR 山田太郎・山田花子
[group=1] DRAW_LINE 親子線（なし：二人とも親なし）
[group=1] DRAW_LINE 婚姻線（太郎↔花子）
[group=1] PAUSE

[group=2] APPEAR 山田一郎・山田美咲
[group=2] DRAW_LINE 親子線（一郎：太郎・花子→一郎）
[group=2] DRAW_LINE 婚姻線（一郎↔美咲）
[group=2] PAUSE

[group=3] APPEAR 山田次郎・山田由美
[group=3] DRAW_LINE 親子線（次郎：太郎・花子→次郎）
[group=3] DRAW_LINE 婚姻線（次郎↔由美）
[group=3] PAUSE
...
```

---

## 懸念事項・考慮点

- **line_duration の共有**: 親子線と婚姻線は同じ `line_duration` を使用する。異なる duration にしたい場合は将来の拡張で対応
- **グループ順序**: CSVの記載順（最初の登場順）で処理するため、グループIDの数値順とは異なる場合がある
- **既存の `animate` コマンド**: `animator.py` は `compute_scene_order` を使うため影響なし
- **`graph_builder.py` の `compute_scene_order`**: 静止画・カットアニメーション用のため変更不要

---

## 実装ステップ

1. `models.py` に `group` フィールドを追加
2. `csv_parser.py` で `group` カラムをパース
3. `flow_animator.py` に `_collect_groups()` を追加し `build_action_sequence()` を書き直す
4. `examples/sample.csv` に `group` カラムを追加
5. `tests/test_flow_animator.py` にグループテストを追加
6. 全テストを実行して確認（`uv run pytest tests/`）
