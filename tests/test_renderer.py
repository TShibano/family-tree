from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from family_tree.csv_parser import parse_csv
from family_tree.graph_builder import build_graph
from family_tree.models import Family, Person, Sex
from family_tree.renderer import render_graph


def _build_minimal_family() -> Family:
    family = Family()
    family.add_person(
        Person(id=1, name="太郎", birth_date=date(2000, 1, 1), sex=Sex.M)
    )
    return family


class TestRenderGraph:
    def test_render_png(self, tmp_path: Path) -> None:
        family = _build_minimal_family()
        dot = build_graph(family)
        output = tmp_path / "test.png"
        result = render_graph(dot, output, fmt="png")
        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    def test_render_svg(self, tmp_path: Path) -> None:
        family = _build_minimal_family()
        dot = build_graph(family)
        output = tmp_path / "test.svg"
        result = render_graph(dot, output, fmt="svg")
        assert result == output
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "<svg" in content

    def test_auto_create_directory(self, tmp_path: Path) -> None:
        """出力先ディレクトリが存在しない場合に自動作成される。"""
        family = _build_minimal_family()
        dot = build_graph(family)
        output = tmp_path / "nested" / "dir" / "test.png"
        render_graph(dot, output, fmt="png")
        assert output.exists()

    def test_default_format_is_png(self, tmp_path: Path) -> None:
        family = _build_minimal_family()
        dot = build_graph(family)
        output = tmp_path / "default.png"
        render_graph(dot, output)
        assert output.exists()

    def test_render_sample_csv_png(self, tmp_path: Path) -> None:
        """examples/sample.csv からPNGを正常に出力できる。"""
        family = parse_csv("examples/sample.csv")
        dot = build_graph(family)
        output = tmp_path / "sample.png"
        render_graph(dot, output, fmt="png")
        assert output.exists()
        assert output.stat().st_size > 0

    def test_render_sample_csv_svg(self, tmp_path: Path) -> None:
        """examples/sample.csv からSVGを正常に出力できる。"""
        family = parse_csv("examples/sample.csv")
        dot = build_graph(family)
        output = tmp_path / "sample.svg"
        render_graph(dot, output, fmt="svg")
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "山田 太郎" in content
