import os
from venv import EnvBuilder

import click

CORE_VENV_DEPS = ("pip",)  # TODO: assure

if os.name == "nt":
    use_symlinks = False
else:
    use_symlinks = True


@click.command()
@click.argument("dirs", help="A directory to create the environment in.")
@click.option(
    "--system-site-packages",
    "system_site",
    is_flag=True,
    help="Give the virtual environment access to the " "system site-packages dir.",
)
@click.option(
    "--symlinks",
    is_flag=True,
    default=use_symlinks,
    help="Try to use symlinks rather than copies, "
    "when symlinks are not the default for "
    "the platform.",
)
@click.option(
    "--copies",
    "symlinks",
    is_flag=True,
    default=not use_symlinks,
    flag_value=False,
    help="Try to use copies rather than symlinks, "
    "even when symlinks are the default for "
    "the platform.",
)
@click.option(
    "--clear",
    is_flag=True,
    help="Delete the contents of the "
    "environment directory if it "
    "already exists, before "
    "environment creation.",
)
@click.option(
    "--upgrade",
    is_flag=True,
    help="Upgrade the environment "
    "directory to use this version "
    "of Python, assuming Python "
    "has been upgraded in-place.",
)
@click.option(
    "--without-pip",
    "with_pip",
    is_flag=True,
    default=True,
    flag_value=False,
    help="Skips installing or upgrading pip in the "
    "virtual environment (pip is bootstrapped "
    "by default)",
)
@click.option(
    "--prompt", help="Provides an alternative prompt prefix for " "this environment."
)
@click.option(
    "--upgrade-deps",
    is_flag=True,
    help=f'Upgrade core dependencies ({", ".join(CORE_VENV_DEPS)}) '
    "to the latest version in PyPI",
)
def cli(dirs, system_site, symlinks, clear, upgrade, with_pip, prompt, upgrade_deps):
    if upgrade and clear:
        raise ValueError("you cannot supply --upgrade and --clear together.")

    builder = EnvBuilder(
        system_site_packages=system_site,
        clear=clear,
        symlinks=symlinks,
        upgrade=upgrade,
        with_pip=with_pip,
        prompt=prompt,
        upgrade_deps=upgrade_deps,
    )

    print(builder)

    for d in dirs:
        builder.create(d)