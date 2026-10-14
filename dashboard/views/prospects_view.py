"""
dashboard/views/prospects_view.py
=================================
Pestaña 5: Prospectos Jóvenes (Sub-23).
Seguimiento a talentos emergentes con regularidad en Primera División.
"""

import streamlit as st
import pandas as pd


def render_prospects_view(df_players: pd.DataFrame):
    st.subheader("Panel de Detección de Prospectos Jóvenes (Sub-23)")
    st.caption("Futbolistas de 23 años o menos con rodaje formal en la máxima categoría del fútbol argentino.")

    u23_pool = df_players[(df_players["age"] <= 23) & (df_players["minutes_played"] >= 200)].copy()

    if u23_pool.empty:
        st.info("No hay futbolistas Sub-23 con los filtros mínimos aplicados.")
        return

    st.markdown(f"Se identificaron **{len(u23_pool)} jóvenes promesas** con más de 200 minutos disputados en el torneo actual.")

    st.markdown("#### Top 10 Prospectos por Regularidad en Primera División")
    u23_top = u23_pool.sort_values(by="minutes_played", ascending=False).head(10)[
        ["player_name", "team_name", "position", "age", "minutes_played", "goals", "assists", "passes_correct", "pass_accuracy_pct", "steals"]
    ].rename(columns={
        "player_name": "Futbolista",
        "team_name": "Club",
        "position": "Posición",
        "age": "Edad",
        "minutes_played": "Minutos",
        "goals": "Goles",
        "assists": "Asist.",
        "passes_correct": "Pases",
        "pass_accuracy_pct": "% Pase",
        "steals": "Recuperac."
    })
    st.dataframe(u23_top, use_container_width=True, hide_index=True)

    st.markdown("""
    > **Nota metodológica de prospección:**  
    > En esta primera etapa del proyecto, el análisis se sustenta en la muestra oficial del torneo en curso. 
    > La acumulación sistemática e inmutable de temporadas en la base de datos sentará las bases empíricas 
    > para futuros modelos predictivos y proyecciones longitudinales de rendimiento.
    """)
