"""
dashboard/views/teams_view.py
=============================
Pestaña 1: Equipos y Planteles.
Inspección institucional de cada club frente a las medias y rankings de Primera División.
"""

import streamlit as st
import pandas as pd
try:
    from dashboard.data import get_team_logo
except ModuleNotFoundError:
    from data import get_team_logo


def render_teams_view(df_players: pd.DataFrame, df_teams: pd.DataFrame):
    st.subheader("Análisis Institucional y Ficha por Club")
    st.caption("Evaluación de la nómina y métricas colectivas en comparación con el promedio general de la Primera División.")

    all_clubs = sorted(df_teams["team_name"].unique())
    selected_team_name = st.selectbox("Seleccionar Club para inspección detallada:", all_clubs)
    team_row = df_teams[df_teams["team_name"] == selected_team_name].iloc[0]
    team_id = int(team_row["team_id"])

    # Medias de la Liga
    league_avg_age = round(df_teams["avg_age"].mean(), 1)
    league_avg_goals = round(df_teams["total_goals"].mean(), 1)
    league_avg_shots = round(df_teams["total_shots_on_target"].mean(), 1)
    league_avg_pass_acc = round(df_teams["team_pass_accuracy"].mean(), 1)

    # Cabecera con Escudo y Métricas Comparativas
    c_logo, c_info = st.columns([1, 4])
    with c_logo:
        logo = get_team_logo(team_id)
        if logo:
            st.image(str(logo), width=140)
        else:
            st.write("[Escudo no disponible]")

    with c_info:
        st.markdown(f"### {team_row['team_name']}")
        st.write(f"Plantel registrado: **{team_row['squad_size']} futbolistas** | Minutos acumulados: **{team_row['total_minutes']}**")

        st.markdown("##### Métricas Colectivas vs. Promedio de la Liga")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        diff_age = round(team_row["avg_age"] - league_avg_age, 1)
        kpi1.metric(
            label="Edad Promedio",
            value=f"{team_row['avg_age']} años",
            delta=f"{diff_age:+} años vs media ({league_avg_age}) | #{int(team_row['rank_age'])}° más joven",
            delta_color="inverse"
        )

        diff_goals = round(team_row["total_goals"] - league_avg_goals, 1)
        kpi2.metric(
            label="Goles Totales",
            value=f"{team_row['total_goals']}",
            delta=f"{diff_goals:+} vs media ({league_avg_goals}) | Puesto #{int(team_row['rank_goals'])}°"
        )

        diff_shots = round(team_row["total_shots_on_target"] - league_avg_shots, 1)
        kpi3.metric(
            label="Tiros al Arco",
            value=f"{team_row['total_shots_on_target']}",
            delta=f"{diff_shots:+} vs media ({league_avg_shots}) | Puesto #{int(team_row['rank_shots'])}°"
        )

        diff_acc = round(team_row["team_pass_accuracy"] - league_avg_pass_acc, 1)
        kpi4.metric(
            label="% Precisión Pase",
            value=f"{team_row['team_pass_accuracy']}%",
            delta=f"{diff_acc:+}% vs media ({league_avg_pass_acc}%) | Puesto #{int(team_row['rank_pass_acc'])}°"
        )

    st.divider()
    st.markdown(f"#### Plantel Completo: {selected_team_name}")
    team_players = df_players[df_players["team_id"] == team_id][
        ["player_name", "position", "age", "minutes_played", "goals", "assists", "shots_on_target", "passes_correct", "pass_accuracy_pct", "steals", "saves_total"]
    ].sort_values(by="minutes_played", ascending=False).rename(columns={
        "player_name": "Futbolista",
        "position": "Posición",
        "age": "Edad",
        "minutes_played": "Minutos",
        "goals": "Goles",
        "assists": "Asistencias",
        "shots_on_target": "Tiros al Arco",
        "passes_correct": "Pases Precisos",
        "pass_accuracy_pct": "% Prec. Pase",
        "steals": "Recuperaciones",
        "saves_total": "Atajadas"
    })
    st.dataframe(team_players, use_container_width=True, hide_index=True)
