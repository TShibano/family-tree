# Family Tree Generator

CSV形式の個人情報ファイルを読み込み、家系図を画像（PNG/SVG）およびアニメーション動画（MP4）として出力するCLIアプリケーション。

![アニメーション動画の例](./assets/flow_sample.gif)

## インストール

```bash
uv sync
```

システムに [Graphviz](https://graphviz.org/download/) がインストールされている必要があります。

```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt install graphviz
```

## 使い方

### 画像出力

```bash
# PNG出力
uv run family-tree render --input data.csv --output tree.png --format png

# SVG出力
uv run family-tree render --input data.csv --output tree.svg --format svg
```

### アニメーション動画出力

```bash
# カット切り替え方式
uv run family-tree animate --input data.csv --output tree.mp4

# フローアニメーション方式（線が動きながら描画される）
uv run family-tree animate-flow --input data.csv --output tree.mp4

# 線アニメーションの速度を変更（デフォルト: 0.5秒）
uv run family-tree animate-flow --input data.csv --output tree.mp4 --line-duration 1.0
```

## CSV仕様

UTF-8エンコーディングのCSVファイルを入力として使用します。

### 必須カラム

| カラム名 | 説明 | 例 |
|---|---|---|
| `id` | 一意の個人識別子 | `1` |
| `name` | 氏名 | `山田 太郎` |
| `birth_date` | 生年月日（YYYY-MM-DD） | `1940-03-15` |
| `sex` | 性別（M/F） | `M` |
| `parent_ids` | 親のID（カンマ区切り） | `1,2` |
| `spouse_id` | 配偶者のID | `2` |

### CSVサンプル

```csv
id,name,birth_date,sex,parent_ids,spouse_id
1,山田 太郎,1940-03-15,M,,2
2,山田 花子,1942-07-22,F,,1
3,山田 一郎,1965-01-10,M,"1,2",4
4,山田 美咲,1967-05-30,F,,3
```

### 拡張カラム

必須カラム以外のカラムはメタデータとして保持されます。将来の拡張として以下のカラムを想定しています:

- `death_date` - 没年月日
- `photo_path` - 写真ファイルパス
- `birth_place` - 出生地
- `occupation` - 職業
- `notes` - 備考

## 開発

```bash
# テスト実行
uv run pytest tests/

# コードフォーマット
uv run ruff format

# リンター
uv run ruff check

# 型チェック
uv run mypy src/
```
