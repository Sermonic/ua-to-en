#!/bin/bash
# uk2en — toggle / start / stop the clipboard daemon

PLIST_NAME="com.user.uk2en"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

if [ ! -f "$PLIST_PATH" ]; then
    echo "❌ Not installed. Run install.sh first."
    exit 1
fi

running() {
    launchctl list "$PLIST_NAME" &>/dev/null && \
    [ "$(launchctl list "$PLIST_NAME" 2>/dev/null | awk '/PID/{print $1}')" != "-" ]
}

cmd="${1:-toggle}"

case "$cmd" in
    start)
        if running; then
            echo "Already running."
        else
            launchctl load "$PLIST_PATH"
            echo "✓ uk2en started"
        fi
        ;;
    stop)
        if running; then
            launchctl unload "$PLIST_PATH"
            echo "✓ uk2en stopped"
        else
            echo "Already stopped."
        fi
        ;;
    status)
        if running; then
            echo "● uk2en is running"
        else
            echo "○ uk2en is stopped"
        fi
        ;;
    toggle|"")
        if running; then
            launchctl unload "$PLIST_PATH"
            echo "○ uk2en stopped"
        else
            launchctl load "$PLIST_PATH"
            echo "● uk2en started"
        fi
        ;;
    *)
        echo "Usage: uk2en [start|stop|status|toggle]"
        exit 1
        ;;
esac