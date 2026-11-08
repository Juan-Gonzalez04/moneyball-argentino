"""
Contratos de Datos (Data Contracts) con Pydantic v2 para MoneyBall Argentino.

Define esquemas formales y tipados para validar el payload de la API de AFA,
asegurando que ningún registro inconsistente o con breaking changes corrompa la BD.
Implementa política de cuarentena por registro (*Quarantine Pattern*).
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field, ValidationError
import logging

logger = logging.getLogger("etl.schemas")


class StrictBaseModel(BaseModel):
    """Modelo base configurado para ignorar campos extras desconocidos pero validar tipos estrictos."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# ------------------------------------------------------------------------------
# 1. Contratos de Jugadores
# ------------------------------------------------------------------------------
class PlayerNameContract(StrictBaseModel):
    first: Optional[str] = Field(default="")
    middle: Optional[str] = Field(default=None)
    last: Optional[str] = Field(default="")
    nick: Optional[str] = Field(default=None)


class PlayerRawContract(StrictBaseModel):
    teamId: Optional[int] = Field(default=None, description="ID del equipo actual")
    squadNo: Optional[int] = Field(default=None, description="Número de dorsal")
    posnId: Optional[int] = Field(default=None, description="ID de posición (1: Arquero, 2: Defensor, 3: Volante, 4: Delantero)")
    birthday: Optional[str] = Field(default=None, description="Fecha de nacimiento en formato YYYY-MM-DD")
    age: Optional[int] = Field(default=None, ge=14, le=55, description="Edad del futbolista")
    height: Optional[int] = Field(default=None, ge=140, le=220, description="Altura en cm")
    weight: Optional[int] = Field(default=None, ge=45, le=130, description="Peso en kg")
    country: Optional[str] = Field(default=None, description="Nacionalidad")
    currentTeam: Optional[str] = Field(default=None, description="Nombre del equipo actual")
    name: PlayerNameContract = Field(default_factory=PlayerNameContract)


# ------------------------------------------------------------------------------
# 2. Contratos de Equipos
# ------------------------------------------------------------------------------
class TeamColorsContract(StrictBaseModel):
    color: Optional[str] = None
    base_color: Optional[str] = None
    text: Optional[str] = None
    path1: Optional[str] = None
    path1_color: Optional[str] = None
    path2: Optional[str] = None
    path2_color: Optional[str] = None
    shirt: Optional[int] = None


class TeamRawContract(StrictBaseModel):
    name: str = Field(min_length=1, description="Nombre del club")
    shortName: Optional[str] = Field(default=None)
    teamType: Optional[str] = Field(default="club")
    colors: Optional[TeamColorsContract] = None


# ------------------------------------------------------------------------------
# 3. Contratos de Métricas y Estadísticas
# ------------------------------------------------------------------------------
class MinutesPlayedContract(StrictBaseModel):
    holds: Optional[int] = 0
    substitute: Optional[int] = 0
    total: Optional[int] = 0


class GoalsContract(StrictBaseModel):
    first_time: Optional[int] = 0
    second_time: Optional[int] = 0
    playedGoals: Optional[int] = 0
    freekick: Optional[int] = 0
    headGoal: Optional[int] = 0
    penalty: Optional[int] = 0


class ShotsContract(StrictBaseModel):
    first_time: Optional[int] = 0
    second_time: Optional[int] = 0
    supp_time: Optional[int] = 0
    goals: Optional[int] = 0
    OnWoodwork: Optional[int] = 0
    OnTarget: Optional[int] = 0
    OffTarget: Optional[int] = 0


class PassesContract(StrictBaseModel):
    correct: Optional[int] = 0
    incorrect: Optional[int] = 0


class CardsContract(StrictBaseModel):
    yellow: Optional[int] = 0
    doubleYellow: Optional[int] = 0
    red: Optional[int] = 0


class FoulsCommittedDetail(StrictBaseModel):
    first_time: Optional[int] = 0
    second_time: Optional[int] = 0
    supp_time: Optional[int] = 0


class FoulsContract(StrictBaseModel):
    committed: Optional[FoulsCommittedDetail] = None


# ------------------------------------------------------------------------------
# 4. Estructura Validada y Reporte de Validación (Quarantine Pattern)
# ------------------------------------------------------------------------------
class ValidatedDataset(BaseModel):
    teams: Dict[int, TeamRawContract]
    players: Dict[int, PlayerRawContract]
    minutes_played: Dict[int, MinutesPlayedContract]
    goals: Dict[int, GoalsContract]
    shots: Dict[int, ShotsContract]
    passes: Dict[int, PassesContract]
    cards: Dict[int, CardsContract]
    raw_payloads: Dict[str, Any]  # Conserva payloads crudos para inserción JSONB


class ValidationReport(BaseModel):
    valid_teams_count: int = 0
    valid_players_count: int = 0
    quarantined_teams_count: int = 0
    quarantined_players_count: int = 0
    quarantine_errors: List[Dict[str, Any]] = Field(default_factory=list)


def validate_afa_payload(raw_payload: Dict[str, Any]) -> Tuple[ValidatedDataset, ValidationReport]:
    """
    Valida el payload completo aplicando la política de cuarentena:
    los registros individuales malformados se aíslan sin abortar el procesamiento global.
    """
    report = ValidationReport()
    valid_teams: Dict[int, TeamRawContract] = {}
    valid_players: Dict[int, PlayerRawContract] = {}
    valid_minutes: Dict[int, MinutesPlayedContract] = {}
    valid_goals: Dict[int, GoalsContract] = {}
    valid_shots: Dict[int, ShotsContract] = {}
    valid_passes: Dict[int, PassesContract] = {}
    valid_cards: Dict[int, CardsContract] = {}

    # 1. Validar Equipos
    raw_teams = raw_payload.get("teams", {})
    for tid_str, t_data in raw_teams.items():
        try:
            team_id = int(tid_str)
            contract = TeamRawContract.model_validate(t_data)
            valid_teams[team_id] = contract
        except (ValueError, ValidationError) as err:
            report.quarantined_teams_count += 1
            report.quarantine_errors.append({
                "entity": "team",
                "id": tid_str,
                "error": str(err),
            })
    report.valid_teams_count = len(valid_teams)

    # 2. Validar Jugadores
    raw_players = raw_payload.get("players", {})
    for pid_str, p_data in raw_players.items():
        try:
            player_id = int(pid_str)
            contract = PlayerRawContract.model_validate(p_data)
            valid_players[player_id] = contract
        except (ValueError, ValidationError) as err:
            report.quarantined_players_count += 1
            report.quarantine_errors.append({
                "entity": "player",
                "id": pid_str,
                "error": str(err),
            })
    report.valid_players_count = len(valid_players)

    # 3. Validar Métricas (con tolerancia a campos nulos o ausentes)
    for pid_str, m_data in raw_payload.get("minutesPlayed", {}).items():
        try:
            pid = int(pid_str)
            if isinstance(m_data, dict):
                valid_minutes[pid] = MinutesPlayedContract.model_validate(m_data)
        except Exception:
            pass

    for pid_str, g_data in raw_payload.get("goals", {}).items():
        try:
            pid = int(pid_str)
            if isinstance(g_data, dict):
                valid_goals[pid] = GoalsContract.model_validate(g_data)
        except Exception:
            pass

    for pid_str, s_data in raw_payload.get("shots", {}).items():
        try:
            pid = int(pid_str)
            if isinstance(s_data, dict):
                valid_shots[pid] = ShotsContract.model_validate(s_data)
        except Exception:
            pass

    for pid_str, p_data in raw_payload.get("passes", {}).items():
        try:
            pid = int(pid_str)
            if isinstance(p_data, dict):
                valid_passes[pid] = PassesContract.model_validate(p_data)
        except Exception:
            pass

    for pid_str, c_data in raw_payload.get("cards", {}).items():
        try:
            pid = int(pid_str)
            if isinstance(c_data, dict):
                valid_cards[pid] = CardsContract.model_validate(c_data)
        except Exception:
            pass

    logger.info(
        "Validación finalizada | Equipos: %d válidos (%d cuarentena) | Jugadores: %d válidos (%d cuarentena)",
        report.valid_teams_count,
        report.quarantined_teams_count,
        report.valid_players_count,
        report.quarantined_players_count,
    )

    dataset = ValidatedDataset(
        teams=valid_teams,
        players=valid_players,
        minutes_played=valid_minutes,
        goals=valid_goals,
        shots=valid_shots,
        passes=valid_passes,
        cards=valid_cards,
        raw_payloads=raw_payload,
    )

    return dataset, report


# ------------------------------------------------------------------------------
# 5. Contratos de Estadísticas Oficiales de Clubes (teamStats.json)
# ------------------------------------------------------------------------------
class TeamMatchRecordContract(StrictBaseModel):
    Win: Optional[int] = 0
    Tied: Optional[int] = 0
    Loose: Optional[int] = 0
    Points: Optional[int] = 0


class TeamMatchesContract(StrictBaseModel):
    total: TeamMatchRecordContract = Field(default_factory=TeamMatchRecordContract)
    first_time: Optional[TeamMatchRecordContract] = None
    second_time: Optional[TeamMatchRecordContract] = None


class TeamGoalsStatsContract(StrictBaseModel):
    first_time: Optional[int] = 0
    second_time: Optional[int] = 0
    playedGoals: Optional[int] = 0
    freekick: Optional[int] = 0
    ownGoal: Optional[int] = 0
    headGoal: Optional[int] = 0
    penalty: Optional[int] = 0


class TeamShotsStatsContract(StrictBaseModel):
    first_time: Optional[int] = 0
    second_time: Optional[int] = 0
    supp_time: Optional[int] = 0
    goals: Optional[int] = 0
    OnWoodwork: Optional[int] = 0
    OnTarget: Optional[int] = 0
    OffTarget: Optional[int] = 0
    conversionRate: Optional[str] = "0.0%"


class TeamPassesStatsContract(StrictBaseModel):
    correct: Optional[int] = 0
    incorrect: Optional[int] = 0
    accuracy: Optional[str] = "0.0%"


class TeamCardsStatsContract(StrictBaseModel):
    yellow: Optional[int] = 0
    doubleYellow: Optional[int] = 0
    red: Optional[int] = 0


class TeamStealingStatsContract(StrictBaseModel):
    first_time: Optional[int] = 0
    second_time: Optional[int] = 0
    supp_time: Optional[int] = 0
    perGame: Optional[float] = 0.0


class ValidatedTeamStatsItem(StrictBaseModel):
    team_id: int
    name: str
    short_name: Optional[str] = None
    matches: TeamMatchesContract = Field(default_factory=TeamMatchesContract)
    goals: TeamGoalsStatsContract = Field(default_factory=TeamGoalsStatsContract)
    shots: TeamShotsStatsContract = Field(default_factory=TeamShotsStatsContract)
    passes: TeamPassesStatsContract = Field(default_factory=TeamPassesStatsContract)
    cards: TeamCardsStatsContract = Field(default_factory=TeamCardsStatsContract)
    stealing: TeamStealingStatsContract = Field(default_factory=TeamStealingStatsContract)
    fouls: Optional[Dict[str, Any]] = None
    corner_kicks: Optional[Dict[str, Any]] = None
    offside: Optional[Dict[str, Any]] = None
    goal_assistances: Optional[Dict[str, Any]] = None
    penalties: Optional[Dict[str, Any]] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class ValidatedTeamsDataset(BaseModel):
    teams_stats: Dict[int, ValidatedTeamStatsItem]
    raw_payload: Dict[str, Any]


class TeamStatsValidationReport(BaseModel):
    valid_count: int = 0
    quarantined_count: int = 0
    quarantine_errors: List[Dict[str, Any]] = Field(default_factory=list)


def validate_teams_stats_payload(raw_payload: Dict[str, Any]) -> Tuple[ValidatedTeamsDataset, TeamStatsValidationReport]:
    """
    Valida el payload de estadísticas colectivas de clubes aplicando la política de cuarentena.
    Aísla anomalías individuales por club sin detener la validación del conjunto.
    """
    report = TeamStatsValidationReport()
    valid_teams_stats: Dict[int, ValidatedTeamStatsItem] = {}

    teams_map = raw_payload.get("teams", {})
    matches_map = raw_payload.get("matches", {})
    goals_map = raw_payload.get("goals", {})
    shots_map = raw_payload.get("shots", {})
    passes_map = raw_payload.get("passes", {})
    cards_map = raw_payload.get("cards", {})
    stealing_map = raw_payload.get("stealing", {})
    fouls_map = raw_payload.get("fouls", {})
    corners_map = raw_payload.get("cornerKicks", {})
    offside_map = raw_payload.get("offside", {})
    assists_map = raw_payload.get("goalAssistances", {})
    penalties_map = raw_payload.get("penalties", {})

    for tid_str, t_info in teams_map.items():
        try:
            team_id = int(tid_str)
            team_name = t_info.get("name") if isinstance(t_info, dict) else str(tid_str)
            short_name = t_info.get("shortName") if isinstance(t_info, dict) else None

            matches = TeamMatchesContract.model_validate(matches_map.get(tid_str, {}))
            goals = TeamGoalsStatsContract.model_validate(goals_map.get(tid_str, {}))
            shots = TeamShotsStatsContract.model_validate(shots_map.get(tid_str, {}))
            passes = TeamPassesStatsContract.model_validate(passes_map.get(tid_str, {}))
            cards = TeamCardsStatsContract.model_validate(cards_map.get(tid_str, {}))
            stealing = TeamStealingStatsContract.model_validate(stealing_map.get(tid_str, {}))

            club_raw = {
                "team": t_info,
                "matches": matches_map.get(tid_str),
                "goals": goals_map.get(tid_str),
                "shots": shots_map.get(tid_str),
                "passes": passes_map.get(tid_str),
                "cards": cards_map.get(tid_str),
                "stealing": stealing_map.get(tid_str),
                "fouls": fouls_map.get(tid_str),
                "cornerKicks": corners_map.get(tid_str),
                "offside": offside_map.get(tid_str),
                "goalAssistances": assists_map.get(tid_str),
                "penalties": penalties_map.get(tid_str),
            }

            item = ValidatedTeamStatsItem(
                team_id=team_id,
                name=team_name,
                short_name=short_name,
                matches=matches,
                goals=goals,
                shots=shots,
                passes=passes,
                cards=cards,
                stealing=stealing,
                fouls=fouls_map.get(tid_str),
                corner_kicks=corners_map.get(tid_str),
                offside=offside_map.get(tid_str),
                goal_assistances=assists_map.get(tid_str),
                penalties=penalties_map.get(tid_str),
                raw_payload=club_raw,
            )
            valid_teams_stats[team_id] = item

        except (ValueError, ValidationError) as err:
            report.quarantined_count += 1
            report.quarantine_errors.append({
                "entity": "team_stats",
                "team_id": tid_str,
                "error": str(err),
            })

    report.valid_count = len(valid_teams_stats)
    logger.info(
        "Validación de estadísticas de clubes finalizada | %d válidos (%d cuarentena)",
        report.valid_count,
        report.quarantined_count,
    )

    return (
        ValidatedTeamsDataset(teams_stats=valid_teams_stats, raw_payload=raw_payload),
        report,
    )

