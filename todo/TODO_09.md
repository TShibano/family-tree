# TODO_09: 親子線 → 子どもセル表示の順序変更

## 概要

現在のアニメーション順序（グループ全員 APPEAR → 親子線 → 婚姻線）を変更し、
「親子線が伸びた後に子どもセルが登場する」演出を実装する。

## 現在の順序

```
1. APPEAR    : グループ全員（親・子・配偶者を同時にフェードイン）
2. DRAW_LINE : 親子線
3. DRAW_LINE : 婚姻線
4. PAUSE
```

## 目標の順序

```
1. APPEAR    : standalone メンバー（親がまだ未表示、または親がいない）
2. DRAW_LINE : 親子線（親が表示済みの子どもへの線）
3. APPEAR    : children（親が表示済みの子ども）
4. DRAW_LINE : 婚姻線
5. PAUSE
```

### 視覚的な効果

- 配偶者として加わる人物（親なし）は先に現れる
- 次に親子線が上から子どもに向かって伸びる
- 線の先端に子どもセルが登場する（「線に導かれて登場」感）
- 最後に婚姻線で配偶者と繋がる

## 変更ファイル

### 1. `src/family_tree/flow_animator.py`

**`build_action_sequence()` の修正**

グループ内のメンバーを2グループに分類する：

```python
# 親子関係に基づく分類
standalone = [p for p in persons if not (
    p.parent_ids and all(pid in shown for pid in p.parent_ids)
)]
children = [p for p in persons if (
    p.parent_ids and all(pid in shown for pid in p.parent_ids)
)]
```

分類ルール：
- `standalone`: 親がいない、または親が未表示 → 先に APPEAR
- `children`: 親が全員表示済み → 親子線の後に APPEAR

**新しいアクション生成ロジック：**

```python
# 1. APPEAR standalone
if standalone:
    actions.append(APPEAR(standalone))
    shown.update(standalone_ids)

# 2. DRAW_LINE 親子線
child_edges = [comb edges for each child]
if child_edges:
    actions.append(DRAW_LINE(child_edges))

# 3. APPEAR children
if children:
    actions.append(APPEAR(children))
    shown.update(children_ids)

# 4. DRAW_LINE 婚姻線
marriage_edges = [marriage edges for pairs where both in shown]
if marriage_edges:
    actions.append(DRAW_LINE(marriage_edges))

# 5. PAUSE
actions.append(PAUSE)
```

### 2. `tests/test_flow_animator.py`

**`TestGroupedActionSequence` の更新**

アクション順序テストを新しい順序に合わせて修正：

- Group 1 (太郎&花子・親なし): APPEAR → 婚姻線 → PAUSE
- Group 2 (一郎・次郎は子ども、美咲・由美は配偶者):
  - APPEAR(美咲・由美) → DRAW_LINE(親子線) → APPEAR(一郎・次郎) → DRAW_LINE(婚姻線) → PAUSE
- Group 3 (翔太・愛、両親表示済み):
  - (standalone なし) → DRAW_LINE(親子線) → APPEAR(翔太・愛) → PAUSE（婚姻線なし）

**`TestFadeInAnimation` の確認**

フェードインの基本ロジックは変わらないため、既存テストはそのまま通るはず。

## エッジケース

| ケース | 対応 |
|--------|------|
| グループ全員が standalone | APPEAR のみ（親子線なし） |
| グループ全員が children | standalone APPEAR なし → 親子線 → APPEAR |
| children も standalone もいる | 両方を適切な順序で処理 |
| 親子線なし・婚姻線あり | APPEAR(全員) → 婚姻線 → PAUSE |

## 影響範囲

- `build_action_sequence()` の内部ロジックのみ
- `make_frame()` / `FrameDrawer` / `create_flow_animation()` は変更不要
- AnimAction・ActionType の型定義は変更不要

## テスト計画

1. `uv run pytest tests/test_flow_animator.py -v` で全テスト通過確認
2. `uv run pytest tests/ -v` で全体テスト通過確認
3. (任意) `uv run family-tree animate-flow --input examples/sample.csv --output output/flow.mp4` で動画確認
