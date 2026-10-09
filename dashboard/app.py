import os
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import altair as alt

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA (ESTILO SOBRIO & EDITORIAL)
# ==============================================================================
st.set_page_config(
    page_title="Moneyball Argentino | Inteligencia y Analítica Deportiva",
    page_icon="https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Flag_of_Argentina.svg/32px-Flag_of_Argentina.svg.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets" / "teams"

POSITION_MAP = {
    1: "Arquero",
    2: "Defensor",
    3: "Mediocampista",
    4: "Delantero"
}

# ==============================================================================
# CARGA Y CACHÉ DE DATOS (POSTGRESQL + IN-MEMORY)
# ==============================================================================
def get_db_connection():
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
    """Carga y normaliza jugadores y clubes en una única consulta optimizada."""
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
        passes_correct=("passes_correct", "sum"),
        passes_incorrect=("passes_incorrect", "sum"),
        u23_count=("is_u23", "sum")
    ).reset_index()

    teams_summary["avg_age"] = teams_summary["avg_age"].round(1)
    tot_passes = teams_summary["passes_correct"] + teams_summary["passes_incorrect"]
    teams_summary["team_pass_accuracy"] = np.where(tot_passes > 0, (teams_summary["passes_correct"] / tot_passes * 100).round(1), 0.0)

    return df_players, teams_summary


def get_team_logo(team_id: int) -> Path | None:
    logo_path = ASSETS_DIR / f"{team_id}.png"
    return logo_path if logo_path.exists() else None


# ==============================================================================
# CARGA INICIAL
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
# ENCABEZADO
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
# PESTAÑAS PRINCIPALES
# ==============================================================================
tab_teams, tab_leaders, tab_player_profile, tab_scatter, tab_prospects, tab_explorer = st.tabs([
    "Equipos y Planteles",
    "Líderes de Rendimiento",
    "Ficha de Futbolista",
    "Dispersión y Análisis",
    "Prospectos Jóvenes",
    "Explorador de Datos"
])

# ------------------------------------------------------------------------------
# PESTAÑA 1: EQUIPOS Y PLANTELES (CON RESPECTO A LA MEDIA DE LA LIGA)
# ------------------------------------------------------------------------------
with tab_teams:
    st.subheader("Análisis Institucional y Ficha por Club")
    st.caption("Evaluación de la nómina y métricas colectivas en comparación con el promedio general de la Primera División.")

    selected_team_name = st.selectbox("Seleccionar Club para inspección detallada:", all_clubs)
    team_row = df_teams[df_teams["team_name"] == selected_team_name].iloc[0]
    team_id = int(team_row["team_id"])

    # Medias de la Liga
    league_avg_age = round(df_teams["avg_age"].mean(), 1)
    league_avg_goals = round(df_teams["total_goals"].mean(), 1)
    league_avg_shots = round(df_teams["total_shots_on_target"].mean(), 1)
    league_avg_steals = round(df_teams["total_steals"].mean(), 1)
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
            delta=f"{diff_age:+} vs media liga ({league_avg_age})",
            delta_color="inverse"
        )

        diff_goals = round(team_row["total_goals"] - league_avg_goals, 1)
        kpi2.metric(
            label="Goles Totales",
            value=f"{team_row['total_goals']}",
            delta=f"{diff_goals:+} vs media liga ({league_avg_goals})"
        )

        diff_shots = round(team_row["total_shots_on_target"] - league_avg_shots, 1)
        kpi3.metric(
            label="Tiros al Arco",
            value=f"{team_row['total_shots_on_target']}",
            delta=f"{diff_shots:+} vs media liga ({league_avg_shots})"
        )

        diff_acc = round(team_row["team_pass_accuracy"] - league_avg_pass_acc, 1)
        kpi4.metric(
            label="% Precisión Pase",
            value=f"{team_row['team_pass_accuracy']}%",
            delta=f"{diff_acc:+} vs media liga ({league_avg_pass_acc}%)"
        )

    st.divider()
    st.markdown(f"#### Plantel Completo: {selected_team_name}")
    team_players = df_players[df_players["team_id"] == team_id][
        ["player_name", "position", "age", "minutes_played", "goals", "assists", "shots_on_target", "passes_correct", "pass_accuracy_pct", "steals"]
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
        "steals": "Recuperaciones"
    })
    st.dataframe(team_players, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# PESTAÑA 2: LÍDERES DE RENDIMIENTO (RANKINGS DIRECTOS)
# ------------------------------------------------------------------------------
with tab_leaders:
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
        st.markdown("#### Mayor Kilometraje (Minutos en Cancha)")
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

# ------------------------------------------------------------------------------
# PESTAÑA 3: FICHA DE FUTBOLISTA (VS. MEDIA DE SU POSICIÓN)
# ------------------------------------------------------------------------------
with tab_player_profile:
    st.subheader("Perfil Individual y Comparativa Posicional")
    st.caption("Contraste de métricas de un futbolista frente a la media de todos los jugadores de su misma posición.")

    # Selección de futbolista
    player_options = df_players.sort_values("player_name")[["player_id", "player_name", "team_name"]].copy()
    player_options["label"] = player_options["player_name"] + " (" + player_options["team_name"] + ")"
    
    player_dict = dict(zip(player_options["label"], player_options["player_id"]))
    selected_player_label = st.selectbox("Buscar e inspeccionar futbolista:", list(player_dict.keys()))
    target_player_id = player_dict[selected_player_label]

    p = df_players[df_players["player_id"] == target_player_id].iloc[0]
    p_pos_id = p["position_id"]
    p_pos_name = p["position"]

    # Grupo de comparación: misma posición con muestra representativa
    pos_peers = df_players[(df_players["position_id"] == p_pos_id) & (df_players["minutes_played"] >= 150)]
    if pos_peers.empty:
        pos_peers = df_players[df_players["position_id"] == p_pos_id]

    # Medias posicionales
    pos_avg_min = round(pos_peers["minutes_played"].mean(), 1)
    pos_avg_goals = round(pos_peers["goals"].mean(), 1)
    pos_avg_shots = round(pos_peers["shots_on_target"].mean(), 1)
    pos_avg_steals = round(pos_peers["steals"].mean(), 1)
    pos_avg_passes = round(pos_peers["passes_correct"].mean(), 1)
    pos_avg_acc = round(pos_peers["pass_accuracy_pct"].mean(), 1)

    p_logo_col, p_header_col = st.columns([1, 4])
    with p_logo_col:
        p_logo = get_team_logo(int(p["team_id"]))
        if p_logo:
            st.image(str(p_logo), width=110)
    with p_header_col:
        st.markdown(f"### {p['player_name']}")
        st.write(f"Club: **{p['team_name']}** | Posición: **{p_pos_name}** | Edad: **{p['age']} años** | Nacionalidad: **{p['nationality']}**")
        st.write(f"Altura: **{p['height'] if p['height'] > 0 else 'N/D'} cm** | Peso: **{p['weight'] if p['weight'] > 0 else 'N/D'} kg**")

    st.markdown(f"##### Métricas del Futbolista vs. Media de {p_pos_name}s (Muestra: {len(pos_peers)} futbolistas)")

    pkpi1, pkpi2, pkpi3, pkpi4, pkpi5 = st.columns(5)
    pkpi1.metric(
        "Minutos Disputados",
        f"{p['minutes_played']}",
        delta=f"{round(p['minutes_played'] - pos_avg_min, 1):+} vs media ({pos_avg_min})"
    )
    pkpi2.metric(
        "Goles",
        f"{p['goals']}",
        delta=f"{round(p['goals'] - pos_avg_goals, 1):+} vs media ({pos_avg_goals})"
    )
    pkpi3.metric(
        "Tiros al Arco",
        f"{p['shots_on_target']}",
        delta=f"{round(p['shots_on_target'] - pos_avg_shots, 1):+} vs media ({pos_avg_shots})"
    )
    pkpi4.metric(
        "Recuperaciones",
        f"{p['steals']}",
        delta=f"{round(p['steals'] - pos_avg_steals, 1):+} vs media ({pos_avg_steals})"
    )
    pkpi5.metric(
        "% Precisión Pase",
        f"{p['pass_accuracy_pct']}%",
        delta=f"{round(p['pass_accuracy_pct'] - pos_avg_acc, 1):+} vs media ({pos_avg_acc}%)"
    )

    st.divider()
    st.markdown("##### Comparativa Visual de Rendimiento")

    comp_data = pd.DataFrame([
        {"Métrica": "Goles", "Jugador": float(p["goals"]), "Media Posición": pos_avg_goals},
        {"Métrica": "Tiros al Arco", "Jugador": float(p["shots_on_target"]), "Media Posición": pos_avg_shots},
        {"Métrica": "Recuperaciones", "Jugador": float(p["steals"]), "Media Posición": pos_avg_steals},
        {"Métrica": "Pases Precisos (/10)", "Jugador": round(float(p["passes_correct"]) / 10, 1), "Media Posición": round(pos_avg_passes / 10, 1)},
    ])

    comp_melted = comp_data.melt(id_vars=["Métrica"], value_vars=["Jugador", "Media Posición"], var_name="Referencia", value_name="Valor")

    bar_comp = alt.Chart(comp_melted).mark_bar().encode(
        x=alt.X("Métrica:N", title="Métrica Analizada", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Valor:Q", title="Valor Absoluto"),
        color=alt.Color("Referencia:N", scale=alt.Scale(domain=["Jugador", "Media Posición"], range=["#1f77b4", "#aec7e8"])),
        xOffset="Referencia:N",
        tooltip=["Métrica", "Referencia", "Valor"]
    ).properties(height=320)

    st.altair_chart(bar_comp, use_container_width=True)

# ------------------------------------------------------------------------------
# PESTAÑA 4: DISPERSIÓN Y ANÁLISIS TÁCTICO (CON INTERPRETACIÓN DE CUADRANTES)
# ------------------------------------------------------------------------------
with tab_scatter:
    st.subheader("Mapas de Dispersión y Relaciones Técnicas")
    st.caption("Visualización interactiva con tooltips. Pasa el cursor por cualquier punto para ver nombre, club y métricas exactas.")

    scatter_base = filtered_df.copy()

    # Gráfico 1: Minutos vs Precisión de Pase
    st.markdown("#### 1. Regularidad de Participación vs. Seguridad en la Posesión")
    
    x_mean_1 = scatter_base["minutes_played"].mean()
    y_mean_1 = scatter_base["pass_accuracy_pct"].mean()

    c1 = alt.Chart(scatter_base).mark_circle(size=70, opacity=0.8).encode(
        x=alt.X("minutes_played:Q", title="Minutos Disputados (Volumen de Presencia)"),
        y=alt.Y("pass_accuracy_pct:Q", title="Precisión de Pase (%) (Seguridad Técnica)"),
        color=alt.Color("position:N", title="Posición"),
        tooltip=[
            alt.Tooltip("player_name:N", title="Futbolista"),
            alt.Tooltip("team_name:N", title="Club"),
            alt.Tooltip("position:N", title="Posición"),
            alt.Tooltip("age:Q", title="Edad"),
            alt.Tooltip("minutes_played:Q", title="Minutos"),
            alt.Tooltip("pass_accuracy_pct:Q", title="% Prec. Pase")
        ]
    ).properties(height=450).interactive()

    rule_x1 = alt.Chart(pd.DataFrame({"x": [x_mean_1]})).mark_rule(strokeDash=[4, 4], color="gray").encode(x="x:Q")
    rule_y1 = alt.Chart(pd.DataFrame({"y": [y_mean_1]})).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")

    st.altair_chart(c1 + rule_x1 + rule_y1, use_container_width=True)

    with st.expander("Interpretación del Gráfico y Cuadrantes Tácticos", expanded=True):
        st.markdown(f"""
        * **Eje X (Horizontal):** Minutos disputados (Línea punteada: Media = **{round(x_mean_1, 1)} min**). Mide la consolidación del futbolista en cancha.
        * **Eje Y (Vertical):** Porcentaje de precisión en pases (Línea punteada: Media = **{round(y_mean_1, 1)}%**). Mide la efectividad técnica en distribución.
        * **Cuadrante Superior Derecho:** **Titulares de alta fiabilidad.** Futbolistas consolidados en el once titular que conservan la posesión con alta efectividad.
        * **Cuadrante Superior Izquierdo:** **Efectividad en roles dosificados.** Suplentes o revulsivos con pocos minutos pero alta prolijidad al ingresar.
        * **Cuadrante Inferior Derecho:** **Alto volumen bajo presión o juego directo.** Titulares con menor tasa de pase (frecuente en delanteros, extremos o defensores que juegan en largo).
        * **Cuadrante Inferior Izquierdo:** **Baja participación y menor acierto.** Jugadores con poco rodaje y registros de precisión por debajo de la media.
        """)

    st.divider()

    # Gráfico 2: Tiros al Arco vs Goles
    st.markdown("#### 2. Generación Ofensiva vs. Capacidad Goleadora")

    offensive_df = scatter_base[scatter_base["shots_total"] > 0].copy()
    if not offensive_df.empty:
        x_mean_2 = offensive_df["shots_on_target"].mean()
        y_mean_2 = offensive_df["goals"].mean()

        c2 = alt.Chart(offensive_df).mark_circle(size=80, opacity=0.85).encode(
            x=alt.X("shots_on_target:Q", title="Tiros al Arco (Generación de Peligro)"),
            y=alt.Y("goals:Q", title="Goles Convertidos (Efectividad Real)"),
            color=alt.Color("position:N", title="Posición"),
            tooltip=[
                alt.Tooltip("player_name:N", title="Futbolista"),
                alt.Tooltip("team_name:N", title="Club"),
                alt.Tooltip("position:N", title="Posición"),
                alt.Tooltip("goals:Q", title="Goles"),
                alt.Tooltip("shots_on_target:Q", title="Tiros al Arco"),
                alt.Tooltip("shots_total:Q", title="Tiros Totales")
            ]
        ).properties(height=450).interactive()

        rule_x2 = alt.Chart(pd.DataFrame({"x": [x_mean_2]})).mark_rule(strokeDash=[4, 4], color="gray").encode(x="x:Q")
        rule_y2 = alt.Chart(pd.DataFrame({"y": [y_mean_2]})).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")

        st.altair_chart(c2 + rule_x2 + rule_y2, use_container_width=True)

        with st.expander("Interpretación del Gráfico y Cuadrantes Tácticos", expanded=True):
            st.markdown(f"""
            * **Eje X:** Tiros dirigidos a los tres palos (Media: **{round(x_mean_2, 1)}**). Evalúa la capacidad individual para encontrar el arco rival.
            * **Eje Y:** Goles anotados en el torneo (Media: **{round(y_mean_2, 1)}**).
            * **Cuadrante Superior Derecho:** **Goleadores de élite.** Altos rematadores con alta tasa de conversión a red.
            * **Cuadrante Superior Izquierdo:** **Máxima contundencia.** Futbolistas que convierten con un volumen mínimo de tiros entre palos.
            * **Cuadrante Inferior Derecho:** **Volumen sin finalización.** Jugadores que generan muchos remates a puerta pero registran sequía o gran porcentaje de atajadas rivales.
            """)

# ------------------------------------------------------------------------------
# PESTAÑA 5: PROSPECTOS JÓVENES (SUB-23)
# ------------------------------------------------------------------------------
with tab_prospects:
    st.subheader("Panel de Detección de Prospectos Jóvenes (Sub-23)")
    st.caption("Futbolistas de 23 años o menos con rodaje formal en la máxima categoría del fútbol argentino.")

    u23_pool = df_players[(df_players["age"] <= 23) & (df_players["minutes_played"] >= 200)].copy()

    if u23_pool.empty:
        st.info("No hay futbolistas Sub-23 con los filtros mínimos aplicados.")
    else:
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

# ------------------------------------------------------------------------------
# PESTAÑA 6: EXPLORADOR GLOBAL DE DATOS
# ------------------------------------------------------------------------------
with tab_explorer:
    st.subheader("Matriz Analítica Consolidada")
    st.caption("Visualización tabular integral de todos los futbolistas bajo los filtros aplicados en la barra lateral.")

    cols_view = [
        "player_name", "team_name", "position", "age", "minutes_played",
        "goals", "penalty_goals", "assists", "shots_on_target",
        "passes_correct", "pass_accuracy_pct", "steals", "yellow_cards"
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

# ==============================================================================
# PIE DE PÁGINA (SOBRIO & PROFESIONAL)
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
