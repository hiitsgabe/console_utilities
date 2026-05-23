"""
p4a recipe for python-zstandard.

Builds the native C extension (zstandard.backend_c) by cross-compiling the
bundled libzstd amalgamation (zstandard-0.21.0/zstd/zstd.c) with the Android
NDK. Without this, NSZ decompression on Android falls back to the much slower
CFFI/Python path, making NSZ→NSP conversion 10-20x slower than necessary.

Notes on cross-compile correctness:

* _PYTHON_HOST_PLATFORM tells distutils we're cross-compiling and what target
  tag to put in the resulting .so filename. Without it, the host's tag
  (e.g. x86_64-linux-gnu) is baked in and Android Python silently refuses to
  load the module, falling back to CFFI — defeating the whole point of this
  recipe. Pattern copied from p4a's stock numpy recipe.

* --no-cffi-backend skips the CFFI extension at build_ext time (we don't need
  it — zstandard's __init__ prefers backend_c on CPython). pip install . in
  current p4a master doesn't accept that flag, so install_python_package
  drops it for the install step.
"""
from pythonforandroid.recipe import CompiledComponentsPythonRecipe


class ZstandardRecipe(CompiledComponentsPythonRecipe):
    version = "0.21.0"
    url = (
        "https://files.pythonhosted.org/packages/source/z/zstandard/"
        "zstandard-{version}.tar.gz"
    )
    depends = ["setuptools"]
    call_hostpython_via_targetpython = False
    # Build-only — stripped before the install step (see install_python_package).
    setup_extra_args = ["--no-cffi-backend"]

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        # Tell distutils we're cross-compiling. arch.command_prefix is
        # 'aarch64-linux-android' / 'arm-linux-androideabi' which becomes
        # the platform tag in the produced .so name. Without this, the .so
        # is tagged with the build host's platform and Android Python won't
        # import it.
        env["_PYTHON_HOST_PLATFORM"] = arch.command_prefix
        # zstd.c is a 50k-line amalgamation. -O2 keeps build times reasonable
        # while still producing fast code; -fvisibility=hidden is what setup.py
        # already passes, kept here so future flag additions don't shadow it.
        env["CFLAGS"] = env.get("CFLAGS", "") + " -O2 -fvisibility=hidden"
        return env

    def install_python_package(self, arch, **kwargs):
        # pip install . doesn't accept --no-cffi-backend (it's a setup.py
        # custom flag). Strip our build-only args for the install step.
        saved = self.setup_extra_args
        self.setup_extra_args = []
        try:
            super().install_python_package(arch, **kwargs)
        finally:
            self.setup_extra_args = saved


recipe = ZstandardRecipe()
