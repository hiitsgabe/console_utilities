#!/bin/bash
# Install required native dependencies for Console Utilities
# Note: pygame should already be installed, requests is bundled
# Works on macOS and Linux

set -e

echo "🔍 Checking for pip..."

# Detect pip command
if command -v pip3 &> /dev/null; then
    PIP="pip3"
elif command -v pip &> /dev/null; then
    PIP="pip"
else
    echo "❌ Error: Neither pip3 nor pip found."
    echo "   Please install Python and pip first."
    echo ""
    echo "   macOS:   brew install python3"
    echo "   Ubuntu:  sudo apt install python3-pip"
    echo "   Fedora:  sudo dnf install python3-pip"
    exit 1
fi

echo "✅ Found: $PIP"
echo ""

# Native libraries that can't be bundled in zip (have .so files)
# pygame is assumed to already be installed
# requests is bundled in the .pygame file
PACKAGES=(
    "zstandard>=0.21.0"
    "pycryptodome>=3.10.0"
)

echo "📦 Installing native dependencies..."
echo "   (pygame should already be installed, requests is bundled)"
echo ""

for pkg in "${PACKAGES[@]}"; do
    echo "   Installing $pkg..."
    $PIP install "$pkg" || {
        echo "⚠️  Warning: Failed to install $pkg"
    }
done

echo ""
echo "✅ Installation complete!"
echo ""
echo "You can now run: python3 console_utils.pygame"
