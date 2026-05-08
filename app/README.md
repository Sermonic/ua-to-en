# uk2en — Desktop App

Clips Ukrainian speech from Handy → translates offline → pastes English in your terminal.

## Quick setup (first time)

### 1. Build & install

```bash
cd app
./build_app.sh          # ~5 min first time → app/dist/uk2en.dmg
open dist/uk2en.dmg     # drag uk2en.app → Applications
open /Applications/uk2en.app
```

On first launch: downloads the translation model (~80 MB, one-time only).

### 2. Grant Accessibility

**System Settings → Privacy & Security → Accessibility → add uk2en → enable**

Without this, keystrokes are silently blocked.

> If it stops working after reinstall: remove the old entry and re-add it.
> Terminal command to reset: `tccutil reset Accessibility com.user.uk2en`

### 3. Configure Handy (Advanced settings)

| Setting | Value |
|---|---|
| Paste Method | **Clipboard (Cmd+V)** |
| Clipboard Handling | **Copy to Clipboard** |

### 4. Set uk2en mode

Click the menu bar icon → **Mode → terminal**

## How it works

1. You dictate Ukrainian into Handy
2. Handy pastes it into your terminal (via Cmd+V)
3. uk2en detects the Ukrainian text in clipboard
4. `Ctrl+U` fires immediately — clears the line before you type more
5. Translation runs offline (~2-3 s)
6. English is pasted via `Cmd+V`

## Menu bar

| Item | Description |
|---|---|
| **Enabled** | Pause / resume — toggle without quitting |
| **Mode → terminal** | For iTerm / Terminal.app — `Ctrl+U` then `Cmd+V` ✓ |
| **Mode → auto** | For GUI text fields — `Cmd+Z` then `Cmd+V` |
| **Mode → paste-only** | `Cmd+V` only, no undo/clear |
| **Mode → copy-only** | Only updates clipboard, no keystrokes |
| **Quit** | Exit the app |

Settings persist in `~/.local/uk2en/app_settings.json`.

## Logs

```bash
tail -f ~/.local/uk2en/app.log
```

## Rebuild after code changes

```bash
cd app
./build_app.sh --dev    # fast alias build for testing
./build_app.sh          # full release DMG
```

## Roll back to LaunchAgent (if needed)

```bash
mv ~/Library/LaunchAgents/com.user.uk2en.plist.disabled \
   ~/Library/LaunchAgents/com.user.uk2en.plist
launchctl load ~/Library/LaunchAgents/com.user.uk2en.plist
```

Then quit the menu bar app.
