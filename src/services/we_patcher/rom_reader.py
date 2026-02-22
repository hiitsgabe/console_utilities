"""WE2002 ROM reader — parses team and player data from the ROM binary."""

import os
from typing import List

from .models import (
    WETeamRecord,
    WEPlayerRecord,
    WETeamSlot,
    WEPlayerAttributes,
    RomInfo,
)


class RomReader:
    # TODO: Get exact offsets from WE2002-editor-2.0 C++ source
    # https://github.com/thyddralisk/WE2002-editor-2.0
    SLPM_MAGIC = b"SLPM"  # WE2002 identifier in executable
    TEAM_DATA_OFFSET = 0x00000000  # placeholder
    TEAM_RECORD_SIZE = 0x00000000  # placeholder
    PLAYER_RECORD_SIZE = 0x00000000  # placeholder
    TEAM_NAME_LENGTH = 16  # approximate
    PLAYER_NAME_LAST_LENGTH = 12  # approximate
    PLAYER_NAME_FIRST_LENGTH = 8  # approximate
    PLAYERS_PER_TEAM = 22
    TEAM_SLOTS_COUNT = 24  # approximate, per league mode

    def __init__(self, rom_path: str):
        self.rom_path = rom_path
        self._data: bytes = b""
        if os.path.exists(rom_path):
            with open(rom_path, "rb") as f:
                self._data = f.read()

    def validate_rom(self) -> bool:
        """Check if file looks like a WE2002 PSX image (size heuristic)."""
        # PSX BIN files are typically 650-800 MB
        # TODO: Add magic byte check once offsets are known
        return len(self._data) > 100 * 1024 * 1024

    def read_teams(self) -> List[WETeamRecord]:
        """Read all team records. Returns stubs until offsets are reverse-engineered."""
        # TODO: Implement once byte offsets are determined from WE2002-editor-2.0 source
        return []

    def read_players(self, team_index: int) -> List[WEPlayerRecord]:
        """Read 22 player records for a team slot."""
        # TODO: Implement once byte offsets are determined
        return []

    def read_team_slots(self) -> List[WETeamSlot]:
        """List all available team slots with their current names."""
        # TODO: Implement once byte offsets are determined
        return []

    def extract_flag(self, team_index: int) -> bytes:
        """Extract team flag TIM graphic data."""
        # TODO: Implement once AFS archive structure is mapped
        return b""

    def get_rom_info(self) -> RomInfo:
        """Return RomInfo for this ROM."""
        slots = self.read_team_slots()
        return RomInfo(
            path=self.rom_path,
            size=len(self._data),
            version="WE2002" if self.validate_rom() else "Unknown",
            team_slots=slots,
            is_valid=self.validate_rom(),
        )
