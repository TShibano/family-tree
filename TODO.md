# animate-flow 実装計画

## 概要

新しいCLIコマンド `animate-flow` を追加する。既存の `animate` コマンド（カット切り替え方式）とは別に、線が動きながら描画されるアニメーション動画を生成する。

## 演出仕様

| シーン | 演出 |
|---|---|
| ルート人物登場 | 人物ブロックが瞬間表示 |
| 配偶者登場 | 配偶者ブロックが瞬間表示 → 二人の間を婚姻線が0.5秒かけて伸びる |
| 子ども登場 | 夫婦の中間点から下へ線が0.5秒かけて伸びる → 線の先に子どものブロックが表示。兄弟は順番に（1人ずつ） |

## 描画スタイル

- **人物ブロック**: シンプルな矩形 + 性別色分け（lightblue/lightpink）+ 名前 + 生年月日
- **婚姻線**: 赤系の水平線（darkred）
- **親子線**: グレーの垂直線（gray30）

## 技術方針

- **レイアウト計算**: Graphviz の `-Tplain` 出力を利用してノード座標を取得
- **フレーム描画**: Pillow で1フレームずつ描画
- **動画生成**: moviepy で MP4 にエンコード（既存と同様）

## 実装ステップ

### Step 1: レイアウト座標の抽出 (`layout_engine.py`)

新規ファイル `src/family_tree/layout_engine.py` を作成。

- Graphviz の `plain` 形式出力をパースし、各ノードの (x, y, width, height) を取得する関数
- `build_graph()` または `build_graph_with_persons()` で生成した Digraph を入力として受け取る
- Graphviz の座標系（Y軸上向き、ポイント単位）を Pillow の座標系（Y軸下向き、ピクセル単位）に変換
- エッジの始点・終点座標も取得

### Step 2: Pillow フレーム描画 (`frame_drawer.py`)

新規ファイル `src/family_tree/frame_drawer.py` を作成。

- レイアウト座標を受け取り、Pillow の `Image` + `ImageDraw` で描画する
- 描画要素:
  - **人物ブロック**: 矩形 + テキスト（名前、生年月日）
  - **婚姻線**: 水平線（darkred、太さ2px）
  - **親子線**: 垂直/折れ線（gray30）
- 線の部分描画（進捗率 0.0〜1.0 を受け取り、始点から途中まで描く）

### Step 3: アニメーションシーケンス生成 (`flow_animator.py`)

新規ファイル `src/family_tree/flow_animator.py` を作成。

- `compute_scene_order()` のシーン順序を拡張し、各シーンのアニメーション種類を定義:
  - `appear` — 人物ブロックの瞬間表示
  - `draw_line` — 線が伸びるアニメーション（0.5秒 = 12フレーム @24fps）
- シーンごとにフレームを生成:
  1. 人物ブロック表示フレーム（1フレーム追加 + 短い静止）
  2. 線アニメーションフレーム（12フレーム、線の進捗率を 0→1 で補間）
  3. 完了後の静止フレーム（0.5秒程度）
- 全フレームを moviepy で MP4 に変換

### Step 4: CLIコマンド追加 (`main.py`)

- `animate-flow` コマンドを追加
- オプション: `--input`, `--output`, `--line-duration`（線アニメーション秒数、デフォルト0.5）

### Step 5: テスト (`test_flow_animator.py`)

- レイアウト座標抽出のテスト
- フレーム描画のテスト（画像サイズ、描画内容の基本確認）
- アニメーション生成の結合テスト

## ファイル構成（変更・追加分）

```
src/family_tree/
├── main.py              # 変更: animate-flow コマンド追加
├── layout_engine.py     # 新規: Graphviz レイアウト座標抽出
├── frame_drawer.py      # 新規: Pillow フレーム描画
└── flow_animator.py     # 新規: フローアニメーション生成

tests/
└── test_flow_animator.py  # 新規: テスト
```

## パラメータ（初期値）

| パラメータ | 値 | 備考 |
|---|---|---|
| FPS | 24 | 既存と同じ |
| 線アニメーション時間 | 0.5秒 | CLI オプションで変更可 |
| ブロック表示後の静止時間 | 0.3秒 | シーン間の間 |
| 全体完成後の静止時間 | 2.0秒 | 最後に全体像を見せる |

---

## 追加修正 (v2)

### 問題1: 婚姻線が2箇所から出る

**原因**: Graphviz のグラフでは婚姻を `person1 → couple_node → person2` の2本のエッジで表現している。`flow_animator.py` では この2本を別々のエッジとして同時にアニメーションしているため、person1 の右端と couple_node の2箇所から線が伸び始める。

**修正方針**: `flow_animator.py` の `_find_marriage_edges` で取得した2本のエッジを、アニメーション時に1本の連続パスとして結合する。具体的には:
- `person1 → couple_node` のポイント列と `couple_node → person2` のポイント列を結合して1つの `EdgeLayout` を作る
- `build_action_sequence` でこの結合エッジを使用する

**変更ファイル**: `flow_animator.py`

### 問題2: 親子線が子ノードに届かない

**原因**: Graphviz の plain 出力のスプライン端点は、ノードの境界上の正確な接触点だが、Graphviz はノードを楕円形として計算するため、矩形ノードとしてPillowで描画する場合にずれが生じる。例: エッジ端点 y=101.3 vs 子ノード top=108.0（約7px の隙間）。

**修正方針**: `flow_animator.py` または `layout_engine.py` にエッジ端点補正処理を追加する:
- エッジの最終点を、head ノードの上端中央 (cx, top) に補正する
- エッジの最初の点を、tail ノードの位置（couple_node の場合は中心、person の場合は下端中央）に補正する

**変更ファイル**: `layout_engine.py`（端点補正関数を追加）

### 実装ステップ

1. `layout_engine.py` にエッジ端点補正関数 `fix_edge_endpoints()` を追加
2. `flow_animator.py` に婚姻エッジ結合ロジックを追加（`_merge_marriage_edges()`）
3. `build_action_sequence()` で結合エッジを使用するよう修正
4. テスト追加・動作確認
