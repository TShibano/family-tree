"""設定ファイルの読み込みと設定値の管理。

TOML 形式の設定ファイルを読み込み、AppConfig として返す。
設定ファイルが存在しない場合はデフォルト値を使用する。
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ColorConfig:
    """描画色の設定（和色）。"""

    background: tuple[int, int, int] = (245, 240, 232)    # 生成色（きなりいろ）
    male_fill: tuple[int, int, int] = (193, 216, 236)      # 白藍（しらあい）
    female_fill: tuple[int, int, int] = (253, 239, 242)    # 桜色（さくらいろ）
    male_border: tuple[int, int, int] = (46, 79, 111)      # 藍色（あいいろ）
    female_border: tuple[int, int, int] = (142, 53, 74)    # 蘇芳（すおう）
    marriage_line: tuple[int, int, int] = (197, 61, 67)    # 朱色（しゅいろ）
    child_line: tuple[int, int, int] = (89, 88, 87)        # 墨色（すみいろ）
    text: tuple[int, int, int] = (43, 43, 43)              # 墨


@dataclass
class DimensionConfig:
    """描画パラメータの設定（6x解像度 — 90インチスクリーン向けデフォルト）。"""

    dpi: int = 432               # 解像度（1インチあたりのピクセル数）
    padding: int = 240           # グラフ周囲の余白 (px)
    line_width_marriage: int = 18
    line_width_child: int = 12
    border_width: int = 10
    corner_radius: int = 48      # ノード角丸半径 (px)
    font_size_name: int = 90     # 名前フォントサイズ (px)


@dataclass
class AnimationConfig:
    """アニメーションパラメータの設定。"""

    fps: int = 24
    line_duration: float = 0.5   # 線アニメーション秒数（animate-flow）
    pause_duration: float = 0.3  # シーン間の静止秒数（animate-flow）
    final_pause: float = 2.0     # 最後の全体表示秒数（animate-flow）
    scene_duration: float = 2.0  # 各シーンの表示秒数（animate）


@dataclass
class AppConfig:
    """アプリケーション全体の設定。"""

    colors: ColorConfig = field(default_factory=ColorConfig)
    dimensions: DimensionConfig = field(default_factory=DimensionConfig)
    animation: AnimationConfig = field(default_factory=AnimationConfig)


# ---------------------------------------------------------------------------
# バリデーション
# ---------------------------------------------------------------------------

_RGB_KEYS = (
    "background",
    "male_fill",
    "female_fill",
    "male_border",
    "female_border",
    "marriage_line",
    "child_line",
    "text",
)

_DIM_INT_KEYS = (
    "dpi",
    "padding",
    "line_width_marriage",
    "line_width_child",
    "border_width",
    "corner_radius",
    "font_size_name",
)

_ANIM_INT_KEYS = ("fps",)
_ANIM_FLOAT_KEYS = ("line_duration", "pause_duration", "final_pause", "scene_duration")


def _validate_rgb(value: object, key: str) -> tuple[int, int, int]:
    """RGB 配列値を検証し tuple[int, int, int] に変換する。"""
    if not isinstance(value, list) or len(value) != 3:
        print(
            f"設定エラー: {key} は [R, G, B] 形式の3要素配列で指定してください",
            file=sys.stderr,
        )
        sys.exit(1)
    for i, v in enumerate(value):
        if not isinstance(v, int) or not (0 <= v <= 255):
            print(
                f"設定エラー: {key}[{i}] は 0〜255 の整数で指定してください",
                file=sys.stderr,
            )
            sys.exit(1)
    return (int(value[0]), int(value[1]), int(value[2]))


def _build_colors(data: dict[str, object]) -> ColorConfig:
    cfg = ColorConfig()
    for key in _RGB_KEYS:
        if key in data:
            setattr(cfg, key, _validate_rgb(data[key], f"style.colors.{key}"))
    return cfg


def _build_dimensions(data: dict[str, object]) -> DimensionConfig:
    cfg = DimensionConfig()
    for key in _DIM_INT_KEYS:
        if key in data:
            val = data[key]
            if not isinstance(val, int):
                print(
                    f"設定エラー: style.dimensions.{key} は整数で指定してください",
                    file=sys.stderr,
                )
                sys.exit(1)
            setattr(cfg, key, val)
    return cfg


def _build_animation(data: dict[str, object]) -> AnimationConfig:
    cfg = AnimationConfig()
    for key in _ANIM_INT_KEYS:
        if key in data:
            val = data[key]
            if not isinstance(val, int):
                print(
                    f"設定エラー: animation.{key} は整数で指定してください",
                    file=sys.stderr,
                )
                sys.exit(1)
            setattr(cfg, key, val)
    for key in _ANIM_FLOAT_KEYS:
        if key in data:
            val = data[key]
            if not isinstance(val, (int, float)):
                print(
                    f"設定エラー: animation.{key} は数値で指定してください",
                    file=sys.stderr,
                )
                sys.exit(1)
            setattr(cfg, key, float(val))
    return cfg


# ---------------------------------------------------------------------------
# ロード
# ---------------------------------------------------------------------------


def load_config(path: Path | None) -> AppConfig:
    """設定ファイルを読み込んで AppConfig を返す。

    Args:
        path: 設定ファイルのパス。None の場合はカレントディレクトリの
              config.toml を探索し、存在しなければデフォルト値を使用する。

    Returns:
        AppConfig オブジェクト。
    """
    config_path = path if path is not None else Path("config.toml")

    if not config_path.exists():
        return AppConfig()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    app_config = AppConfig()

    style: dict[str, object] = data.get("style", {})  # type: ignore[assignment]
    if isinstance(style, dict):
        colors = style.get("colors")
        if isinstance(colors, dict):
            app_config.colors = _build_colors(colors)  # type: ignore[arg-type]
        dimensions = style.get("dimensions")
        if isinstance(dimensions, dict):
            app_config.dimensions = _build_dimensions(dimensions)  # type: ignore[arg-type]

    animation = data.get("animation")
    if isinstance(animation, dict):
        app_config.animation = _build_animation(animation)  # type: ignore[arg-type]

    return app_config
