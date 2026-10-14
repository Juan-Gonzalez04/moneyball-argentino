"""
dashboard/views/explorer_view.py
================================
Pestaña 6: Explorador Global de Datos.
Tabla consolidada con exportación a formato CSV para analistas.
"""

import streamlit as st
import pandas as pd


def render_explorer_view(filtered_df: pd.DataFrame):
    st.subheader("Matriz Analítica Consolidada")
    st.caption("Visualización tabular integral de todos los futbolistas bajo los filtros aplicados en la barra lateral.")

    cols_view = [
        "player_name", "team_name", "position", "age", "minutes_played",
        "goals", "penalty_goals", "assists", "shots_on_target",
        "passes_correct", "pass_accuracy_pct", "steals", "saves_total", "yellow_cards"
    ]
    renamed_view = filtered_df[cols_view].rename(columns={
        "player_name": "Futbolista",
        "team_name": "Club",
        "position": "Posición",
        "age": "Edad",
        "minutes_played": "Minutos",
        "goals": "Goles",
        "penalty_goals": "Penales",
        "assists": "Asistencias",
        "shots_on_target": "Tiros al Arco",
        "passes_correct": "Pases Precisos",
        "pass_accuracy_pct": "% Prec. Pase",
        "steals": "Recuperaciones",
        "saves_total": "Atajadas",
        "yellow_cards": "Tarjetas Amarillas"
    })

    st.dataframe(renamed_view, use_container_width=True, hide_index=True)

    csv_data = renamed_view.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Descargar datos en formato CSV",
        data=csv_data,
        file_name="moneyball_argentino_scouting.csv",
        mime="text/csv"
    )
