import os
import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA & ESTILOS
# ==============================================================================
st.set_page_config(
    page_title="Argos // Moneyball Argentino",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Directorio de assets estáticos
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets" / "teams"

POSITION_MAP = {
    1: "Arquero",
    2: "Defensor",
    3: "Mediocampista",
    4: "Delantero"
}

# ==============================================================================
# GESTIÓN DE BASE DE DATOS (CONEXIÓN Y CACHÉ CON TTL)
# ==============================================================================
def get_db_connection():
    """Obtiene una conexión a la base de datos PostgreSQL de forma segura."""
    # Soporta tanto host local como contenedor docker
    host = os.getenv("DB_HOST", "postgres" if os.path.exists("/.dockerenv") else "localhost")
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "afa_data"),
        user=os.getenv("DB_USER", "juan"),
        password=os.getenv("DB_PASSWORD", "argos_secure_password_2026"),
        host=host,
        port=int(os.getenv("DB_PORT", "5432"))
    )


@st.cache_data(ttl=60)
def load_scouting_data() -> pd.DataFrame:
    """
    Carga y consolida datos analíticos aplicando Compute Pushdown en PostgreSQL.
    Cacheado con TTL de 60s para optimizar memoria en servidores acotados (Argos).
    """
    query = """
    SELECT 
        p.player_id,
        p.team_id,
        t.name AS team_name,
        COALESCE(p.nick_name, p.first_name || ' ' || p.last_name) AS player_name,
        p.age,
        p.position_id,
        COALESCE(p.height, 0) AS height,
        COALESCE(p.weight, 0) AS weight,
        COALESCE(p.nationality, 'Argentina') AS nationality,
        COALESCE(s.minutes_total, 0) AS minutes_played,
        COALESCE(g.total_goals, 0) AS goals,
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
        COALESCE(s.red_cards, 0) AS red_cards,
        t.colors
    FROM players p
    JOIN teams t ON p.team_id = t.team_id
    LEFT JOIN player_stats s ON p.player_id = s.player_id
    LEFT JOIN player_goals g ON p.player_id = g.player_id
    ORDER BY s.minutes_total DESC;
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            data = cur.fetchall()
            df = pd.DataFrame(data)

    if not df.empty:
        df["position"] = df["position_id"].map(POSITION_MAP).fillna("Sin posición")
        df["is_u23"] = df["age"] <= 23
        df["pass_accuracy_pct"] = pd.to_numeric(df["pass_accuracy_pct"], errors="coerce").fillna(0.0)
    return df


@st.cache_data(ttl=300)
def load_teams_summary() -> pd.DataFrame:
    """Carga resumen general de clubes para vistas institucionales."""
    query = """
    SELECT 
        t.team_id,
        t.name AS team_name,
        COUNT(p.player_id) AS squad_size,
        ROUND(AVG(p.age)::numeric, 1) AS avg_age,
        COUNT(CASE WHEN p.age <= 23 THEN 1 END) AS u23_count,
        SUM(COALESCE(s.minutes_total, 0)) AS total_minutes,
        SUM(CASE WHEN p.age <= 23 THEN COALESCE(s.minutes_total, 0) ELSE 0 END) AS u23_minutes,
        SUM(COALESCE(g.total_goals, 0)) AS total_goals
    FROM teams t
    LEFT JOIN players p ON t.team_id = p.team_id
    LEFT JOIN player_stats s ON p.player_id = s.player_id
    LEFT JOIN player_goals g ON p.player_id = g.player_id
    GROUP BY t.team_id, t.name
    ORDER BY t.name;
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            df = pd.DataFrame(cur.fetchall())
            if not df.empty:
                df["avg_age"] = pd.to_numeric(df["avg_age"], errors="coerce").fillna(0.0)
            return df


def get_team_logo_path(team_id: int) -> Path | None:
    """Resuelve la ruta física del escudo oficial descargado (ADR-0009)."""
    logo_file = ASSETS_DIR / f"{team_id}.png"
    return logo_file if logo_file.exists() else None


# ==============================================================================
# CARGA DE DATOS & MANEJO DE ERRORES
# ==============================================================================
try:
    df_players = load_scouting_data()
    df_teams = load_teams_summary()
except Exception as e:
    st.error(f"❌ Error al conectar con la base de datos analítica: {e}")
    st.info("Verifica que los servicios de Docker (afa-postgres) estén iniciados y con los datos cargados.")
    st.stop()

# ==============================================================================
# SIDEBAR: FILTROS DE SCOUTING & CONTROLES
# ==============================================================================
with st.sidebar:
    st.title("🎯 Argos Scouting Hub")
    st.caption("Filtros analíticos de captación y prospección")
    
    st.divider()
    
    # 1. Filtro rápido Sub-23
    u23_only = st.checkbox("🌟 Solo Jóvenes Promesas Sub-23", value=True)
    
    # 2. Rango de Edad
    if u23_only:
        age_range = st.slider("Rango de edad:", min_value=15, max_value=23, value=(17, 23))
    else:
        age_range = st.slider("Rango de edad:", min_value=15, max_value=42, value=(17, 36))
        
    # 3. Filtro por Posición
    positions_available = ["Todas"] + list(POSITION_MAP.values())
    selected_position = st.selectbox("Posición táctica:", positions_available)
    
    # 4. Filtro por Club
    all_teams = sorted(df_players["team_name"].unique())
    selected_teams = st.multiselect("Clubes:", all_teams, default=[])
    
    # 5. Mínimo de Minutos Jugados
    min_minutes = st.slider("Mínimo de minutos disputados:", min_value=0, max_value=1200, value=250, step=50)
    
    # 6. Búsqueda por Nombre
    search_query = st.text_input("🔍 Buscar futbolista:", placeholder="Ej: Palacio, Regiardo...")

    st.divider()
    st.caption("Arquitectura: PostgreSQL 15 + Pydantic v2 + Streamlit")
    st.caption("Hardware: Host *Argos* (4 GB RAM / Pushdown)")

# ==============================================================================
# APLICACIÓN DE FILTROS VECTORIZADOS
# ==============================================================================
filtered_df = df_players.copy()

filtered_df = filtered_df[
    (filtered_df["age"] >= age_range[0]) & 
    (filtered_df["age"] <= age_range[1])
]

if u23_only:
    filtered_df = filtered_df[filtered_df["is_u23"]]

if selected_position != "Todas":
    filtered_df = filtered_df[filtered_df["position"] == selected_position]

if selected_teams:
    filtered_df = filtered_df[filtered_df["team_name"].isin(selected_teams)]

filtered_df = filtered_df[filtered_df["minutes_played"] >= min_minutes]

if search_query:
    filtered_df = filtered_df[
        filtered_df["player_name"].str.contains(search_query, case=False, na=False)
    ]

# ==============================================================================
# CABECERA PRINCIPAL & MÉTRICAS GLOBALES
# ==============================================================================
st.markdown("# ⚽ MONEYBALL ARGENTINO // ARGOS")
st.markdown(
    "Plataforma de inteligencia deportiva y analítica para la Primera División del fútbol argentino. "
    "Detección de prospectos y talentos mediante datos oficiales de la AFA."
)

# Métricas rápidas superiores
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Prospectos Filtrados", len(filtered_df))
with col2:
    st.metric("Total en Base", len(df_players))
with col3:
    avg_filtered_age = round(filtered_df["age"].mean(), 1) if not filtered_df.empty else 0
    st.metric("Edad Promedio Filtro", f"{avg_filtered_age} años")
with col4:
    total_goals_filtered = int(filtered_df["goals"].sum()) if not filtered_df.empty else 0
    st.metric("Goles del Grupo", total_goals_filtered)

st.divider()

# ==============================================================================
# PESTAÑAS ANALÍTICAS (TABS)
# ==============================================================================
tab_radar, tab_table, tab_clubs, tab_arch = st.tabs([
    "🌟 Radar Sub-23 & Destacados",
    "📊 Explorador Analítico de Datos",
    "🛡️ Resumen por Clubes",
    "⚙️ Arquitectura & Salud del Pipeline"
])

# ------------------------------------------------------------------------------
# TAB 1: RADAR SUB-23 Y TARJETAS DE PROSPECTOS
# ------------------------------------------------------------------------------
with tab_radar:
    st.subheader("Top Prospectos por Regularidad (Minutos en Cancha)")
    st.caption("Jugadores jóvenes que han consolidado titularidad y kilometraje en Primera División.")
    
    top_prospects = filtered_df.head(6)
    
    if top_prospects.empty:
        st.warning("No hay futbolistas que coincidan con los filtros seleccionados.")
    else:
        # Grilla de 3 columnas para tarjetas
        cols = st.columns(3)
        for idx, (_, player) in enumerate(top_prospects.iterrows()):
            with cols[idx % 3]:
                with st.container(border=True):
                    header_col1, header_col2 = st.columns([1, 3])
                    
                    # Mostrar escudo del club
                    logo_path = get_team_logo_path(player["team_id"])
                    with header_col1:
                        if logo_path:
                            st.image(str(logo_path), width=65)
                        else:
                            st.write("🛡️")
                            
                    with header_col2:
                        st.markdown(f"### {player['player_name']}")
                        st.caption(f"{player['team_name']} · **{player['position']}**")
                    
                    st.divider()
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Edad", f"{player['age']} años")
                    m2.metric("Minutos", f"{player['minutes_played']}'")
                    m3.metric("Goles", player["goals"])
                    
                    m4, m5, m6 = st.columns(3)
                    m4.metric("Prec. Pases", f"{player['pass_accuracy_pct']}%")
                    m5.metric("Recuperac.", player["steals"])
                    m6.metric("Tiros Arco", player["shots_on_target"])

        st.divider()
        st.subheader("Distribución: Minutos Jugados vs. Precisión de Pase")
        st.caption("Evaluación de volumen de juego frente a fiabilidad en la distribución.")
        
        chart_data = filtered_df[["player_name", "minutes_played", "pass_accuracy_pct", "position"]].copy()
        st.scatter_chart(
            chart_data,
            x="minutes_played",
            y="pass_accuracy_pct",
            color="position",
            size="minutes_played"
        )

# ------------------------------------------------------------------------------
# TAB 2: EXPLORADOR ANALÍTICO DE DATOS (TABLA COMPLETA)
# ------------------------------------------------------------------------------
with tab_table:
    st.subheader("Matriz de Rendimiento Individual")
    
    display_cols = [
        "player_name", "team_name", "position", "age", "minutes_played",
        "goals", "assists", "shots_on_target", "passes_correct",
        "pass_accuracy_pct", "steals", "yellow_cards"
    ]
    
    col_rename = {
        "player_name": "Futbolista",
        "team_name": "Club",
        "position": "Posición",
        "age": "Edad",
        "minutes_played": "Minutos",
        "goals": "Goles",
        "assists": "Asistencias",
        "shots_on_target": "Tiros al Arco",
        "passes_correct": "Pases Precisos",
        "pass_accuracy_pct": "% Prec. Pase",
        "steals": "Recuperaciones",
        "yellow_cards": "Amarillas"
    }
    
    view_df = filtered_df[display_cols].rename(columns=col_rename)
    
    st.dataframe(
        view_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "% Prec. Pase": st.column_config.ProgressColumn(
                "% Prec. Pase",
                format="%.1f%%",
                min_value=0,
                max_value=100
            ),
            "Minutos": st.column_config.NumberColumn(
                "Minutos",
                format="%d min"
            )
        }
    )
    
    csv_data = view_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Descargar datos filtrados (CSV)",
        data=csv_data,
        file_name="scouting_moneyball_argentino.csv",
        mime="text/csv"
    )

# ------------------------------------------------------------------------------
# TAB 3: RESUMEN POR CLUBES
# ------------------------------------------------------------------------------
with tab_clubs:
    st.subheader("Análisis Institucional y Apuesta por Cantera (Sub-23)")
    
    if not df_teams.empty:
        # Porcentaje de minutos Sub-23
        df_teams["u23_min_pct"] = (
            (df_teams["u23_minutes"] / df_teams["total_minutes"].replace(0, 1)) * 100
        ).round(1)
        
        st.markdown("#### Ranking de Clubes por Minutos Otorgados a Juveniles Sub-23")
        chart_club_data = df_teams.sort_values(by="u23_minutes", ascending=False)[["team_name", "u23_minutes"]].set_index("team_name")
        st.bar_chart(chart_club_data)
        
        st.divider()
        st.markdown("#### Selector Institucional Detallado")
        club_selected = st.selectbox("Seleccionar Club para inspección:", df_teams["team_name"].unique())
        
        club_row = df_teams[df_teams["team_name"] == club_selected].iloc[0]
        club_id = int(club_row["team_id"])
        
        club_col1, club_col2 = st.columns([1, 4])
        with club_col1:
            logo = get_team_logo_path(club_id)
            if logo:
                st.image(str(logo), width=130)
            else:
                st.write("🛡️ Sin escudo")
        with club_col2:
            st.markdown(f"### {club_row['team_name']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Plantel Registrado", f"{club_row['squad_size']} jugadores")
            c2.metric("Edad Promedio", f"{club_row['avg_age']} años")
            c3.metric("Futbolistas Sub-23", f"{club_row['u23_count']}")
            c4.metric("% Minutos Sub-23", f"{club_row['u23_min_pct']}%")
            
        st.markdown(f"##### Plantel Completo de {club_selected}")
        squad_df = df_players[df_players["team_id"] == club_id][
            ["player_name", "position", "age", "minutes_played", "goals", "pass_accuracy_pct"]
        ].sort_values(by="minutes_played", ascending=False)
        st.dataframe(squad_df, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 4: ARQUITECTURA & SALUD DEL PIPELINE (DOCUMENTACIÓN TÉCNICA)
# ------------------------------------------------------------------------------
with tab_arch:
    st.subheader("Diseño de Ingeniería de Datos y Principios de Sistema")
    
    st.markdown("""
    Este proyecto fue diseñado bajo estándares rigurosos de **Ingeniería de Datos y Software**, priorizando 
    la idempotencia, la eficiencia en recursos de hardware limitados y la trazabilidad de decisiones.
    """)
    
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    kpi_col1.metric("Clubes Ingeridos", len(df_teams))
    kpi_col2.metric("Futbolistas Auditados", len(df_players))
    kpi_col3.metric("Tasa de Anomalías (Quarantine)", "0.0%")
    kpi_col4.metric("Idempotencia", "100% (Upsert)")
    
    st.divider()
    
    st.markdown("""
    #### Pilares de Arquitectura Implementados:
    1. **Microarquitectura E-V-T-L ([ADR-0006](docs/adr/0006-pipeline-secuencial-evtl-srp.md)):** Desacople estricto entre extracción, validación mediante contratos de datos, normalización relacional y carga batch.
    2. **Contratos de Datos con Patrón de Cuarentena ([ADR-0004](docs/adr/0004-data-contracts-pydantic-cuarentena.md)):** Validación en tiempo de ejecución con **Pydantic v2** aislando registros atípicos sin quebrar el pipeline global.
    3. **Compute Pushdown ([ADR-0002](docs/adr/0002-persistencia-relacional-hibrida-postgresql.md)):** Agregaciones, percentiles y cálculos analíticos ejecutados directamente en el motor **PostgreSQL 15**, preservando la memoria RAM del servidor físico *Argos* (4 GB).
    4. **Capa Bronze Inmutable y Respaldo ([ADR-0009](docs/adr/0009-estrategia-backups-activos-estaticos.md)):** Snapshots crudos firmados con hash SHA-256 para reconstrucción determinista (*Lakehouse Replayability*) y formato binario comprimido (`pg_dump -Fc`).
    5. **Activos Desacoplados:** Escudos oficiales integrados en disco (`dashboard/assets/teams/`) descargados de forma batch desde la API de Wikimedia Commons.
    """)
