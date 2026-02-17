# 設定ファイル対応 実装計画

## 概要

色・解像度・アニメーション時間パラメータを TOML 形式の設定ファイルから読み込めるようにする。
設定ファイルが存在しない場合は現在のハードコード値をデフォルトとして使用する。

## 設定ファイルの仕様

### 配置・指定方法

- **デフォルト**: カレントディレクトリの `config.toml` を自動読み込み
- **CLI オプション**: 全コマンドで `--config <パス>` により任意のファイルを指定可能
- 優先順位: `--config` 指定 > カレントディレクトリの `config.toml` > ハードコードデフォルト値

### 設定ファイルの構造

```toml
# config.toml

[style.colors]
background    = [245, 240, 232]  # 生成色（きなりいろ）
male_fill     = [193, 216, 236]  # 白藍（しらあい）
female_fill   = [253, 239, 242]  # 桜色（さくらいろ）
male_border   = [46,  79,  111]  # 藍色（あいいろ）
female_border = [142, 53,  74 ]  # 蘇芳（すおう）
marriage_line = [197, 61,  67 ]  # 朱色（しゅいろ）
child_line    = [89,  88,  87 ]  # 墨色（すみいろ）
text          = [43,  43,  43 ]  # 墨

[style.dimensions]
dpi              = 432  # 解像度（1インチあたりのピクセル数）
padding          = 240  # グラフ周囲の余白 (px)
line_width_marriage = 18
line_width_child    = 12
border_width        = 10
corner_radius       = 48  # ノード角丸半径 (px)
font_size_name      = 90  # 名前フォントサイズ (px)

[animation]
fps            = 24   # フレームレート
line_duration  = 0.5  # 線アニメーション秒数（animate-flow）
pause_duration = 0.3  # シーン間の静止秒数（animate-flow）
final_pause    = 2.0  # 最後の全体表示秒数（animate-flow）
scene_duration = 2.0  # 各シーンの表示秒数（animate）
```

---

## 実装ステップ

### Step 1: `config.py` の新規作成

**ファイル**: `src/family_tree/config.py`

- `ColorConfig`, `DimensionConfig`, `AnimationConfig`, `AppConfig` の dataclass を定義
  - 全フィールドに現在のハードコード値をデフォルト値として設定
- `load_config(path: Path | None) -> AppConfig` 関数を実装
  - `path` が指定されている場合: そのファイルをロード
  - `path` が `None` の場合: カレントディレクトリの `config.toml` を探索、なければデフォルト
  - 存在しないキーはデフォルト値にフォールバック（部分的な設定ファイルも許容）
  - TOML のパースには Python 3.11+ 標準の `tomllib` を使用
  - 不正な値（例: RGB 配列が3要素でない）はエラーメッセージを出して終了

**AppConfig の型定義**:
```python
@dataclass
class ColorConfig:
    background: tuple[int, int, int] = (245, 240, 232)
    male_fill: tuple[int, int, int] = (193, 216, 236)
    # ... 以下同様

@dataclass
class DimensionConfig:
    dpi: int = 432
    padding: int = 240
    # ... 以下同様

@dataclass
class AnimationConfig:
    fps: int = 24
    line_duration: float = 0.5
    # ... 以下同様

@dataclass
class AppConfig:
    colors: ColorConfig = field(default_factory=ColorConfig)
    dimensions: DimensionConfig = field(default_factory=DimensionConfig)
    animation: AnimationConfig = field(default_factory=AnimationConfig)
```

---

### Step 2: `layout_engine.py` の修正

**変更内容**:
- モジュールレベルの `DPI = 432` と `SCALE = DPI` を削除
- `extract_layout(dot, dpi: int = 432) -> GraphLayout` にシグネチャ変更
- `_parse_plain(plain_text, scale: int) -> GraphLayout` に引数追加
- 内部で `SCALE` を使っている箇所を `scale` パラメータに置き換え

**影響範囲**: `flow_animator.py` から呼ばれる `extract_layout` の呼び出し元を更新

---

### Step 3: `frame_drawer.py` の修正

**変更内容**:
- モジュールレベルの `COLOR_*`, `PADDING`, `LINE_WIDTH_*`, `BORDER_WIDTH`, `CORNER_RADIUS`, `FONT_SIZE_NAME` 定数を削除
- `FrameDrawer.__init__(self, layout, family, config: AppConfig)` に `config` 引数を追加
- `self.config = config` として保持し、全描画メソッドで参照
- `_draw_person_node`, `_draw_edge`, `draw_frame` 内の定数参照を `self.config.*` に置き換え

---

### Step 4: `flow_animator.py` の修正

**変更内容**:
- モジュールレベルの `DEFAULT_FPS`, `DEFAULT_LINE_DURATION`, `DEFAULT_PAUSE_DURATION`, `DEFAULT_FINAL_PAUSE` を削除
- `create_flow_animation(family, output_path, config: AppConfig, line_duration: float | None = None) -> str` に変更
  - `line_duration` は CLI の `--line-duration` による上書き用（`None` の場合は `config.animation.line_duration` を使用）
- `FrameDrawer` の生成時に `config` を渡す
- `extract_layout` の呼び出しに `dpi=config.dimensions.dpi` を渡す

---

### Step 5: `animator.py` の修正

**変更内容**:
- モジュールレベルの `SCENE_DURATION = 2.0` と `FPS = 24` を削除
- `create_animation(family, output_path, config: AppConfig) -> str` に変更
- `generate_scene_frames` にも `config` を渡す形に変更

---

### Step 6: `main.py` の修正

**変更内容**:
- 全コマンド（`render`, `animate`, `animate-flow`）に以下を追加:
  ```python
  @click.option(
      "--config",
      "config_path",
      type=click.Path(exists=True, dir_okay=False),
      default=None,
      help="設定ファイルのパス（省略時はカレントディレクトリの config.toml を自動検索）",
  )
  ```
- 各コマンド関数内で `config = load_config(Path(config_path) if config_path else None)` を呼び出し
- `create_animation`, `create_flow_animation`, `render_graph` に `config` を渡す
- `animate-flow` の `--line-duration` は引き続き CLI から受け取り、`config.animation.line_duration` を上書きする形で維持

---

### Step 7: サンプル設定ファイルの作成

**ファイル**: `examples/config.toml`

- 全設定キーとデフォルト値を記載
- 和風カラーの説明コメントを付記
- README の参照先として機能する

---

### Step 8: テストの追加・更新

**新規**: `tests/test_config.py`
- `load_config(None)` でデフォルト値が返ること
- 設定ファイルを部分的に記述した場合に残りがデフォルト値になること
- 不正な値（RGB が3要素でない等）でエラーになること

**既存テストの更新**:
- `frame_drawer.py`, `flow_animator.py`, `animator.py` を使うテストに `AppConfig()` をデフォルト引数として渡すように修正

---

## 変更ファイル一覧

| ファイル | 変更種別 | 概要 |
|---|---|---|
| `src/family_tree/config.py` | **新規作成** | AppConfig dataclass・load_config() |
| `src/family_tree/layout_engine.py` | 修正 | DPI定数削除・dpi引数化 |
| `src/family_tree/frame_drawer.py` | 修正 | 色定数削除・config引数化 |
| `src/family_tree/flow_animator.py` | 修正 | DEFAULT_*定数削除・config引数化 |
| `src/family_tree/animator.py` | 修正 | SCENE_DURATION/FPS削除・config引数化 |
| `src/family_tree/main.py` | 修正 | --configオプション追加・config引き渡し |
| `examples/config.toml` | **新規作成** | デフォルト値を記載したサンプル設定 |
| `tests/test_config.py` | **新規作成** | config.py の単体テスト |
| `tests/test_flow_animator.py` | 修正 | config引数対応 |
| `tests/test_animator.py` | 修正 | config引数対応 |

---

## 実装上の注意点

- `tomllib` は Python 3.11 以降の標準ライブラリ。`pyproject.toml` で `python = ">=3.12"` が指定されているため追加依存不要
- 設定ファイルが存在しない場合は警告なしにデフォルト値を使用する（エラーにしない）
- `--config` で指定したファイルが存在しない場合は Click が `exists=True` で自動的にエラーを出す
- `animate-flow` の `--line-duration` は CLI からの上書きとして残す（設定ファイルより CLI 引数を優先）
- 色値は TOML 配列 `[R, G, B]` として定義し、`tuple[int, int, int]` に変換する
