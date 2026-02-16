# TODO - アニメーション シーン単位化

## 概要

現在のアニメーションは「世代ごとに一気に表示」だが、より細かいシーン単位に分割する。

### シーン展開ルール（幅優先・世代順）

1. ルート人物（親がいない人物のうち、配偶者でない方）を1人ずつ表示
2. ルート人物の配偶者を1人ずつ表示
3. 以降、世代順に以下を繰り返す:
   - 各夫婦の子供（兄弟姉妹）をまとめて1シーンで表示
   - 各子供の配偶者を1人ずつ1シーンで表示

### sample.csv での展開例

```
シーン1: 太郎（ルート）
シーン2: 花子（太郎の配偶者）
シーン3: 一郎, 次郎（太郎+花子の子、兄弟）
シーン4: 美咲（一郎の配偶者）
シーン5: 由美（次郎の配偶者）
シーン6: 翔太, 愛（一郎+美咲の子、兄弟姉妹）
シーン7: 健太（次郎+由美の子）
シーン8: 真理（健太の配偶者）
シーン9: 大輝, さくら（健太+真理の子、兄弟姉妹）
```

## 実装計画

### Step 1: シーン順序算出ロジック追加

- [ ] `graph_builder.py` に `compute_scene_order(family) -> list[list[int]]` を追加
  - 各シーンに登場する person_id のリストを返す
  - 幅優先で世代順に処理
  - ルート人物 → ルート配偶者 → 子供グループ → 配偶者 → ... の順
- [ ] `tests/test_graph_builder.py` に `compute_scene_order` のテスト追加

### Step 2: 任意の人物集合でグラフ構築

- [ ] `build_graph_up_to_generation` を `build_graph_with_persons(family, visible_ids)` にリファクタ
  - 世代番号ではなく、表示する person_id の集合を受け取る形に汎用化
  - 既存の `build_graph_up_to_generation` はこの関数のラッパーにする

### Step 3: animator.py のシーン単位化

- [ ] `generate_generation_frames` を `generate_scene_frames` にリネーム・書き換え
  - `compute_scene_order` で得たシーン順に累積的にフレームを生成
- [ ] `create_animation` を新しいフレーム生成関数に対応させる
- [ ] `tests/test_animator.py` のテスト更新

### Step 4: 動作確認 & 仕上げ

- [ ] sample.csv でアニメーション出力し、シーン順序が正しいか目視確認
- [ ] ruff format / ruff check 通過
- [ ] mypy 通過
- [ ] 全テスト通過
