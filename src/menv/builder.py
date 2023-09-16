import logging
import os
import shutil
import types
from pathlib import Path

import tomlkit
from tomlkit.toml_file import TOMLFile

MODULAR_NAME = ".modular"
MODULAR_PKG_FOLDER = "pkg"
MODULAR_PKG_NAME = "packages.modular.com_mojo"

MODULAR_DIR = Path.home() / MODULAR_NAME
MOJO_PKG_DIR = MODULAR_DIR / MODULAR_PKG_FOLDER / MODULAR_PKG_NAME
MOJO_BIN_DIR = MOJO_PKG_DIR / "bin"
MOJO_LIB_DIR = MOJO_PKG_DIR / "lib"
MOJO_EXECUTABLE = MOJO_BIN_DIR / "mojo"

logger = logging.getLogger(__name__)


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
        # scm_ignore_files=frozenset(),
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
        # self.scm_ignore_files = frozenset(map(str.lower, scm_ignore_files))

    def create(self, env_dir):
        """
        Create a virtual environment in a directory.

        :param env_dir: The target directory to create an environment in.

        """
        env_dir = os.path.abspath(env_dir)
        context = self.ensure_directories(env_dir)
        # for scm in self.scm_ignore_files:
        #     getattr(self, f"create_{scm}_ignore_file")(context)
        # See issue 24875. We need system_site_packages to be False
        # until after pip is installed.
        true_system_site_packages = self.system_site_packages
        self.system_site_packages = False
        self.create_configuration(context)
        self.setup_mojo(context)
        # if self.with_pip:
        #     self._setup_pip(context)
        if not self.upgrade:
            self.setup_scripts(context)
            self.post_setup(context)
        if true_system_site_packages:
            # We had set it to False before, now
            # restore it and rewrite the configuration
            self.system_site_packages = True
            self.create_configuration(context)
        if self.upgrade_deps:
            self.upgrade_dependencies(context)
        self.create_git_ignore_file(context)

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

        # venv paths
        venv_modular_dir = Path(env_dir) / MODULAR_NAME
        venv_pkg_dir = venv_modular_dir / MODULAR_PKG_FOLDER / MODULAR_PKG_NAME

        bin_name = "bin"
        venv_bin_dir = venv_pkg_dir / bin_name
        venv_lib_dir = venv_pkg_dir / "lib"
        venv_mojo_excutable = venv_bin_dir / "mojo"

        context.executable = MOJO_EXECUTABLE
        context.bin_name = bin_name
        context.bin_path = str(venv_bin_dir)
        context.lib_path = str(venv_lib_dir)
        context.env_exe = str(venv_mojo_excutable)

        create_if_needed(venv_bin_dir)
        create_if_needed(venv_lib_dir)

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
        cfg.add("home", context.mojo_dir)

        if self.system_site_packages:
            incl = True
        else:
            incl = False
        cfg.add("include-system-site-packages", incl)

        # Read VERSION
        with open(MOJO_PKG_DIR / "VERSION") as f:
            version = f.read().strip()

        cfg.add("version", version)

        if self.prompt is not None:
            cfg.add("prompt", f"{self.prompt!r}")

        cfg.add("mojo-executable", str(MOJO_EXECUTABLE))

        # build command
        args = []
        nt = os.name == "nt"
        if nt and self.symlinks:
            args.append("--symlinks")
        if not nt and not self.symlinks:
            args.append("--copies")
        if self.system_site_packages:
            args.append("--system-site-packages")
        if self.clear:
            args.append("--clear")
        if self.upgrade:
            args.append("--upgrade")
        if self.upgrade_deps:
            args.append("--upgrade-deps")
        if self.orig_prompt is not None:
            args.append(f'--prompt="{self.orig_prompt}"')
        # if not self.scm_ignore_files:
        #     args.append("--without-scm-ignore-files")

        args.append(context.env_dir)
        args = " ".join(args)

        cfg.add("command", f"menv {args}")

        TOMLFile(path).write(cfg)

    if os.name != "nt":

        def symlink_or_copy(self, src, dst, relative_symlinks_ok=False):
            """
            Try symlinking a file, and if that fails, fall back to copying.
            """
            force_copy = not self.symlinks
            if not force_copy:
                try:
                    if not os.path.islink(dst):  # can't link to itself!
                        if relative_symlinks_ok:
                            assert os.path.dirname(src) == os.path.dirname(dst)
                            os.symlink(os.path.basename(src), dst)
                        else:
                            os.symlink(src, dst)
                except Exception:  # may need to use a more specific exception
                    logger.warning("Unable to symlink %r to %r", src, dst)
                    force_copy = True
            if force_copy:
                shutil.copyfile(src, dst)

    else:

        def symlink_or_copy(self, src, dst, relative_symlinks_ok=False):
            """
            Try symlinking a file, and if that fails, fall back to copying.
            """
            bad_src = os.path.lexists(src) and not os.path.exists(src)
            if self.symlinks and not bad_src and not os.path.islink(dst):
                try:
                    if relative_symlinks_ok:
                        assert os.path.dirname(src) == os.path.dirname(dst)
                        os.symlink(os.path.basename(src), dst)
                    else:
                        os.symlink(src, dst)
                    return
                except Exception:  # may need to use a more specific exception
                    logger.warning("Unable to symlink %r to %r", src, dst)

            if not os.path.exists(src):
                if not bad_src:
                    logger.warning("Unable to copy %r", src)
                return

            shutil.copyfile(src, dst)

    def recursive_symlink_or_copy(self, src, dst, relative_symlinks_ok=False):
        for item in os.listdir(src):
            src_item = os.path.join(src, item)
            dst_item = os.path.join(dst, item)
            if os.path.isfile(src_item):
                self.symlink_or_copy(src_item, dst_item, relative_symlinks_ok)
                shutil.copymode(src_item, dst_item)
            elif os.path.isdir(src_item):
                os.makedirs(dst_item, exist_ok=True)
                self.recursive_symlink_or_copy(src_item, dst_item, relative_symlinks_ok)
            else:
                logger.warning(f"Skipping {src_item}")

    def create_git_ignore_file(self, context):
        """
        Create a .gitignore file in the environment directory.

        The contents of the file cause the entire environment directory to be
        ignored by git.
        """
        gitignore_path = os.path.join(context.env_dir, ".gitignore")
        with open(gitignore_path, "w", encoding="utf-8") as file:
            file.write(
                "# Created by venv; "
                "see https://docs.python.org/3/library/venv.html\n"
            )  # TODO: change this?
            file.write("*\n")

    def setup_mojo(self, context):
        """
        Set up a Mojo executable in the environment.

        Args:
            context (obj): The information for the environment creation request being processed.
        """
        binpath = context.bin_path
        libpath = context.lib_path
        path = context.env_exe
        copier = self.symlink_or_copy
        dirname = context.mojo_dir  # context.mojo_dir = str(MOJO_BIN_DIR)

        if os.name != "nt":
            # copy lib and bin to venv
            self.recursive_symlink_or_copy(MOJO_LIB_DIR, libpath)
            self.recursive_symlink_or_copy(MOJO_BIN_DIR, binpath)

            for bin_item in os.listdir(binpath):
                if not os.path.islink(os.path.join(binpath, bin_item)):
                    # Set the executable's permissions
                    os.chmod(os.path.join(binpath, bin_item), 0o755)

            # Create symbolic links for mojo executables
            for suffix in "mojo":
                path = os.path.join(binpath, suffix)
                if not os.path.exists(path):
                    # Make copies if symlinks are not wanted
                    copier(context.env_exe, path, relative_symlinks_ok=True)
                    if not os.path.islink(path):
                        os.chmod(path, 0o755)

        else:
            pass  # TODO

    def replace_variables(self, text, context):
        """
        Replace variable placeholders in the script text with context-specific
        variables.

        Args:
            text (str): The text in which to replace placeholder variables.
            context (Context): The information for the environment creation request
                being processed.

        Returns:
            str: The text passed in, but with variables replaced.
        """
        # Replace '__VENV_DIR__' placeholder with context.env_dir
        text = text.replace("__VENV_DIR__", context.env_dir)

        # Replace '__VENV_NAME__' placeholder with context.env_name
        text = text.replace("__VENV_NAME__", context.env_name)

        # Replace '__VENV_PROMPT__' placeholder with context.prompt
        text = text.replace("__VENV_PROMPT__", context.prompt)

        # Replace '__VENV_BIN_NAME__' placeholder with context.bin_name
        text = text.replace("__VENV_BIN_NAME__", context.bin_name)

        # Replace '__VENV_MOJO__' placeholder with context.env_exe
        text = text.replace("__VENV_MOJO__", context.env_exe)

        return text

    def setup_scripts(self, context):
        """
        Set up scripts into the created environment from a directory.

        This method installs the default scripts into the environment
        being created. You can prevent the default installation by overriding
        this method if you really need to, or if you need to specify
        a different location for the scripts to install. By default, the
        'scripts' directory in the venv package is used as the source of
        scripts to install.
        """
        path = str(Path(__file__).with_name("scripts").absolute())
        self.install_scripts(context, path)

    def install_scripts(self, context, path):
        """
        Install scripts into the created environment from a directory.

        Args:
            context: The information for the environment creation request
                being processed.
            path: Absolute pathname of a directory containing script.
                Scripts in the 'common' subdirectory of this directory,
                and those in the directory named for the platform
                being run on, are installed in the created environment.
                Placeholder variables are replaced with environment-
                specific values.
        """
        binpath = context.bin_path  # Get the bin path from the context
        plen = len(path)  # Get the length of the path
        for root, dirs, files in os.walk(path):
            if root == path:  # At top-level, remove irrelevant dirs
                for d in dirs[:]:
                    if d not in ("common", os.name):
                        dirs.remove(d)
                continue  # Ignore files in top level
            for f in files:
                if (
                    os.name == "nt"
                    and f.startswith("mojo")
                    and f.endswith((".exe", ".pdb"))
                ):
                    continue  # Skip files that start with 'python' and end with '.exe' or '.pdb' on Windows
                srcfile = os.path.join(root, f)  # Get the source file path
                suffix = root[plen:].split(os.sep)[
                    2:
                ]  # Get the relative path of the file
                if not suffix:
                    dstdir = binpath  # If there is no suffix, set the destination directory as binpath
                else:
                    dstdir = os.path.join(
                        binpath, *suffix
                    )  # Set the destination directory as binpath + suffix
                if not os.path.exists(dstdir):
                    os.makedirs(
                        dstdir
                    )  # Create the destination directory if it does not exist
                dstfile = os.path.join(dstdir, f)  # Get the destination file path
                with open(srcfile, "rb") as f:
                    data = f.read()  # Read the source file data
                if not srcfile.endswith((".exe", ".pdb")):
                    try:
                        data = data.decode("utf-8")  # Decode the data as utf-8
                        data = self.replace_variables(
                            data, context
                        )  # Replace the placeholder variables with environment-specific values
                        data = data.encode("utf-8")  # Encode the data as utf-8
                    except UnicodeError as e:
                        data = None
                        logger.error(f"UnicodeError: {e}")
                        logger.warning(
                            "unable to copy script %r, " "may be binary: %s", srcfile, e
                        )  # Log a warning if unable to copy script due to UnicodeError
                if data is not None:
                    with open(dstfile, "wb") as f:
                        f.write(data)  # Write the data to the destination file
                    shutil.copymode(
                        srcfile, dstfile
                    )  # Copy the permissions from the source file to the destination file

    def upgrade_dependencies(self, context):
        logger.warning("TODO: upgrade CORE_VENV_DEPS")
        logger.warning("NOP right now.")

    def post_setup(self, context):
        """
        Hook for post-setup modification of the venv.
        Subclasses may install additional packages or scripts here,
        add activation shell scripts, etc.

        Parameters:
          - context: The information for the environment creation request
                     being processed.

        No changes are made in the function body.
        """

        pass


def create(
    env_dir,
    system_site_packages=False,
    clear=False,
    symlinks=False,
    prompt=None,
    upgrade_deps=False,
):
    """Create a virtual environment in a directory."""
    builder = MojoEnvBuilder(
        system_site_packages=system_site_packages,
        clear=clear,
        symlinks=symlinks,
        prompt=prompt,
        upgrade_deps=upgrade_deps,
    )
    builder.create(env_dir)


if __name__ == "__main__":
    # m = MojoEnvBuilder()
    # c = m.ensure_directories(".asdf")
    # m.create_configuration(c)
    # m.setup_mojo(c)
    # m.create_git_ignore_file(c)
    create(".asdf")
