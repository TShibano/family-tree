# TODO_08: 人物セルのフェードインアニメーション

## 概要

`animate-flow` コマンドで人物ブロックを瞬間表示（duration=0.0）からフェードイン（透明→不透明）に変更する。

## 背景・要件

現在の `APPEAR` アクションは `duration=0.0` で即座に表示される。
フェードインにより、ブロックが滑らかに出現する演出が可能になる。

### アニメーション動作

```
[現在]
  APPEAR: 瞬間表示（alpha=1.0 で即座）

[変更後]
  APPEAR: appear_duration 秒かけて alpha 0.0 → 1.0 に線形補間
```

- デフォルトの `appear_duration`: 0.3秒
- `--appear-duration 0.0` を指定すると従来の瞬間表示と同等
- 線アニメーション（`--line-duration`）と独立して設定可能

---

## 変更ファイルと実装詳細

### 1. `src/family_tree/config.py`

`AnimationConfig` に `appear_duration` フィールドを追加する。

```python
@dataclass
class AnimationConfig:
    fps: int = 24
    line_duration: float = 0.5
    appear_duration: float = 0.3   # ← 追加: フェードイン秒数（0.0で瞬間表示）
    pause_duration: float = 0.3
    final_pause: float = 2.0
    scene_duration: float = 2.0
```

`_ANIM_FLOAT_KEYS` に `"appear_duration"` を追加する。

```python
_ANIM_FLOAT_KEYS = ("line_duration", "appear_duration", "pause_duration", "final_pause", "scene_duration")
```

### 2. `src/family_tree/frame_drawer.py`

#### `draw_frame()` のシグネチャ変更

`visible_person_ids` の型を `set[int]` から `dict[int, float]`（person_id → alpha 0.0〜1.0）に変更する。

```python
def draw_frame(
    self,
    visible_person_ids: dict[int, float],  # person_id → alpha（0.0〜1.0）
    visible_edges: list[tuple[EdgeLayout, float]],
) -> Image.Image:
    ...
    for pid, alpha in visible_person_ids.items():
        node_name = str(pid)
        if node_name in self.layout.nodes:
            person = self.family.get_person(pid)
            if person is not None:
                self._draw_person_node(draw, self.layout.nodes[node_name], person, alpha)
```

#### `_draw_person_node()` に alpha パラメータを追加

Pillow の RGBA モード画像では fill/outline/text 色を `(R, G, B, A)` の4タプルで指定できるため、alpha をそのまま適用できる。

```python
def _draw_person_node(
    self,
    draw: ImageDraw.ImageDraw,
    node: NodeLayout,
    person: object,
    alpha: float = 1.0,   # ← 追加
) -> None:
    ...
    alpha_int = int(alpha * 255)
    fill_rgba = (*fill, alpha_int)
    border_rgba = (*border, alpha_int)
    text_rgba = (*colors.text, alpha_int)

    draw.rectangle([x0, y0, x1, y1], fill=fill_rgba, outline=border_rgba, width=dims.border_width)
    draw.text((name_x, name_y), name_text, fill=text_rgba, font=self.font_name)
```

> **注意**: 既存の `draw.rectangle()` は `fill=tuple[int,int,int]` を渡していたが、
> RGBA 画像に対して4タプルを渡すことで透明度が反映される。
> `alpha=1.0`（デフォルト）時は `alpha_int=255` となり従来と同等の描画になる。

### 3. `src/family_tree/flow_animator.py`

#### `build_action_sequence()` のシグネチャ変更

```python
def build_action_sequence(
    family: Family,
    layout: GraphLayout,
    line_duration: float = 0.5,
    appear_duration: float = 0.3,   # ← 追加
    pause_duration: float = 0.3,
) -> list[AnimAction]:
```

`APPEAR` アクションの `duration` を `appear_duration` に変更する。

```python
# 変更前
actions.append(AnimAction(action_type=ActionType.APPEAR, duration=0.0, new_person_ids=[pid]))

# 変更後
actions.append(AnimAction(action_type=ActionType.APPEAR, duration=appear_duration, new_person_ids=[pid]))
```

#### `create_flow_animation()` の変更

`config.animation.appear_duration` を読み込み、`build_action_sequence()` に渡す。

```python
appear_duration = config.animation.appear_duration
actions = build_action_sequence(
    family, layout, effective_line_duration, appear_duration, pause_duration
)
```

#### `make_frame()` の状態管理変更

`visible_persons` の型を `set[int]` → `dict[int, float]` に変更し、フェードイン進捗を管理する。

```python
def make_frame(t: float) -> np.ndarray:
    visible_persons: dict[int, float] = {}   # person_id → alpha
    ...

    if action.action_type == ActionType.APPEAR:
        if action.duration == 0 or t >= action_end:
            # 完了済み（または瞬間表示）
            for pid in action.new_person_ids:
                visible_persons[pid] = 1.0
        else:
            # フェードイン中
            elapsed = t - action_start
            progress = elapsed / action.duration
            progress = min(max(progress, 0.0), 1.0)
            for pid in action.new_person_ids:
                visible_persons[pid] = progress
```

> `visible_persons` は辞書なので、後のアクションで同一 `pid` が上書きされる場合も
> 最終的な alpha が正しく保たれる（フェードイン完了後は 1.0 で上書き）。

`drawer.draw_frame()` の呼び出しも `set → dict` に合わせて変更。

```python
img = drawer.draw_frame(visible_persons, visible_edge_list)
```

### 4. `src/family_tree/main.py`

`animate-flow` コマンドに `--appear-duration` オプションを追加する。

```python
@click.option(
    "--appear-duration",
    type=float,
    default=None,
    help="フェードインアニメーションの秒数（省略時は設定ファイルの値を使用）",
)
```

`create_flow_animation()` の呼び出しに `appear_duration` を追加する。

```python
result = create_flow_animation(
    family, output_path, config,
    line_duration=line_duration,
    appear_duration=appear_duration,
)
```

`create_flow_animation()` のシグネチャも対応させる。

```python
def create_flow_animation(
    family: Family,
    output_path: str | Path,
    config: AppConfig,
    line_duration: float | None = None,
    appear_duration: float | None = None,   # ← 追加
) -> Path:
    ...
    effective_appear_duration = appear_duration if appear_duration is not None else anim.appear_duration
```

### 5. `tests/test_flow_animator.py`

既存テストへの影響:
- `build_action_sequence()` の `APPEAR` アクションが `duration=0.3`（デフォルト）になる
- `duration=0.0` を明示すれば従来通り。既存テストは `appear_duration=0.0` を渡すか、duration の検証を更新する

新規テスト:

```python
class TestFadeInAnimation:
    def test_appear_action_has_duration(self):
        """APPEAR アクションが appear_duration を持つ。"""

    def test_appear_action_zero_duration(self):
        """appear_duration=0.0 のとき APPEAR.duration が 0 になる。"""

    def test_make_frame_fading_person_has_partial_alpha(self):
        """フェードイン中（t が APPEAR の途中）は alpha が 0〜1 の中間値になる。"""

    def test_make_frame_completed_person_has_full_alpha(self):
        """フェードイン完了後は alpha=1.0 になる。"""
```

### 6. `tests/test_frame_drawer.py`

```python
class TestDrawFrameAlpha:
    def test_visible_persons_dict_accepted(self):
        """draw_frame() が dict[int, float] を受け取れる。"""

    def test_alpha_zero_person_not_visible(self):
        """alpha=0.0 の人物ブロックは描画されない（背景と一致）。"""

    def test_alpha_one_same_as_opaque(self):
        """alpha=1.0 の描画結果が従来の不透明描画と等しい。"""
```

---

## CLIオプションまとめ

```bash
# デフォルト（フェードイン 0.3秒）
uv run family-tree animate-flow --input data.csv --output flow.mp4

# フェードイン時間を指定
uv run family-tree animate-flow --input data.csv --output flow.mp4 --appear-duration 0.5

# 瞬間表示（従来の動作）
uv run family-tree animate-flow --input data.csv --output flow.mp4 --appear-duration 0.0
```

config.toml での設定:

```toml
[animation]
appear_duration = 0.3
```

---

## 懸念事項・考慮点

- **APPEAR アクションの duration 追加による総時間増加**: 各人物ごとに `appear_duration` 分だけ動画が長くなる。グループ表示（TODO_07）と組み合わせた場合はグループ単位での1回分のみ。
- **`visible_persons` の辞書更新順序**: 同一 `pid` の APPEAR が複数ある場合は最後の値が使われる。これは意図通り（フェードイン完了後の上書き）。
- **既存テストの互換性**: `draw_frame()` の引数型が変わるため、既存テストで `set` を渡している箇所は `dict` に更新が必要。

---

## 実装ステップ

1. `config.py` に `appear_duration` を追加
2. `frame_drawer.py` の `draw_frame()` と `_draw_person_node()` を変更
3. `flow_animator.py` の `build_action_sequence()`・`make_frame()`・`create_flow_animation()` を変更
4. `main.py` に `--appear-duration` オプションを追加
5. `tests/test_flow_animator.py` の既存テストを更新・新規テストを追加
6. `tests/test_frame_drawer.py` に alpha テストを追加
7. 全テストを実行して確認（`uv run pytest tests/`）
