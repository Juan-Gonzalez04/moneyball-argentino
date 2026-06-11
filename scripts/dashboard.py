import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Configurar página
st.set_page_config(page_title="AFA Scouting Dashboard", layout="wide")

# Título
st.title("⚽ AFA Scouting Dashboard")

try:
    # Crear conexión nueva cada vez (sin cache)
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "afa_data"),
        user=os.getenv("DB_USER", "juan"),
        password=os.getenv("DB_PASSWORD"),
        host="postgres",
        port=5432
    )
    
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Mostrar cantidad de jugadores
    cur.execute("SELECT COUNT(*) as total FROM players")
    result = cur.fetchone()
    st.metric("Total de Jugadores", result['total'] if result else 0)

    # Mostrar tabla de jugadores
    st.subheader("Jugadores")
    cur.execute("SELECT * FROM players LIMIT 10")
    df = pd.DataFrame(cur.fetchall())
    st.dataframe(df)

    cur.close()
    conn.close()

except Exception as e:
    st.error(f"Error: {e}")
