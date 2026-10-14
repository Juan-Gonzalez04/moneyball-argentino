"""
dashboard/views/scatter_view.py
===============================
Pestaña 4: Dispersión y Análisis Táctico.
Mapas interactivos en Altair con tooltips detallados y división interpretada de cuadrantes.
"""

import streamlit as st
import pandas as pd
import altair as alt
try:
    from dashboard.components.charts import build_quadrant_scatter
except ModuleNotFoundError:
    from components.charts import build_quadrant_scatter


def render_scatter_view(filtered_df: pd.DataFrame):
    st.subheader("Mapas de Dispersión y Relaciones Técnicas")
    st.caption("Visualización interactiva con tooltips. Pasa el cursor por cualquier punto para ver nombre, club y métricas exactas.")

    scatter_base = filtered_df.copy()

    # 1. Gráfico: Minutos vs Precisión de Pase
    st.markdown("#### 1. Regularidad de Participación vs. Seguridad en la Posesión")
    
    tooltips_1 = [
        alt.Tooltip("player_name:N", title="Futbolista"),
        alt.Tooltip("team_name:N", title="Club"),
        alt.Tooltip("position:N", title="Posición"),
        alt.Tooltip("age:Q", title="Edad"),
        alt.Tooltip("minutes_played:Q", title="Minutos"),
        alt.Tooltip("pass_accuracy_pct:Q", title="% Prec. Pase")
    ]

    chart_1, x_m1, y_m1 = build_quadrant_scatter(
        scatter_base,
        x_col="minutes_played",
        y_col="pass_accuracy_pct",
        x_title="Minutos Disputados (Volumen de Presencia)",
        y_title="Precisión de Pase (%) (Seguridad Técnica)",
        tooltip_cols=tooltips_1
    )

    st.altair_chart(chart_1, use_container_width=True)

    with st.expander("Interpretación del Gráfico y Cuadrantes Tácticos", expanded=True):
        st.markdown(f"""
        * **Eje X (Horizontal):** Minutos disputados (Línea punteada: Media = **{round(x_m1, 1)} min**). Mide la consolidación del futbolista en cancha.
        * **Eje Y (Vertical):** Porcentaje de precisión en pases (Línea punteada: Media = **{round(y_m1, 1)}%**). Mide la efectividad técnica en distribución.
        * **Cuadrante Superior Derecho:** **Titulares de alta fiabilidad.** Futbolistas consolidados en el once titular que conservan la posesión con alta efectividad.
        * **Cuadrante Superior Izquierdo:** **Efectividad en roles dosificados.** Suplentes o revulsivos con pocos minutos pero alta prolijidad al ingresar.
        * **Cuadrante Inferior Derecho:** **Alto volumen bajo presión o juego directo.** Titulares con menor tasa de pase (frecuente en delanteros, extremos o defensores que juegan en largo).
        * **Cuadrante Inferior Izquierdo:** **Baja participación y menor acierto.** Jugadores con poco rodaje y registros de precisión por debajo de la media.
        """)

    st.divider()

    # 2. Gráfico: Tiros al Arco vs Goles
    st.markdown("#### 2. Generación Ofensiva vs. Capacidad Goleadora")

    offensive_df = scatter_base[scatter_base["shots_total"] > 0].copy()
    if not offensive_df.empty:
        tooltips_2 = [
            alt.Tooltip("player_name:N", title="Futbolista"),
            alt.Tooltip("team_name:N", title="Club"),
            alt.Tooltip("position:N", title="Posición"),
            alt.Tooltip("goals:Q", title="Goles"),
            alt.Tooltip("shots_on_target:Q", title="Tiros al Arco"),
            alt.Tooltip("shots_total:Q", title="Tiros Totales")
        ]

        chart_2, x_m2, y_m2 = build_quadrant_scatter(
            offensive_df,
            x_col="shots_on_target",
            y_col="goals",
            x_title="Tiros al Arco (Generación de Peligro)",
            y_title="Goles Convertidos (Efectividad Real)",
            tooltip_cols=tooltips_2
        )

        st.altair_chart(chart_2, use_container_width=True)

        with st.expander("Interpretación del Gráfico y Cuadrantes Tácticos", expanded=True):
            st.markdown(f"""
            * **Eje X:** Tiros dirigidos a los tres palos (Media: **{round(x_m2, 1)}**). Evalúa la capacidad individual para encontrar el arco rival.
            * **Eje Y:** Goles anotados en el torneo (Media: **{round(y_m2, 1)}**).
            * **Cuadrante Superior Derecho:** **Goleadores de élite.** Altos rematadores con alta tasa de conversión a red.
            * **Cuadrante Superior Izquierdo:** **Máxima contundencia.** Futbolistas que convierten con un volumen mínimo de tiros entre palos.
            * **Cuadrante Inferior Derecho:** **Volumen sin finalización.** Jugadores que generan muchos remates a puerta pero registran sequía o gran porcentaje de atajadas rivales.
            """)
