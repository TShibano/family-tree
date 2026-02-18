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

# 線アニメーションの速度を変更
uv run family-tree animate-flow --input data.csv --output tree.mp4 --line-duration 1.0
```

### 設定ファイルによるスタイルカスタマイズ

色・解像度・アニメーション時間などを TOML 形式の設定ファイルで変更できます。

```bash
# サンプル設定ファイルをコピーして編集
cp examples/config.toml config.toml

# --config オプションで設定ファイルを指定（全コマンド対応）
uv run family-tree animate-flow --input data.csv --output tree.mp4 --config config.toml
uv run family-tree animate --input data.csv --output tree.mp4 --config config.toml
uv run family-tree render --input data.csv --output tree.png --config config.toml
```

`--config` を省略した場合、カレントディレクトリの `config.toml` が自動的に読み込まれます。

#### 設定ファイルの構造

```toml
[style.colors]
background    = [245, 240, 232]  # 生成色（きなりいろ）— 背景
male_fill     = [193, 216, 236]  # 白藍（しらあい）  — 男性ノード
female_fill   = [253, 239, 242]  # 桜色（さくらいろ）— 女性ノード
male_border   = [46,  79,  111]  # 藍色（あいいろ）  — 男性枠線
female_border = [142, 53,  74]   # 蘇芳（すおう）    — 女性枠線
marriage_line = [197, 61,  67]   # 朱色（しゅいろ）  — 婚姻線
child_line    = [89,  88,  87]   # 墨色（すみいろ）  — 親子線
text          = [43,  43,  43]   # 墨                — テキスト

[style.dimensions]
dpi              = 432  # 解像度（1インチあたりのピクセル数）
padding          = 240  # グラフ周囲の余白 (px)
line_width_marriage = 18
line_width_child    = 12
border_width        = 10
corner_radius       = 48
font_size_name      = 90

[animation]
fps            = 24   # フレームレート
line_duration  = 0.5  # 線アニメーション秒数（animate-flow）
pause_duration = 0.3  # シーン間の静止秒数（animate-flow）
final_pause    = 2.0  # 最後の全体表示秒数（animate-flow）
scene_duration = 2.0  # 各シーンの表示秒数（animate）
```

全項目の記載は任意です。省略した項目はデフォルト値が使用されます。

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
