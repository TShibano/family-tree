# TODO - Family Tree Generator 実行計画

## Phase 1: プロジェクト初期設定

- [x] `uv init` でプロジェクト初期化、`pyproject.toml` 設定
- [x] 依存ライブラリ追加（graphviz, Pillow, moviepy, click, pytest, ruff, mypy）
- [x] `src/family_tree/` パッケージ構成作成
- [x] `.gitignore` 作成（output/, __pycache__, .venv 等）
- [x] サンプルCSVファイル（`examples/sample.csv`）作成

## Phase 2: データモデル & CSV読み込み

- [ ] `models.py` - Person データクラス定義（必須フィールド + メタデータ辞書で拡張対応）
- [ ] `models.py` - Family データクラス定義（Person集合 + 関係性管理）
- [ ] `csv_parser.py` - CSV読み込み処理の実装
- [ ] `csv_parser.py` - バリデーション（必須カラム存在確認、ID重複チェック、参照整合性）
- [ ] `csv_parser.py` - 未知カラムをメタデータとして保持する処理
- [ ] `tests/test_csv_parser.py` - CSV読み込みのユニットテスト

## Phase 3: 家系図グラフ構築

- [ ] `graph_builder.py` - Family データから世代（depth）を算出するロジック
- [ ] `graph_builder.py` - 親子関係・婚姻関係のグラフ構造構築
- [ ] `graph_builder.py` - Graphviz の Digraph オブジェクト生成
- [ ] `graph_builder.py` - ノードのスタイル設定（性別による色分け、ラベル表示）
- [ ] `graph_builder.py` - エッジのスタイル設定（婚姻=横線、親子=縦線）
- [ ] `tests/test_graph_builder.py` - グラフ構築のユニットテスト

## Phase 4: 画像出力（PNG/SVG）

- [ ] `renderer.py` - Graphviz グラフからPNG出力
- [ ] `renderer.py` - Graphviz グラフからSVG出力
- [ ] `renderer.py` - 出力先ディレクトリの自動作成
- [ ] `tests/test_renderer.py` - 画像出力のユニットテスト
- [ ] サンプルCSVを使った出力結果の目視確認・レイアウト調整

## Phase 5: CLIインターフェース

- [ ] `main.py` - click を使った CLI 構築
- [ ] `main.py` - `render` サブコマンド（--input, --output, --format オプション）
- [ ] `main.py` - `animate` サブコマンド（--input, --output オプション）
- [ ] `pyproject.toml` - `[project.scripts]` でエントリーポイント設定
- [ ] CLI の動作確認

## Phase 6: アニメーション動画出力

- [ ] `animator.py` - 世代ごとにフレーム画像を生成するロジック
- [ ] `animator.py` - moviepy を使って連番画像からMP4を生成
- [ ] `animator.py` - フェードイン等のトランジション演出
- [ ] `tests/test_animator.py` - アニメーション生成のユニットテスト
- [ ] サンプルCSVを使った動画出力の目視確認

## Phase 7: 仕上げ

- [ ] ruff format / ruff check で全体のコード品質チェック
- [ ] mypy で型チェック通過確認
- [ ] 全テスト通過確認
- [ ] README.md 作成（使い方・CSV仕様の説明）
