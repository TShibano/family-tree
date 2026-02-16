from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from family_tree.animator import create_animation, generate_generation_frames
from family_tree.csv_parser import parse_csv
from family_tree.graph_builder import compute_generations
from family_tree.models import Family, Person, Sex


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


class TestGenerateGenerationFrames:
    def test_frame_count_matches_generations(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        gens = compute_generations(family)
        max_gen = max(gens.values())
        frames = generate_generation_frames(family, tmp_path)
        assert len(frames) == max_gen + 1

    def test_frames_are_png_files(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        frames = generate_generation_frames(family, tmp_path)
        for frame in frames:
            assert frame.exists()
            assert frame.stat().st_size > 0


class TestCreateAnimation:
    def test_creates_mp4(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        output = tmp_path / "test.mp4"
        result = create_animation(family, output, generation_duration=1.0, fade_duration=0.5)
        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    def test_auto_create_directory(self, tmp_path: Path) -> None:
        family = _build_two_gen_family()
        output = tmp_path / "nested" / "dir" / "test.mp4"
        create_animation(family, output, generation_duration=1.0, fade_duration=0.5)
        assert output.exists()

    def test_sample_csv_animation(self, tmp_path: Path) -> None:
        """examples/sample.csv からアニメーションを正常に生成できる。"""
        family = parse_csv("examples/sample.csv")
        output = tmp_path / "sample.mp4"
        create_animation(family, output, generation_duration=1.0, fade_duration=0.5)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_single_generation(self, tmp_path: Path) -> None:
        """1世代（親なし1人）でもエラーにならない。"""
        family = Family()
        family.add_person(
            Person(id=1, name="単独者", birth_date=date(2000, 1, 1), sex=Sex.M)
        )
        output = tmp_path / "single.mp4"
        create_animation(family, output, generation_duration=1.0, fade_duration=0.5)
        assert output.exists()
