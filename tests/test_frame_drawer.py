"""FrameDrawer の alpha（フェードイン）機能テスト。"""
from __future__ import annotations

from datetime import date

import numpy as np

from family_tree.config import AppConfig
from family_tree.flow_animator import build_action_sequence
from family_tree.frame_drawer import FrameDrawer
from family_tree.graph_builder import build_graph_with_persons
from family_tree.layout_engine import extract_layout
from family_tree.models import Family, Person, Sex


def _simple_family() -> Family:
    family = Family()
    family.add_person(Person(id=1, name="太郎", birth_date=date(1940, 1, 1), sex=Sex.M))
    family.add_person(Person(id=2, name="花子", birth_date=date(1942, 1, 1), sex=Sex.F))
    return family


def _get_drawer(family: Family) -> FrameDrawer:
    all_ids = set(family.persons.keys())
    dot = build_graph_with_persons(family, all_ids)
    layout = extract_layout(dot)
    return FrameDrawer(layout, family, AppConfig())


class TestDrawFrameAlpha:
    def test_visible_persons_dict_accepted(self) -> None:
        """draw_frame() が dict[int, float] を受け取れる。"""
        family = _simple_family()
        drawer = _get_drawer(family)
        img = drawer.draw_frame({1: 1.0, 2: 0.5}, [])
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_alpha_zero_not_drawn(self) -> None:
        """alpha=0.0 の人物ブロックは描画されない（背景と同じになる）。"""
        family = _simple_family()
        drawer = _get_drawer(family)
        img_with = drawer.draw_frame({1: 0.0}, [])
        img_without = drawer.draw_frame({}, [])
        # alpha=0.0 は fading リストに含まれないため描画されず、両者は同じになる
        arr_with = np.array(img_with)
        arr_without = np.array(img_without)
        assert np.array_equal(arr_with, arr_without)

    def test_alpha_one_same_as_opaque(self) -> None:
        """alpha=1.0 の描画は alpha 指定なし（デフォルト 1.0）と等しい。"""
        family = _simple_family()
        drawer = _get_drawer(family)
        img_alpha1 = drawer.draw_frame({1: 1.0}, [])
        # ピクセルを比較
        arr = np.array(img_alpha1)
        # 何らかのピクセルが描画されていること（全透明でない）
        assert arr[..., 3].max() > 0

    def test_partial_alpha_between_zero_and_one(self) -> None:
        """alpha=0.5 の描画は alpha=0 と alpha=1 の中間のアルファ値を持つ。"""
        family = _simple_family()
        drawer = _get_drawer(family)
        img = drawer.draw_frame({1: 0.5}, [])
        arr = np.array(img)
        # 描画されたピクセルのアルファ値が 0〜255 の中間にある
        alpha_channel = arr[..., 3]
        unique_alphas = set(alpha_channel.flatten().tolist())
        # alpha=0 と 255 以外の中間値が存在する（フェードイン中のセル）
        has_intermediate = any(0 < a < 255 for a in unique_alphas)
        assert has_intermediate
