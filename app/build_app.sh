#!/usr/bin/env bash
# Build uk2en.app and package it into a distributable uk2en.dmg
# Usage:
#   ./build_app.sh        — full release build  → app/dist/uk2en.dmg
#   ./build_app.sh --dev  — alias (fast) build  → app/dist/uk2en.app only (no DMG)
set -euo pipefail
cd "$(dirname "$0")"

DEV=0
[[ "${1:-}" == "--dev" ]] && DEV=1

VENV=".build-venv"

echo "==> Setting up build venv…"
python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet \
    rumps \
    py2app \
    argostranslate \
    certifi \
    "pyobjc-framework-Cocoa>=10" \
    Pillow

echo "==> Generating icon…"
python3 - <<'EOF'
from PIL import Image, ImageDraw
img = Image.new("RGBA", (44, 22), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
# Two-line template icon: black on transparent, macOS colours it automatically
draw.text((1, 0), "UK", fill=(0, 0, 0, 255))
draw.text((1, 11), "→EN", fill=(0, 0, 0, 255))
img.save("icon.png")
print("  icon.png written (44×22 px)")
EOF

echo "==> Copying daemon module…"
cp ../uk2en_daemon.py .

echo "==> Cleaning previous build artefacts…"
rm -rf build dist

echo "==> Running py2app…"
if [[ $DEV -eq 1 ]]; then
    echo "    (alias / development mode)"
    python setup.py py2app -A
else
    python setup.py py2app
fi

if [[ $DEV -eq 1 ]]; then
    echo ""
    echo "Done (dev)!  $(pwd)/dist/uk2en.app"
    echo "Run:  open dist/uk2en.app"
    exit 0
fi

# ------------------------------------------------------------------
# Package into a DMG
# ------------------------------------------------------------------
echo "==> Creating DMG…"
APP="dist/uk2en.app"
STAGING="dist/_dmg_staging"
DMG="dist/uk2en.dmg"
VOLUME="uk2en"

rm -rf "$STAGING" "$DMG"
mkdir -p "$STAGING"
cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

hdiutil create \
    -volname  "$VOLUME" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDZO \
    "$DMG" > /dev/null

rm -rf "$STAGING"

echo ""
echo "Done!  $(pwd)/$DMG"
echo ""
echo "To install:"
echo "  1. Open the DMG:     open $DMG"
echo "  2. Drag uk2en.app → Applications folder"
echo "  3. Eject the DMG"
echo "  4. Open uk2en from Applications (first launch downloads model ~80 MB)"
echo "  5. Grant Accessibility: System Settings → Privacy & Security → Accessibility"
