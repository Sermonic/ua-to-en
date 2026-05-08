"""py2app build configuration for uk2en.app."""
import sys
sys.setrecursionlimit(10000)  # argostranslate has deeply nested ASTs that trip modulegraph
from setuptools import setup

APP = ["uk2en_app.py"]
DATA_FILES = []

OPTIONS = {
    "argv_emulation": False,
    "iconfile": None,
    "plist": {
        "CFBundleName": "uk2en",
        "CFBundleDisplayName": "uk2en",
        "CFBundleIdentifier": "com.user.uk2en",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "LSUIElement": True,
        "NSAppleEventsUsageDescription":
            "uk2en sends keystrokes to paste translated text.",
        "NSPasteboardUsageDescription":
            "uk2en reads the clipboard to detect and translate Ukrainian text.",
    },
    "packages": [
        "rumps",
        "argostranslate",
        "certifi",
        "AppKit",
        "Foundation",
    ],
    "includes": ["uk2en_daemon"],
    "resources": ["icon.png"],
    "strip": False,
}

setup(
    name="uk2en",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
