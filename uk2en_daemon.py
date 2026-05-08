#!/usr/bin/env python3
"""
uk2en daemon — фонова утіліта для macOS.

Стежить за буфером обміну. Коли там з'являється український текст
(переважно — від Handy), перекладає його англійською (офлайн через
Argos Translate) і вставляє переклад замість оригіналу.

Режими:
  (за замовчуванням) — daemon робить Cmd+Z щоб скасувати українську
    вставку, потім Cmd+V щоб вставити англійський переклад.
    Працює коли Handy налаштовано на auto-paste (типова поведінка).

  --copy-only — daemon тільки оновлює буфер обміну на англійський,
    нічого не натискає. Корисно якщо Handy налаштований "тільки копіювати".

  --once — обробити поточний вміст буферу один раз і вийти (для тесту).
"""

import argparse
import logging
import os
import re
import subprocess
import sys
import threading
import time

# Фікс SSL для macOS Python з venv: примушуємо urllib використовувати
# сертифікати з certifi (інакше Argos не зможе нічого завантажити)
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

try:
    from AppKit import NSPasteboard
except ImportError:
    sys.stderr.write(
        "ERROR: pyobjc не встановлено.\n"
        "  pip3 install pyobjc-framework-Cocoa\n"
    )
    sys.exit(1)

try:
    import argostranslate.package
    import argostranslate.translate
except ImportError:
    sys.stderr.write(
        "ERROR: argostranslate не встановлено.\n"
        "  pip3 install argostranslate\n"
    )
    sys.exit(1)


CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
# Унікальні для української; відсутні в російській/болгарській/сербській
UA_SPECIFIC_RE = re.compile(r"[\u0456\u0457\u0454\u0491\u0406\u0407\u0404\u0490]")
LOG = logging.getLogger("uk2en")

MIN_CHARS = 3
MIN_CYRILLIC_RATIO = 0.3

# Set by the rumps wrapper to stop the watch() loop cleanly.
# Never set when running from the CLI, so the CLI behaves identically.
STOP_EVENT = threading.Event()


def ensure_model() -> None:
    """Перевіряє наявність моделі uk→en, встановлює якщо потрібно."""
    for lang in argostranslate.translate.get_installed_languages():
        if lang.code != "uk":
            continue
        for t in lang.translations_from:
            if t.to_lang.code == "en":
                LOG.debug("Модель uk→en вже встановлена")
                return

    LOG.info("Завантажую модель Ukrainian → English (одноразово, ~80 МБ)...")
    argostranslate.package.update_package_index()
    available = argostranslate.package.get_available_packages()
    pkg = next(
        (p for p in available if p.from_code == "uk" and p.to_code == "en"),
        None,
    )
    if pkg is None:
        raise RuntimeError("Модель uk→en не знайдена в репозиторії Argos")
    path = pkg.download()
    argostranslate.package.install_from_path(path)
    LOG.info("Модель встановлено")


def translate(text: str) -> str:
    return argostranslate.translate.translate(text, "uk", "en")


def is_ukrainian(text: str) -> bool:
    """Чи виглядає текст українською (достатньо кирилиці)."""
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < MIN_CHARS:
        return False
    cyrillic = CYRILLIC_RE.findall(text)
    if len(cyrillic) < MIN_CHARS:
        return False
    if len(cyrillic) / len(stripped) < MIN_CYRILLIC_RATIO:
        return False
    # Require at least one Ukrainian-specific letter (filters out Russian/Bulgarian)
    return bool(UA_SPECIFIC_RE.search(text))


def osa(script: str) -> None:
    """Run AppleScript in-process via NSAppleScript so TCC maps the call to this
    bundle's identifier.  Falls back to subprocess osascript when Foundation is
    unavailable (e.g. unit tests without pyobjc)."""
    try:
        from Foundation import NSAppleScript  # type: ignore[import]
        s = NSAppleScript.alloc().initWithSource_(script)
        _, err = s.executeAndReturnError_(None)
        if err:
            LOG.warning("AppleScript error: %s",
                        err.get("NSAppleScriptErrorMessage", str(err)))
    except ImportError:
        r = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            LOG.warning("osascript subprocess error: %s", r.stderr.strip())


def undo_then_paste() -> None:
    """Скасувати останню вставку (Cmd+Z) і вставити новий вміст (Cmd+V)."""
    osa(
        'tell application "System Events"\n'
        '    keystroke "z" using command down\n'
        '    delay 0.05\n'
        '    keystroke "v" using command down\n'
        'end tell'
    )


def kill_line_then_paste() -> None:
    """Очистити поточний рядок терміналу (Ctrl+U) і вставити переклад (Cmd+V).
    Використовується в режимі --terminal замість Cmd+Z."""
    osa(
        'tell application "System Events"\n'
        '    keystroke "u" using control down\n'
        '    delay 0.05\n'
        '    keystroke "v" using command down\n'
        'end tell'
    )


def paste_only() -> None:
    osa(
        'tell application "System Events" to '
        'keystroke "v" using command down'
    )


def set_clipboard(pb, text: str) -> bool:
    """Write text to clipboard and wait until the write is readable (max 300 ms)."""
    pb.clearContents()
    pb.setString_forType_(text, "public.utf8-plain-text")
    deadline = time.monotonic() + 0.3
    while time.monotonic() < deadline:
        if pb.stringForType_("public.utf8-plain-text") == text:
            return True
        time.sleep(0.01)
    return False


def process_text(pb, text: str, mode: str) -> bool:
    """Один цикл обробки. Повертає True якщо переклали."""
    if not is_ukrainian(text):
        LOG.debug("Не виявлено української — пропускаю")
        return False

    short = text.replace("\n", " ").strip()
    LOG.info("UK: %s", short[:100] + ("…" if len(short) > 100 else ""))

    # Fire undo/clear BEFORE translation so it lands ~100 ms after the paste,
    # not 2-3 s later when the user has already continued typing.
    if mode == "auto":
        osa(
            'tell application "System Events"\n'
            '    keystroke "z" using command down\n'
            'end tell'
        )
    elif mode == "terminal":
        osa(
            'tell application "System Events"\n'
            '    keystroke "u" using control down\n'
            'end tell'
        )

    try:
        translated = translate(text).strip()
    except Exception as e:  # noqa: BLE001
        LOG.error("Помилка перекладу: %s", e)
        return False

    LOG.info(
        "EN: %s",
        translated[:100].replace("\n", " ")
        + ("…" if len(translated) > 100 else ""),
    )

    ready = set_clipboard(pb, translated)
    if not ready:
        LOG.warning("Clipboard write timed out — skipping keystrokes")
        return False

    if mode in ("auto", "terminal", "paste-only"):
        paste_only()
    # mode == "copy-only" — тільки оновлюємо буфер обміну

    return True


def watch(mode: str, poll: float) -> None:
    pb = NSPasteboard.generalPasteboard()
    last_count = pb.changeCount()
    last_translated = None

    LOG.info("uk2en daemon запущено (режим: %s, опитування: %.0fмс)",
             mode, poll * 1000)
    LOG.info("Ctrl+C — вихід")

    while not STOP_EVENT.is_set():
        try:
            time.sleep(poll)
            count = pb.changeCount()
            if count == last_count:
                continue
            last_count = count

            text = pb.stringForType_("public.utf8-plain-text")
            if not text:
                continue
            # Не реагувати на власний переклад
            if last_translated is not None and text == last_translated:
                continue

            translated_now = process_text(pb, text, mode)
            if translated_now:
                last_translated = pb.stringForType_("public.utf8-plain-text")
                last_count = pb.changeCount()
        except KeyboardInterrupt:
            LOG.info("Зупинка")
            return
        except Exception as e:  # noqa: BLE001
            LOG.exception("Несподівана помилка: %s", e)
            time.sleep(0.5)


def run_once(mode: str) -> int:
    pb = NSPasteboard.generalPasteboard()
    text = pb.stringForType_("public.utf8-plain-text")
    if not text:
        LOG.error("Буфер обміну порожній")
        return 1
    if not is_ukrainian(text):
        LOG.error("У буфері не український текст")
        return 1
    process_text(pb, text, mode)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="UK→EN clipboard daemon for macOS (Argos Translate, offline)"
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--copy-only",
        action="store_const",
        dest="mode",
        const="copy-only",
        help="Тільки оновлювати буфер, не вставляти",
    )
    mode_group.add_argument(
        "--paste-only",
        action="store_const",
        dest="mode",
        const="paste-only",
        help="Вставити (Cmd+V) без скасування попередньої вставки. "
             "Якщо Handy вже налаштовано в режим 'тільки копіювати'",
    )
    mode_group.add_argument(
        "--terminal",
        action="store_const",
        dest="mode",
        const="terminal",
        help="Режим для терміналу: Ctrl+U очищає поточний рядок, "
             "потім Cmd+V вставляє переклад. Використовуй в WebStorm / iTerm.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Перекласти поточний буфер один раз і вийти",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=0.12,
        help="Інтервал опитування буферу, секунди (за замовч. 0.12)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    mode = args.mode or "auto"

    try:
        ensure_model()
    except Exception as e:  # noqa: BLE001
        LOG.error("Не вдалося встановити модель: %s", e)
        return 1

    if args.once:
        return run_once(mode)

    watch(mode, args.poll)
    return 0


if __name__ == "__main__":
    sys.exit(main())
