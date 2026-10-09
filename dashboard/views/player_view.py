"""
dashboard/views/player_view.py
==============================
Pestaña 3: Ficha de Futbolista.
Inspección individual contrastada contra la media de su posición específica,
con rankings directos por métrica y Dumbbell Plots individuales por dimensión técnica.
"""

import streamlit as st
import pandas as pd
from dashboard.data import get_team_logo
from dashboard.components.charts import build_single_dumbbell


def compute_peer_rank(peers_df: pd.DataFrame, col: str, val: float, ascending: bool = False) -> int:
    """Calcula el puesto relativo del jugador en una métrica frente a sus pares posicionales."""
    if ascending:
        return int((peers_df[col] < val).sum()) + 1
    return int((peers_df[col] > val).sum()) + 1


def render_player_view(df_players: pd.DataFrame):
    st.subheader("Perfil Individual y Comparativa Posicional")
    st.caption("Contraste de métricas de un futbolista frente a la media de todos los jugadores de su misma posición.")

    # 1. Selector de futbolista
    player_options = df_players.sort_values("player_name")[["player_id", "player_name", "team_name"]].copy()
    player_options["label"] = player_options["player_name"] + " (" + player_options["team_name"] + ")"
    
    player_dict = dict(zip(player_options["label"], player_options["player_id"]))
    selected_player_label = st.selectbox("Buscar e inspeccionar futbolista:", list(player_dict.keys()))
    target_player_id = player_dict[selected_player_label]

    p = df_players[df_players["player_id"] == target_player_id].iloc[0]
    p_pos_id = int(p["position_id"])
    p_pos_name = p["position"]
    is_goalkeeper = (p_pos_id == 1)

    # 2. Grupo de comparación: misma posición con muestra mínima representativa (>= 150 min)
    pos_peers = df_players[(df_players["position_id"] == p_pos_id) & (df_players["minutes_played"] >= 150)]
    if pos_peers.empty or len(pos_peers) < 3:
        pos_peers = df_players[df_players["position_id"] == p_pos_id]
    
    peer_count = len(pos_peers)

    # 3. Cabecera del jugador
    p_logo_col, p_header_col = st.columns([1, 4])
    with p_logo_col:
        p_logo = get_team_logo(int(p["team_id"]))
        if p_logo:
            st.image(str(p_logo), width=110)
    with p_header_col:
        st.markdown(f"### {p['player_name']}")
        st.write(f"Club: **{p['team_name']}** | Posición: **{p_pos_name}** | Edad: **{p['age']} años** | Nacionalidad: **{p['nationality']}**")
        st.write(f"Altura: **{p['height'] if p['height'] > 0 else 'N/D'} cm** | Peso: **{p['weight'] if p['weight'] > 0 else 'N/D'} kg**")

    st.markdown(f"##### Métricas vs. Media de {p_pos_name}s (Muestra de referencia: {peer_count} {p_pos_name.lower()}s)")

    # 4. Métricas contextuales adaptadas al rol táctico (Arquero vs. Jugador de Campo)
    if is_goalkeeper:
        # ARQUEROS
        avg_min = round(pos_peers["minutes_played"].mean(), 1)
        avg_saves = round(pos_peers["saves_total"].mean(), 1)
        avg_passes = round(pos_peers["passes_correct"].mean(), 1)
        avg_acc = round(pos_peers["pass_accuracy_pct"].mean(), 1)
        avg_cards = round(pos_peers["yellow_cards"].mean(), 1)

        rank_saves = compute_peer_rank(pos_peers, "saves_total", p["saves_total"])
        rank_min = compute_peer_rank(pos_peers, "minutes_played", p["minutes_played"])
        rank_passes = compute_peer_rank(pos_peers, "passes_correct", p["passes_correct"])
        rank_acc = compute_peer_rank(pos_peers, "pass_accuracy_pct", p["pass_accuracy_pct"])

        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            "Atajadas Totales",
            f"{p['saves_total']}",
            delta=f"{round(p['saves_total'] - avg_saves, 1):+} vs media ({avg_saves}) | #{rank_saves}° en atajadas"
        )
        k2.metric(
            "Minutos Disputados",
            f"{p['minutes_played']}",
            delta=f"{round(p['minutes_played'] - avg_min, 1):+} vs media ({avg_min}) | #{rank_min}° en rodaje"
        )
        k3.metric(
            "Pases Precisos",
            f"{p['passes_correct']}",
            delta=f"{round(p['passes_correct'] - avg_passes, 1):+} vs media ({avg_passes}) | #{rank_passes}° en pases"
        )
        k4.metric(
            "% Precisión Pase",
            f"{p['pass_accuracy_pct']}%",
            delta=f"{round(p['pass_accuracy_pct'] - avg_acc, 1):+}% vs media ({avg_acc}%) | #{rank_acc}° en precisión"
        )

        st.divider()
        st.markdown("##### Comparativa Visual: Dumbbell Plots Individuales")
        st.caption("Punto Azul: **Valor del Arquero** | Punto Gris: **Media de Arqueros de Primera División**")

        c_g1, c_g2 = st.columns(2)
        with c_g1:
            st.markdown(f"**Atajadas Totales** (Puesto #{rank_saves}° de {peer_count})")
            chart_saves = build_single_dumbbell("Atajadas", p["player_name"], float(p["saves_total"]), p_pos_name, avg_saves)
            st.altair_chart(chart_saves, use_container_width=True)

            st.markdown(f"**Pases Precisos** (Puesto #{rank_passes}° de {peer_count})")
            chart_passes = build_single_dumbbell("Pases Precisos", p["player_name"], float(p["passes_correct"]), p_pos_name, avg_passes)
            st.altair_chart(chart_passes, use_container_width=True)

        with c_g2:
            st.markdown(f"**Minutos en Cancha** (Puesto #{rank_min}° de {peer_count})")
            chart_min = build_single_dumbbell("Minutos", p["player_name"], float(p["minutes_played"]), p_pos_name, avg_min)
            st.altair_chart(chart_min, use_container_width=True)

            st.markdown(f"**% Precisión de Pase** (Puesto #{rank_acc}° de {peer_count})")
            chart_acc = build_single_dumbbell("Precisión de Pase", p["player_name"], float(p["pass_accuracy_pct"]), p_pos_name, avg_acc, is_pct=True)
            st.altair_chart(chart_acc, use_container_width=True)

    else:
        # JUGADORES DE CAMPO (Defensores, Mediocampistas, Delanteros)
        avg_min = round(pos_peers["minutes_played"].mean(), 1)
        avg_goals = round(pos_peers["goals"].mean(), 1)
        avg_shots = round(pos_peers["shots_on_target"].mean(), 1)
        avg_assists = round(pos_peers["assists"].mean(), 1)
        avg_steals = round(pos_peers["steals"].mean(), 1)
        avg_passes = round(pos_peers["passes_correct"].mean(), 1)
        avg_acc = round(pos_peers["pass_accuracy_pct"].mean(), 1)

        rank_goals = compute_peer_rank(pos_peers, "goals", p["goals"])
        rank_shots = compute_peer_rank(pos_peers, "shots_on_target", p["shots_on_target"])
        rank_assists = compute_peer_rank(pos_peers, "assists", p["assists"])
        rank_steals = compute_peer_rank(pos_peers, "steals", p["steals"])
        rank_passes = compute_peer_rank(pos_peers, "passes_correct", p["passes_correct"])
        rank_acc = compute_peer_rank(pos_peers, "pass_accuracy_pct", p["pass_accuracy_pct"])
        rank_min = compute_peer_rank(pos_peers, "minutes_played", p["minutes_played"])

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric(
            "Minutos Disputados",
            f"{p['minutes_played']}",
            delta=f"{round(p['minutes_played'] - avg_min, 1):+} vs media ({avg_min}) | #{rank_min}° en rodaje"
        )
        k2.metric(
            "Goles",
            f"{p['goals']}",
            delta=f"{round(p['goals'] - avg_goals, 1):+} vs media ({avg_goals}) | #{rank_goals}° en goles"
        )
        k3.metric(
            "Tiros al Arco",
            f"{p['shots_on_target']}",
            delta=f"{round(p['shots_on_target'] - avg_shots, 1):+} vs media ({avg_shots}) | #{rank_shots}° en tiros"
        )
        k4.metric(
            "Recuperaciones",
            f"{p['steals']}",
            delta=f"{round(p['steals'] - avg_steals, 1):+} vs media ({avg_steals}) | #{rank_steals}° en quites"
        )
        k5.metric(
            "% Precisión Pase",
            f"{p['pass_accuracy_pct']}%",
            delta=f"{round(p['pass_accuracy_pct'] - avg_acc, 1):+}% vs media ({avg_acc}%) | #{rank_acc}° en precisión"
        )

        st.divider()
        st.markdown("##### Comparativa Visual: Dumbbell Plots Individuales")
        st.caption(f"Punto Azul: **Valor de {p['player_name']}** | Punto Gris: **Media de {p_pos_name}s de Primera División**")

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown(f"**Goles Convertidos** (Puesto #{rank_goals}° de {peer_count})")
            ch_goals = build_single_dumbbell("Goles", p["player_name"], float(p["goals"]), p_pos_name, avg_goals)
            st.altair_chart(ch_goals, use_container_width=True)

            st.markdown(f"**Tiros al Arco** (Puesto #{rank_shots}° de {peer_count})")
            ch_shots = build_single_dumbbell("Tiros al Arco", p["player_name"], float(p["shots_on_target"]), p_pos_name, avg_shots)
            st.altair_chart(ch_shots, use_container_width=True)

            st.markdown(f"**Asistencias** (Puesto #{rank_assists}° de {peer_count})")
            ch_ast = build_single_dumbbell("Asistencias", p["player_name"], float(p["assists"]), p_pos_name, avg_assists)
            st.altair_chart(ch_ast, use_container_width=True)

        with col_right:
            st.markdown(f"**Recuperaciones de Balón** (Puesto #{rank_steals}° de {peer_count})")
            ch_steals = build_single_dumbbell("Recuperaciones", p["player_name"], float(p["steals"]), p_pos_name, avg_steals)
            st.altair_chart(ch_steals, use_container_width=True)

            st.markdown(f"**Pases Precisos** (Puesto #{rank_passes}° de {peer_count})")
            ch_pass = build_single_dumbbell("Pases Precisos", p["player_name"], float(p["passes_correct"]), p_pos_name, avg_passes)
            st.altair_chart(ch_pass, use_container_width=True)

            st.markdown(f"**% Precisión de Pase** (Puesto #{rank_acc}° de {peer_count})")
            ch_acc = build_single_dumbbell("Precisión Pase", p["player_name"], float(p["pass_accuracy_pct"]), p_pos_name, avg_acc, is_pct=True)
            st.altair_chart(ch_acc, use_container_width=True)
