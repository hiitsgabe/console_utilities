"""MVP Baseball PSP Patcher - Main orchestrator.

Coordinates fetching MLB roster data from ESPN, mapping stats,
and patching MVP Baseball PSP (ULUS-10012) ISO.
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from services.sports_api.models import Player
from services.mvp_psp_patcher.models import (
    MVPTeamRecord,
    MVPPlayerRecord,
    MVPRomInfo,
    TEAM_COUNT,
    MVP_TEAM_ORDER,
    TEAM_HASHES,
    MVP_ABBREV_TO_INDEX,
    ATTRIB_FIRST_NAME,
    ATTRIB_LAST_NAME,
    ATTRIB_JERSEY,
    ATTRIB_BATS,
    ATTRIB_THROWS,
    ATTRIB_PRIMARY_POS,
    ATTRIB_SECONDARY_POS,
    ATTRIB_HEIGHT,
    ATTRIB_WEIGHT,
    ATTRIB_SPEED,
    ATTRIB_FIELDING,
    ATTRIB_RANGE,
    ATTRIB_THROW_STRENGTH,
    ATTRIB_THROW_ACCURACY,
    ATTRIB_DURABILITY,
    ATTRIB_PLATE_DISCIPLINE,
    ATTRIB_BUNTING,
    ATTRIB_BASERUNNING,
    ATTRIB_STEALING_AGGRESSIVE,
    ATTRIB_STARPOWER,
    LR_CONTACT,
    LR_POWER,
    PA_STAMINA,
    PA_PICKOFF,
    PA_PITCH1_MOVEMENT,
    PA_PITCH1_CONTROL,
    PA_PITCH1_VELOCITY,
    PA_PITCH2_TYPE,
    PA_PITCH2_MOVEMENT,
    PA_PITCH2_CONTROL,
    PA_PITCH2_VELOCITY,
    POS_STRING_TO_NUM,
    ROSTER_TEAMID,
    ROSTER_PLAYERID,
    ROSTER_RH_AL_POS,
    ROSTER_RH_AL_ORDER,
    ROSTER_RH_NL_POS,
    ROSTER_RH_NL_ORDER,
    ROSTER_LH_AL_POS,
    ROSTER_LH_AL_ORDER,
    ROSTER_LH_NL_POS,
    ROSTER_LH_NL_ORDER,
    POSITIONS,
)
from services.mvp_psp_patcher.stat_mapper import MVPPSPStatMapper
from services.mvp_psp_patcher.rom_reader import MVPPSPRomReader
from services.mvp_psp_patcher.rom_writer import MVPPSPRomWriter


@dataclass
class PatchResult:
    """Result of a patch operation."""

    success: bool
    output_path: str = ""
    error: str = ""
    teams_patched: int = 0
    players_patched: int = 0


class MVPPSPPatcher:
    """Main orchestrator for MVP Baseball PSP roster patching."""

    def __init__(
        self,
        cache_dir: str,
        on_status: Optional[Callable] = None,
    ):
        self.cache_dir = cache_dir
        self.on_status = on_status
        self.mapper = MVPPSPStatMapper()

        from services.sports_api.espn_client import EspnClient
        self.api = EspnClient(cache_dir, on_status)

    def analyze_rom(self, iso_path: str) -> MVPRomInfo:
        """Validate ISO and read team slots."""
        reader = MVPPSPRomReader(iso_path)
        if not reader.load():
            return MVPRomInfo(path=iso_path, size=0)
        return reader.get_info()

    def fetch_rosters(
        self,
        on_progress: Optional[Callable[[float, str], None]] = None,
        season: int = 2025,
    ) -> Dict[str, List[Player]]:
        """Fetch all MLB team rosters + stats."""
        rosters: Dict[str, List[Player]] = {}
        self.team_stats: Dict[str, dict] = {}

        if self.on_status:
            self.on_status("Fetching MLB teams...")
        mlb_teams = self.api.get_mlb_teams()

        if not mlb_teams:
            if self.on_status:
                self.on_status("No MLB teams found")
            return rosters

        # Filter to teams with MVP ROM slots
        mapped = [
            t for t in mlb_teams
            if self.mapper.get_team_slot(t.code) is not None
        ]
        total = len(mapped)

        for i, team in enumerate(mapped):
            if on_progress:
                on_progress(i / total, f"Fetching {team.name}...")

            players = self.api.get_baseball_squad(team.id)
            stats = self.api.get_baseball_team_leaders(team.id, season)

            if players:
                rosters[team.code] = players
            if stats:
                self.team_stats[team.code] = stats

        if on_progress:
            on_progress(1.0, "Complete")

        return rosters

    def map_rosters(
        self,
        rosters: Dict[str, List[Player]],
    ) -> List[MVPTeamRecord]:
        """Map fetched rosters to MVP team records.

        Returns list of 30 MVPTeamRecord (one per ROM slot).
        """
        teams: List[MVPTeamRecord] = []
        team_stats = getattr(self, "team_stats", {})
        abbrevs = list(TEAM_HASHES.keys())

        for i in range(TEAM_COUNT):
            abbrev = abbrevs[i] if i < len(abbrevs) else ""
            teams.append(MVPTeamRecord(
                index=i,
                name=MVP_TEAM_ORDER[i],
                abbrev=abbrev,
                hash_id=TEAM_HASHES.get(abbrev, ""),
                players=[],
            ))

        for team_code, players in rosters.items():
            slot = self.mapper.get_team_slot(team_code)
            if slot is None or slot >= TEAM_COUNT:
                continue

            mvp_abbrev = self.mapper.get_mvp_abbrev(team_code)
            if not mvp_abbrev:
                continue

            stats = team_stats.get(team_code, {})

            # Select 25 players ordered for ROM slots
            selected = self.mapper.select_roster(players, stats)

            mvp_players = []
            for idx, player in enumerate(selected):
                pid = str(player.id)
                pstats = stats.get(pid, {})
                is_pitcher = self.mapper._is_pitcher(player)
                is_starter = idx >= 15 and idx < 20

                if is_pitcher:
                    record = self.mapper.map_pitcher(
                        player, pstats, is_starter=is_starter,
                    )
                else:
                    record = self.mapper.map_batter(player, pstats)

                # Assign roster position based on slot
                record.roster_position = self._slot_to_position(idx)
                if idx < 9:
                    record.batting_order = idx + 1  # 1-based (game uses order-1 as index)
                else:
                    record.batting_order = -1

                mvp_players.append(record)

            teams[slot].players = mvp_players

        return teams

    def _slot_to_position(self, slot: int) -> str:
        """Map roster slot index to MVP position string."""
        if slot < 9:
            return ["C", "1B", "2B", "SS", "3B", "LF", "CF", "RF", "DH"][slot]
        elif slot < 15:
            return "B"  # Bench
        elif slot < 20:
            return ["SP1", "SP2", "SP3", "SP4", "SP5"][slot - 15]
        else:
            return ["CP", "SU", "MR", "MR", "LR"][min(slot - 20, 4)]

    def patch_rom(
        self,
        iso_path: str,
        output_path: str,
        rosters: Dict[str, List[Player]],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> PatchResult:
        """Apply roster patches to ISO."""
        if self.on_status:
            self.on_status("Loading ISO...")

        writer = MVPPSPRomWriter(iso_path, output_path)
        if not writer.load():
            return PatchResult(
                success=False,
                error="Failed to load MVP Baseball PSP ISO",
            )

        if self.on_status:
            self.on_status("Mapping rosters...")
        mvp_teams = self.map_rosters(rosters)

        # Separate existing hashes into pitcher and batter pools
        # to preserve cross-table references (pitchstat, batstat, etc.)
        pitcher_hashes_set = set(
            writer.reader.records.get("pitchattrib", {}).keys()
        )
        all_hashes = list(writer.reader.records.get("attrib", {}).keys())
        pitcher_pool = [h for h in all_hashes if h in pitcher_hashes_set]
        batter_pool = [h for h in all_hashes if h not in pitcher_hashes_set]
        pitcher_iter = iter(pitcher_pool)
        batter_iter = iter(batter_pool)

        teams_patched = 0
        players_patched = 0

        # Clear existing roster records for teams we're patching
        patched_team_hashes = set()
        for team in mvp_teams:
            if team.players and team.hash_id:
                patched_team_hashes.add(team.hash_id)

        # Remove old roster entries for patched teams
        old_roster = dict(writer.reader.records.get("roster", {}))
        new_roster: Dict[str, Dict[int, str]] = {}
        preserved_ids: set = set()
        for rec_id, fields in old_roster.items():
            team_hash = fields.get(ROSTER_TEAMID, "")
            if team_hash not in patched_team_hashes:
                new_roster[rec_id] = fields
                preserved_ids.add(rec_id)

        # Use IDs that don't collide with preserved entries
        roster_counter = max(
            (int(rid, 16) for rid in old_roster.keys()),
            default=0,
        ) + 1

        for i, team in enumerate(mvp_teams):
            if on_progress:
                on_progress(
                    i / TEAM_COUNT,
                    f"Writing {team.name} ({len(team.players)} players)...",
                )

            if not team.players or not team.hash_id:
                continue

            for p_idx, player in enumerate(team.players):
                # Reuse hash from matching pool (pitcher or batter)
                if player.is_pitcher:
                    try:
                        player_hash = next(pitcher_iter)
                    except StopIteration:
                        # Fallback to batter pool
                        try:
                            player_hash = next(batter_iter)
                        except StopIteration:
                            player_hash = f"00{i:02x}{p_idx:05x}ff"
                else:
                    try:
                        player_hash = next(batter_iter)
                    except StopIteration:
                        try:
                            player_hash = next(pitcher_iter)
                        except StopIteration:
                            player_hash = f"00{i:02x}{p_idx:05x}ff"

                player.hash_id = player_hash

                # Write attrib record
                attrib_fields = self._build_attrib_fields(player)
                writer.update_player_record("attrib", player_hash, attrib_fields)

                # Write LR attrib records (vs RHP and LHP)
                lr_rhp = self._build_lr_attrib_fields(player, "rhp")
                writer.update_player_record("lrattrib_rhp", player_hash, lr_rhp)
                lr_lhp = self._build_lr_attrib_fields(player, "lhp")
                writer.update_player_record("lrattrib_lhp", player_hash, lr_lhp)

                # Write pitch attrib for pitchers
                if player.is_pitcher:
                    pa_fields = self._build_pitchattrib_fields(player)
                    writer.update_player_record("pitchattrib", player_hash, pa_fields)

                # Build roster entry with non-colliding hex ID
                roster_id = f"{roster_counter:09x}"
                roster_counter += 1
                roster_fields = self._build_roster_fields(
                    team.hash_id, player_hash, player, i
                )
                new_roster[roster_id] = roster_fields

                players_patched += 1

            teams_patched += 1

        # Apply the rebuilt roster table
        writer.update_records("roster", new_roster)

        if on_progress:
            on_progress(1.0, "Saving patched ISO...")

        if self.on_status:
            self.on_status("Saving patched ISO...")
        if not writer.finalize():
            return PatchResult(
                success=False,
                error="Failed to save patched ISO",
            )

        return PatchResult(
            success=True,
            output_path=output_path,
            teams_patched=teams_patched,
            players_patched=players_patched,
        )

    def _build_attrib_fields(self, player: MVPPlayerRecord) -> Dict[int, str]:
        """Build attrib CSV fields from a player record."""
        pos_num = POS_STRING_TO_NUM.get(player.primary_position, 7)
        fields = {
            ATTRIB_FIRST_NAME: player.first_name,
            ATTRIB_LAST_NAME: player.last_name,
            ATTRIB_JERSEY: str(player.jersey),
            ATTRIB_BATS: str(player.bats),
            ATTRIB_THROWS: str(player.throws),
            ATTRIB_PRIMARY_POS: str(pos_num),
            ATTRIB_HEIGHT: str(player.height),
            ATTRIB_WEIGHT: str(player.weight),
            ATTRIB_PLATE_DISCIPLINE: str(player.plate_discipline),
            ATTRIB_BUNTING: str(player.bunting),
            ATTRIB_STEALING_AGGRESSIVE: str(player.stealing),
            ATTRIB_BASERUNNING: str(player.baserunning),
            ATTRIB_SPEED: str(player.speed),
            ATTRIB_FIELDING: str(player.fielding),
            ATTRIB_RANGE: str(player.arm_range),
            ATTRIB_THROW_STRENGTH: str(player.throw_strength),
            ATTRIB_THROW_ACCURACY: str(player.throw_accuracy),
            ATTRIB_DURABILITY: str(player.durability),
            ATTRIB_STARPOWER: str(player.starpower),
        }
        if player.secondary_position:
            sec_num = POS_STRING_TO_NUM.get(player.secondary_position, 0)
            fields[ATTRIB_SECONDARY_POS] = str(sec_num)
        return fields

    def _build_lr_attrib_fields(
        self, player: MVPPlayerRecord, vs: str
    ) -> Dict[int, str]:
        """Build LR attrib fields (vs RHP or LHP).

        Only updates name and contact/power — spray charts and
        tendencies are preserved from the original record via merge.
        """
        if vs == "rhp":
            contact = player.contact_rhp
            power = player.power_rhp
        else:
            contact = player.contact_lhp
            power = player.power_lhp

        return {
            0: player.first_name,
            1: player.last_name,
            LR_CONTACT: str(contact),
            LR_POWER: str(power),
        }

    def _build_pitchattrib_fields(
        self, player: MVPPlayerRecord
    ) -> Dict[int, str]:
        """Build pitch attrib fields for a pitcher.

        Pitch 1 is always fastball (no type field, fields 4-7).
        Pitches 2-5 each have type+movement+desc+control+velocity (5 fields).
        """
        fields: Dict[int, str] = {
            0: player.first_name,
            1: player.last_name,
            PA_STAMINA: str(player.stamina),
            PA_PICKOFF: str(player.pickoff),
        }
        if player.pitches:
            # Pitch 1 (fastball): fields 4-7, no type
            p1 = player.pitches[0]
            fields[PA_PITCH1_MOVEMENT] = str(p1.get("movement", 50))
            fields[PA_PITCH1_CONTROL] = str(p1.get("control", 50))
            fields[PA_PITCH1_VELOCITY] = str(p1.get("velocity", 50))

        # Pitches 2-5: fields 8-12, 13-17, 18-22, 23-27
        for i, pitch in enumerate(player.pitches[1:4]):
            base = PA_PITCH2_TYPE + i * 5
            fields[base] = str(pitch.get("type", 1))
            fields[base + 1] = str(pitch.get("movement", 50))
            fields[base + 3] = str(pitch.get("control", 50))
            fields[base + 4] = str(pitch.get("velocity", 50))
        return fields

    def _build_roster_fields(
        self,
        team_hash: str,
        player_hash: str,
        player: MVPPlayerRecord,
        team_index: int,
    ) -> Dict[int, str]:
        """Build roster CSV fields for a player."""
        pos = player.roster_position
        order = player.batting_order

        # AL teams: indices 0-13, NL teams: 14-29
        is_al = team_index < 14

        fields = {
            ROSTER_TEAMID: team_hash,
            ROSTER_PLAYERID: player_hash,
        }

        if is_al:
            fields[ROSTER_RH_AL_POS] = pos
            fields[ROSTER_RH_AL_ORDER] = str(order)
            fields[ROSTER_RH_NL_POS] = pos
            fields[ROSTER_RH_NL_ORDER] = str(-1)
            fields[ROSTER_LH_AL_POS] = pos
            fields[ROSTER_LH_AL_ORDER] = str(order)
            fields[ROSTER_LH_NL_POS] = pos
            fields[ROSTER_LH_NL_ORDER] = str(-1)
        else:
            fields[ROSTER_RH_AL_POS] = pos
            fields[ROSTER_RH_AL_ORDER] = str(-1)
            fields[ROSTER_RH_NL_POS] = pos
            fields[ROSTER_RH_NL_ORDER] = str(order)
            fields[ROSTER_LH_AL_POS] = pos
            fields[ROSTER_LH_AL_ORDER] = str(-1)
            fields[ROSTER_LH_NL_POS] = pos
            fields[ROSTER_LH_NL_ORDER] = str(order)

        return fields
