#!/bin/bash
# uk2en — uninstaller

set -e

INSTALL_DIR="$HOME/.local/uk2en"
PLIST_NAME="com.user.uk2en"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

echo "🗑  Видалення uk2en..."

if [ -f "$PLIST_PATH" ]; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    echo "✓ LaunchAgent видалено"
fi

if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "✓ Каталог $INSTALL_DIR видалено"
fi

echo ""
echo "✅ Готово. Моделі Argos зберігаються в ~/argos-translate/"
echo "   Якщо хочете видалити і їх: rm -rf ~/argos-translate"
