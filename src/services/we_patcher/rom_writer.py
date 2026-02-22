"""WE2002 ROM writer — patches team and player data into a copy of the ROM."""

import os
import shutil
from typing import List

from .models import WETeamRecord, WEPlayerRecord


class RomWriter:
    TEAM_DATA_OFFSET = 0x00000000  # placeholder — see RomReader
    TEAM_RECORD_SIZE = 0x00000000  # placeholder
    PLAYER_RECORD_SIZE = 0x00000000  # placeholder
    TEAM_NAME_LENGTH = 16
    PLAYER_NAME_LAST_LENGTH = 12
    PLAYER_NAME_FIRST_LENGTH = 8
    PLAYERS_PER_TEAM = 22

    def __init__(self, rom_path: str, output_path: str):
        """Copy the ROM to output_path for patching. Never modifies the original."""
        if os.path.exists(rom_path):
            shutil.copy2(rom_path, output_path)
        self.output_path = output_path

    def write_team(self, slot_index: int, team: WETeamRecord):
        """Write team name, abbreviation, kit colors to the specified slot."""
        # TODO: Implement once byte offsets are determined
        pass

    def write_players(self, slot_index: int, players: List[WEPlayerRecord]):
        """Write all 22 player records for a team slot."""
        # TODO: Implement once byte offsets are determined
        pass

    def write_flag(self, slot_index: int, tim_data: bytes):
        """Write team flag/emblem TIM graphic into AFS archive."""
        # TODO: Implement once AFS structure is mapped in the ROM
        pass

    def finalize(self):
        """Regenerate EDC/ECC checksums for the patched BIN file."""
        # TODO: Implement EDC/ECC regeneration
        # Options: use edcre subprocess, or implement Mode2/Form1 checksum in Python
        # Reference: https://github.com/alex-free/edcre
        pass
