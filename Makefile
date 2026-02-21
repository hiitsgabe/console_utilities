.PHONY: run debug stream watch install dev clean test lint format setup build-android bundle bundle-macos bundle-windows release

CONDA_ENV = app_cutil
CONDA_ACTIVATE = conda run -n $(CONDA_ENV)

# Default target
run:
	DEV_MODE=true $(CONDA_ACTIVATE) watchmedo auto-restart --patterns="*.py;download.json" --recursive --signal SIGTERM python src/app.py

# Stream to phone browser for touch testing (open the printed URL on your phone)
stream:
	DEV_MODE=true $(CONDA_ACTIVATE) python src/stream_server.py

# Run without auto-restart to see full error logs
debug:
	DEV_MODE=true $(CONDA_ACTIVATE) python src/app.py 2>&1 | tee debug.log

# 	DEV_MODE=true $(CONDA_ACTIVATE) python src/index.py
# 	rm -rf py_downloads
# 	rm -rf roms
# Setup development environment
setup:
	conda env create -f environment.yml
	$(CONDA_ACTIVATE) pip install -e .[dev]

# Install in development mode
install:
	$(CONDA_ACTIVATE) pip install -e .

# Install with dev dependencies
dev:
	$(CONDA_ACTIVATE) pip install -e .[dev]

# Clean generated files
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .bundle_tmp/
	rm -f error.log
	rm -f config.json
	rm -rf py_downloads/
	rm -rf downloads/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Create bundled pygame distribution (single .pygame file + assets)
# Dependencies are bundled by default (except pygame which users already have)
# Set BUNDLE_DEPS=0 to skip bundling dependencies

bundle:
	@echo "📦 Creating pygame bundle..."
	@rm -rf .bundle_tmp dist/pygame
	@mkdir -p .bundle_tmp/bundle
	@mkdir -p dist
	@# Copy all source modules into bundle (excluding __pycache__ and .pyc files)
	@rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' src/ .bundle_tmp/bundle/
	@# Inject build info into constants
	@if [ -n "$(VERSION)" ]; then \
		sed -i.bak 's/^APP_VERSION = .*/APP_VERSION = "$(VERSION)"/' .bundle_tmp/bundle/constants.py; \
		rm -f .bundle_tmp/bundle/constants.py.bak; \
	fi
	@sed -i.bak 's/^BUILD_TARGET = .*/BUILD_TARGET = "pygame"/' .bundle_tmp/bundle/constants.py
	@rm -f .bundle_tmp/bundle/constants.py.bak
	@# Bundle pure-Python dependencies only (native libs can't load from zip)
	@# requests is pure Python, but zstandard/pycryptodome have native code
	@echo "📥 Bundling pure-Python dependencies (requests, rarfile)..."
	@mkdir -p .bundle_tmp/libs_temp
	@pip3 install --target .bundle_tmp/libs_temp --no-compile \
		requests rarfile 2>/dev/null || \
	pip install --target .bundle_tmp/libs_temp --no-compile \
		requests rarfile
	@# Move lib packages to bundle root (flat structure)
	@find .bundle_tmp/libs_temp -maxdepth 1 -mindepth 1 -exec mv {} .bundle_tmp/bundle/ \;
	@rm -rf .bundle_tmp/libs_temp
	@# Clean up unnecessary files
	@find .bundle_tmp/bundle -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	@find .bundle_tmp/bundle -type d -name '*.dist-info' -exec rm -rf {} + 2>/dev/null || true
	@find .bundle_tmp/bundle -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	@find .bundle_tmp/bundle -type f -name '*.pyc' -delete 2>/dev/null || true
	@# Create __main__.py entry point for the bundle
	@echo '#!/usr/bin/env python3' > .bundle_tmp/bundle/__main__.py
	@echo 'from app import main' >> .bundle_tmp/bundle/__main__.py
	@echo 'if __name__ == "__main__": main()' >> .bundle_tmp/bundle/__main__.py
	@# Create the .pygame bundle (zip that Python can execute)
	@cd .bundle_tmp/bundle && zip -qr ../../dist/console_utils.pygame .
	@# Create pygame distribution folder
	@mkdir -p dist/pygame
	@mv dist/console_utils.pygame dist/pygame/
	@cp -r assets dist/pygame/
	@cp assets/docs/pygame.md dist/pygame/README.md 2>/dev/null || echo "No pygame docs found"
	@cp assets/examples/archive_example.json dist/pygame/example.json 2>/dev/null || echo "No example json found"
	@# Create requirements.txt (native libs that can't be bundled in zip)
	@echo "# Install these (requests is bundled, native libs are not)" > dist/pygame/requirements.txt
	@echo "pygame>=2.0.0" >> dist/pygame/requirements.txt
	@echo "zstandard>=0.21.0" >> dist/pygame/requirements.txt
	@echo "pycryptodome>=3.10.0" >> dist/pygame/requirements.txt
	@# Copy install script
	@cp assets/scripts/install_req.sh dist/pygame/install_req.sh 2>/dev/null || true
	@chmod +x dist/pygame/install_req.sh 2>/dev/null || true
	@# Create final zip
	@cd dist/pygame && zip -qr ../pygame.zip *
	@rm -rf dist/pygame .bundle_tmp
	@echo "✅ Bundle created: dist/pygame.zip"
	@echo "   Contents:"
	@echo "     - console_utils.pygame"
	@echo "     - assets/ folder"
	@echo "     - requirements.txt"
	@echo "   📦 Bundled: requests, rarfile (pure Python)"
	@echo "   ⚠️  Install native libs: pip install pygame zstandard pycryptodome"

# Build macOS .app bundle (standalone executable)
bundle-macos:
	@echo "🍎 Building macOS app bundle..."
	@rm -rf build/macos dist/macos dist/macos.zip
	@mkdir -p dist/macos
	@# Inject build info into constants before building
	@if [ -n "$(VERSION)" ]; then \
		sed -i.bak 's/^APP_VERSION = .*/APP_VERSION = "$(VERSION)"/' src/constants.py; \
	fi
	@sed -i.bak 's/^BUILD_TARGET = .*/BUILD_TARGET = "macos"/' src/constants.py
	@rm -f src/constants.py.bak
	@echo "📦 Running PyInstaller..."
	@python3 -m PyInstaller console_utils.spec --distpath dist/macos --workpath build/macos --noconfirm
	@# Restore constants after build
	@git checkout src/constants.py 2>/dev/null || true
	@# Copy macOS-specific docs
	@cp assets/docs/macos.md dist/macos/README.md 2>/dev/null || echo "No macOS docs found"
	@# Create zip with the .app and README
	@cd dist/macos && zip -qr ../macos.zip "Console Utilities.app" README.md
	@rm -rf build/macos dist/macos
	@echo "✅ macOS app created: dist/macos.zip"
	@echo "   Extract and drag Console Utilities.app to Applications"

# Build Windows .exe bundle (standalone executable)
bundle-windows:
	@echo "🪟 Building Windows executable..."
	@rm -rf build/windows dist/windows dist/windows.zip
	@mkdir -p dist/windows
	@# Inject build info into constants before building
	@if [ -n "$(VERSION)" ]; then \
		sed -i.bak 's/^APP_VERSION = .*/APP_VERSION = "$(VERSION)"/' src/constants.py; \
	fi
	@sed -i.bak 's/^BUILD_TARGET = .*/BUILD_TARGET = "windows"/' src/constants.py
	@rm -f src/constants.py.bak
	@echo "📦 Running PyInstaller..."
	@python -m PyInstaller console_utils_win.spec --distpath dist/windows --workpath build/windows --noconfirm
	@# Restore constants after build
	@git checkout src/constants.py 2>/dev/null || true
	@# Copy Windows-specific docs
	@cp assets/docs/windows.md dist/windows/README.md 2>/dev/null || echo "No Windows docs found"
	@# Create zip with the exe folder and README
	@cd dist/windows && zip -qr ../windows.zip "Console Utilities" README.md
	@rm -rf build/windows dist/windows
	@echo "✅ Windows exe created: dist/windows.zip"
	@echo "   Extract and run Console Utilities.exe"

prepare-build-zip:
	mkdir -p build
	mkdir -p build/assets/images
	mkdir -p build/src
	cp -r src/* build/src
	cp -r assets/images/background.png build/assets/images/background.png
	cp -r buildozer.spec build/
	cp -r main.py build/
	mkdir -p build/recipes
	cp -r recipes/* build/recipes
	cp -r assets/images/logo.png build/icon.png
	cp -r assets/images/logo_big.png build/presplash.png
	cd build && zip -r ../build.zip *
	rm -rf build
	@echo "Distribution created in dist/ folder"
	@echo "Copy dist/dw.pygame and dist/download.json to console pygame directory"

# Build Android APK using custom buildozer Docker image
CMD ?= debug

build-android:
	@echo "🚀 Building Console Utilities Android APK ($(CMD))..."
	@mkdir -p dist
	@# Inject build info into constants before building
	@if [ -n "$(VERSION)" ]; then \
		sed -i.bak 's/^APP_VERSION = .*/APP_VERSION = "$(VERSION)"/' src/constants.py; \
	fi
	@sed -i.bak 's/^BUILD_TARGET = .*/BUILD_TARGET = "android"/' src/constants.py
	@rm -f src/constants.py.bak
	@echo "🚀 Building Docker Image..."
	docker build -t rom-builder -f docker/dockerfile.android .
	@echo "🚀 Running Docker Container..."
	docker run --name rom-build rom-builder
	mkdir -p dist/android
	cp assets/docs/android.md dist/android/README.md
	cp assets/examples/archive_example.json dist/android/example.json
	@echo "🚀 Copying APK..."
	docker cp rom-build:/dist/. ./dist/android/
	cd dist/android && zip -r ../android.zip *
	rm -rf dist/android
	@echo "🚀 Removing Docker Container..."
	docker rm rom-build
	@# Restore constants after build
	@git checkout src/constants.py 2>/dev/null || true
	@echo "🎉 APK built successfully!"
# Format code with black
format:
	$(CONDA_ACTIVATE) black src/

# Lint code with flake8
lint:
	$(CONDA_ACTIVATE) flake8 src/

# Run tests with pytest
test:
	$(CONDA_ACTIVATE) pytest

# Create release and upload to GitHub
# Usage: make release VERSION=v1.0.0
release:
	@./scripts/local_release.sh $(VERSION)

# Show help
help:
	@echo "Available targets:"
	@echo "  run           - Run the console utilities application"
	@echo "  stream        - Stream to phone browser for touch testing"
	@echo "  debug         - Run without auto-restart (shows full error logs)"
	@echo "  watch         - Run with file watching (auto-restart on changes)"
	@echo "  setup         - Create conda environment"
	@echo "  install       - Install in development mode"
	@echo "  dev           - Install with dev dependencies"
	@echo "  clean         - Clean generated files and caches"
	@echo "  format        - Format code with black"
	@echo "  lint          - Lint code with flake8"
	@echo "  test          - Run tests with pytest"
	@echo "  bundle        - Create pygame bundle (.pygame file + assets)"
	@echo "  bundle-macos  - Create macOS .app bundle (standalone)"
	@echo "  bundle-windows- Create Windows .exe bundle (standalone)"
	@echo "  build-android - Build Android APK using Docker"
	@echo "  release       - Create release and upload to GitHub (VERSION=v1.0.0)"
	@echo "  help          - Show this help message"