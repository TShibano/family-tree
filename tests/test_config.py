from __future__ import annotations

import sys
from pathlib import Path

import pytest

from family_tree.config import AppConfig, AnimationConfig, ColorConfig, DimensionConfig, load_config


class TestAppConfigDefaults:
    def test_default_colors(self) -> None:
        cfg = AppConfig()
        assert cfg.colors.background == (245, 240, 232)
        assert cfg.colors.male_fill == (193, 216, 236)
        assert cfg.colors.female_fill == (253, 239, 242)
        assert cfg.colors.male_border == (46, 79, 111)
        assert cfg.colors.female_border == (142, 53, 74)
        assert cfg.colors.marriage_line == (197, 61, 67)
        assert cfg.colors.child_line == (89, 88, 87)
        assert cfg.colors.text == (43, 43, 43)

    def test_default_dimensions(self) -> None:
        cfg = AppConfig()
        assert cfg.dimensions.dpi == 432
        assert cfg.dimensions.padding == 240
        assert cfg.dimensions.line_width_marriage == 18
        assert cfg.dimensions.line_width_child == 12
        assert cfg.dimensions.border_width == 10
        assert cfg.dimensions.corner_radius == 48
        assert cfg.dimensions.font_size_name == 90

    def test_default_animation(self) -> None:
        cfg = AppConfig()
        assert cfg.animation.fps == 24
        assert cfg.animation.line_duration == 0.5
        assert cfg.animation.pause_duration == 0.3
        assert cfg.animation.final_pause == 2.0
        assert cfg.animation.scene_duration == 2.0


class TestLoadConfigNone:
    def test_no_file_returns_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """config.toml が存在しないディレクトリでは AppConfig デフォルト値を返す。"""
        monkeypatch.chdir(tmp_path)
        cfg = load_config(None)
        assert isinstance(cfg, AppConfig)
        assert cfg.colors.background == (245, 240, 232)
        assert cfg.dimensions.dpi == 432
        assert cfg.animation.fps == 24

    def test_auto_discover_config_toml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """カレントディレクトリに config.toml があれば自動で読み込む。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.toml").write_text(
            "[style.colors]\nbackground = [10, 20, 30]\n", encoding="utf-8"
        )
        cfg = load_config(None)
        assert cfg.colors.background == (10, 20, 30)
        # 指定していないキーはデフォルト値
        assert cfg.colors.male_fill == (193, 216, 236)


class TestLoadConfigPartial:
    def test_partial_colors(self, tmp_path: Path) -> None:
        """一部の色だけ上書きして残りはデフォルト値になる。"""
        toml = tmp_path / "cfg.toml"
        toml.write_text(
            "[style.colors]\nbackground = [0, 0, 0]\n", encoding="utf-8"
        )
        cfg = load_config(toml)
        assert cfg.colors.background == (0, 0, 0)
        assert cfg.colors.male_fill == (193, 216, 236)  # デフォルト維持

    def test_partial_dimensions(self, tmp_path: Path) -> None:
        toml = tmp_path / "cfg.toml"
        toml.write_text(
            "[style.dimensions]\ndpi = 72\n", encoding="utf-8"
        )
        cfg = load_config(toml)
        assert cfg.dimensions.dpi == 72
        assert cfg.dimensions.padding == 240  # デフォルト維持

    def test_partial_animation(self, tmp_path: Path) -> None:
        toml = tmp_path / "cfg.toml"
        toml.write_text(
            "[animation]\nfps = 30\nline_duration = 1.0\n", encoding="utf-8"
        )
        cfg = load_config(toml)
        assert cfg.animation.fps == 30
        assert cfg.animation.line_duration == 1.0
        assert cfg.animation.pause_duration == 0.3  # デフォルト維持

    def test_empty_file(self, tmp_path: Path) -> None:
        """空ファイルはデフォルト値を返す。"""
        toml = tmp_path / "cfg.toml"
        toml.write_text("", encoding="utf-8")
        cfg = load_config(toml)
        assert cfg.colors.background == (245, 240, 232)

    def test_explicit_path(self, tmp_path: Path) -> None:
        """Path を明示指定した場合に正しく読み込む。"""
        toml = tmp_path / "my_config.toml"
        toml.write_text(
            "[animation]\nscene_duration = 5.0\n", encoding="utf-8"
        )
        cfg = load_config(toml)
        assert cfg.animation.scene_duration == 5.0


class TestLoadConfigValidation:
    def test_rgb_wrong_length(self, tmp_path: Path) -> None:
        """RGB 配列が3要素でない場合は sys.exit(1) する。"""
        toml = tmp_path / "cfg.toml"
        toml.write_text(
            "[style.colors]\nbackground = [1, 2]\n", encoding="utf-8"
        )
        with pytest.raises(SystemExit) as exc_info:
            load_config(toml)
        assert exc_info.value.code == 1

    def test_rgb_out_of_range(self, tmp_path: Path) -> None:
        """RGB 値が 0〜255 の範囲外の場合は sys.exit(1) する。"""
        toml = tmp_path / "cfg.toml"
        toml.write_text(
            "[style.colors]\nbackground = [256, 0, 0]\n", encoding="utf-8"
        )
        with pytest.raises(SystemExit) as exc_info:
            load_config(toml)
        assert exc_info.value.code == 1

    def test_rgb_not_list(self, tmp_path: Path) -> None:
        """RGB 値がリストでない場合は sys.exit(1) する。"""
        toml = tmp_path / "cfg.toml"
        toml.write_text(
            "[style.colors]\nbackground = \"white\"\n", encoding="utf-8"
        )
        with pytest.raises(SystemExit) as exc_info:
            load_config(toml)
        assert exc_info.value.code == 1

    def test_dpi_not_int(self, tmp_path: Path) -> None:
        """dpi が整数でない場合は sys.exit(1) する。"""
        toml = tmp_path / "cfg.toml"
        toml.write_text(
            "[style.dimensions]\ndpi = 432.5\n", encoding="utf-8"
        )
        with pytest.raises(SystemExit) as exc_info:
            load_config(toml)
        assert exc_info.value.code == 1

    def test_fps_not_int(self, tmp_path: Path) -> None:
        """fps が整数でない場合は sys.exit(1) する。"""
        toml = tmp_path / "cfg.toml"
        toml.write_text(
            "[animation]\nfps = 24.0\n", encoding="utf-8"
        )
        with pytest.raises(SystemExit) as exc_info:
            load_config(toml)
        assert exc_info.value.code == 1
