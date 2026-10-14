#!/usr/bin/env python3
"""
scripts/fetch_team_logos.py
===========================
Descarga automatizada de escudos oficiales de los clubes de Primera División
desde la API de Wikimedia Commons / Wikipedia.

Principios de ingeniería:
- Idempotencia: No descarga imágenes que ya existan localmente (salvo flag --force).
- Higiene de Red: Utiliza User-Agent descriptivo y consultas batch para no saturar la API.
- Desacople: Almacena los activos en 'dashboard/assets/teams/{team_id}.png' siguiendo la
  convención de clave primaria de la base de datos (ADR-0007 / ADR-0009).
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
import urllib.request
import urllib.parse
import json
import time

try:
    import httpx
except ImportError:
    httpx = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("fetch_team_logos")

# Base directory para assets
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "assets" / "teams"

# API Base URLs configurables vía entorno (12-Factor App) con valores por defecto abiertos
WIKIPEDIA_ES_API = os.getenv("WIKIPEDIA_ES_API_URL", "https://es.wikipedia.org/w/api.php")
WIKIPEDIA_EN_API = os.getenv("WIKIPEDIA_EN_API_URL", "https://en.wikipedia.org/w/api.php")

USER_AGENT = "MoneyballArgentinoScouting/1.0 (https://github.com/juan; personal-data-project) Python/urllib"

# Mapeo de team_id a artículos estándar de Wikipedia (pageimages)
STANDARD_WIKI_ARTICLES: Dict[int, str] = {
    2: "Asociación Atlética Argentinos Juniors",
    4: "Club Atlético Banfield",
    5: "Club Atlético Boca Juniors",
    7: "Club Estudiantes de La Plata",
    8: "Club de Gimnasia y Esgrima La Plata",
    10: "Club Atlético Independiente",
    11: "Instituto Atlético Central Córdoba",
    12: "Club Atlético Lanús",
    13: "Club Atlético Newell's Old Boys",
    16: "Racing Club",
    17: "Club Atlético River Plate",
    18: "Club Atlético Rosario Central",
    19: "Club Atlético San Lorenzo de Almagro",
    20: "Club Atlético Vélez Sarsfield",
    100: "Club Atlético Huracán",
    124: "Club Atlético Belgrano",
    129: "Club Social y Deportivo Defensa y Justicia",
    135: "Club Atlético Talleres (Córdoba)",
    137: "Club Atlético Unión (Santa Fe)",
    142: "Club Atlético Sarmiento (Junín)",
    489: "Club Atlético Platense",
    664: "Club Sportivo Independiente Rivadavia",
    685: "Club Atlético Barracas Central",
    815: "Club Atlético Tucumán",
    816: "Club Atlético Gimnasia y Esgrima (Mendoza)",
    834: "Asociación Atlética Estudiantes",
    1485: "Club Atlético Central Córdoba (Santiago del Estero)",
}

# Mapeo especial para clubes cuyos escudos están en archivos multimedia específicos
SPECIAL_WIKI_FILES: Dict[int, Tuple[str, str]] = {
    122: (WIKIPEDIA_EN_API, "File:Aldosivi logo.svg"),
    136: (WIKIPEDIA_ES_API, "Archivo:Escudo del Club Atlético Tigre - 2019.svg"),
    788: (WIKIPEDIA_ES_API, "Archivo:Escudo del Club Deportivo Riestra.svg"),
}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_image(url: str, dest_path: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read()
            if len(content) < 500:
                logger.warning(f"Respuesta demasiado pequeña ({len(content)} bytes) para {dest_path.name}")
                return False
            dest_path.write_bytes(content)
            return True
    except Exception as e:
        logger.error(f"Error descargando {url} -> {e}")
        return False


def resolve_standard_thumbnails() -> Dict[str, str]:
    """Consulta la API de Wikipedia en lote para obtener URLs de thumbnails de 250px."""
    titles = list(STANDARD_WIKI_ARTICLES.values())
    encoded_titles = urllib.parse.quote("|".join(titles))
    url = f"{WIKIPEDIA_ES_API}?action=query&titles={encoded_titles}&prop=pageimages&format=json&pithumbsize=250"
    
    logger.info(f"Consultando lote de {len(titles)} clubes a la API de Wikipedia...")
    data = fetch_json(url)
    pages = data.get("query", {}).get("pages", {})
    
    title_to_thumb = {}
    for _, page_info in pages.items():
        title = page_info.get("title")
        thumb_url = page_info.get("thumbnail", {}).get("source")
        if title and thumb_url:
            title_to_thumb[title] = thumb_url

    # Mapear títulos normalizados si los hay
    normalized = data.get("query", {}).get("normalized", [])
    for norm in normalized:
        orig = norm.get("from")
        target = norm.get("to")
        if target in title_to_thumb and orig:
            title_to_thumb[orig] = title_to_thumb[target]

    return title_to_thumb


def resolve_special_thumbnails() -> Dict[int, str]:
    """Resuelve URLs de thumbnails para archivos multimedia específicos."""
    special_thumbs = {}
    for team_id, (api_url, file_title) in SPECIAL_WIKI_FILES.items():
        encoded_title = urllib.parse.quote(file_title)
        url = f"{api_url}?action=query&titles={encoded_title}&prop=imageinfo&iiprop=url&iiurlwidth=250&format=json"
        try:
            data = fetch_json(url)
            pages = data.get("query", {}).get("pages", {})
            first_page = list(pages.values())[0]
            imageinfo = first_page.get("imageinfo", [{}])[0]
            thumb_url = imageinfo.get("thumburl")
            if thumb_url:
                special_thumbs[team_id] = thumb_url
                logger.info(f"Resuelto archivo especial para team_id {team_id}: {file_title}")
        except Exception as e:
            logger.error(f"Error resolviendo archivo especial para team_id {team_id}: {e}")
        time.sleep(0.5)  # Cortesía para evitar rate limit
    return special_thumbs


def main():
    parser = argparse.ArgumentParser(description="Descarga escudos de clubes para Moneyball Argentino")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directorio destino")
    parser.add_argument("--force", action="store_true", help="Sobrescribir archivos existentes")
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Directorio de salida: {output_dir}")

    # 1. Resolver URLs estándar
    title_to_thumb = resolve_standard_thumbnails()

    # 2. Resolver archivos especiales
    special_thumbs = resolve_special_thumbnails()

    # 3. Consolidar mapeo team_id -> image_url
    team_urls: Dict[int, str] = {}

    for team_id, article_title in STANDARD_WIKI_ARTICLES.items():
        thumb = title_to_thumb.get(article_title)
        if thumb:
            team_urls[team_id] = thumb
        else:
            logger.warning(f"No se encontró thumbnail para team_id {team_id} ({article_title})")

    for team_id, thumb in special_thumbs.items():
        team_urls[team_id] = thumb

    logger.info(f"Se obtuvieron URLs para {len(team_urls)}/30 clubes.")

    # 4. Descargar archivos localmente
    downloaded = 0
    skipped = 0
    failed = 0

    for team_id, img_url in sorted(team_urls.items()):
        dest_file = output_dir / f"{team_id}.png"
        if dest_file.exists() and dest_file.stat().st_size > 0 and not args.force:
            logger.debug(f"Saltando team_id {team_id} (ya existe)")
            skipped += 1
            continue

        logger.info(f"Descargando escudo para team_id {team_id} -> {dest_file.name}...")
        success = download_image(img_url, dest_file)
        if success:
            downloaded += 1
        else:
            failed += 1
        time.sleep(0.3)  # Rate limiting gentil

    logger.info("=" * 50)
    logger.info(f"Resumen de descarga:")
    logger.info(f"  Descargados: {downloaded}")
    logger.info(f"  Existentes omitidos: {skipped}")
    logger.info(f"  Fallidos: {failed}")
    logger.info(f"  Total activos en disco: {len(list(output_dir.glob('*.png')))}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
