import shutil
from pathlib import Path
from pprint import pprint

import pytest

from menv.builder import (
    MojoEnvBuilder,
    change_config,
    clear_directory,
    create_if_needed,
)


class TestMojoEnvBuilder:

    @classmethod
    def setup_class(cls):
        cls.builder = MojoEnvBuilder()
        cls.venv_path = Path(__file__).parent / "venv"
        cls.context = cls.builder.ensure_directories(cls.venv_path)


    def test_init(self) -> None:
        pprint(f"{self.context = }")  # use pytest -s to show this print
        pass

    def test_ensure_directories(self) -> None:
        assert hasattr(self.context, "env_dir")
        assert hasattr(self.context, "env_name")
        assert hasattr(self.context, "prompt")
        assert hasattr(self.context, "mojo_dir")
        assert hasattr(self.context, "mojo_exe")
        assert hasattr(self.context, "executable")
        assert hasattr(self.context, "bin_name")
        assert hasattr(self.context, "pkg_dir")
        assert hasattr(self.context, "bin_path")
        assert hasattr(self.context, "lib_path")
        assert hasattr(self.context, "env_exe")
        assert hasattr(self.context, "env_cfg")

    # comment to debug venv
    @classmethod
    def teardown_class(cls) -> None:
        shutil.rmtree(cls.venv_path)
