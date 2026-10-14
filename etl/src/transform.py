"""
Módulo de Transformación (Transform) para MoneyBall Argentino / Argos.

Responsabilidades:
1. Recibir el conjunto de datos validado (ValidatedDataset de Pydantic v2).
2. Desanidar estructuras complejas (ej. objetos de nombre a columnas planas).
3. Castear y normalizar tipos de datos primitivos (ej. fechas en string 'YYYY-MM-DD' a datetime.date).
4. Asignar valores por defecto coherentes para métricas ausentes o dispersas (sparsity).
5. Empaquetar payloads crudos en cadenas JSON válidas para columnas JSONB.
6. Entregar tuplas de datos normalizados listas para inserción batch en PostgreSQL.
"""

from datetime import date, datetime
from typing import Any, Dict, List, NamedTuple, Optional
import json
import logging
import os

from etl.src.schemas import ValidatedDataset

logger = logging.getLogger("etl.transform")


class TransformedDataset(NamedTuple):
    teams: List[Dict[str, Any]]
    players: List[Dict[str, Any]]
    player_goals: List[Dict[str, Any]]
    player_stats: List[Dict[str, Any]]


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Castea de forma segura una fecha en formato YYYY-MM-DD a un objeto date."""
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        # La API suele entregar fechas como '2002-09-30'
        return datetime.strptime(date_str.strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def resolve_season_year(dataset: ValidatedDataset, explicit_year: Optional[int] = None) -> int:
    """
    Resuelve dinámicamente el año de la temporada en cascada:
    1. Valor explícito pasado por parámetro (si existe).
    2. Variable de entorno SEASON_YEAR (si está configurada).
    3. Primeros 4 dígitos del campo 'competitionStart' del payload crudo (ej: '20260723' -> 2026).
    4. Año actual del sistema como fallback seguro.
    """
    if explicit_year is not None:
        return explicit_year

    env_season = os.getenv("SEASON_YEAR")
    if env_season and env_season.strip().isdigit():
        return int(env_season.strip())

    comp_start = dataset.raw_payloads.get("competitionStart")
    if comp_start:
        comp_start_str = str(comp_start).strip()
        if len(comp_start_str) >= 4 and comp_start_str[:4].isdigit():
            return int(comp_start_str[:4])

    return datetime.now().year


def transform_dataset(dataset: ValidatedDataset, season_year: Optional[int] = None) -> TransformedDataset:
    """
    Transforma el dataset validado a colecciones planas alineadas con el esquema de PostgreSQL.
    Si season_year no se especifica, se infiere dinámicamente desde los metadatos de la competencia.
    """
    effective_season_year = resolve_season_year(dataset, season_year)
    logger.info("Iniciando transformación de datos para la temporada %d...", effective_season_year)
    raw_payloads = dataset.raw_payloads
    raw_teams_map = raw_payloads.get("teams", {})
    raw_players_map = raw_payloads.get("players", {})

    # --------------------------------------------------------------------------
    # 1. Transformación de Equipos (teams)
    # --------------------------------------------------------------------------
    transformed_teams: List[Dict[str, Any]] = []
    valid_team_ids = set(dataset.teams.keys())

    for team_id, team_contract in dataset.teams.items():
        colors_dict = team_contract.colors.model_dump() if team_contract.colors else None
        raw_team_data = raw_teams_map.get(str(team_id), {})

        transformed_teams.append({
            "team_id": team_id,
            "name": team_contract.name,
            "short_name": team_contract.shortName,
            "team_type": team_contract.teamType or "club",
            "colors": json.dumps(colors_dict) if colors_dict else None,
            "raw_payload": json.dumps(raw_team_data),
        })

    # --------------------------------------------------------------------------
    # 2. Transformación de Jugadores (players)
    # --------------------------------------------------------------------------
    transformed_players: List[Dict[str, Any]] = []
    transformed_goals: List[Dict[str, Any]] = []
    transformed_stats: List[Dict[str, Any]] = []

    for player_id, player_contract in dataset.players.items():
        # Validar si el team_id asignado existe en la tabla de equipos para integridad referencial
        assigned_team_id = player_contract.teamId
        if assigned_team_id not in valid_team_ids:
            assigned_team_id = None

        name_obj = player_contract.name
        first_name = name_obj.first.strip() if name_obj.first else None
        middle_name = name_obj.middle.strip() if name_obj.middle else None
        last_name = name_obj.last.strip() if name_obj.last else None
        
        # Si no hay apodo explícito, construimos uno con primer nombre y apellido
        nick_name = name_obj.nick.strip() if name_obj.nick else None
        if not nick_name and (first_name or last_name):
            nick_name = f"{first_name or ''} {last_name or ''}".strip()

        raw_player_data = raw_players_map.get(str(player_id), {})

        transformed_players.append({
            "player_id": player_id,
            "team_id": assigned_team_id,
            "squad_no": player_contract.squadNo,
            "position_id": player_contract.posnId,
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "nick_name": nick_name,
            "birth_date": parse_date(player_contract.birthday),
            "age": player_contract.age,
            "height": player_contract.height,
            "weight": player_contract.weight,
            "nationality": player_contract.country.strip() if player_contract.country else None,
            "current_team_name": player_contract.currentTeam.strip() if player_contract.currentTeam else None,
            "raw_payload": json.dumps(raw_player_data),
        })

        # ----------------------------------------------------------------------
        # 3. Transformación de Goles (player_goals)
        # ----------------------------------------------------------------------
        goals_contract = dataset.goals.get(player_id)
        if goals_contract:
            # Calcular total de goles sumando las variantes
            total_goals = (
                (goals_contract.playedGoals or 0)
                + (goals_contract.freekick or 0)
                + (goals_contract.headGoal or 0)
                + (goals_contract.penalty or 0)
            )
            raw_goals_data = raw_payloads.get("goals", {}).get(str(player_id), {})
            transformed_goals.append({
                "player_id": player_id,
                "season_year": effective_season_year,
                "total_goals": total_goals,
                "played_goals": goals_contract.playedGoals or 0,
                "first_time_goals": goals_contract.first_time or 0,
                "second_time_goals": goals_contract.second_time or 0,
                "head_goals": goals_contract.headGoal or 0,
                "free_kick_goals": goals_contract.freekick or 0,
                "penalty_goals": goals_contract.penalty or 0,
                "raw_payload": json.dumps(raw_goals_data),
            })
        else:
            # Si el jugador no figura en goles, registramos fila en cero para integridad
            transformed_goals.append({
                "player_id": player_id,
                "season_year": effective_season_year,
                "total_goals": 0,
                "played_goals": 0,
                "first_time_goals": 0,
                "second_time_goals": 0,
                "head_goals": 0,
                "free_kick_goals": 0,
                "penalty_goals": 0,
                "raw_payload": json.dumps({}),
            })

        # ----------------------------------------------------------------------
        # 4. Transformación de Métricas de Rendimiento (player_stats)
        # ----------------------------------------------------------------------
        min_contract = dataset.minutes_played.get(player_id)
        shots_contract = dataset.shots.get(player_id)
        passes_contract = dataset.passes.get(player_id)
        cards_contract = dataset.cards.get(player_id)

        # Extraer asistencias, faltas, recuperaciones y atajadas de los diccionarios raw
        assists = raw_payloads.get("goalAssistances", {}).get(str(player_id), {})
        total_assists = assists.get("first_time", 0) + assists.get("second_time", 0) if isinstance(assists, dict) else 0

        steals = raw_payloads.get("stealing", {}).get(str(player_id), {})
        total_steals = steals.get("first_time", 0) + steals.get("second_time", 0) if isinstance(steals, dict) else 0

        saves = raw_payloads.get("saves", {}).get(str(player_id), {})
        total_saves = saves.get("first_time", 0) + saves.get("second_time", 0) if isinstance(saves, dict) else 0

        fouls_comm = raw_payloads.get("fouls", {}).get(str(player_id), {}).get("committed", {})
        total_fouls_comm = fouls_comm.get("first_time", 0) + fouls_comm.get("second_time", 0) if isinstance(fouls_comm, dict) else 0

        fouls_rec = raw_payloads.get("foulsReceived", {}).get(str(player_id), {})
        total_fouls_rec = fouls_rec.get("first_time", 0) + fouls_rec.get("second_time", 0) if isinstance(fouls_rec, dict) else 0

        shots_total = 0
        shots_on_target = 0
        shots_off_target = 0
        shots_woodwork = 0
        if shots_contract:
            shots_total = (shots_contract.first_time or 0) + (shots_contract.second_time or 0)
            shots_on_target = shots_contract.OnTarget or 0
            shots_off_target = shots_contract.OffTarget or 0
            shots_woodwork = shots_contract.OnWoodwork or 0

        transformed_stats.append({
            "player_id": player_id,
            "season_year": effective_season_year,
            "minutes_total": min_contract.total if min_contract else 0,
            "minutes_holds": min_contract.holds if min_contract else 0,
            "minutes_substitute": min_contract.substitute if min_contract else 0,
            "shots_total": shots_total,
            "shots_on_target": shots_on_target,
            "shots_off_target": shots_off_target,
            "shots_woodwork": shots_woodwork,
            "passes_correct": passes_contract.correct if passes_contract else 0,
            "passes_incorrect": passes_contract.incorrect if passes_contract else 0,
            "fouls_committed": total_fouls_comm,
            "fouls_received": total_fouls_rec,
            "yellow_cards": cards_contract.yellow if cards_contract else 0,
            "double_yellow_cards": cards_contract.doubleYellow if cards_contract else 0,
            "red_cards": cards_contract.red if cards_contract else 0,
            "steals_total": total_steals,
            "goal_assistances": total_assists,
            "saves_total": total_saves,
            "raw_payload": json.dumps({
                "minutes": min_contract.model_dump() if min_contract else {},
                "shots": shots_contract.model_dump() if shots_contract else {},
                "passes": passes_contract.model_dump() if passes_contract else {},
                "cards": cards_contract.model_dump() if cards_contract else {},
            }),
        })

    logger.info(
        "Transformación completada con éxito: %d equipos, %d jugadores, %d métricas de gol, %d métricas de rendimiento.",
        len(transformed_teams),
        len(transformed_players),
        len(transformed_goals),
        len(transformed_stats),
    )

    return TransformedDataset(
        teams=transformed_teams,
        players=transformed_players,
        player_goals=transformed_goals,
        player_stats=transformed_stats,
    )
