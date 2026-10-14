"""
dashboard/views/leaders_view.py
===============================
Pestaña 2: Líderes de Rendimiento.
Rankings directos en las principales dimensiones técnicas de la competición.
"""

import streamlit as st
import pandas as pd


def render_leaders_view(df_players: pd.DataFrame):
    st.subheader("Tablas de Líderes por Dimensión Técnica")
    st.caption("Rankings individuales de la temporada en las principales áreas del juego.")

    r_col1, r_col2 = st.columns(2)

    with r_col1:
        st.markdown("#### Máximos Goleadores")
        top_scorers = df_players[df_players["goals"] > 0].sort_values(
            by=["goals", "shots_on_target"], ascending=[False, False]
        ).head(10)[["player_name", "team_name", "position", "age", "goals", "penalty_goals", "shots_on_target", "minutes_played"]].rename(columns={
            "player_name": "Futbolista",
            "team_name": "Club",
            "position": "Posición",
            "age": "Edad",
            "goals": "Goles",
            "penalty_goals": "Penales",
            "shots_on_target": "Tiros al Arco",
            "minutes_played": "Minutos"
        })
        st.dataframe(top_scorers, use_container_width=True, hide_index=True)

    with r_col2:
        st.markdown("#### Mejores Pasadores (Mín. 200 pases intentados)")
        passers = df_players[(df_players["passes_correct"] + df_players["passes_incorrect"]) >= 200].sort_values(
            by="pass_accuracy_pct", ascending=False
        ).head(10)[["player_name", "team_name", "position", "age", "pass_accuracy_pct", "passes_correct", "minutes_played"]].rename(columns={
            "player_name": "Futbolista",
            "team_name": "Club",
            "position": "Posición",
            "age": "Edad",
            "pass_accuracy_pct": "% Acierto",
            "passes_correct": "Pases Precisos",
            "minutes_played": "Minutos"
        })
        st.dataframe(passers, use_container_width=True, hide_index=True)

    st.divider()

    r_col3, r_col4 = st.columns(2)

    with r_col3:
        st.markdown("#### Mayor Rodaje (Minutos en Cancha)")
        top_minutes = df_players.sort_values(by="minutes_played", ascending=False).head(10)[
            ["player_name", "team_name", "position", "age", "minutes_played", "steals", "pass_accuracy_pct"]
        ].rename(columns={
            "player_name": "Futbolista",
            "team_name": "Club",
            "position": "Posición",
            "age": "Edad",
            "minutes_played": "Minutos",
            "steals": "Recuperaciones",
            "pass_accuracy_pct": "% Pase"
        })
        st.dataframe(top_minutes, use_container_width=True, hide_index=True)

    with r_col4:
        st.markdown("#### Líderes Defensivos (Recuperaciones de Balón)")
        top_steals = df_players.sort_values(by="steals", ascending=False).head(10)[
            ["player_name", "team_name", "position", "age", "steals", "passes_correct", "minutes_played"]
        ].rename(columns={
            "player_name": "Futbolista",
            "team_name": "Club",
            "position": "Posición",
            "age": "Edad",
            "steals": "Recuperaciones",
            "passes_correct": "Pases Precisos",
            "minutes_played": "Minutos"
        })
        st.dataframe(top_steals, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Líderes bajo los Tres Palos (Atajadas)")
    top_saves = df_players[df_players["saves_total"] > 0].sort_values(by="saves_total", ascending=False).head(10)[
        ["player_name", "team_name", "age", "saves_total", "minutes_played", "passes_correct", "pass_accuracy_pct"]
    ].rename(columns={
        "player_name": "Arquero",
        "team_name": "Club",
        "age": "Edad",
        "saves_total": "Atajadas",
        "minutes_played": "Minutos",
        "passes_correct": "Pases Precisos",
        "pass_accuracy_pct": "% Pase"
    })
    st.dataframe(top_saves, use_container_width=True, hide_index=True)
