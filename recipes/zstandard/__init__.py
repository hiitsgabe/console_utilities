"""
p4a recipe for python-zstandard.

Builds the native C extension (zstandard.backend_c) by cross-compiling the
bundled libzstd amalgamation (zstandard-0.21.0/zstd/zstd.c) with the Android
NDK. Without this, NSZ decompression on Android falls back to the much slower
CFFI/Python path, making NSZ→NSP conversion 10-20x slower than necessary.

Uses PyProjectRecipe (current p4a master's recipe class for pure-Python +
compiled-extension packages) which:
  * Drives the build via `python -m build --wheel`, which respects the
    isolated build environment — cffi isn't in zstandard's build deps, so
    setup.py auto-sets cffi=None and skips the CFFI backend without us
    having to pass any custom flag.
  * Writes build-opts.cfg with bdist_wheel.plat_name=android_<api>_<arch>
    so the produced wheel's .so files are tagged with the Android ABI
    (e.g. android_24_arm64_v8a / android_24_arm) — Python on Android can
    actually load them.

The earlier CompiledComponentsPythonRecipe attempt produced an ARM .so
tagged as x86_64-linux-gnu in the filename, which Python on Android refused
to import, silently falling back to CFFI.
"""
from pythonforandroid.recipe import PyProjectRecipe


class ZstandardRecipe(PyProjectRecipe):
    # Bumped 0.21.0 → 0.23.0. 0.21.0's backend_c.so was failing to dlopen on
    # Android with "undefined symbol: PyObject_GetBuffer" — every static
    # analysis said the symbol IS exported by libpython3.10.so and identical
    # extensions like _pickle load fine. 0.23.0 drops the CFFI backend
    # requirement and has a cleaner build that may sidestep whatever Android
    # linker quirk is biting 0.21.0.
    version = "0.23.0"
    url = (
        "https://files.pythonhosted.org/packages/source/z/zstandard/"
        "zstandard-{version}.tar.gz"
    )
    depends = ["setuptools"]

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        # -O2 keeps build times for the 50k-line zstd.c amalgamation
        # reasonable while still producing fast code.
        env["CFLAGS"] = env.get("CFLAGS", "") + " -O2"
        return env


recipe = ZstandardRecipe()
