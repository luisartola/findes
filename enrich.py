#!/usr/bin/env python3
"""
Enriquece los JSON de películas con datos de TMDB API.

Uso:
  python3 enrich.py <TMDB_BEARER_TOKEN>            # solo las que faltan
  python3 enrich.py <TOKEN> --rehacer slug1 slug2  # rehace fichas concretas
  python3 enrich.py <TOKEN> --rehacer-imposibles   # rehace las que check_data
                                                   # marca como imposibles

Consigue tu token en https://www.themoviedb.org/settings/api
Por defecto solo toca películas que aún no tienen tmdb_id, así que puedes
ejecutarlo varias veces sin perder ediciones manuales.

Al elegir entre los resultados de TMDB no se coge el primero a ciegas: se
puntúan por parecido del título y se descartan los estrenos posteriores al
finde en que se vio la película (nadie vio en 2009 un estreno de 2024).

Para corregir una ficha mal enlazada: pon su `imdb_id` correcto a mano y
deja `tmdb_id` a null. La próxima ejecución la resolverá por ese ID exacto
en vez de buscarla por título.
"""

import difflib
import json
import os
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = [a for a in sys.argv[1:] if a.startswith("--")]

if not args:
    print(__doc__.strip())
    sys.exit(1)

TOKEN = args[0]
SOLO_SLUGS = set(args[1:])
REHACER = "--rehacer" in flags or "--rehacer-imposibles" in flags
REHACER_IMPOSIBLES = "--rehacer-imposibles" in flags

PELICULAS_DIR = "peliculas"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}


def normaliza(texto):
    texto = unicodedata.normalize("NFD", texto or "").encode("ascii", "ignore").decode()
    return "".join(c for c in texto.lower() if c.isalnum() or c == " ").strip()


def tmdb_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def anios_de_findes():
    """Año en que se celebró cada finde, según data.json."""
    with open("data.json", encoding="utf-8") as f:
        data = json.load(f)
    return {
        finde["numero"]: int(finde["fecha_sort"][:4])
        for finde in data
        if (finde.get("fecha_sort") or "")[:4].isdigit()
    }


def puntua(candidato, titulo, anio_tope):
    """Cuánto encaja un resultado de TMDB con lo que buscamos."""
    objetivo = normaliza(titulo)
    parecidos = [
        difflib.SequenceMatcher(None, objetivo, normaliza(candidato.get(campo))).ratio()
        for campo in ("title", "original_title")
    ]
    score = max(parecidos) * 100

    anio = (candidato.get("release_date") or "")[:4]
    if anio.isdigit():
        anio = int(anio)
        if anio_tope and anio > anio_tope:
            # Imposible: se estrenó después de verla. Descartado salvo que no
            # haya nada mejor.
            score -= 1000
    elif anio_tope:
        score -= 10

    # Ante dos títulos igual de parecidos, la más conocida suele ser la buena.
    score += min(candidato.get("vote_count", 0), 500) / 100
    return score


def search_movie(titulo, anio_tope):
    """Busca en TMDB y devuelve el candidato que mejor encaja."""
    url = (
        "https://api.themoviedb.org/3/search/movie"
        f"?query={urllib.parse.quote(titulo)}&language=es-ES&include_adult=true"
    )
    try:
        resultados = tmdb_get(url).get("results") or []
    except Exception as e:
        print(f"⚠ Error buscando: {e}")
        return None
    if not resultados:
        return None
    return max(resultados[:10], key=lambda c: puntua(c, titulo, anio_tope))


def buscar_por_imdb(imdb_id):
    """Resuelve un IMDb ID a su ficha de TMDB. Exacto: aquí no se adivina."""
    url = (
        f"https://api.themoviedb.org/3/find/{urllib.parse.quote(imdb_id)}"
        "?external_source=imdb_id&language=es-ES"
    )
    try:
        resultados = tmdb_get(url).get("movie_results") or []
    except Exception as e:
        print(f"⚠ Error resolviendo {imdb_id}: {e}")
        return None
    return resultados[0] if resultados else None


def get_movie_details(tmdb_id):
    """Ficha completa, con créditos e IDs externos."""
    url = (
        f"https://api.themoviedb.org/3/movie/{tmdb_id}"
        "?language=es-ES&append_to_response=credits,external_ids"
    )
    try:
        return tmdb_get(url)
    except Exception as e:
        print(f"⚠ Error detalles: {e}")
    return None


def imposibles(findes_anio):
    """Slugs cuya ficha es posterior al finde en que se vio."""
    fuera = set()
    for fname in os.listdir(PELICULAS_DIR):
        if not fname.endswith(".json") or fname == "index.json":
            continue
        with open(os.path.join(PELICULAS_DIR, fname), encoding="utf-8") as f:
            m = json.load(f)
        anio = (m.get("year") or "")
        vistos = [findes_anio[n] for n in (m.get("findes") or []) if n in findes_anio]
        if anio.isdigit() and vistos and int(anio) > min(vistos):
            fuera.add(fname[:-5])
    return fuera


FINDES_ANIO = anios_de_findes()
if REHACER_IMPOSIBLES:
    SOLO_SLUGS |= imposibles(FINDES_ANIO)
    print(f"Rehaciendo {len(SOLO_SLUGS)} fichas imposibles\n")

files = sorted(
    f for f in os.listdir(PELICULAS_DIR) if f.endswith(".json") and f != "index.json"
)
total = len(files)
enriched = skipped = not_found = 0

for i, fname in enumerate(files):
    path = os.path.join(PELICULAS_DIR, fname)
    with open(path, encoding="utf-8") as f:
        movie = json.load(f)

    slug = fname[:-5]
    if SOLO_SLUGS and slug not in SOLO_SLUGS:
        skipped += 1
        continue
    if movie.get("tmdb_id") and not REHACER:
        skipped += 1
        continue

    titulo = movie["titulo"]
    vistos = [FINDES_ANIO[n] for n in (movie.get("findes") or []) if n in FINDES_ANIO]
    anio_tope = min(vistos) if vistos else None
    print(f"[{i+1}/{total}] {titulo}...", end=" ", flush=True)

    # Un imdb_id sin tmdb_id significa que alguien lo puso a mano para
    # corregir la ficha: se resuelve por él, que es exacto. Si vienen los dos,
    # el imdb_id salió del mismo emparejamiento que estamos rehaciendo, así
    # que no es de fiar y se vuelve a buscar por título.
    result = None
    if movie.get("imdb_id") and not movie.get("tmdb_id"):
        result = buscar_por_imdb(movie["imdb_id"])
        if result:
            print("(por IMDb)", end=" ", flush=True)
    if not result:
        result = search_movie(titulo, anio_tope)
    if not result:
        print("✗")
        not_found += 1
        time.sleep(0.25)
        continue

    details = get_movie_details(result["id"])
    if not details:
        print("✗ (detalles)")
        not_found += 1
        time.sleep(0.25)
        continue

    directors = [
        c["name"]
        for c in details.get("credits", {}).get("crew", [])
        if c.get("job") == "Director"
    ]
    ext = details.get("external_ids", {})
    poster = details.get("poster_path")
    genres = details.get("genres", [])

    movie["tmdb_id"] = details["id"]
    movie["imdb_id"] = ext.get("imdb_id")
    movie["titulo_es"] = details.get("title")
    movie["titulo_original"] = details.get("original_title")
    movie["year"] = (details.get("release_date") or "")[:4] or None
    movie["director"] = ", ".join(directors) if directors else None
    movie["plot"] = details.get("overview") or None
    movie["poster"] = f"{TMDB_IMG}{poster}" if poster else None
    movie["genre"] = ", ".join(g["name"] for g in genres) if genres else None
    movie["imdb_rating"] = None  # TMDB no da la nota de IMDb
    movie["tmdb_rating"] = round(details.get("vote_average", 0), 1) or None
    movie["runtime"] = f"{details.get('runtime', 0)} min" if details.get("runtime") else None

    with open(path, "w", encoding="utf-8") as f:
        json.dump(movie, f, ensure_ascii=False, indent=2)

    print(f"✓ {movie.get('titulo_original', '')} ({movie.get('year', '?')})")
    enriched += 1
    time.sleep(0.25)

import build_index

build_index.build()

print(f"\n{'='*50}")
print(f"Enriquecidas: {enriched}")
print(f"Ya tenían datos o fuera de filtro: {skipped}")
print(f"No encontradas: {not_found}")
if not_found:
    print("\nLas no encontradas puedes editarlas a mano en peliculas/<slug>.json")
    print("Añade tmdb_id y ejecuta de nuevo, o rellena los campos.")
print("\nRevisa el resultado con: python3 check_data.py")
print("Y completa reparto, países, etc. con: python3 enrich_wikidata.py")
