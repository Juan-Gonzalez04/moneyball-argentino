"""
dashboard/components/charts.py
==============================
Constructores reutilizables de visualizaciones en Altair.
"""

import pandas as pd
import altair as alt


def build_single_dumbbell(
    metric_label: str,
    player_name: str,
    player_val: float,
    pos_name: str,
    avg_val: float,
    is_pct: bool = False,
    height: int = 80
) -> alt.Chart:
    """
    Construye un Dumbbell Plot individual aislado para una única métrica.
    Cada gráfico posee su propio eje horizontal adaptado al rango natural del indicador.
    """
    min_v = min(player_val, avg_val)
    max_v = max(player_val, avg_val)
    
    # Padding lateral para evitar que los círculos se recorten en los bordes
    if is_pct:
        domain = [0.0, 100.0]
    else:
        diff = max_v - min_v
        pad = diff * 0.25 if diff > 0 else (1.0 if max_v == 0 else max_v * 0.2)
        domain = [max(0.0, min_v - pad), max_v + pad]

    df_metric = pd.DataFrame([{
        "métrica": metric_label,
        "min_v": min_v,
        "max_v": max_v,
        "player_val": player_val,
        "avg_val": avg_val
    }])

    rule = alt.Chart(df_metric).mark_rule(
        color="#cbd5e1",
        strokeWidth=4
    ).encode(
        y=alt.Y("métrica:N", title=None, axis=None),
        x=alt.X(
            "min_v:Q",
            scale=alt.Scale(domain=domain),
            title=f"{metric_label} {'(%)' if is_pct else ''}"
        ),
        x2="max_v:Q"
    )

    p_dot = alt.Chart(df_metric).mark_circle(
        size=220,
        color="#1e40af"  # Azul profundo
    ).encode(
        y=alt.Y("métrica:N"),
        x=alt.X("player_val:Q"),
        tooltip=[
            alt.Tooltip("métrica:N", title="Métrica"),
            alt.Tooltip("player_val:Q", title=f"{player_name} (Futbolista)", format=".1f" if is_pct or not isinstance(player_val, int) else "d"),
            alt.Tooltip("avg_val:Q", title=f"Media {pos_name}s", format=".1f")
        ]
    )

    m_dot = alt.Chart(df_metric).mark_circle(
        size=220,
        color="#94a3b8"  # Gris neutral
    ).encode(
        y=alt.Y("métrica:N"),
        x=alt.X("avg_val:Q"),
        tooltip=[
            alt.Tooltip("métrica:N", title="Métrica"),
            alt.Tooltip("avg_val:Q", title=f"Media {pos_name}s", format=".1f"),
            alt.Tooltip("player_val:Q", title=f"{player_name} (Futbolista)", format=".1f" if is_pct or not isinstance(player_val, int) else "d")
        ]
    )

    return (rule + m_dot + p_dot).properties(height=height)


def build_quadrant_scatter(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    x_title: str,
    y_title: str,
    tooltip_cols: list[alt.Tooltip],
    height: int = 450
) -> tuple[alt.Chart, float, float]:
    """Construye un gráfico de dispersión interactivo con cuadrantes divididos por medias."""
    x_mean = df[x_col].mean()
    y_mean = df[y_col].mean()

    base_scatter = alt.Chart(df).mark_circle(size=70, opacity=0.8).encode(
        x=alt.X(f"{x_col}:Q", title=x_title),
        y=alt.Y(f"{y_col}:Q", title=y_title),
        color=alt.Color("position:N", title="Posición"),
        tooltip=tooltip_cols
    ).properties(height=height).interactive()

    rule_x = alt.Chart(pd.DataFrame({"x": [x_mean]})).mark_rule(
        strokeDash=[4, 4],
        color="gray"
    ).encode(x="x:Q")

    rule_y = alt.Chart(pd.DataFrame({"y": [y_mean]})).mark_rule(
        strokeDash=[4, 4],
        color="gray"
    ).encode(y="y:Q")

    return (base_scatter + rule_x + rule_y), x_mean, y_mean
