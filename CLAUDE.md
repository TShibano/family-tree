# Family Tree Generator - 家系図作成アプリ

## プロジェクト概要

CSV形式の個人情報ファイルを読み込み、家系図を画像（PNG/SVG）およびアニメーション動画（MP4）として出力するCLIアプリケーション。

## 技術スタック

- **言語**: Python 3.12+
- **パッケージ管理**: uv
- **主要ライブラリ**:
  - `graphviz` - 家系図のグラフ構造生成・画像出力
  - `Pillow` - 画像処理・加工
  - `moviepy` - アニメーション動画生成
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

#### 2. アニメーション動画出力
- **形式**: MP4
- **内容**: 家系図が世代ごとに順番に展開されるアニメーション
- **演出**: 古い世代から新しい世代へ順に表示

### 想定規模

- 小〜中規模（最大約60人、3〜4世代）

### CLI インターフェース

```
# 画像出力
family-tree render --input data.csv --output tree.png --format png
family-tree render --input data.csv --output tree.svg --format svg

# 動画出力
family-tree animate --input data.csv --output tree.mp4
```

## プロジェクト構成

```
family-tree/
├── CLAUDE.md
├── pyproject.toml
├── src/
│   └── family_tree/
│       ├── __init__.py
│       ├── main.py          # CLIエントリーポイント
│       ├── models.py         # データモデル（Person, Family）
│       ├── csv_parser.py     # CSV読み込み・バリデーション
│       ├── graph_builder.py  # 家系図グラフ構築
│       ├── renderer.py       # 画像出力（PNG/SVG）
│       └── animator.py       # アニメーション動画生成
├── tests/
│   ├── __init__.py
│   ├── test_csv_parser.py
│   ├── test_graph_builder.py
│   ├── test_renderer.py
│   └── test_animator.py
├── examples/
│   └── sample.csv            # サンプルデータ
└── output/                   # 出力先ディレクトリ（.gitignore対象）
```

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
```

## 開発ルール

- テストは `pytest` で実行
- コードフォーマッタ: `ruff format`
- リンター: `ruff check`
- 型チェック: `mypy src/`
- データモデルの変更時は既存CSVとの後方互換性を維持すること
- 未知のCSVカラムはエラーにせず、メタデータとして保持すること
