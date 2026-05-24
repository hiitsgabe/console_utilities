from pythonforandroid.recipe import PythonRecipe


class ZstandardRecipe(PythonRecipe):
    version = "0.21.0"
    url = "https://files.pythonhosted.org/packages/source/z/zstandard/zstandard-{version}.tar.gz"
    call_hostpython_via_targetpython = False

    def build_compiled_components(self, arch):
        # Skip native build entirely
        print("⚠️ Skipping native zstd build, using pure-Python mode.")


recipe = ZstandardRecipe()