"""
Módulo de Extracción (Extract) para MoneyBall Argentino / Argos.

Responsabilidades:
1. Conectarse de forma segura y resiliente al endpoint público de AFA vía HTTPX.
2. Descargar el payload completo de estadísticas de jugadores y equipos.
3. Calcular la firma criptográfica (SHA-256) del contenido para verificar integridad.
4. Persistir una copia inmutable del JSON crudo con marca de tiempo UTC en RAW_DATA_DIR (Bronze Layer).
5. Retornar los metadatos de la extracción y el contenido deserializado.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, NamedTuple
import hashlib
import json
import logging
import httpx

from etl.src.config import (
    AFA_PLAYERS_STATS_URL,
    AFA_TEAMS_STATS_URL,
    HTTP_TIMEOUT_SECONDS,
    HTTP_USER_AGENT,
    RAW_DATA_DIR,
)

logger = logging.getLogger("etl.extract")


class ExtractionResult(NamedTuple):
    raw_file_path: Path
    sha256_hash: str
    bytes_count: int
    timestamp_utc: str
    payload: Dict[str, Any]


def calculate_sha256(content_bytes: bytes) -> str:
    """Calcula el hash SHA-256 del contenido binario para verificar integridad."""
    hasher = hashlib.sha256()
    hasher.update(content_bytes)
    return hasher.hexdigest()


def fetch_afa_endpoint(
    url: str,
    file_prefix: str,
    env_var_name: str,
    save_raw: bool = True,
) -> ExtractionResult:
    """
    Descarga genérica y resiliente para endpoints de estadísticas de AFA.
    Valida la respuesta HTTP, computa el hash SHA-256 y persiste el snapshot Bronze inmutable.
    """
    now_utc = datetime.now(timezone.utc)
    timestamp_str = now_utc.strftime("%Y%m%dT%H%M%SZ")

    if not url:
        raise ValueError(
            f"La URL del endpoint no está configurada. "
            f"Por favor, configure {env_var_name} en su archivo .env"
        )

    logger.info("Iniciando extracción desde endpoint (%s): %s", file_prefix, url)
    headers = {
        "User-Agent": HTTP_USER_AGENT,
        "Accept": "application/json",
    }

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        raw_bytes = response.content

    bytes_count = len(raw_bytes)
    sha256_hash = calculate_sha256(raw_bytes)
    logger.info(
        "Descarga exitosa (%s): %d bytes recibidos | SHA-256: %s",
        file_prefix,
        bytes_count,
        sha256_hash,
    )

    # Validar que sea un JSON válido antes de guardarlo
    payload = json.loads(raw_bytes.decode("utf-8"))

    raw_file_path = RAW_DATA_DIR / f"{file_prefix}_{timestamp_str}.json"
    if save_raw:
        with open(raw_file_path, "wb") as f:
            f.write(raw_bytes)
        logger.info("Snapshot inmutable persistido en: %s", raw_file_path)

    return ExtractionResult(
        raw_file_path=raw_file_path,
        sha256_hash=sha256_hash,
        bytes_count=bytes_count,
        timestamp_utc=timestamp_str,
        payload=payload,
    )


def fetch_players_stats_full(
    url: str = AFA_PLAYERS_STATS_URL,
    save_raw: bool = True,
) -> ExtractionResult:
    """Ejecuta la descarga del endpoint de estadísticas individuales de futbolistas."""
    return fetch_afa_endpoint(
        url=url,
        file_prefix="playersStatsFull",
        env_var_name="AFA_PLAYERS_STATS_URL",
        save_raw=save_raw,
    )


def fetch_teams_stats_full(
    url: str = AFA_TEAMS_STATS_URL,
    save_raw: bool = True,
) -> ExtractionResult:
    """Ejecuta la descarga del endpoint de estadísticas colectivas de clubes."""
    return fetch_afa_endpoint(
        url=url,
        file_prefix="teamsStats",
        env_var_name="AFA_TEAMS_STATS_URL",
        save_raw=save_raw,
    )


if __name__ == "__main__":
    try:
        p_res = fetch_players_stats_full()
        print(f"\n[OK] Extracción de futbolistas finalizada con éxito:")
        print(f" - Archivo: {p_res.raw_file_path.name}")
        print(f" - SHA-256: {p_res.sha256_hash}")
        print(f" - Tamaño:  {p_res.bytes_count / 1024:.2f} KB")

        t_res = fetch_teams_stats_full()
        print(f"\n[OK] Extracción de equipos finalizada con éxito:")
        print(f" - Archivo: {t_res.raw_file_path.name}")
        print(f" - SHA-256: {t_res.sha256_hash}")
        print(f" - Tamaño:  {t_res.bytes_count / 1024:.2f} KB")
        print(f" - Clubes en payload: {len(t_res.payload.get('teams', {}))}")
    except Exception as exc:
        logger.error("Fallo crítico en la extracción: %s", exc, exc_info=True)
        raise SystemExit(1)
