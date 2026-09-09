# Console Utilities, Linux Installation Guide

The standalone Linux build. Python, pygame, and every library the app needs are inside the folder, so there's nothing to install and nothing to conflict with whatever your distro ships.

## Requirements

- x86_64 Linux with glibc 2.35 or newer (Ubuntu 22.04+, Debian 12+, Fedora 36+, current Batocera)
- A working display, X11 or Wayland
- Disk space for your downloads and a network connection

On ARM handhelds (RG35xxSP and friends) this binary won't run. Use `pygame.zip` there instead, it uses the pygame that ships with the device.

## Installation

### Standalone binary (recommended)

1. Download `linux.zip` from the [releases page](https://github.com/hiitsgabe/console_utilities/releases)
2. Extract it. You get a `console_utilities` folder.
3. Run it:

```bash
unzip linux.zip
./console_utilities/console_utilities
```

The executable bit is stored in the zip, so `unzip` restores it. If you extracted with something that dropped it, run `chmod +x console_utilities/console_utilities`.

Keep the folder together. The binary loads everything else from the `_internal` directory next to it.

### From source

```bash
git clone https://github.com/hiitsgabe/console_utilities.git
cd console_utilities

conda env create -f environment.yml
conda activate console_utilities
pip install -e .[dev]

python src/app.py
```

## First run

Point the app at your ROMs directory and working directory in **Settings**, then set the archive JSON location if you use one. Systems reload automatically once it's set.

The archive JSON looks like this:

```json
[
  {
    "name": "System Name",
    "url": "https://example.com/backups/system/",
    "file_format": [".iso", ".bin", ".zip"],
    "roms_folder": "system_folder",
    "boxarts": "https://example.com/boxart/system/",
    "should_unzip": true
  }
]
```

## Controls

Keyboard and controller only. There is no mouse or touch input anywhere in the app.

- Arrow keys: navigate
- Enter: select or confirm
- Escape: back or cancel
- Space: toggle selection in the game list
- Page Up/Down: jump by page or letter in the game list

A connected gamepad is picked up automatically and mapped on first launch.

## Web companion

The browser remote works on this build. Turn it on in **Settings**, then open the address it shows from a phone or laptop on the same network.

## Troubleshooting

**Logs.** `error.log` lands next to the executable, or inside your working directory once you've set one.

**It won't start and says something about libGL or libasound.** The bundle carries its own copies of most things, but a few graphics and audio libraries have to come from the system. On a minimal install: `sudo apt install libgl1 libasound2`.

**"cannot execute binary file".** You're on ARM, or the executable bit was lost. Check `uname -m`, then `chmod +x` if it says `x86_64`.

**"GLIBC_2.xx not found".** Your distro is older than the build. Run from source instead, or use the pygame bundle.

**No games showing.** Check that the archive JSON is valid and the path in Settings points at it.

**Downloads failing.** Check free space, permissions on the target directory, and your network.

## Legal notice and disclaimer

**Please read this.**

- **No ROM data storage.** This project does not host, store, or distribute ROM files, game data, or copyrighted content of any kind. It is a download manager and a patching tool, nothing else.

- **No game copies.** The application contains no copies of games, ROMs, or any copyrighted gaming content whatsoever.

- **Your responsibility.** You alone are responsible for:
  - Ensuring you have the legal right to download any content
  - Complying with copyright law in your jurisdiction
  - Checking the legality of any source you configure
  - Understanding that downloading copyrighted content without permission may be illegal

- **Third-party sources.** Any site referenced in a configuration example is a third-party service. Research and evaluate its legal status yourself.

- **Lawful use only.** This tool is meant for legally owned content, homebrew, and content explicitly cleared for distribution.

**By using this software you acknowledge these responsibilities and agree to use it only for lawful purposes.**

## Credits

hiitsgabe @ github
Made w/ <3 in Toronto
