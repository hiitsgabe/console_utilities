.PHONY: run watch install dev clean test lint format setup build-apk build-arm64

CONDA_ENV = roms_downloader
CONDA_ACTIVATE = conda run -n $(CONDA_ENV)

# Default target
run:
	DEV_MODE=true $(CONDA_ACTIVATE) watchmedo auto-restart --patterns="*.py" --recursive --signal SIGTERM python src/main.py

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
	rm -f error.log
	rm -f config.json
	rm -rf py_downloads/
	rm -rf roms/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Create distribution package for console deployment
build:
	mkdir -p dist
	cp src/index.py dist/dw.pygame
	cp assets/config/download.json dist/download.json
	@echo "Distribution created in dist/ folder"
	@echo "Copy dist/dw.pygame and dist/download.json to console pygame directory"

# Build APK using official Buildozer Docker image
build-apk:
	mkdir -p dist
	docker pull ghcr.io/kivy/buildozer:latest
	docker run --rm \
		--volume "$(HOME)/.buildozer":/home/user/.buildozer \
		--volume "$(shell pwd)":/home/user/hostcwd \
		ghcr.io/kivy/buildozer:latest android debug
	cp bin/*.apk dist/ 2>/dev/null || echo "APK build completed, check buildozer output"
	@echo "APK build completed, output available in dist/ directory"

# Build ARM64 binary using Docker and PyInstaller
build-arm64:
	mkdir -p dist
	docker build -f docker/Dockerfile.arm64 -t roms-downloader-arm64 .
	docker run --rm \
		--volume "$(shell pwd)/dist":/app/output \
		roms-downloader-arm64
	@echo "ARM64 build completed, binary available in dist/romsdownloader_arm64"

# Format code with black
format:
	$(CONDA_ACTIVATE) black src/

# Lint code with flake8
lint:
	$(CONDA_ACTIVATE) flake8 src/

# Run tests with pytest
test:
	$(CONDA_ACTIVATE) pytest

# Show help
help:
	@echo "Available targets:"
	@echo "  run      - Run the ROM downloader application"
	@echo "  watch    - Run with file watching (auto-restart on changes)"
	@echo "  setup    - Create conda environment"
	@echo "  install  - Install in development mode"
	@echo "  dev      - Install with dev dependencies"
	@echo "  clean    - Clean generated files and caches"
	@echo "  format   - Format code with black"
	@echo "  lint     - Lint code with flake8"
	@echo "  test     - Run tests with pytest"
	@echo "  build     - Create distribution package"
	@echo "  build-apk - Build Android APK using Docker"
	@echo "  build-arm64 - Build ARM64 binary using Docker and PyInstaller"
	@echo "  help      - Show this help message"