#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  uk2en — Ukrainian → English clipboard daemon for macOS     ║
# ╠══════════════════════════════════════════════════════════════╣
# ║  Встановити:      ./install.sh                              ║
# ║  Фікс сертиф.:   ./install.sh --fix-certs                  ║
# ║  Запуск вручну:  ~/.local/uk2en/uk2en_daemon.py --terminal  ║
# ║  Лог:            tail -f ~/.local/uk2en/daemon.log          ║
# ║  Видалити:       ./uninstall.sh                             ║
# ╚══════════════════════════════════════════════════════════════╝

set -e

INSTALL_DIR="$HOME/.local/uk2en"
PLIST_NAME="com.user.uk2en"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
FIX_ONLY=false

if [[ "$1" == "--fix-certs" ]]; then
    FIX_ONLY=true
fi

# ── Перевірки ──────────────────────────────────────────────────────────────

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не знайдено. Встановіть: brew install python3"
    exit 1
fi

if $FIX_ONLY && [ ! -d "$INSTALL_DIR/venv" ]; then
    echo "❌ Не знайдено $INSTALL_DIR/venv — спочатку запустіть install.sh без аргументів"
    exit 1
fi

# ── Повна установка ────────────────────────────────────────────────────────

if ! $FIX_ONLY; then
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "🛠  Встановлення uk2en daemon..."
    echo "   Каталог: $INSTALL_DIR"
    echo "   Python:  $PY_VERSION"
    echo ""

    mkdir -p "$INSTALL_DIR"

    if [ ! -d "$INSTALL_DIR/venv" ]; then
        echo "📦 Створюю Python venv..."
        python3 -m venv "$INSTALL_DIR/venv"
    fi
fi

# ── Залежності та certifi ──────────────────────────────────────────────────

echo "📦 Встановлюю / оновлюю залежності..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
"$INSTALL_DIR/venv/bin/pip" install --upgrade argostranslate certifi "pyobjc-framework-Cocoa>=10" --quiet
echo "✓ Залежності встановлено"

CERT_PATH=$("$INSTALL_DIR/venv/bin/python3" -c "import certifi; print(certifi.where())")
export SSL_CERT_FILE="$CERT_PATH"
export REQUESTS_CA_BUNDLE="$CERT_PATH"
echo "✓ Сертифікати: $CERT_PATH"

# ── Daemon ─────────────────────────────────────────────────────────────────

if ! $FIX_ONLY; then
    cp "$SCRIPT_DIR/uk2en_daemon.py" "$INSTALL_DIR/uk2en_daemon.py"
    chmod +x "$INSTALL_DIR/uk2en_daemon.py"
    echo "✓ Daemon скопійовано"

    mkdir -p "$HOME/.local/bin"
    cp "$SCRIPT_DIR/toggle.sh" "$HOME/.local/bin/uk2en"
    chmod +x "$HOME/.local/bin/uk2en"
    echo "✓ uk2en команда встановлена → ~/.local/bin/uk2en"
fi

# ── Модель uk→en ───────────────────────────────────────────────────────────

echo "📥 Перевіряю / завантажую модель uk→en (~80 МБ перший раз)..."
SSL_CERT_FILE="$CERT_PATH" REQUESTS_CA_BUNDLE="$CERT_PATH" \
"$INSTALL_DIR/venv/bin/python3" - <<'PY'
import argostranslate.package, argostranslate.translate

for lang in argostranslate.translate.get_installed_languages():
    if lang.code == "uk":
        for t in lang.translations_from:
            if t.to_lang.code == "en":
                print("  Уже встановлена")
                raise SystemExit(0)

argostranslate.package.update_package_index()
pkg = next(
    p for p in argostranslate.package.get_available_packages()
    if p.from_code == "uk" and p.to_code == "en"
)
print("  Завантажую (~80 МБ)...")
path = pkg.download()
argostranslate.package.install_from_path(path)
print("  ✓ Готово")
PY

# ── LaunchAgent ────────────────────────────────────────────────────────────

echo "🚀 Налаштовую LaunchAgent..."
cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/venv/bin/python3</string>
        <string>$INSTALL_DIR/uk2en_daemon.py</string>
        <string>--terminal</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/daemon.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/daemon.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>SSL_CERT_FILE</key>
        <string>$CERT_PATH</string>
        <key>REQUESTS_CA_BUNDLE</key>
        <string>$CERT_PATH</string>
    </dict>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
echo "✓ LaunchAgent активовано"

# ── Підсумок ───────────────────────────────────────────────────────────────

echo ""
echo "✅ Готово!"
echo ""
echo "📂 Логи:    $INSTALL_DIR/daemon.log"
echo "📂 Помилки: $INSTALL_DIR/daemon.err"

if ! $FIX_ONLY; then
    echo ""
    echo "📝 Що далі:"
    echo "  1. System Settings → Privacy & Security → Accessibility"
    echo "     — додайте та увімкніть пермішн для Python (буде запит при першому Cmd+V)"
    echo ""
    echo "  2. Продиктуйте щось українською в терміналі."
    echo "     Текст має замінитись на англійський переклад."
fi

echo ""
echo "🔧 Керування:"
echo "  Увімк/вимк:     uk2en            (toggle)"
echo "  Старт:          uk2en start"
echo "  Стоп:           uk2en stop"
echo "  Статус:         uk2en status"
echo "  Перезапуск:     launchctl kickstart -k gui/\$UID/$PLIST_NAME"
echo "  Лог онлайн:     tail -f $INSTALL_DIR/daemon.log"
echo "  Тест вручну:    $INSTALL_DIR/uk2en_daemon.py --once -v --terminal"
echo "  Фікс сертиф.:   $SCRIPT_DIR/install.sh --fix-certs"
echo ""
echo "  💡 Якщо 'uk2en' не знайдено — додайте до ~/.zshrc:"
echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""