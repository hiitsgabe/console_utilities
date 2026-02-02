#!/bin/bash
# Local Release Script
# Builds all bundles locally and uploads to GitHub releases
# Usage: ./scripts/local_release.sh [version]
# Example: ./scripts/local_release.sh v1.0.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Load .env file if it exists
if [ -f .env ]; then
    echo -e "${YELLOW}Loading environment from .env...${NC}"
    export $(grep -v '^#' .env | xargs)
fi

# Get version from argument or prompt
VERSION="${1:-}"
if [ -z "$VERSION" ]; then
    # Try to get latest tag
    LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
    echo -e "${YELLOW}Latest tag: $LATEST_TAG${NC}"
    read -p "Enter version (e.g., v1.0.0): " VERSION
fi

# Validate version format
if [[ ! "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: Version must be in format vX.Y.Z (e.g., v1.0.0)${NC}"
    exit 1
fi

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Local Release Script - $VERSION${NC}"
echo -e "${BLUE}======================================${NC}"

# Check for required tools
echo -e "\n${YELLOW}Checking required tools...${NC}"
command -v gh >/dev/null 2>&1 || { echo -e "${RED}Error: gh (GitHub CLI) is required but not installed.${NC}"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}Error: python3 is required but not installed.${NC}"; exit 1; }
command -v zip >/dev/null 2>&1 || { echo -e "${RED}Error: zip is required but not installed.${NC}"; exit 1; }
echo -e "${GREEN}✅ All required tools found${NC}"

# Check gh auth - use token from .env if available
if [ -n "$GITHUB_TOKEN" ]; then
    echo -e "${GREEN}✅ Using GITHUB_TOKEN from .env${NC}"
    export GH_TOKEN="$GITHUB_TOKEN"
elif ! gh auth status >/dev/null 2>&1; then
    echo -e "${RED}Error: Not authenticated with GitHub.${NC}"
    echo -e "${RED}Either add GITHUB_TOKEN to .env or run 'gh auth login'${NC}"
    exit 1
else
    echo -e "${GREEN}✅ GitHub CLI authenticated${NC}"
fi

# Clean previous builds
echo -e "\n${YELLOW}Cleaning previous builds...${NC}"
rm -rf dist/ build/ .bundle_tmp/
mkdir -p dist
echo -e "${GREEN}✅ Cleaned${NC}"

# Download bundled data
echo -e "\n${YELLOW}Downloading bundled data...${NC}"
curl -L -o assets/bundled_data.json "https://files.catbox.moe/sro0jy.json" 2>/dev/null
if [ -f assets/bundled_data.json ]; then
    echo -e "${GREEN}✅ Bundled data downloaded${NC}"
else
    echo -e "${YELLOW}⚠️  Bundled data not available, continuing without it${NC}"
fi

# Build pygame bundle
echo -e "\n${YELLOW}Building pygame bundle...${NC}"
make bundle
if [ -f dist/pygame.zip ]; then
    echo -e "${GREEN}✅ pygame.zip created${NC}"
else
    echo -e "${RED}❌ Failed to create pygame.zip${NC}"
    exit 1
fi

# Build macOS bundle (only on macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "\n${YELLOW}Building macOS bundle...${NC}"

    # Check for PyInstaller
    if ! python3 -c "import PyInstaller" 2>/dev/null; then
        echo -e "${YELLOW}Installing PyInstaller...${NC}"
        pip3 install pyinstaller
    fi

    make bundle-macos
    if [ -f dist/macos.zip ]; then
        echo -e "${GREEN}✅ macos.zip created${NC}"
    else
        echo -e "${RED}❌ Failed to create macos.zip${NC}"
    fi
else
    echo -e "\n${YELLOW}⚠️  Skipping macOS bundle (not on macOS)${NC}"
fi

# List built artifacts
echo -e "\n${YELLOW}Built artifacts:${NC}"
ls -la dist/*.zip 2>/dev/null || echo "No zip files found"

# Confirm upload
echo -e "\n${YELLOW}Ready to upload to GitHub${NC}"
read -p "Create release $VERSION and upload artifacts? (y/n): " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo -e "${YELLOW}Aborted.${NC}"
    exit 0
fi

# Create git tag if it doesn't exist
if git rev-parse "$VERSION" >/dev/null 2>&1; then
    echo -e "${YELLOW}Tag $VERSION already exists${NC}"
else
    echo -e "${YELLOW}Creating tag $VERSION...${NC}"
    git tag "$VERSION"
    git push origin "$VERSION"
    echo -e "${GREEN}✅ Tag created and pushed${NC}"
fi

# Build release notes
RELEASE_NOTES="## Console Utilities $VERSION

### Downloads

| Platform | File | Description |
|----------|------|-------------|
| 🎮 Pygame | \`pygame.zip\` | For systems with pygame installed |
| 🍎 macOS | \`macos.zip\` | Standalone .app bundle |
| 🪟 Windows | \`windows.zip\` | Standalone .exe bundle |
| 🤖 Android | \`android.zip\` | APK for Android devices |

### Installation

**Pygame Bundle:**
1. Extract and run \`./install_req.sh\`
2. Run: \`python3 console_utils.pygame\`

**macOS:**
1. Extract and drag \`Console Utilities.app\` to Applications

**Windows:**
1. Extract and run \`Console Utilities.exe\`

**Android:**
1. Extract and install the APK
"

# Create release and upload
echo -e "\n${YELLOW}Creating GitHub release...${NC}"

# Collect files to upload
UPLOAD_FILES=""
[ -f dist/pygame.zip ] && UPLOAD_FILES="$UPLOAD_FILES dist/pygame.zip"
[ -f dist/macos.zip ] && UPLOAD_FILES="$UPLOAD_FILES dist/macos.zip"
[ -f dist/windows.zip ] && UPLOAD_FILES="$UPLOAD_FILES dist/windows.zip"
[ -f dist/android.zip ] && UPLOAD_FILES="$UPLOAD_FILES dist/android.zip"

if [ -z "$UPLOAD_FILES" ]; then
    echo -e "${RED}No files to upload!${NC}"
    exit 1
fi

# Create release
gh release create "$VERSION" \
    --title "Console Utilities $VERSION" \
    --notes "$RELEASE_NOTES" \
    $UPLOAD_FILES

echo -e "\n${GREEN}======================================${NC}"
echo -e "${GREEN}  Release $VERSION created successfully!${NC}"
echo -e "${GREEN}======================================${NC}"

# Get release URL
RELEASE_URL=$(gh release view "$VERSION" --json url -q .url)
echo -e "\n${BLUE}Release URL: $RELEASE_URL${NC}"

# Cleanup
rm -f assets/bundled_data.json
echo -e "\n${GREEN}✅ Done!${NC}"
