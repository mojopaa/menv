import os
import shutil
import types
from pathlib import Path

import tomlkit
from tomlkit.toml_file import TOMLFile

MODULAR_DIR = Path.home() / ".modular"
MOJO_PKG_DIR = MODULAR_DIR / "pkg/packages.modular.com_mojo"
MOJO_BIN_DIR = MOJO_PKG_DIR / "bin"


def create_if_needed(d):
    if not os.path.exists(d):
        os.makedirs(d)
    elif os.path.islink(d) or os.path.isfile(d):
        raise ValueError("Unable to create directory %r" % d)


def clear_directory(path):
    for fn in os.listdir(path):
        fn = os.path.join(path, fn)
        if os.path.islink(fn) or os.path.isfile(fn):
            os.remove(fn)
        elif os.path.isdir(fn):
            shutil.rmtree(fn)


class MojoEnvBuilder:
    def __init__(
        self,
        system_site_packages=False,
        clear=False,
        symlinks=False,
        upgrade=False,
        prompt=None,
        upgrade_deps=False,
    ):
        self.system_site_packages = system_site_packages
        self.clear = clear
        self.symlinks = symlinks
        self.upgrade = upgrade
        self.orig_prompt = prompt
        if prompt == ".":  # see bpo-38901
            prompt = os.path.basename(os.getcwd())
        self.prompt = prompt
        self.upgrade_deps = upgrade_deps

    def ensure_directories(self, env_dir):
        """
        Create the directories for the environment.

        Returns a context object which holds paths in the environment,
        for use by subsequent logic.
        """
        if os.pathsep in os.fspath(env_dir):
            raise ValueError(
                f"Refusing to create a venv in {env_dir} because "
                f"it contains the PATH separator {os.pathsep}."
            )

        if os.path.exists(env_dir) and self.clear:
            clear_directory(env_dir)

        context = types.SimpleNamespace()
        context.env_dir = env_dir
        context.env_name = os.path.split(env_dir)[1]
        prompt = self.prompt if self.prompt is not None else context.env_name
        context.prompt = "(%s) " % prompt
        create_if_needed(env_dir)

        context.mojo_dir = str(MOJO_BIN_DIR)  # TODO: use findmojo
        context.mojo_exe = "mojo"

        return context

    def create_configuration(self, context):
        """
        Create a configuration file indicating where the environment's Python
        was copied from, and whether the system site-packages should be made
        available in the environment.

        Args:
            context: The context object containing information about the environment.

        Returns:
            None
        """
        context.cfg_path = path = os.path.join(context.env_dir, "mojovenv.toml")

        cfg = tomlkit.document()
        cfg.add("home", context.mojo_dir)  # TODO

        if self.system_site_packages:
            incl = True
        else:
            incl = False
        cfg.add("include-system-site-packages", incl)

        # TODO: Read VERSION
        with open(MOJO_PKG_DIR / "VERSION") as f:
            version = f.read().strip()

        cfg.add("version", version)

        TOMLFile(path).write(cfg)


if __name__ == "__main__":
    m = MojoEnvBuilder()
    c = m.ensure_directories(".asdf")
    m.create_configuration(c)
