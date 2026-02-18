# TODO_06: CSVによる個人ノードの色指定機能

## 概要

CSVに `fill_color`・`border_color` 列を追加し、個人ごとにノードの塗り色・枠色を指定できるようにする。
列が省略された場合や値が空の場合は、従来の性別デフォルト色を使用する。

## 色指定フォーマット

- CSS hex 形式: `#RRGGBB`（例: `#FF8800`）
- 両列とも独立したオプション（片方だけの指定も可）
- 不正な値はエラーとして `CsvParseError` を発生させる

## 対象列

| 列名          | 意味             | 省略時の挙動                     |
|---------------|------------------|----------------------------------|
| `fill_color`  | ノード塗り色     | 性別デフォルト（男: 白藍、女: 桜色） |
| `border_color`| ノード枠線色     | 性別デフォルト（男: 藍色、女: 蘇芳） |

## 実装ステップ

---

### Step 1: `models.py` — Person にカラーフィールドを追加

**変更内容:**
- `Person` dataclass に `fill_color: str | None = None` と `border_color: str | None = None` を追加
- `metadata` に保存するのではなく、明示的なフィールドとして管理（型安全性・可読性のため）

**変更後の `Person` フィールド一覧:**
```python
id: int
name: str
birth_date: date
sex: Sex
parent_ids: list[int]
spouse_id: int | None
fill_color: str | None      # 追加: ノード塗り色 (#RRGGBB or None)
border_color: str | None    # 追加: ノード枠線色 (#RRGGBB or None)
metadata: dict[str, str]
```

---

### Step 2: `csv_parser.py` — 色カラムのパースと検証

**変更内容:**
- `REQUIRED_COLUMNS` には追加しない（オプション列）
- `_parse_row()` 内で `fill_color`・`border_color` 列を明示的に読み取り、`Person` に渡す
- `_validate_hex_color()` ヘルパー関数を追加

```python
COLOR_COLUMNS = {"fill_color", "border_color"}

def _validate_hex_color(value: str, column: str) -> str:
    """#RRGGBB 形式を検証して返す。不正な場合は ValueError を発生させる。"""
    import re
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError(f"{column} の値が不正です（#RRGGBB 形式で指定してください）: {value!r}")
    return value.upper()
```

- `extra_columns` から `COLOR_COLUMNS` を除外（metadata には入れない）
- `_parse_row()` で `fill_color`・`border_color` を個別に抽出・検証・Person に渡す

---

### Step 3: `graph_builder.py` — Graphviz 静止画レンダリングへの反映

**変更内容:**
- `_get_node_color()` を `_get_node_fill_color(person)` と `_get_node_border_color(person)` に分割、またはシグネチャを変更してカスタム色を優先
- `build_graph()` と `build_graph_with_persons()` の `dot.node()` 呼び出しで、カスタム色があれば `fillcolor` に適用

```python
def _get_node_fill_color(person: Person) -> str:
    if person.fill_color:
        return person.fill_color
    return COLOR_MALE if person.sex == Sex.M else COLOR_FEMALE

def _get_node_border_color(person: Person) -> str | None:
    return person.border_color  # None の場合は Graphviz デフォルト
```

- `dot.node()` に `color=_get_node_border_color(person)` を追加（Noneなら省略）

---

### Step 4: `frame_drawer.py` — フローアニメーション描画への反映

**変更内容:**
- `_draw_person_node()` 内の色選択ロジックを修正
- `person.fill_color` が指定されていれば hex→RGB 変換して使用、なければ config のデフォルト色を使用

```python
def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """#RRGGBB を (R, G, B) に変換する。"""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
```

修正箇所:
```python
# 変更前
fill = colors.male_fill if person.sex == Sex.M else colors.female_fill
border = colors.male_border if person.sex == Sex.M else colors.female_border

# 変更後
default_fill = colors.male_fill if person.sex == Sex.M else colors.female_fill
default_border = colors.male_border if person.sex == Sex.M else colors.female_border
fill = _hex_to_rgb(person.fill_color) if person.fill_color else default_fill
border = _hex_to_rgb(person.border_color) if person.border_color else default_border
```

---

### Step 5: `examples/sample.csv` — サンプルデータの更新

**変更内容:**
- `fill_color`・`border_color` 列を追加
- 一部の行にカスタム色を指定し、残りは空欄（デフォルト色）

例:
```csv
id,name,birth_date,sex,parent_ids,spouse_id,fill_color,border_color
1,山田 太郎,1940-03-15,M,,2,#D4A853,#8B6914
2,山田 花子,1942-07-22,F,,1,,
...
```

---

### Step 6: テストの更新

**変更対象ファイル:**
- `tests/test_csv_parser.py`
  - 色列が正しく `Person` フィールドに反映されることを確認
  - 不正な hex 値（`red`, `#GGG`, `#1234567` など）で `CsvParseError` が発生することを確認
  - 色列が存在しない CSV（既存フォーマット）でも正常に動作することを確認
- `tests/test_graph_builder.py`
  - カスタム色を持つ `Person` のノードに正しい fillcolor が設定されることを確認
- `tests/test_flow_animator.py` または `test_renderer.py`
  - 必要に応じてフロー描画のカスタム色パスも確認

---

## 影響範囲まとめ

| ファイル            | 変更の種類 |
|---------------------|------------|
| `models.py`         | `Person` にフィールド追加 |
| `csv_parser.py`     | 色列のパース・バリデーション追加 |
| `graph_builder.py`  | ノード色取得ロジック修正 |
| `frame_drawer.py`   | ノード描画色選択ロジック修正 |
| `examples/sample.csv` | 列追加 |
| `tests/test_csv_parser.py` | テスト追加 |
| `tests/test_graph_builder.py` | テスト更新 |

## 後方互換性

- 既存の CSV（色列なし）は今まで通り動作する
- `fill_color`・`border_color` が空欄の行はデフォルト色が適用される
- `metadata` には色列の値は入らない（明示的フィールドとして管理）
