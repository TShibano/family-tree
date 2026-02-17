from pathlib import Path

import click

from family_tree.config import load_config
from family_tree.csv_parser import CsvParseError, parse_csv
from family_tree.graph_builder import build_graph
from family_tree.renderer import render_graph

_CONFIG_OPTION = click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    default=None,
    help="設定ファイルのパス（省略時はカレントディレクトリの config.toml を自動検索）",
)


@click.group()
def cli() -> None:
    """家系図作成CLIアプリケーション"""
    pass


@cli.command()
@click.option("--input", "input_path", required=True, help="入力CSVファイルパス")
@click.option("--output", "output_path", required=True, help="出力ファイルパス")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["png", "svg"]),
    default="png",
    help="出力形式",
)
@_CONFIG_OPTION
def render(input_path: str, output_path: str, fmt: str, config_path: str | None) -> None:
    """家系図を画像として出力する"""
    try:
        family = parse_csv(input_path)
    except CsvParseError as e:
        raise click.ClickException(str(e))

    load_config(Path(config_path) if config_path else None)  # 将来の拡張用（renderは現状config不使用）
    dot = build_graph(family)
    result = render_graph(dot, output_path, fmt=fmt)
    click.echo(f"出力しました: {result}")


@cli.command()
@click.option("--input", "input_path", required=True, help="入力CSVファイルパス")
@click.option("--output", "output_path", required=True, help="出力MP4ファイルパス")
@_CONFIG_OPTION
def animate(input_path: str, output_path: str, config_path: str | None) -> None:
    """家系図をアニメーション動画として出力する"""
    from family_tree.animator import create_animation

    try:
        family = parse_csv(input_path)
    except CsvParseError as e:
        raise click.ClickException(str(e))

    config = load_config(Path(config_path) if config_path else None)
    result = create_animation(family, output_path, config)
    click.echo(f"出力しました: {result}")


@cli.command(name="animate-flow")
@click.option("--input", "input_path", required=True, help="入力CSVファイルパス")
@click.option("--output", "output_path", required=True, help="出力MP4ファイルパス")
@click.option(
    "--line-duration",
    type=float,
    default=None,
    help="線アニメーションの秒数（省略時は設定ファイルの値を使用）",
)
@_CONFIG_OPTION
def animate_flow(
    input_path: str,
    output_path: str,
    line_duration: float | None,
    config_path: str | None,
) -> None:
    """家系図をフローアニメーション動画として出力する（線が動くバージョン）"""
    from family_tree.flow_animator import create_flow_animation

    try:
        family = parse_csv(input_path)
    except CsvParseError as e:
        raise click.ClickException(str(e))

    config = load_config(Path(config_path) if config_path else None)
    result = create_flow_animation(family, output_path, config, line_duration=line_duration)
    click.echo(f"出力しました: {result}")
