#!/bin/bash
# Install required native dependencies for Console Utilities
# This script ensures pip and python exist, then installs native packages.
# If pygame is not installed, it will attempt to install it as well.
# Works on macOS and Linux

set -e

echo "🔍 Checking for python..."

# Find a usable python executable
if command -v python3 &> /dev/null; then
    PYTHON="python3"
elif command -v python &> /dev/null; then
    PYTHON="python"
else
    echo "❌ Error: Neither python3 nor python found."
    echo "   Please install Python first."
    echo "   macOS:   brew install python3"
    echo "   Ubuntu:  sudo apt install python3"
    echo "   Fedora:  sudo dnf install python3"
    exit 1
fi

echo "✅ Found: $PYTHON"

echo "\n🔍 Checking for pip..."
# Detect pip command linked to the chosen python
if command -v "${PYTHON}-pip" &> /dev/null; then
    PIP="${PYTHON}-pip"
elif command -v pip3 &> /dev/null; then
    PIP="pip3"
elif command -v pip &> /dev/null; then
    PIP="pip"
else
    # Try using python -m pip
    if "$PYTHON" -m pip --version &> /dev/null; then
        PIP="$PYTHON -m pip"
    else
        echo "❌ Error: pip not found for $PYTHON."
        echo "   Please install pip first."
        echo "   macOS:   brew install python3"
        echo "   Ubuntu:  sudo apt install python3-pip"
        echo "   Fedora:  sudo dnf install python3-pip"
        exit 1
    fi
fi

echo "✅ Found: $PIP"
echo ""

# Native libraries that can't be bundled in zip (have .so files)
PACKAGES=(
    "zstandard>=0.21.0"
    "pycryptodome>=3.10.0"
)

# Add pygame to the list only if it's missing
check_pygame() {
    if "$PYTHON" -c "import pygame" &> /dev/null; then
        return 0
    fi
    return 1
}

if check_pygame; then
    echo "✅ pygame is already installed."
else
    echo "⚠️  pygame not found — attempting to install via pip..."
    # On some platforms, installing pygame may require dev libs. We try pip first.
    # Use the same pip command we detected (it may be "python -m pip").
    if ! $PIP install "pygame"; then
        echo "\n❌ Automatic pygame install failed."
        echo "   On many Linux systems you need SDL and build dependencies installed first."
        echo "   Try one of the following depending on your OS:"
        echo "     Ubuntu/Debian: sudo apt install libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev libjpeg-dev libfreetype6-dev"
        echo "     Fedora: sudo dnf install SDL2-devel SDL2_image-devel SDL2_mixer-devel SDL2_ttf-devel portmidi-devel libjpeg-turbo-devel freetype-devel"
        echo "     macOS: brew install sdl2 sdl2_image sdl2_mixer sdl2_ttf"
        echo "   After installing system deps, re-run this script or run: $PIP install pygame"
        echo ""
    else
        echo "✅ pygame installed successfully."
    fi
fi

echo "\n📦 Installing native dependencies..."
echo ""

for pkg in "${PACKAGES[@]}"; do
    echo "   Installing $pkg..."
    if ! $PIP install "$pkg"; then
        echo "⚠️  Warning: Failed to install $pkg"
    fi
done

echo ""
echo "✅ Installation complete!"
echo ""
echo "You can now run: python3 console_utils.pygame"
