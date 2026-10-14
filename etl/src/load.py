"""
Módulo de Carga (Load) para MoneyBall Argentino / Argos.

Responsabilidades:
1. Conectar con el clúster PostgreSQL utilizando psycopg2.
2. Ejecutar inserciones masivas idempotentes (Upsert) mediante cláusulas ON CONFLICT DO UPDATE.
3. Respetar el orden estricto de integridad referencial:
   - 1° Equipos (teams)
   - 2° Jugadores (players)
   - 3° Estadísticas (player_goals, player_stats)
4. Gestionar transacciones atómicas: si una tabla falla, se revierte todo el lote (Rollback).
5. Retornar métricas detalladas de registros insertados o actualizados.
"""

from typing import Any, Dict, List, NamedTuple
import logging
import psycopg2
from psycopg2.extras import execute_values

from etl.src.config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
)
from etl.src.transform import TransformedDataset

logger = logging.getLogger("etl.load")


class LoadSummary(NamedTuple):
    teams_upserted: int
    players_upserted: int
    goals_upserted: int
    stats_upserted: int
    success: bool


def get_db_connection():
    """Crea y retorna una conexión a la base de datos PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def load_dataset_to_postgres(dataset: TransformedDataset) -> LoadSummary:
    """
    Ejecuta el Upsert masivo de los datos transformados dentro de una única transacción atómica.
    """
    logger.info("Iniciando carga idempotente en PostgreSQL (%s:%d/%s)...", DB_HOST, DB_PORT, DB_NAME)

    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # --------------------------------------------------------------
                # 1. Cargar Equipos (teams)
                # --------------------------------------------------------------
                teams_query = """
                INSERT INTO teams (
                    team_id, name, short_name, team_type, colors, raw_payload
                ) VALUES %s
                ON CONFLICT (team_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    short_name = EXCLUDED.short_name,
                    team_type = EXCLUDED.team_type,
                    colors = EXCLUDED.colors,
                    raw_payload = EXCLUDED.raw_payload,
                    updated_at = NOW();
                """
                teams_data = [
                    (
                        t["team_id"],
                        t["name"],
                        t["short_name"],
                        t["team_type"],
                        t["colors"],
                        t["raw_payload"],
                    )
                    for t in dataset.teams
                ]
                execute_values(cur, teams_query, teams_data, page_size=500)
                logger.info("Equipos procesados exitosamente: %d filas", len(teams_data))

                # --------------------------------------------------------------
                # 2. Cargar Jugadores (players)
                # --------------------------------------------------------------
                players_query = """
                INSERT INTO players (
                    player_id, team_id, squad_no, position_id, first_name,
                    middle_name, last_name, nick_name, birth_date, age,
                    height, weight, nationality, current_team_name, raw_payload
                ) VALUES %s
                ON CONFLICT (player_id) DO UPDATE SET
                    team_id = EXCLUDED.team_id,
                    squad_no = EXCLUDED.squad_no,
                    position_id = EXCLUDED.position_id,
                    first_name = EXCLUDED.first_name,
                    middle_name = EXCLUDED.middle_name,
                    last_name = EXCLUDED.last_name,
                    nick_name = EXCLUDED.nick_name,
                    birth_date = EXCLUDED.birth_date,
                    age = EXCLUDED.age,
                    height = EXCLUDED.height,
                    weight = EXCLUDED.weight,
                    nationality = EXCLUDED.nationality,
                    current_team_name = EXCLUDED.current_team_name,
                    raw_payload = EXCLUDED.raw_payload,
                    updated_at = NOW();
                """
                players_data = [
                    (
                        p["player_id"],
                        p["team_id"],
                        p["squad_no"],
                        p["position_id"],
                        p["first_name"],
                        p["middle_name"],
                        p["last_name"],
                        p["nick_name"],
                        p["birth_date"],
                        p["age"],
                        p["height"],
                        p["weight"],
                        p["nationality"],
                        p["current_team_name"],
                        p["raw_payload"],
                    )
                    for p in dataset.players
                ]
                execute_values(cur, players_query, players_data, page_size=500)
                logger.info("Jugadores procesados exitosamente: %d filas", len(players_data))

                # --------------------------------------------------------------
                # 3. Cargar Goles (player_goals)
                # --------------------------------------------------------------
                goals_query = """
                INSERT INTO player_goals (
                    player_id, season_year, total_goals, played_goals, first_time_goals,
                    second_time_goals, head_goals, free_kick_goals, penalty_goals, raw_payload
                ) VALUES %s
                ON CONFLICT (player_id, season_year) DO UPDATE SET
                    total_goals = EXCLUDED.total_goals,
                    played_goals = EXCLUDED.played_goals,
                    first_time_goals = EXCLUDED.first_time_goals,
                    second_time_goals = EXCLUDED.second_time_goals,
                    head_goals = EXCLUDED.head_goals,
                    free_kick_goals = EXCLUDED.free_kick_goals,
                    penalty_goals = EXCLUDED.penalty_goals,
                    raw_payload = EXCLUDED.raw_payload,
                    updated_at = NOW();
                """
                goals_data = [
                    (
                        g["player_id"],
                        g["season_year"],
                        g["total_goals"],
                        g["played_goals"],
                        g["first_time_goals"],
                        g["second_time_goals"],
                        g["head_goals"],
                        g["free_kick_goals"],
                        g["penalty_goals"],
                        g["raw_payload"],
                    )
                    for g in dataset.player_goals
                ]
                execute_values(cur, goals_query, goals_data, page_size=500)
                logger.info("Métricas de goles procesadas exitosamente: %d filas", len(goals_data))

                # --------------------------------------------------------------
                # 4. Cargar Estadísticas Generales (player_stats)
                # --------------------------------------------------------------
                stats_query = """
                INSERT INTO player_stats (
                    player_id, season_year, minutes_total, minutes_holds, minutes_substitute,
                    shots_total, shots_on_target, shots_off_target, shots_woodwork,
                    passes_correct, passes_incorrect, fouls_committed, fouls_received,
                    yellow_cards, double_yellow_cards, red_cards, steals_total,
                    goal_assistances, saves_total, raw_payload
                ) VALUES %s
                ON CONFLICT (player_id, season_year) DO UPDATE SET
                    minutes_total = EXCLUDED.minutes_total,
                    minutes_holds = EXCLUDED.minutes_holds,
                    minutes_substitute = EXCLUDED.minutes_substitute,
                    shots_total = EXCLUDED.shots_total,
                    shots_on_target = EXCLUDED.shots_on_target,
                    shots_off_target = EXCLUDED.shots_off_target,
                    shots_woodwork = EXCLUDED.shots_woodwork,
                    passes_correct = EXCLUDED.passes_correct,
                    passes_incorrect = EXCLUDED.passes_incorrect,
                    fouls_committed = EXCLUDED.fouls_committed,
                    fouls_received = EXCLUDED.fouls_received,
                    yellow_cards = EXCLUDED.yellow_cards,
                    double_yellow_cards = EXCLUDED.double_yellow_cards,
                    red_cards = EXCLUDED.red_cards,
                    steals_total = EXCLUDED.steals_total,
                    goal_assistances = EXCLUDED.goal_assistances,
                    saves_total = EXCLUDED.saves_total,
                    raw_payload = EXCLUDED.raw_payload,
                    updated_at = NOW();
                """
                stats_data = [
                    (
                        s["player_id"],
                        s["season_year"],
                        s["minutes_total"],
                        s["minutes_holds"],
                        s["minutes_substitute"],
                        s["shots_total"],
                        s["shots_on_target"],
                        s["shots_off_target"],
                        s["shots_woodwork"],
                        s["passes_correct"],
                        s["passes_incorrect"],
                        s["fouls_committed"],
                        s["fouls_received"],
                        s["yellow_cards"],
                        s["double_yellow_cards"],
                        s["red_cards"],
                        s["steals_total"],
                        s["goal_assistances"],
                        s["saves_total"],
                        s["raw_payload"],
                    )
                    for s in dataset.player_stats
                ]
                execute_values(cur, stats_query, stats_data, page_size=500)
                logger.info("Métricas de rendimiento procesadas exitosamente: %d filas", len(stats_data))

        logger.info("Transacción confirmada (COMMIT). Carga masiva exitosa.")
        return LoadSummary(
            teams_upserted=len(dataset.teams),
            players_upserted=len(dataset.players),
            goals_upserted=len(dataset.player_goals),
            stats_upserted=len(dataset.player_stats),
            success=True,
        )

    except Exception as exc:
        logger.error("Error durante la carga a PostgreSQL (ROLLBACK automático): %s", exc, exc_info=True)
        raise
    finally:
        conn.close()
