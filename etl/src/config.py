"""
Configuración centralizada del pipeline ETL MoneyBall Argentino / Argos.
Maneja rutas de almacenamiento, URLs de origen, credenciales de PostgreSQL
y parámetros de ejecución.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe en la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# --------------------------------------------------------------------------
# 1. Configuración de Almacenamiento y Directorios
# --------------------------------------------------------------------------
# Si se ejecuta dentro de un contenedor Docker, los volúmenes están en /data/raw.
# Si se ejecuta en el host local, se resuelve relativo a PROJECT_ROOT.
def _resolve_dir(env_var: str, docker_default: str, local_default: Path) -> Path:
    if os.getenv(env_var):
        target = Path(os.getenv(env_var))
    elif Path(docker_default).exists():
        target = Path(docker_default)
    else:
        target = local_default
    target.mkdir(parents=True, exist_ok=True)
    return target

RAW_DATA_DIR: Path = _resolve_dir("RAW_DATA_DIR", "/data/raw", PROJECT_ROOT / "data" / "raw")
PROCESSED_DATA_DIR: Path = _resolve_dir("PROCESSED_DATA_DIR", "/data/processed", PROJECT_ROOT / "data" / "processed")
LOGS_DIR: Path = _resolve_dir("LOGS_DIR", "/app/logs", PROJECT_ROOT / "logs")

# --------------------------------------------------------------------------
# 2. Configuración de Extracción HTTP (AFA API)
# --------------------------------------------------------------------------
AFA_PLAYERS_STATS_URL: str = os.getenv(
    "AFA_PLAYERS_STATS_URL",
    "https://info.afa.org.ar/deposito/html/v3/htmlCenter/data/deportes/futbol/primeraa/statsCenter/playersStatsFull.json"
)

HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30.0"))
HTTP_USER_AGENT: str = os.getenv(
    "HTTP_USER_AGENT",
    "Mozilla/5.0 (compatible; MoneyBallBot/1.0; +https://github.com/Juan-Gonzalez04/moneyball-argentino)"
)

# --------------------------------------------------------------------------
# 3. Configuración de Base de Datos PostgreSQL
# --------------------------------------------------------------------------
DB_HOST: str = os.getenv("DB_HOST", "localhost" if not Path("/.dockerenv").exists() else "postgres")
DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
DB_NAME: str = os.getenv("DB_NAME", "afa_data")
DB_USER: str = os.getenv("DB_USER", "juan")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "devpassword123")

DB_URL: str = os.getenv(
    "DB_URL",
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
