# アニメーション描画順序の変更 (v4)

## 概要

フローアニメーション（`animate-flow`）の描画順序を、CSVファイルの行順（上から順）に変更する。
これまでの世代・家族構造ベースのシーン順序（`compute_scene_order`）は使用しない。

## 現状

- `flow_animator.py` の `build_action_sequence()` が `compute_scene_order()` を呼び出してシーン順序を決定
- 兄弟姉妹は同じシーンでまとめて表示される

## 変更後の仕様

- CSVの行順に **1人ずつ** 描画する
- 兄弟姉妹のまとめ表示はなし（全員個別に表示）
- 各人物の表示後、関連する線をアニメーション:
  - 配偶者が既に表示済み → 婚姻線を描画
  - 両親が既に表示済み → 親子線を描画

## 変更方針

`Family.persons` は `dict[int, Person]` で、`parse_csv()` がCSV行順に `add_person()` を呼ぶため、
`family.persons.values()` の順序がそのままCSV行順となる。

`flow_animator.py` の `build_action_sequence()` を修正し、
`compute_scene_order()` の代わりに `family.persons.values()` を直接イテレーションする。

## 変更ファイル

- `flow_animator.py` — `build_action_sequence()` のシーン順序ロジックを変更

## 実装ステップ

1. `build_action_sequence()` で `compute_scene_order()` の呼び出しを削除
2. `family.persons.values()` を順にイテレーションし、1人ずつ APPEAR + 関連線の DRAW_LINE を生成
3. テスト更新・動作確認
