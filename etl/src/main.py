"""
Entrypoint principal del pipeline ETL MoneyBall Argentino / Argos.
Orquesta secuencialmente las cuatro fases:
Extract -> Validate -> Transform -> Load (E-V-T-L)
y ejecuta un smoke test analítico sobre PostgreSQL.
"""

from datetime import datetime, timezone
import logging
import time

from etl.src.config import AFA_PLAYERS_STATS_URL
from etl.src.extract import fetch_players_stats_full
from etl.src.schemas import validate_afa_payload
from etl.src.transform import transform_dataset
from etl.src.load import get_db_connection, load_dataset_to_postgres

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

            cur.execute("SELECT COUNT(*) FROM players;")
            players_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM player_goals WHERE total_goals > 0;")
            scorers_count = cur.fetchone()[0]

            print("\n" + "=" * 65)
            print("         📊 RESULTADOS DE CARGA EN POSTGRESQL (SILVER LAYER)")
            print("=" * 65)
            print(f" * Equipos registrados:     {teams_count:>5}")
            print(f" * Futbolistas cargados:    {players_count:>5}")
            print(f" * Goleadores con registro: {scorers_count:>5}")

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
    logger.info("[FASE 1/4] Ejecutando Extracción...")
    extraction = fetch_players_stats_full(url=AFA_PLAYERS_STATS_URL, save_raw=True)

    # --------------------------------------------------------------------------
    # FASE 2: VALIDATE (Data Contracts & Quarantine)
    # --------------------------------------------------------------------------
    logger.info("[FASE 2/4] Ejecutando Validación de Contratos (Pydantic v2)...")
    dataset, report = validate_afa_payload(extraction.payload)
    if report.quarantined_players_count > 0 or report.quarantined_teams_count > 0:
        logger.warning(
            "Registros derivados a cuarentena: %d equipos, %d jugadores",
            report.quarantined_teams_count,
            report.quarantined_players_count,
        )

    # --------------------------------------------------------------------------
    # FASE 3: TRANSFORM (Normalización Relacional)
    # --------------------------------------------------------------------------
    logger.info("[FASE 3/4] Ejecutando Transformación y Casteo de Tipos...")
    transformed = transform_dataset(dataset, season_year=2026)

    # --------------------------------------------------------------------------
    # FASE 4: LOAD (Idempotent Upsert en PostgreSQL)
    # --------------------------------------------------------------------------
    logger.info("[FASE 4/4] Ejecutando Carga Idempotente en PostgreSQL...")
    load_summary = load_dataset_to_postgres(transformed)

    elapsed_time = time.perf_counter() - start_time
    logger.info("Pipeline completado exitosamente en %.2f segundos.", elapsed_time)

    # --------------------------------------------------------------------------
    # VERIFICACIÓN ANALÍTICA
    # --------------------------------------------------------------------------
    run_scouting_smoke_test()


if __name__ == "__main__":
    main()
