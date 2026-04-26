# Tiamat

Tiamat is now a Windows system tray app for League of Legends client utilities.

## Important Notice

Use at your own risk. Some features may violate Riot Games' Terms of Service.

## Features

- Icon Changer
- Client-Only Icon Changer
- Background Changer
- Lobby Reveal
- Auto Accept Match
- Smart Dodge
- Riot ID Changer
- Restart Client UX
- Instalock Champion
- AutoBan Champion
- Disconnect Chat
- Remove All Friends
- Change Profile Badges
- Change Status

## Requirements

- Windows
- Python 3.8 or higher
- League of Legends client installed

## Install

1. Clone the repository.
2. Install the dependencies in the same Python environment you will use to run or build the app:

```bash
pip install -r tiamat/requirements.txt
```

## Run

Use the tray app entrypoint directly:

```bash
pythonw tiamat/tray_app.pyw
```

Or launch it with:

```bash
Tiamat.cmd
```

## Build

Use the build script to clean old artifacts and generate a fresh `dist/Tiamat`:

```bash
Build-Tiamat.cmd
```

Run the built app with:

```bash
dist/Tiamat/Tiamat.exe
```

## Usage

1. Start Tiamat.
2. Find the tray icon on the Windows taskbar.
3. Right-click the icon to open the feature menu.
4. Use popups for the options that require text, numbers or confirmation.

## Support

- Discord: gabrielgyaf
- Issues: https://github.com/gyaaf/tiamat/issues
