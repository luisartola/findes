#!/usr/bin/env python3
"""
Genera peliculas/index.json: un único fichero con todas las fichas de películas.

La web carga ese índice de una sola vez en lugar de pedir ~460 JSON sueltos,
lo que reduce la carga inicial de cientos de peticiones a una.

Uso:
  python3 build_index.py

Ejecútalo siempre que edites algo en peliculas/*.json (enrich.py ya lo llama).
"""

import json
import os
import sys

PELICULAS_DIR = "peliculas"
INDEX_PATH = os.path.join(PELICULAS_DIR, "index.json")


def build():
    base = os.path.dirname(os.path.abspath(__file__))
    peli_dir = os.path.join(base, PELICULAS_DIR)
    index = {}

    for name in sorted(os.listdir(peli_dir)):
        if not name.endswith(".json") or name == "index.json":
            continue
        slug = name[:-5]
        with open(os.path.join(peli_dir, name), encoding="utf-8") as f:
            try:
                movie = json.load(f)
            except json.JSONDecodeError as e:
                print(f"⚠ {name}: JSON inválido ({e})")
                continue
        movie.setdefault("slug", slug)
        # Campos vacíos fuera: el índice se descarga entero en cada visita.
        index[slug] = {k: v for k, v in movie.items() if v not in (None, "", [], "N/A")}

    out = os.path.join(base, INDEX_PATH)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(out) / 1024
    print(f"✓ {INDEX_PATH}: {len(index)} películas ({size:.0f} KB)")
    return len(index)


if __name__ == "__main__":
    sys.exit(0 if build() else 1)
