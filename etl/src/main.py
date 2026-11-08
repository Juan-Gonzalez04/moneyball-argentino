"""
Entrypoint principal del pipeline ETL MoneyBall Argentino / Argos.
Orquesta secuencialmente las cuatro fases:
Extract -> Validate -> Transform -> Load (E-V-T-L)
y ejecuta un smoke test analítico sobre PostgreSQL.
"""

from datetime import datetime, timezone
import logging
import time

from etl.src.config import AFA_PLAYERS_STATS_URL, AFA_TEAMS_STATS_URL
from etl.src.extract import fetch_players_stats_full, fetch_teams_stats_full
from etl.src.schemas import validate_afa_payload, validate_teams_stats_payload
from etl.src.transform import transform_dataset, transform_teams_stats, resolve_season_year
from etl.src.load import get_db_connection, load_dataset_to_postgres, load_team_stats_to_postgres

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("etl.main")


def run_scouting_smoke_test():
    """Ejecuta una consulta SQL de scouting directo sobre la base para validar la carga."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Conteo total de entidades
            cur.execute("SELECT COUNT(*) FROM teams;")
            teams_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM team_stats;")
            team_stats_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM players;")
            players_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM player_goals WHERE total_goals > 0;")
            scorers_count = cur.fetchone()[0]

            print("\n" + "=" * 65)
            print("         📊 RESULTADOS DE CARGA EN POSTGRESQL (SILVER LAYER)")
            print("=" * 65)
            print(f" * Equipos registrados:          {teams_count:>5}")
            print(f" * Métricas de clubes cargadas:  {team_stats_count:>5}")
            print(f" * Futbolistas cargados:         {players_count:>5}")
            print(f" * Goleadores con registro:      {scorers_count:>5}")

            # Top 5 clubes por puntos
            top_clubs_query = """
            SELECT t.name, ts.points, ts.matches_played, ts.matches_won, ts.goals_for
            FROM team_stats ts
            JOIN teams t ON ts.team_id = t.team_id
            ORDER BY ts.points DESC, ts.goals_for DESC
            LIMIT 5;
            """
            cur.execute(top_clubs_query)
            club_rows = cur.fetchall()
            print("\n" + "-" * 65)
            print(" 🏆 TOP 5 CLUBES CON MAYOR PUNTAJE (TABLA OFICIAL)")
            print("-" * 65)
            print(f"{'Club':<26} {'Pts':<6} {'PJ':<5} {'PG':<5} {'Goles':<5}")
            print("-" * 65)
            for cr in club_rows:
                print(f"{cr[0][:25]:<26} {cr[1]:<6} {cr[2]:<5} {cr[3]:<5} {cr[4]:<5}")

            # 2. Query de scouting: Top 5 talentos Sub-23 con mayor minutaje
            u23_query = """
            SELECT 
                p.player_id,
                COALESCE(p.nick_name, p.first_name || ' ' || p.last_name) AS nombre,
                t.name AS club,
                p.age AS edad,
                s.minutes_total AS minutos,
                COALESCE(g.total_goals, 0) AS goles,
                s.shots_on_target AS tiros_al_arco
            FROM players p
            JOIN teams t ON p.team_id = t.team_id
            JOIN player_stats s ON p.player_id = s.player_id
            LEFT JOIN player_goals g ON p.player_id = g.player_id
            WHERE p.age <= 23 AND s.minutes_total > 0
            ORDER BY s.minutes_total DESC, g.total_goals DESC
            LIMIT 5;
            """
            cur.execute(u23_query)
            rows = cur.fetchall()

            print("\n" + "-" * 65)
            print(" ⭐ TOP 5 TALENTOS SUB-23 CON MAYOR PARTICIPACIÓN (MINUTOS)")
            print("-" * 65)
            print(f"{'Jugador':<24} {'Club':<20} {'Edad':<5} {'Minutos':<8} {'Goles':<5}")
            print("-" * 65)
            for r in rows:
                p_name, club, edad, mins, goles = r[1], r[2], r[3], r[4], r[5]
                print(f"{p_name[:23]:<24} {club[:19]:<20} {edad:<5} {mins:<8} {goles:<5}")
            print("=" * 65 + "\n")

    finally:
        conn.close()


def main():
    start_time = time.perf_counter()
    logger.info("==========================================================")
    logger.info("  INICIANDO PIPELINE MONEYBALL ARGENTINO (E-V-T-L)        ")
    logger.info("==========================================================")

    # --------------------------------------------------------------------------
    # FASE 1: EXTRACT (I/O Red y Bronze Snapshot)
    # --------------------------------------------------------------------------
    logger.info("[FASE 1/4] Ejecutando Extracción de Jugadores y Clubes...")
    players_extraction = fetch_players_stats_full(url=AFA_PLAYERS_STATS_URL, save_raw=True)
    teams_extraction = fetch_teams_stats_full(url=AFA_TEAMS_STATS_URL, save_raw=True)

    # --------------------------------------------------------------------------
    # FASE 2: VALIDATE (Data Contracts & Quarantine)
    # --------------------------------------------------------------------------
    logger.info("[FASE 2/4] Ejecutando Validación de Contratos (Pydantic v2)...")
    players_dataset, players_report = validate_afa_payload(players_extraction.payload)
    if players_report.quarantined_players_count > 0 or players_report.quarantined_teams_count > 0:
        logger.warning(
            "Registros derivados a cuarentena (jugadores): %d equipos, %d jugadores",
            players_report.quarantined_teams_count,
            players_report.quarantined_players_count,
        )

    teams_dataset, teams_report = validate_teams_stats_payload(teams_extraction.payload)
    if teams_report.quarantined_count > 0:
        logger.warning(
            "Registros derivados a cuarentena (clubes): %d clubes",
            teams_report.quarantined_count,
        )

    # --------------------------------------------------------------------------
    # FASE 3: TRANSFORM (Normalización Relacional)
    # --------------------------------------------------------------------------
    logger.info("[FASE 3/4] Ejecutando Transformación y Casteo de Tipos...")
    season_year = resolve_season_year(players_dataset)
    transformed_players = transform_dataset(players_dataset, season_year=season_year)
    transformed_teams_stats = transform_teams_stats(teams_dataset, season_year=season_year)

    # --------------------------------------------------------------------------
    # FASE 4: LOAD (Idempotent Upsert en PostgreSQL)
    # --------------------------------------------------------------------------
    logger.info("[FASE 4/4] Ejecutando Carga Idempotente en PostgreSQL...")
    load_summary = load_dataset_to_postgres(transformed_players)
    teams_stats_loaded = load_team_stats_to_postgres(transformed_teams_stats)

    elapsed_time = time.perf_counter() - start_time
    logger.info(
        "Pipeline completado exitosamente en %.2f segundos (%d equipos, %d jugadores, %d métricas de clubes).",
        elapsed_time,
        load_summary.teams_upserted,
        load_summary.players_upserted,
        teams_stats_loaded,
    )

    # --------------------------------------------------------------------------
    # VERIFICACIÓN ANALÍTICA
    # --------------------------------------------------------------------------
    run_scouting_smoke_test()


if __name__ == "__main__":
    main()
