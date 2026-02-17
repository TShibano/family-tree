# Family Tree Generator - 家系図作成アプリ

## プロジェクト概要

CSV形式の個人情報ファイルを読み込み、家系図を画像（PNG/SVG）およびアニメーション動画（MP4）として出力するCLIアプリケーション。

## 技術スタック

- **言語**: Python 3.12+
- **パッケージ管理**: uv
- **主要ライブラリ**:
  - `graphviz` - 家系図のグラフ構造生成・画像出力・レイアウト座標計算
  - `Pillow` - 画像処理・フレーム描画（フローアニメーション用）
  - `moviepy` - アニメーション動画生成
  - `numpy` - フレームデータの配列変換（moviepy連携）
  - `csv` (標準ライブラリ) - CSV読み込み

## 要件定義

### 入力仕様

- **形式**: CSV ファイル（UTF-8）
- **初期必須カラム**:
  - `id` - 一意の個人識別子
  - `name` - 氏名
  - `birth_date` - 生年月日（YYYY-MM-DD）
  - `sex` - 性別（M/F）
  - `parent_ids` - 親のID（カンマ区切り、例: `1,2`）
  - `spouse_id` - 配偶者のID
- **将来拡張予定カラム**（スキーマ設計時に考慮すること）:
  - `death_date` - 没年月日
  - `photo_path` - 写真ファイルパス
  - `birth_place` - 出生地
  - `occupation` - 職業
  - `notes` - 備考
- **設計方針**: 未知のカラムは無視せず、メタデータとして保持する（拡張性確保）

### 出力仕様

#### 1. 静止画像出力
- **対応形式**: PNG, SVG（コマンドオプションで選択）
- **レイアウト**: 世代を縦方向（上が古い世代）に配置
- **表示内容**:
  - 各人物: 名前、生年月日を表示するノード
  - 婚姻関係: 横線で接続
  - 親子関係: 縦線で接続
  - 性別による色分け

#### 2. アニメーション動画出力（カット切り替え方式）
- **コマンド**: `family-tree animate`
- **形式**: MP4
- **内容**: 家系図が世代ごとに順番に展開されるアニメーション
- **演出**: 古い世代から新しい世代へシーン単位でカット切り替え
- **実装**: Graphviz で各シーンの静止画を生成し、moviepy で結合

#### 3. フローアニメーション動画出力（線が動く方式）
- **コマンド**: `family-tree animate-flow`
- **形式**: MP4
- **内容**: 人物ブロックが表示された後、線が伸びるアニメーションで関係性を描画
- **演出**:
  - 人物ブロック: 瞬間表示
  - 婚姻線: 一方の人物から他方へ水平に伸びるアニメーション（1本の連続線）
  - 親子線: 夫婦の中間点から子どもへ下方向に伸びるアニメーション
- **描画スタイル（和風）**:
  - 背景: 生成色（きなりいろ）— 和紙のような温かみ
  - 男性ブロック: 白藍（しらあい）塗り、藍色枠
  - 女性ブロック: 桜色塗り、蘇芳枠
  - 婚姻線: 朱色（しゅいろ）
  - 親子線: 墨色（すみいろ）
  - フォント: ヒラギノ明朝 W6（太字）
  - ノード表示: 名前のみ
  - 角丸矩形ブロック
- **解像度**: 432 DPI（90インチスクリーン対応、4K超出力）
- **実装**: Graphviz でレイアウト座標を算出 → Pillow でフレーム単位描画 → moviepy で MP4 エンコード
- **オプション**: `--line-duration`（線アニメーション秒数、デフォルト 0.5秒）

### 想定規模

- 小〜中規模（最大約60人、3〜4世代）

### CLI インターフェース

```
# 画像出力
family-tree render --input data.csv --output tree.png --format png
family-tree render --input data.csv --output tree.svg --format svg

# 動画出力（カット切り替え方式）
family-tree animate --input data.csv --output tree.mp4

# 動画出力（フローアニメーション方式）
family-tree animate-flow --input data.csv --output tree.mp4
family-tree animate-flow --input data.csv --output tree.mp4 --line-duration 1.0
```

## プロジェクト構成

```
family-tree/
├── CLAUDE.md
├── pyproject.toml
├── src/
│   └── family_tree/
│       ├── __init__.py
│       ├── main.py            # CLIエントリーポイント
│       ├── models.py           # データモデル（Person, Family）
│       ├── csv_parser.py       # CSV読み込み・バリデーション
│       ├── graph_builder.py    # 家系図グラフ構築・シーン順序算出
│       ├── renderer.py         # 画像出力（PNG/SVG）
│       ├── animator.py         # アニメーション動画生成（カット切り替え方式）
│       ├── layout_engine.py    # Graphviz レイアウト座標抽出・端点補正
│       ├── frame_drawer.py     # Pillow フレーム描画（和風スタイル）
│       └── flow_animator.py    # フローアニメーション生成（線が動く方式）
├── tests/
│   ├── __init__.py
│   ├── test_csv_parser.py
│   ├── test_graph_builder.py
│   ├── test_renderer.py
│   ├── test_animator.py
│   └── test_flow_animator.py
├── examples/
│   └── sample.csv              # サンプルデータ
└── output/                     # 出力先ディレクトリ（.gitignore対象）
```

## アーキテクチャ

### フローアニメーションのパイプライン

```
CSV → models.py → graph_builder.py → layout_engine.py → frame_drawer.py → flow_animator.py → MP4
         ↓               ↓                  ↓                  ↓                  ↓
       Family      Digraph生成        座標抽出・補正      Pillowフレーム描画    moviepyエンコード
                   シーン順序算出      (plain形式パース)    (進捗率による部分描画)  (VideoClip)
```

### 主要モジュールの役割

| モジュール | 責務 |
|---|---|
| `layout_engine.py` | Graphviz の `-Tplain` 出力をパースし、ノード・エッジの座標をピクセル単位で取得。エッジ端点をノード境界に補正。 |
| `frame_drawer.py` | レイアウト座標を受け取り、Pillow で1フレームを描画。線の進捗率（0.0〜1.0）による部分描画をサポート。 |
| `flow_animator.py` | シーン順序からアニメーションアクション列を構築。婚姻エッジの結合、`VideoClip(make_frame)` によるフレーム単位の動画生成。 |

## 開発コマンド

```bash
# 依存関係インストール
uv sync

# テスト実行
uv run pytest tests/

# コードフォーマット
uv run ruff format

# リンター
uv run ruff check

# 型チェック
uv run mypy src/

# アプリ実行
uv run family-tree render --input examples/sample.csv --output output/tree.png
uv run family-tree animate --input examples/sample.csv --output output/tree.mp4
uv run family-tree animate-flow --input examples/sample.csv --output output/flow.mp4
```

## 開発ルール

- テストは `pytest` で実行
- コードフォーマッタ: `ruff format`
- リンター: `ruff check`
- 型チェック: `mypy src/`
- データモデルの変更時は既存CSVとの後方互換性を維持すること
- 未知のCSVカラムはエラーにせず、メタデータとして保持すること
