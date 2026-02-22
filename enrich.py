#!/usr/bin/env python3
"""
Enriquece los JSON de películas con datos de TMDB API.

Uso:
  python3 enrich.py <TMDB_BEARER_TOKEN>

Consigue tu token en https://www.themoviedb.org/settings/api
Solo actualiza películas que aún no tienen tmdb_id.
Puedes ejecutarlo varias veces sin perder ediciones manuales.
"""

import json, os, sys, time, urllib.request, urllib.parse

if len(sys.argv) < 2:
    print("Uso: python3 enrich.py <TMDB_BEARER_TOKEN>")
    sys.exit(1)

TOKEN = sys.argv[1]
PELICULAS_DIR = "peliculas"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}

def tmdb_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def search_movie(title):
    """Search TMDB by Spanish title."""
    url = f"https://api.themoviedb.org/3/search/movie?query={urllib.parse.quote(title)}&language=es-ES&include_adult=true"
    try:
        data = tmdb_get(url)
        if data.get("results"):
            return data["results"][0]
    except Exception as e:
        print(f"⚠ Error buscando: {e}")
    return None

def get_movie_details(tmdb_id):
    """Get full movie details including credits and external IDs."""
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?language=es-ES&append_to_response=credits,external_ids"
    try:
        return tmdb_get(url)
    except Exception as e:
        print(f"⚠ Error detalles: {e}")
    return None

files = sorted(f for f in os.listdir(PELICULAS_DIR) if f.endswith(".json") and f != "index.json")
total = len(files)
enriched = 0
skipped = 0
not_found = 0

for i, fname in enumerate(files):
    path = os.path.join(PELICULAS_DIR, fname)
    with open(path, encoding="utf-8") as f:
        movie = json.load(f)

    if movie.get("tmdb_id"):
        skipped += 1
        continue

    titulo = movie["titulo"]
    print(f"[{i+1}/{total}] {titulo}...", end=" ", flush=True)

    result = search_movie(titulo)
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

    directors = [c["name"] for c in details.get("credits", {}).get("crew", []) if c.get("job") == "Director"]
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
    movie["imdb_rating"] = None  # TMDB doesn't have IMDB ratings
    movie["tmdb_rating"] = round(details.get("vote_average", 0), 1) or None
    movie["runtime"] = f"{details.get('runtime', 0)} min" if details.get("runtime") else None

    with open(path, "w", encoding="utf-8") as f:
        json.dump(movie, f, ensure_ascii=False, indent=2)

    print(f"✓ {movie.get('titulo_original', '')} ({movie.get('year', '?')})")
    enriched += 1
    time.sleep(0.25)

print(f"\n{'='*50}")
print(f"Enriquecidas: {enriched}")
print(f"Ya tenían datos: {skipped}")
print(f"No encontradas: {not_found}")
if not_found:
    print(f"\nLas no encontradas puedes editarlas manualmente en peliculas/<slug>.json")
    print(f"Añade tmdb_id y ejecuta de nuevo, o rellena los campos a mano.")

