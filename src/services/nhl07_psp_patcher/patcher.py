"""NHL 07 PSP Patcher - Main orchestrator.

Coordinates fetching roster data, mapping stats, and patching the ISO.
Supports ESPN (current season) and NHL official API (historical).
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from services.sports_api.models import Player
from services.nhl07_psp_patcher.models import (
    NHL07PlayerRecord,
    NHL07RomInfo,
    NHL07_TEAM_NAMES,
    TDB_MASTER,
    TDB_BIOATT,
    TDB_ROSTER,
)
from services.nhl07_psp_patcher.stat_mapper import NHL07StatMapper
from services.nhl07_psp_patcher.rom_reader import NHL07PSPRomReader
from services.nhl07_psp_patcher.rom_writer import NHL07PSPRomWriter, LINE_FLAGS


@dataclass
class PatchResult:
    """Result of a patch operation."""

    success: bool
    output_path: str = ""
    error: str = ""
    teams_patched: int = 0
    players_patched: int = 0


class NHL07PSPPatcher:
    """Main orchestrator for NHL 07 PSP roster patching.

    Supports two providers:
      - "espn": ESPN public API (current season only)
      - "nhl": NHL official API (historical back to 1993)
    """

    def __init__(
        self,
        cache_dir: str,
        on_status: Optional[Callable] = None,
        provider: str = "espn",
    ):
        self.cache_dir = cache_dir
        self.on_status = on_status
        self.provider = provider
        self.mapper = NHL07StatMapper()

        if provider == "nhl":
            from services.sports_api.nhl_api_client import NhlApiClient

            self.api = NhlApiClient(cache_dir, on_status)
        else:
            from services.sports_api.espn_client import EspnClient

            self.api = EspnClient(cache_dir, on_status)

    def analyze_rom(self, iso_path: str, deep: bool = False) -> NHL07RomInfo:
        """Validate ISO and read team slots.

        Args:
            deep: If True, decompress TDB files for full validation (slow).
                  If False, just check BIGF header + use hardcoded teams (fast).
        """
        reader = NHL07PSPRomReader(iso_path)
        if not reader.load():
            return NHL07RomInfo(
                path=iso_path,
                size=0,
                team_slots=[],
                is_valid=False,
            )
        return reader.get_info(deep=deep)

    def fetch_rosters(
        self,
        on_progress: Optional[Callable[[float, str], None]] = None,
        season: int = 2025,
    ) -> Dict[str, List[Player]]:
        """Fetch all NHL team rosters + stats.

        Returns dict mapping team abbreviation to player list.
        Also populates self.team_stats for use during patching.
        """
        rosters: Dict[str, List[Player]] = {}
        self.team_stats: Dict[str, dict] = {}

        if self.on_status:
            self.on_status("Fetching NHL teams...")
        nhl_teams = self.api.get_nhl_teams()

        if not nhl_teams:
            if self.on_status:
                self.on_status("No NHL teams found")
            return rosters

        # Filter to teams with NHL 07 ROM slots
        mapped = [t for t in nhl_teams if self.mapper.get_team_slot(t.code) is not None]
        total = len(mapped)

        for i, team in enumerate(mapped):
            if on_progress:
                on_progress(i / total, f"Fetching {team.name}...")

            if self.provider == "nhl":
                players = self.api.get_hockey_squad(team.code, season)
                stats = self.api.get_hockey_team_leaders(team.code, season)
            else:
                players = self.api.get_hockey_squad(team.id)
                stats = self.api.get_hockey_team_leaders(team.id)

            if players:
                rosters[team.code] = players
            if stats:
                self.team_stats[team.code] = stats

        if on_progress:
            on_progress(1.0, "Complete")

        return rosters

    def map_rosters_to_nhl07(
        self,
        rosters: Dict[str, List[Player]],
    ) -> Dict[int, List[NHL07PlayerRecord]]:
        """Map fetched rosters to NHL 07 team records.

        Returns dict mapping team index to list of player records.
        """
        teams: Dict[int, List[NHL07PlayerRecord]] = {}
        team_stats = getattr(self, "team_stats", {})

        for team_code, players in rosters.items():
            slot = self.mapper.get_team_slot(team_code)
            if slot is None or slot >= 32:
                continue

            stats = team_stats.get(team_code, {})

            # Select ~25 players, ordered for proper lines
            selected = self.mapper.select_roster(
                players,
                stats,
                max_players=25,
            )

            # Map to NHL 07 format with real stats
            nhl07_players = []
            for player in selected:
                pid = str(player.id)
                pstats = stats.get(pid, {})
                record = self.mapper.map_player(
                    player,
                    team_code,
                    pstats,
                )
                nhl07_players.append(record)

            teams[slot] = nhl07_players

        return teams

    def patch_rom(
        self,
        iso_path: str,
        output_path: str,
        rosters: Dict[str, List[Player]],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> PatchResult:
        """Apply roster patches to ISO.

        Steps:
          1. Copy ISO to output_path (1.6GB — show progress)
          2. Extract db.viv from copy
          3. Decompress relevant TDB files
          4. Modify SPBT, SPAI, SGAI, ROST tables
          5. Recompress + rebuild BIGF
          6. Replace db.viv in ISO
        """
        # Step 1: Copy ISO
        if self.on_status:
            self.on_status("Copying ISO...")
        writer = NHL07PSPRomWriter(iso_path, output_path)
        if not writer.copy_iso(on_progress):
            return PatchResult(
                success=False,
                error="Failed to copy ISO file",
            )

        # Step 2: Load the copy
        if self.on_status:
            self.on_status("Loading db.viv...")
        if on_progress:
            on_progress(0.3, "Loading db.viv...")
        if not writer.load():
            return PatchResult(
                success=False,
                error="Failed to load db.viv from ISO",
            )

        # Step 3: Parse TDB files
        if self.on_status:
            self.on_status("Parsing TDB tables...")
        reader = writer.reader
        if not reader:
            return PatchResult(
                success=False,
                error="Reader not initialized",
            )

        try:
            master_tdb = reader.get_tdb(TDB_MASTER)
            bioatt_tdb = reader.get_tdb(TDB_BIOATT)
            roster_tdb = reader.get_tdb(TDB_ROSTER)
        except Exception as e:
            return PatchResult(
                success=False,
                error=f"Failed to parse TDB: {e}",
            )

        if not master_tdb:
            from services.nhl07_psp_patcher.ea_tdb import bigf_parse

            viv = reader.get_db_viv()
            names = []
            if viv:
                try:
                    names = [e.name for e in bigf_parse(viv)]
                except Exception:
                    pass
            return PatchResult(
                success=False,
                error=f"Master TDB not found: {TDB_MASTER}. BIGF has: {names}",
            )

        # Primary tables from master TDB (what the game actually reads)
        spbt = master_tdb.get_table("SPBT")
        spai = master_tdb.get_table("SPAI")
        sgai = master_tdb.get_table("SGAI")
        rost = master_tdb.get_table("ROST")
        play = master_tdb.get_table("PLAY")

        if not spbt or not rost or not play:
            missing = []
            if not spbt:
                missing.append("SPBT")
            if not rost:
                missing.append("ROST")
            if not play:
                missing.append("PLAY")
            master_tables = list(master_tdb.tables.keys())
            return PatchResult(
                success=False,
                error=(
                    f"Tables not found in master: {', '.join(missing)}. "
                    f"master has: {master_tables}"
                ),
            )

        # Secondary tables from split TDBs (write both for consistency)
        split_spbt = bioatt_tdb.get_table("SPBT") if bioatt_tdb else None
        split_spai = bioatt_tdb.get_table("SPAI") if bioatt_tdb else None
        split_sgai = bioatt_tdb.get_table("SGAI") if bioatt_tdb else None
        split_rost = roster_tdb.get_table("ROST") if roster_tdb else None

        # Build PLAY lookup: PLAY.INDX → {TBLE, ID__}
        # Chain: ROST.INDX == PLAY.INDX → PLAY.ID__ == SPBT.INDX == SPAI/SGAI.INDX
        play_by_indx = {}
        for i in range(play.num_records):
            try:
                rec = play.read_record(i)
                play_by_indx[rec.get("INDX", -1)] = rec
            except Exception:
                continue

        # Build SPBT/SPAI/SGAI index lookups (INDX → record index)
        spbt_idx_map = {}
        for i in range(spbt.num_records):
            try:
                indx = spbt.read_record(i).get("INDX", 0)
                if indx > 0:
                    spbt_idx_map[indx] = i
            except Exception:
                continue

        spai_idx_map = {}
        if spai:
            for i in range(spai.num_records):
                try:
                    indx = spai.read_record(i).get("INDX", 0)
                    if indx > 0:
                        spai_idx_map[indx] = i
                except Exception:
                    continue

        sgai_idx_map = {}
        if sgai:
            for i in range(sgai.num_records):
                try:
                    indx = sgai.read_record(i).get("INDX", 0)
                    if indx > 0:
                        sgai_idx_map[indx] = i
                except Exception:
                    continue

        # Step 4: Map rosters and write to tables
        if self.on_status:
            self.on_status("Mapping rosters...")
        nhl07_teams = self.map_rosters_to_nhl07(rosters)

        teams_patched = 0
        players_patched = 0
        total_teams = len(nhl07_teams)

        for ti, (team_idx, players) in enumerate(sorted(nhl07_teams.items())):
            if on_progress:
                team_name = (
                    NHL07_TEAM_NAMES[team_idx]
                    if team_idx < len(NHL07_TEAM_NAMES)
                    else f"Team {team_idx}"
                )
                on_progress(
                    0.35 + (ti / max(total_teams, 1)) * 0.25,
                    f"Writing {team_name} ({len(players)} players)...",
                )

            if not players:
                continue

            # Find existing ROST records for this team — these define
            # the roster slots and their cross-references via PLAY table
            team_rost_indices = rost.find_records("TEAM", team_idx)

            # Classify each ROST slot as goalie or skater based on
            # whether its player_id has an SGAI entry (goalie attrs).
            # Players MUST be mapped to compatible slots — a goalie
            # player needs a goalie slot (one whose player_id is in
            # SGAI) so its attrs can be written to the correct table.
            goalie_slots = []  # (rost_idx, play_rec, player_id, bio_idx)
            skater_slots = []
            for rost_idx in team_rost_indices:
                rost_rec = rost.read_record(rost_idx)
                rost_indx = rost_rec.get("INDX", 0)
                play_rec = play_by_indx.get(rost_indx)
                if not play_rec:
                    continue
                player_id = play_rec.get("ID__", 0)
                bio_idx = spbt_idx_map.get(player_id, -1)
                if bio_idx < 0:
                    continue
                slot_info = (rost_idx, play_rec, player_id, bio_idx)
                if sgai_idx_map.get(player_id, -1) >= 0:
                    goalie_slots.append(slot_info)
                else:
                    skater_slots.append(slot_info)

            # Split incoming players by type
            new_goalies = [p for p in players if p.is_goalie]
            new_skaters = [p for p in players if not p.is_goalie]

            # Build ordered (player, slot_info) pairs:
            # goalies → goalie slots, skaters → skater slots
            pairs = []
            for i, player in enumerate(new_goalies):
                if i < len(goalie_slots):
                    pairs.append((player, goalie_slots[i]))
            for i, player in enumerate(new_skaters):
                if i < len(skater_slots):
                    pairs.append((player, skater_slots[i]))

            # Track which slots are used so we can undress the rest
            used_rost_indices = set()

            # Generate line flags for the whole team at once
            # (position-aware: fills lines properly, sets PP/PK)
            team_players = [p for p, _ in pairs]
            all_line_flags = self.mapper.generate_team_line_flags(
                team_players
            )

            for pi, (player, slot_info) in enumerate(pairs):
                rost_idx, play_rec, player_id, bio_idx = slot_info
                used_rost_indices.add(rost_idx)

                # Write bio to SPBT (name, jersey, etc.) — preserves INDX
                writer.write_player_bio(master_tdb, bio_idx, player)
                if split_spbt and bio_idx < split_spbt.capacity:
                    writer.write_player_bio(bioatt_tdb, bio_idx, player)

                # Write attributes to the matching table (SGAI or SPAI)
                if player.is_goalie and player.goalie_attrs and sgai:
                    sgai_idx = sgai_idx_map.get(player_id, -1)
                    if sgai_idx >= 0:
                        writer.write_goalie_attrs(
                            master_tdb, sgai_idx, player.goalie_attrs,
                        )
                        if split_sgai and sgai_idx < split_sgai.capacity:
                            writer.write_goalie_attrs(
                                bioatt_tdb, sgai_idx, player.goalie_attrs,
                            )
                elif player.skater_attrs and spai:
                    spai_idx = spai_idx_map.get(player_id, -1)
                    if spai_idx >= 0:
                        writer.write_skater_attrs(
                            master_tdb, spai_idx, player.skater_attrs,
                        )
                        if split_spai and spai_idx < split_spai.capacity:
                            writer.write_skater_attrs(
                                bioatt_tdb, spai_idx, player.skater_attrs,
                            )

                # Update ROST: jersey, line flags, captain — but NOT INDX
                line_flags = all_line_flags[pi] if pi < len(all_line_flags) else {}
                rost_values = {
                    "JERS": player.jersey_number,
                    "CAPT": 2 if pi == 0 else (1 if pi in (1, 2) else 0),
                    "DRES": 1,
                }
                for flag in LINE_FLAGS:
                    rost_values[flag] = 0
                if line_flags:
                    for flag, val in line_flags.items():
                        if flag in LINE_FLAGS:
                            rost_values[flag] = val
                rost.write_record(rost_idx, rost_values)
                if split_rost and rost_idx < split_rost.capacity:
                    split_rost = roster_tdb.get_table("ROST")
                    if split_rost:
                        split_rost.write_record(rost_idx, rost_values)

                players_patched += 1

            # Mark remaining old roster entries as undressed
            for rost_idx in team_rost_indices:
                if rost_idx not in used_rost_indices:
                    rost.write_record(rost_idx, {"DRES": 0})
                    if split_rost and rost_idx < split_rost.capacity:
                        split_rost_t = roster_tdb.get_table("ROST")
                        if split_rost_t:
                            split_rost_t.write_record(rost_idx, {"DRES": 0})

            teams_patched += 1

        # Step 5-6: Recompress and write back to ISO
        if self.on_status:
            self.on_status("Rebuilding db.viv...")

        modified_tdbs = {}
        # Use the original filename casing from the BIGF
        from services.nhl07_psp_patcher.ea_tdb import bigf_parse

        if writer._db_viv:
            entries = bigf_parse(writer._db_viv)
            master_name = TDB_MASTER
            bioatt_name = TDB_BIOATT
            roster_name = TDB_ROSTER
            for entry in entries:
                if entry.name.lower() == TDB_MASTER.lower():
                    master_name = entry.name
                if entry.name.lower() == TDB_BIOATT.lower():
                    bioatt_name = entry.name
                if entry.name.lower() == TDB_ROSTER.lower():
                    roster_name = entry.name
            modified_tdbs[master_name] = master_tdb
            if bioatt_tdb:
                modified_tdbs[bioatt_name] = bioatt_tdb
            if roster_tdb:
                modified_tdbs[roster_name] = roster_tdb

        if not writer.rebuild_and_write(modified_tdbs, on_progress):
            detail = getattr(writer, "_last_error", "unknown")
            tb = getattr(writer, "_last_traceback", "")
            return PatchResult(
                success=False,
                error=f"Failed to write db.viv: {detail}\n{tb}",
            )

        return PatchResult(
            success=True,
            output_path=output_path,
            teams_patched=teams_patched,
            players_patched=players_patched,
        )

