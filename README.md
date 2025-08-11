# ROM Downloader

**Disclaimer: This application does not endorse any form of piracy. Only download games you legally own.**

A PyGame-based ROM downloader designed for handheld gaming consoles, tested specifically with Knulli RG35xxSP.

## Features

- Interactive menu system with D-pad navigation
- Multi-game selection and batch downloading
- Real-time download progress with speed indicators
- Automatic file extraction and organization
- Error logging and recovery
- Support for various file formats

## Installation

### Console Installation
1. Create a `downloader` folder inside your console's `pygame` roms directory
2. Copy `dw.pygame` and `download.json` to this folder
3. Configure `download.json` with your download sources
4. Rescan games in EmulationStation
5. Navigate to PyGame library and run the downloader

### Development Setup
1. Create conda environment:
   ```bash
   `conda env create -f environment.yml`
   conda activate roms_downloader
   ```

2. Run locally:
   ```bash
   python dw.pygame
   ```

## Configuration

Edit `download.json` to configure your download sources:

```json
[
  {
    "name": "System Name",
    "list_url": "URL to get JSON file list",
    "list_json_file_location": "files",
    "list_item_id": "name",
    "download_url": "https://example.com/download",
    "commands": [],
    "file_format": [".iso", ".bin"],
    "roms_folder": "system_folder"
  }
]
```

### Configuration Fields

- `name`: Display name for the system
- `list_url`: API endpoint returning JSON with available files
- `list_json_file_location`: JSON property containing file array
- `list_item_id`: Property name for file identifier
- `download_url`: Base download URL (file ID will be appended)
- `commands`: Shell commands for post-processing (not implemented)
- `file_format`: Array of supported file extensions
- `roms_folder`: Target folder within roms directory

## Controls

### System Selection
- **D-pad Up/Down**: Navigate systems
- **B Button**: Select system
- **A Button**: Exit

### Game Selection
- **D-pad Up/Down**: Navigate games
- **D-pad Left/Right**: Jump to different letter
- **B Button**: Toggle game selection
- **A Button**: Return to systems
- **START Button**: Begin download

### During Download
- **A Button**: Cancel download

## Dependencies

- Python 3.11+
- pygame >= 2.0.0
- requests >= 2.25.0

## File Structure

```
roms_downloader/
├── dw.pygame          # Main application
├── download.json      # Configuration file
├── environment.yml    # Conda environment
└── README.md         # Documentation
```

## Compatibility

- Tested with Knulli RG35xxSP
- Should work with other Batocera-based systems
- Compatible with Internet Archive downloads

## Legal Notice and Disclaimer

**IMPORTANT LEGAL DISCLAIMER:**

- **No ROM Data Storage**: This system does not host, store, or distribute any ROM files, game data, or copyrighted content. It is purely a download management tool.

- **No Game Copies**: This application contains no copies of games, ROMs, or any copyrighted gaming content whatsoever.

- **Example Configuration**: The included `download.json` file serves as an example configuration only. It demonstrates how the system works but does not endorse or recommend any specific download sources.

- **Legal Responsibility**: Users are solely responsible for:
  - Ensuring they have legal rights to download any content
  - Complying with copyright laws in their jurisdiction  
  - Verifying the legality of any download sources they configure
  - Understanding that downloading copyrighted content without permission may be illegal

- **Third-Party Sources**: Any websites or download sources referenced in configuration examples are third-party services. Users should research and evaluate the legal status of such sources independently.

- **Legal Use Only**: This tool is intended exclusively for downloading legally owned content, homebrew games, or content explicitly permitted for distribution.

**By using this software, you acknowledge that you understand these legal responsibilities and agree to use it only for lawful purposes.**

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss proposed modifications.

## Troubleshooting

Check `/userdata/roms/pygame/downloader/error.log` for detailed error information if the application encounters issues.