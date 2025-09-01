.PHONY: run watch install dev clean test lint format setup build-android

CONDA_ENV = console_utilities
CONDA_ACTIVATE = conda run -n $(CONDA_ENV)

# Default target
run:
# 	DEV_MODE=true $(CONDA_ACTIVATE) watchmedo auto-restart --patterns="*.py;download.json" --recursive --signal SIGTERM python src/index.py
	DEV_MODE=true $(CONDA_ACTIVATE) python src/index.py
	rm -rf py_downloads 
	rm -rf roms
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
	rm -rf downloads/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Create distribution package for console deployment
build:
	mkdir -p dist
	mkdir -p dist/pygame
	mkdir -p dist/pygame/assets
	mkdir -p dist/pygame/assets/images
	cp src/index.py dist/pygame/console-utilities.pygame
	sed -i '' 's|from nsz import|import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from nsz import|' dist/pygame/console-utilities.pygame
	cp -r src/nsz dist/pygame/
	cp assets/images/background.png dist/pygame/assets/images/background.png
	cp assets/docs/pygame.md dist/pygame/README.md
	cp assets/examples/archive_example.json dist/pygame/example.json
	cd dist/pygame && zip -r ../pygame.zip *
	rm -rf dist/pygame
	@echo "Distribution created in dist/ folder"
	@echo "Copy dist/dw.pygame and dist/download.json to console pygame directory"

# Build Android APK using custom buildozer Docker image
CMD ?= debug

build-android:
	@echo "🚀 Building Console Utilities Android APK ($(CMD))..."
	@mkdir -p dist
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

# Show help
help:
	@echo "Available targets:"
	@echo "  run           - Run the console utilities application"
	@echo "  watch         - Run with file watching (auto-restart on changes)"
	@echo "  setup         - Create conda environment"
	@echo "  install       - Install in development mode"
	@echo "  dev           - Install with dev dependencies"
	@echo "  clean         - Clean generated files and caches"
	@echo "  format        - Format code with black"
	@echo "  lint          - Lint code with flake8"
	@echo "  test          - Run tests with pytest"
	@echo "  build         - Create distribution package"
	@echo "  build-android - Build Android APK using Docker"
	@echo "  help          - Show this help message"