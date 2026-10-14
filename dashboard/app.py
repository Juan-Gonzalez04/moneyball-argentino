"""
dashboard/app.py
================
Punto de entrada y orquestador modular del Dashboard de Moneyball Argentino.
Coordina la barra lateral de filtros, el encabezado y el enrutamiento a vistas modularizadas.
"""

import sys
from pathlib import Path

# Garantizar resolución de paquetes tanto en Docker como en ejecución local o desde subcarpetas
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DASHBOARD_DIR = Path(__file__).resolve().parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

import streamlit as st
import pandas as pd

try:
    from dashboard.data import load_all_data, POSITION_MAP
    from dashboard.views.teams_view import render_teams_view
    from dashboard.views.leaders_view import render_leaders_view
    from dashboard.views.player_view import render_player_view
    from dashboard.views.scatter_view import render_scatter_view
    from dashboard.views.prospects_view import render_prospects_view
    from dashboard.views.explorer_view import render_explorer_view
except ModuleNotFoundError:
    from data import load_all_data, POSITION_MAP
    from views.teams_view import render_teams_view
    from views.leaders_view import render_leaders_view
    from views.player_view import render_player_view
    from views.scatter_view import render_scatter_view
    from views.prospects_view import render_prospects_view
    from views.explorer_view import render_explorer_view

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA (ESTILO SOBRIO & EDITORIAL)
# ==============================================================================
st.set_page_config(
    page_title="Moneyball Argentino | Inteligencia y Analítica Deportiva",
    page_icon="https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Flag_of_Argentina.svg/32px-Flag_of_Argentina.svg.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# CARGA INICIAL DE DATOS
# ==============================================================================
try:
    df_players, df_teams = load_all_data()
except Exception as e:
    st.error(f"Error al conectar con el almacén analítico: {e}")
    st.info("Asegúrate de que la base de datos PostgreSQL esté en ejecución y poblada.")
    st.stop()

# ==============================================================================
# PANEL LATERAL: FILTROS DE CONSULTA
# ==============================================================================
with st.sidebar:
    st.title("Panel de Filtros")
    st.caption("Parámetros de consulta sobre la base activa")
    st.divider()

    # Filtro por Edad
    age_range = st.slider("Rango de Edad", min_value=16, max_value=42, value=(17, 38))

    # Filtro por Posición
    positions = ["Todas"] + list(POSITION_MAP.values())
    selected_pos = st.selectbox("Posición Táctica", positions)

    # Filtro por Club
    all_clubs = sorted(df_teams["team_name"].unique())
    selected_clubs = st.multiselect("Clubes Seleccionados", all_clubs, default=[])

    # Minutos mínimos
    min_mins = st.slider("Mínimo de Minutos Disputados", min_value=0, max_value=1100, value=200, step=50)

    # Búsqueda por nombre
    name_search = st.text_input("Búsqueda por Futbolista", placeholder="Apellido o nombre...")

    st.divider()
    st.caption("Primera División Argentina | Temporada Oficial")

# ==============================================================================
# FILTRADO VECTORIAL
# ==============================================================================
filtered_df = df_players.copy()
filtered_df = filtered_df[
    (filtered_df["age"] >= age_range[0]) & 
    (filtered_df["age"] <= age_range[1]) &
    (filtered_df["minutes_played"] >= min_mins)
]

if selected_pos != "Todas":
    filtered_df = filtered_df[filtered_df["position"] == selected_pos]

if selected_clubs:
    filtered_df = filtered_df[filtered_df["team_name"].isin(selected_clubs)]

if name_search:
    filtered_df = filtered_df[filtered_df["player_name"].str.contains(name_search, case=False, na=False)]

# ==============================================================================
# ENCABEZADO Y MÉTRICAS GENERALES
# ==============================================================================
st.title("MONEYBALL ARGENTINO")
st.markdown(
    "Plataforma de inteligencia de datos y analítica deportiva para la Primera División del fútbol argentino. "
    "Métricas de producción individual, perfiles institucionales y detección de patrones de rendimiento."
)

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Futbolistas Filtrados", len(filtered_df))
col_m2.metric("Total en Registro", len(df_players))
col_m3.metric("Edad Promedio Grupo", f"{round(filtered_df['age'].mean(), 1) if not filtered_df.empty else 0} años")
col_m4.metric("Goles del Grupo", int(filtered_df["goals"].sum()) if not filtered_df.empty else 0)

st.divider()

# ==============================================================================
# ENRUTAMIENTO DE PESTAÑAS (VISTAS MODULARES)
# ==============================================================================
tab_teams, tab_leaders, tab_player_profile, tab_scatter, tab_prospects, tab_explorer = st.tabs([
    "Equipos y Planteles",
    "Líderes de Rendimiento",
    "Ficha de Futbolista",
    "Dispersión y Análisis",
    "Prospectos Jóvenes",
    "Explorador de Datos"
])

with tab_teams:
    render_teams_view(df_players, df_teams)

with tab_leaders:
    render_leaders_view(df_players)

with tab_player_profile:
    render_player_view(df_players)

with tab_scatter:
    render_scatter_view(filtered_df)

with tab_prospects:
    render_prospects_view(df_players)

with tab_explorer:
    render_explorer_view(filtered_df)

# ==============================================================================
# PIE DE PÁGINA
# ==============================================================================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray; font-size: 0.85rem; padding: 10px 0;'>"
    "Moneyball Argentino &middot; Desarrollado por <b>Juan González</b> &middot; "
    "<a href='https://github.com/juan' target='_blank' style='color: gray; text-decoration: underline;'>"
    "Código fuente en GitHub</a>"
    "</div>",
    unsafe_allow_html=True
)
