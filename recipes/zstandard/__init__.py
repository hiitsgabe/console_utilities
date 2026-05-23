"""
p4a recipe for python-zstandard.

Builds the native C extension (zstandard.backend_c) by cross-compiling the
bundled libzstd amalgamation (zstandard-0.21.0/zstd/zstd.c) with the Android
NDK. Without this, NSZ decompression on Android falls back to the much slower
CFFI/Python path, making NSZ→NSP conversion 10-20x slower than necessary.

We pass --no-cffi-backend so only the C backend is built — the CFFI backend
needs cffi at build time and is the slow path we're trying to avoid anyway.
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
    setup_extra_args = ["--no-cffi-backend"]

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        # zstd.c is a 50k-line amalgamation. -O2 keeps build times reasonable
        # while still producing fast code; -fvisibility=hidden is what setup.py
        # already passes, kept here so future flag additions don't shadow it.
        env["CFLAGS"] = env.get("CFLAGS", "") + " -O2 -fvisibility=hidden"
        return env


recipe = ZstandardRecipe()
