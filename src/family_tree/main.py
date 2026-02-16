import click

from family_tree.csv_parser import CsvParseError, parse_csv
from family_tree.graph_builder import build_graph
from family_tree.renderer import render_graph


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
def render(input_path: str, output_path: str, fmt: str) -> None:
    """家系図を画像として出力する"""
    try:
        family = parse_csv(input_path)
    except CsvParseError as e:
        raise click.ClickException(str(e))

    dot = build_graph(family)
    result = render_graph(dot, output_path, fmt=fmt)
    click.echo(f"出力しました: {result}")


@cli.command()
@click.option("--input", "input_path", required=True, help="入力CSVファイルパス")
@click.option("--output", "output_path", required=True, help="出力MP4ファイルパス")
def animate(input_path: str, output_path: str) -> None:
    """家系図をアニメーション動画として出力する"""
    from family_tree.animator import create_animation

    try:
        family = parse_csv(input_path)
    except CsvParseError as e:
        raise click.ClickException(str(e))

    result = create_animation(family, output_path)
    click.echo(f"出力しました: {result}")
