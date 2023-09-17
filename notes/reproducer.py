import click
from click.testing import CliRunner


@click.command()
@click.option(
    "--without-scm-ignore-files",
    "scm_ignore_files",
    is_flag=True,
    type=frozenset,
    flag_value=frozenset(),
    default=frozenset(["git"]),
    help="Skips adding SCM ignore files to the environment "
    "directory (Git is supported by default).",
)
def rcli(scm_ignore_files):
    print(f"{scm_ignore_files = }")
    print(f"{type(scm_ignore_files) = }")


def test_rcli():
    runner = CliRunner()
    result = runner.invoke(rcli)
    assert result.exit_code == 0
    print(result.output)


if __name__ == "__main__":
    test_rcli()
