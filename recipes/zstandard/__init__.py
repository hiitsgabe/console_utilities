"""
p4a recipe for python-zstandard.

NSZ extraction needs zstandard to work at runtime. The native C backend
(backend_c.so) compiles fine cross-platform but fails to dlopen on Android
with "undefined symbol: PyObject_GetBuffer" — every static analysis says
the symbol IS exported by libpython3.10.so, but the on-device dlopen
disagrees (likely Android linker namespace quirk). Bisecting upstream p4a
didn't pinpoint the regression.

Pragmatic workaround: patch zstandard's setup.py before build so:

  * C_BACKEND = False     → no broken backend_c.so gets built
  * cffi is imported and the CFFI extension (backend_c.cffi.so / _zstd_cffi)
    DOES get built — same code path zstandard tries first when it's the
    only option.

Slower than native, but it's what shipped in v1.6.5 and worked reliably.
"""
from os.path import join

from pythonforandroid.recipe import PythonRecipe
from pythonforandroid.toolchain import current_directory, shprint
import sh


class ZstandardRecipe(PythonRecipe):
    version = "0.21.0"
    url = "https://files.pythonhosted.org/packages/source/z/zstandard/zstandard-{version}.tar.gz"
    call_hostpython_via_targetpython = False
    # cffi must be importable in the build env so zstandard's setup.py
    # builds the CFFI backend instead of skipping it.
    hostpython_prerequisites = ["cffi>=1.16.0"]

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        # Force C_BACKEND off in zstandard's setup.py — the C extension
        # builds but won't load on Android. Use the CFFI backend instead.
        setup_py = join(self.get_build_dir(arch.arch), "setup.py")
        shprint(
            sh.sed,
            "-i",
            "s/^C_BACKEND = True/C_BACKEND = False  # patched by p4a recipe/",
            setup_py,
        )

    def build_compiled_components(self, arch):
        # Native-build step is a no-op — we don't want backend_c.so to be
        # produced. install_python_package will run pip install . which
        # honors the C_BACKEND = False patch and builds only CFFI.
        pass


recipe = ZstandardRecipe()
