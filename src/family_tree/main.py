import click


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
    click.echo(f"Rendering {input_path} -> {output_path} ({fmt})")


@cli.command()
@click.option("--input", "input_path", required=True, help="入力CSVファイルパス")
@click.option("--output", "output_path", required=True, help="出力MP4ファイルパス")
def animate(input_path: str, output_path: str) -> None:
    """家系図をアニメーション動画として出力する"""
    click.echo(f"Animating {input_path} -> {output_path}")
