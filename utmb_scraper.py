"""
utmb_scraper.py
----------------
Scrapea los resultados públicos de "Puerto Vallarta México by UTMB 2024" desde las páginas de UTMB Index en utmb.world, NO desde live.utmb.world, pues esta contiene los resultados en el HTML inicial (sin necesidad de ejecutar JavaScript), paginados de 25 en 25 corredores. Por eso este script usa esa fuente.

USO:
    pip install requests beautifulsoup4 pandas lxml
    python utmb_scraper.py

SALIDA:
    utmb_puerto_vallarta_2024.csv
"""

import re
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PortfolioScraper/1.0; contacto: tu_correo@example.com)"
}

BASE_URL = "https://utmb.world/utmb-index/races/{race_id}.{slug}.{year}"
YEAR = 2024

# IDs de carrera confirmados navegando/buscando en utmb.world.
# Cada entrada arma la URL de esa distancia (race_id + slug + YEAR) y
# lleva los metadatos que se le van a pegar a cada corredor scrapeado.

RACES = [
    {"category": "100M", "race_id": 32454, "slug": "puertovallartamexicobyutmbwixarika-100m",
     "name": "Wixárika", "distance_km": 152, "elevation_gain_m": 5300},
    {"category": "100K", "race_id": 32456, "slug": "puertovallartamexicobyutmbhikuri100k",
     "name": "Hikuri", "distance_km": 95, "elevation_gain_m": 3500},
    {"category": "50K", "race_id": 32458, "slug": "puertovallartamexicobyutmbnakawe50k",
     "name": "Nakawé", "distance_km": 49, "elevation_gain_m": 2300},
    {"category": "33K", "race_id": 39600, "slug": "puertovallartamexicobyutmbharamara33k",
     "name": "Haramara", "distance_km": 33, "elevation_gain_m": 1550},
    {"category": "20K", "race_id": 32460, "slug": "puertovallartamexicobyutmbereno20k",
     "name": "Ereno", "distance_km": 20, "elevation_gain_m": 1000},
    {"category": "10K", "race_id": 39602, "slug": "puertovallartamexicobyutmbpatasalada10k",
     "name": "Pata Salada", "distance_km": 8, "elevation_gain_m": 400},
]


def fetch_page(race_id, slug, year, page=1):
    """
    Descarga una página de resultados y la regresa ya parseada con
    BeautifulSoup, lista para extraerle datos.
 
    page=1 no manda el parámetro ?page en la URL (así es como el sitio
    espera la primera página); del resto sí se manda como query param.
    """
    url = BASE_URL.format(race_id=race_id, slug=slug, year=year)
    params = {} if page == 1 else {"page": page}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()  # lanza un error si el request falla (404, 500, etc.)
    return BeautifulSoup(resp.text, "html.parser")
 
 
def get_last_page(soup):
    """
    Lee la barra de paginación de la página 1 y regresa el número de
    página más alto que existe para esta carrera.
    """
    page_numbers = [1]  # si no hay paginación, la carrera tiene solo 1 página
    for link in soup.find_all("a", href=True):
        match = re.search(r"[?&]page=(\d+)", link["href"])  # busca "?page=N" en el href
        if match:
            page_numbers.append(int(match.group(1)))
    return max(page_numbers)
 
 
GENDER_VALUES = ("Men", "Women")           # ancla fija: siempre aparece en cada fila
TIME_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")       # ej. "16:20:20" -> corredor con tiempo real
RANK_RE = re.compile(r"^\d+$")                        # ej. "1", "76" -> número de posición
DASH_RE = re.compile(r"^-+$")                         # ej. "-" -> celda vacía en el sitio
STATUS_RE = re.compile(r"^(DNF|DNS|DSQ|AB)$", re.IGNORECASE)  # estados de no-finisher
 
 
def _looks_like_rank(s):
    """True si el texto podría ser un número de rank (o un placeholder vacío '-')."""
    return bool(RANK_RE.match(s) or DASH_RE.match(s))
 
 
def _looks_like_time_or_status(s):
    """True si el texto es un tiempo real (HH:MM:SS) o un estado de no-finisher."""
    return bool(TIME_RE.match(s) or DASH_RE.match(s) or STATUS_RE.match(s))
 
 
def parse_results_table(soup):
    """
    Convierte una página de resultados en una lista de diccionarios.
 
    utmb.world NO usa una <table> semántica para esta tabla, así que se
    recorre el texto visible de la página en orden y se reconoce cada
    fila anclándose en la palabra "Men"/"Women" (siempre presente).
 
    Los corredores DNF no traen número de rank en la página -- eso
    significa que su fila tiene una línea menos que la de un finisher
    (rank, tiempo, nombre, nacionalidad, género, categoría vs. solo
    tiempo="DNF", nombre, nacionalidad, género, categoría). Por eso el
    rank ya no se busca con un offset fijo: primero se revisa si la
    línea de "tiempo" (3 líneas antes del género) es un tiempo real; si
    no lo es (viene "DNF", "-", etc.), se asume que no hay rank para esa
    fila y se descarta lo que haya 4 líneas antes (pertenece a otra
    cosa, no a esta fila).
    """
    text = soup.get_text(separator="\n")  # todo el texto visible de la página, en orden
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]  # una línea por celda, sin vacíos
 
    rows = []
    n = len(lines)
    for i in range(2, n):
        if lines[i] not in GENDER_VALUES:
            continue  # no es el inicio de una fila de resultado, se sigue buscando
 
        nationality = lines[i - 1]
        name = lines[i - 2]
        age_category = lines[i + 1] if i + 1 < n else ""
 
        time_candidate = lines[i - 3] if i - 3 >= 0 else ""
        rank_candidate = lines[i - 4] if i - 4 >= 0 else ""
 
        if not _looks_like_time_or_status(time_candidate):
            continue  # no hay tiempo/DNF reconocible: no es una fila real
 
        if TIME_RE.match(time_candidate):
            status = "Finisher"
            time_value = time_candidate
            rank_value = rank_candidate if _looks_like_rank(rank_candidate) else ""
        else:
            # "-", "DNF", "DNS", "DSQ": no terminó la carrera. Estas filas
            # no traen rank en la página, así que rank_candidate en
            # realidad no le pertenece a esta fila -- se descarta.
            status = "DNF"
            time_value = "00:00:00"
            rank_value = ""
 
        rows.append({
            "rank": rank_value,
            "time": time_value,
            "name": name,
            "nationality": nationality,
            "gender": lines[i],
            "age_category": age_category,
            "status": status,  # "Finisher" o "DNF", para filtrar/comparar después
        })
    return rows
 
 
def scrape_race(race, year=YEAR, delay=1.5):
    """
    Descarga y parsea TODAS las páginas de una carrera, y le agrega a
    cada corredor los metadatos de esa carrera (categoría, distancia,
    desnivel, año) para que, al juntar todas las carreras en un solo
    DataFrame, no se pierda de dónde vino cada fila.
    """
    all_rows = []
    first_page = fetch_page(race["race_id"], race["slug"], year, page=1)
    last_page = get_last_page(first_page)  # cuántas páginas tiene esta carrera
 
    for page in range(1, last_page + 1):
        # la página 1 ya la tenemos descargada, no hace falta pedirla otra vez
        soup = first_page if page == 1 else fetch_page(race["race_id"], race["slug"], year, page)
        rows = parse_results_table(soup)
 
        # le pega a cada corredor de esta página los datos de la carrera
        for row in rows:
            row["category"] = race["category"]
            row["race_name"] = race["name"]
            row["distance_km"] = race["distance_km"]
            row["elevation_gain_m"] = race["elevation_gain_m"]
            row["year"] = year
 
        all_rows.extend(rows)
        print(f"  {race['category']} - pagina {page}/{last_page}: {len(rows)} filas")
        time.sleep(delay)  # para no saturar el servidor con requests seguidos
 
    return all_rows
 
 
def main():
    """
    Recorre las 6 distancias definidas en RACES, junta los resultados de
    todas en un solo DataFrame, y lo exporta a un único CSV.
    """
    all_results = []
    for race in RACES:
        if race["race_id"] is None:
            # por si en el futuro se agrega una distancia sin confirmar su race_id todavía
            print(f"Saltando {race['category']} ({race['name']}) - falta confirmar race_id, ver README")
            continue
        print(f"Scrapeando {race['category']} ({race['name']})...")
        all_results.extend(scrape_race(race))
 
    df = pd.DataFrame(all_results)
    # utf-8-sig para que los acentos/ñ se vean bien si se abre el CSV en Excel
    df.to_csv("utmb_puerto_vallarta_2024.csv", index=False, encoding="utf-8-sig")
    print(f"\nListo: {len(df)} corredores guardados en utmb_puerto_vallarta_2024.csv")
 
 
if __name__ == "__main__":
    main()