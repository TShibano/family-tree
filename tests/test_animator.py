from __future__ import annotations

from datetime import date
from pathlib import Path


from family_tree.animator import create_animation, generate_scene_frames
from family_tree.config import AppConfig
from family_tree.csv_parser import parse_csv
from family_tree.graph_builder import compute_scene_order
from family_tree.models import Family, Person, Sex


def _fast_config() -> AppConfig:
    """テスト用の短時間設定。"""
    cfg = AppConfig()
    cfg.animation.scene_duration = 1.0
    return cfg


def _build_two_gen_family() -> Family:
    """2世代のシンプルな家族。"""
    family = Family()
    family.add_person(
        Person(id=1, name="太郎", birth_date=date(1940, 1, 1), sex=Sex.M, spouse_id=2)
    )
    family.add_person(
        Person(id=2, name="花子", birth_date=date(1942, 1, 1), sex=Sex.F, spouse_id=1)
    )
    family.add_person(
        Person(
            id=3,
            name="一郎",
            birth_date=date(1965, 1, 1),
            sex=Sex.M,
            parent_ids=[1, 2],
        )
    )
    return family


class TestGenerateSceneFrames:
    def test_frame_count_matches_scenes(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        scenes = compute_scene_order(family)
        frames = generate_scene_frames(family, tmp_path)
        assert len(frames) == len(scenes)

    def test_frames_are_png_files(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        frames = generate_scene_frames(family, tmp_path)
        for frame in frames:
            assert frame.exists()
            assert frame.stat().st_size > 0


class TestCreateAnimation:
    def test_creates_mp4(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        output = tmp_path / "test.mp4"
        result = create_animation(family, output, _fast_config())
        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    def test_auto_create_directory(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        output = tmp_path / "nested" / "dir" / "test.mp4"
        create_animation(family, output, _fast_config())
        assert output.exists()

    def test_sample_csv_animation(self, tmp_path: Path) -> None:
        """examples/sample.csv からアニメーションを正常に生成できる。"""
        family = parse_csv("examples/sample.csv")
        output = tmp_path / "sample.mp4"
        create_animation(family, output, _fast_config())
        assert output.exists()
        assert output.stat().st_size > 0

    def test_single_person(self, tmp_path: Path) -> None:
        """1人だけでもエラーにならない。"""
        family = Family()
        family.add_person(
            Person(id=1, name="単独者", birth_date=date(2000, 1, 1), sex=Sex.M)
        )
        output = tmp_path / "single.mp4"
        create_animation(family, output, _fast_config())
        assert output.exists()
