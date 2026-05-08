#!/usr/bin/env python3
"""uk2en menu bar app — rumps wrapper for the clipboard translation daemon."""

import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

import rumps

# Resolve project root so uk2en_daemon is importable both from source
# (app/ is one level below project root) and inside a py2app bundle
# (Resources/ contains both files).
_HERE = Path(__file__).resolve().parent
_PROJ_ROOT = (
    _HERE.parent if (_HERE.parent / "uk2en_daemon.py").exists() else _HERE
)
sys.path.insert(0, str(_PROJ_ROOT))

import uk2en_daemon as d  # noqa: E402

ICON_PATH = _HERE / "icon.png"
SETTINGS_PATH = Path.home() / ".local" / "uk2en" / "app_settings.json"
MODES = ["auto", "terminal", "paste-only", "copy-only"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    filename=Path.home() / ".local" / "uk2en" / "app.log",
)


class Uk2EnApp(rumps.App):
    def __init__(self):
        has_icon = ICON_PATH.exists()
        super().__init__(
            "uk2en",
            icon=str(ICON_PATH) if has_icon else None,
            title=None if has_icon else "UK→EN",
            template=has_icon,
            quit_button="Quit",
        )

        self.settings = self._load()
        self._model_ready = False
        self._watch_thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()

        self._toggle_item = rumps.MenuItem("Enabled", callback=self.toggle_enabled)
        self._mode_items: dict[str, rumps.MenuItem] = {}
        mode_menu = rumps.MenuItem("Mode")
        for mode in MODES:
            item = rumps.MenuItem(mode, callback=self.set_mode)
            self._mode_items[mode] = item
            mode_menu.add(item)

        self.menu = [self._toggle_item, None, mode_menu]
        self._sync_menu()
        self._first_run_takeover()
        threading.Thread(target=self._bootstrap, daemon=True).start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _bootstrap(self):
        try:
            d.ensure_model()
        except Exception as e:
            rumps.notification("uk2en", "Model error", str(e))
            return
        self._model_ready = True
        if self.settings.get("enabled", True):
            self._start_watch()

    def _start_watch(self):
        with self._thread_lock:
            d.STOP_EVENT.clear()
            self._watch_thread = threading.Thread(
                target=d.watch,
                args=(self.settings.get("mode", "auto"), 0.12),
                daemon=True,
            )
            self._watch_thread.start()

    def _stop_watch(self):
        d.STOP_EVENT.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=0.5)

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def toggle_enabled(self, sender):
        sender.state = not sender.state
        enabled = bool(sender.state)
        self.settings["enabled"] = enabled
        self._save()
        if enabled:
            if self._model_ready:
                self._start_watch()
            else:
                rumps.notification("uk2en", "Loading…",
                                   "Translation model is still loading, please wait.")
        else:
            self._stop_watch()

    def set_mode(self, sender):
        self._stop_watch()
        self.settings["mode"] = sender.title
        self._save()
        self._sync_menu()
        if self.settings.get("enabled", True) and self._model_ready:
            self._start_watch()

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        if SETTINGS_PATH.exists():
            try:
                return json.loads(SETTINGS_PATH.read_text())
            except Exception:
                pass
        return {"enabled": True, "mode": "auto"}

    def _save(self):
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(self.settings, indent=2))

    def _sync_menu(self):
        self._toggle_item.state = 1 if self.settings.get("enabled", True) else 0
        active = self.settings.get("mode", "auto")
        for mode, item in self._mode_items.items():
            item.state = 1 if mode == active else 0

    # ------------------------------------------------------------------
    # First-run: replace LaunchAgent and register as a Login Item
    # ------------------------------------------------------------------

    def _first_run_takeover(self):
        if self.settings.get("setup_done"):
            return
        plist = Path.home() / "Library" / "LaunchAgents" / "com.user.uk2en.plist"
        if plist.exists():
            subprocess.run(
                ["launchctl", "unload", str(plist)],
                check=False, capture_output=True,
            )
            plist.rename(str(plist) + ".disabled")

        app_path = self._bundle_path()
        if app_path:
            check = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get the name of every login item'],
                capture_output=True, text=True,
            )
            if "uk2en" not in check.stdout:
                subprocess.run(
                    ["osascript", "-e",
                     f'tell application "System Events" to make login item at end '
                     f'with properties {{path:"{app_path}", hidden:true}}'],
                    check=False, capture_output=True,
                )

        self.settings["setup_done"] = True
        self._save()

    @staticmethod
    def _bundle_path() -> str | None:
        """Return the enclosing .app bundle path, or None when running from source."""
        for parent in Path(sys.executable).resolve().parents:
            if parent.suffix == ".app":
                return str(parent)
        return None


if __name__ == "__main__":
    Uk2EnApp().run()
