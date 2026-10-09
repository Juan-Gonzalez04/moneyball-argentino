"""
dashboard/data.py
=================
Carga, normalización y cálculo de estadísticas analíticas desde PostgreSQL.
Aplica compute pushdown y almacenamiento en caché con TTL en memoria.
"""

import os
from pathlib import Path
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets" / "teams"

POSITION_MAP = {
    1: "Arquero",
    2: "Defensor",
    3: "Mediocampista",
    4: "Delantero"
}


def get_db_connection():
    """Conexión robusta a PostgreSQL adaptada a Docker y entorno local."""
    host = os.getenv("DB_HOST", "postgres" if os.path.exists("/.dockerenv") else "localhost")
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "afa_data"),
        user=os.getenv("DB_USER", "juan"),
        password=os.getenv("DB_PASSWORD", "argos_secure_password_2026"),
        host=host,
        port=int(os.getenv("DB_PORT", "5432"))
    )


@st.cache_data(ttl=120)
def load_all_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Carga jugadores y clubes con todas las métricas analíticas (incluyendo arqueros).
    Calcula rankings colectivos en memoria.
    """
    players_query = """
    SELECT 
        p.player_id,
        p.team_id,
        t.name AS team_name,
        COALESCE(p.nick_name, p.first_name || ' ' || p.last_name) AS player_name,
        p.first_name,
        p.last_name,
        p.age,
        p.position_id,
        COALESCE(p.height, 0) AS height,
        COALESCE(p.weight, 0) AS weight,
        COALESCE(p.nationality, 'Argentina') AS nationality,
        COALESCE(s.minutes_total, 0) AS minutes_played,
        COALESCE(g.total_goals, 0) AS goals,
        COALESCE(g.penalty_goals, 0) AS penalty_goals,
        COALESCE(s.goal_assistances, 0) AS assists,
        COALESCE(s.shots_total, 0) AS shots_total,
        COALESCE(s.shots_on_target, 0) AS shots_on_target,
        COALESCE(s.steals_total, 0) AS steals,
        COALESCE(s.passes_correct, 0) AS passes_correct,
        COALESCE(s.passes_incorrect, 0) AS passes_incorrect,
        ROUND(
            CASE 
                WHEN (COALESCE(s.passes_correct, 0) + COALESCE(s.passes_incorrect, 0)) > 0 
                THEN (COALESCE(s.passes_correct, 0)::numeric / (s.passes_correct + s.passes_incorrect)::numeric) * 100 
                ELSE 0 
            END, 1
        ) AS pass_accuracy_pct,
        COALESCE(s.saves_total, 0) AS saves_total,
        COALESCE(s.yellow_cards, 0) AS yellow_cards,
        COALESCE(s.red_cards, 0) AS red_cards
    FROM players p
    JOIN teams t ON p.team_id = t.team_id
    LEFT JOIN player_stats s ON p.player_id = s.player_id
    LEFT JOIN player_goals g ON p.player_id = g.player_id
    ORDER BY s.minutes_total DESC;
    """
    
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(players_query)
            df_players = pd.DataFrame(cur.fetchall())
            
    if not df_players.empty:
        df_players["position"] = df_players["position_id"].map(POSITION_MAP).fillna("Sin posición")
        df_players["pass_accuracy_pct"] = pd.to_numeric(df_players["pass_accuracy_pct"], errors="coerce").fillna(0.0)
        df_players["is_u23"] = df_players["age"] <= 23

    # Agregación institucional de clubes
    teams_summary = df_players.groupby(["team_id", "team_name"]).agg(
        squad_size=("player_id", "count"),
        avg_age=("age", "mean"),
        total_minutes=("minutes_played", "sum"),
        total_goals=("goals", "sum"),
        total_shots_on_target=("shots_on_target", "sum"),
        total_steals=("steals", "sum"),
        total_saves=("saves_total", "sum"),
        passes_correct=("passes_correct", "sum"),
        passes_incorrect=("passes_incorrect", "sum"),
        u23_count=("is_u23", "sum")
    ).reset_index()

    teams_summary["avg_age"] = teams_summary["avg_age"].round(1)
    tot_passes = teams_summary["passes_correct"] + teams_summary["passes_incorrect"]
    teams_summary["team_pass_accuracy"] = np.where(tot_passes > 0, (teams_summary["passes_correct"] / tot_passes * 100).round(1), 0.0)

    # Posiciones relativas en el ranking de Primera División (1 a 30)
    teams_summary["rank_goals"] = teams_summary["total_goals"].rank(ascending=False, method="min").astype(int)
    teams_summary["rank_shots"] = teams_summary["total_shots_on_target"].rank(ascending=False, method="min").astype(int)
    teams_summary["rank_pass_acc"] = teams_summary["team_pass_accuracy"].rank(ascending=False, method="min").astype(int)
    teams_summary["rank_age"] = teams_summary["avg_age"].rank(ascending=True, method="min").astype(int)

    return df_players, teams_summary


def get_team_logo(team_id: int) -> Path | None:
    """Devuelve la ruta física del escudo PNG si existe."""
    logo_path = ASSETS_DIR / f"{team_id}.png"
    return logo_path if logo_path.exists() else None
