#!/usr/bin/env python3
"""
Completa las fichas de peliculas/*.json con datos de Wikidata: países de
producción, reparto, música, fotografía, guion, temas y dónde transcurre.

Uso:
  python3 enrich_wikidata.py

No necesita token: se consulta el endpoint SPARQL público por imdb_id, unas
pocas peticiones en total. Reescribe siempre esos campos (y solo esos), así
que se puede ejecutar cuantas veces haga falta, por ejemplo después de
enrich.py cuando entren películas nuevas.

El quiz usa estos datos para enlazar películas entre sí (mismo actor, mismo
músico, mismo director de fotografía…) y para las cifras por país.
"""

import collections
import glob
import json
import os
import time
import urllib.parse
import urllib.request

PELICULAS_DIR = "peliculas"
ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "finde-pres/1.0 (archivo de los Findes Precríticos)"

# Campo de la ficha → propiedad de Wikidata.
CAMPOS = {
    "paises": "P495",      # país de origen
    "reparto": "P161",
    "musica": "P86",
    "fotografia": "P344",
    "guion": "P58",
    "temas": "P921",       # tema principal
    "escenario": "P840",   # dónde transcurre
}

# Etiquetas en castellano mal escritas en Wikidata.
CORRECCIONES = {
    "George Delerue": "Georges Delerue",
}


def sparql(query):
    data = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    req = urllib.request.Request(ENDPOINT, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())["results"]["bindings"]


def consulta(prop, imdb_ids):
    valores = " ".join(f'"{i}"' for i in imdb_ids)
    # Castellano y, si no hay, inglés: sin el segundo se perderían en
    # silencio los que no tienen etiqueta en castellano.
    filas = sparql(f"""
        SELECT ?imdb ?v ?vLabel WHERE {{
          VALUES ?imdb {{ {valores} }}
          ?film wdt:P345 ?imdb ; wdt:{prop} ?v .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "es,en". }}
        }}""")
    por_imdb = collections.defaultdict(list)
    for f in filas:
        etiqueta = f["vLabel"]["value"]
        # Sin etiqueta en ningún idioma el servicio devuelve el Q-id.
        if etiqueta.startswith("Q") and etiqueta[1:].isdigit():
            continue
        etiqueta = CORRECCIONES.get(etiqueta, etiqueta)
        if etiqueta not in por_imdb[f["imdb"]["value"]]:
            por_imdb[f["imdb"]["value"]].append(etiqueta)
    return por_imdb


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    rutas = [p for p in sorted(glob.glob(os.path.join(base, PELICULAS_DIR, "*.json")))
             if not p.endswith("index.json")]
    fichas = {}
    for ruta in rutas:
        with open(ruta, encoding="utf-8") as f:
            fichas[ruta] = json.load(f)
    imdb_ids = sorted({m["imdb_id"] for m in fichas.values() if m.get("imdb_id")})
    print(f"{len(imdb_ids)} películas con imdb_id")

    datos = {}
    for campo, prop in CAMPOS.items():
        datos[campo] = consulta(prop, imdb_ids)
        print(f"  {campo}: {len(datos[campo])} películas con datos")
        time.sleep(1)

    cambiadas = 0
    for ruta, movie in fichas.items():
        imdb = movie.get("imdb_id")
        if not imdb:
            continue
        antes = json.dumps(movie, ensure_ascii=False, sort_keys=True)
        for campo in CAMPOS:
            valores = sorted(datos[campo].get(imdb, []))
            if valores:
                movie[campo] = valores
            else:
                movie.pop(campo, None)
        if json.dumps(movie, ensure_ascii=False, sort_keys=True) != antes:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(movie, f, ensure_ascii=False, indent=2)
            cambiadas += 1

    print(f"✓ {cambiadas} fichas actualizadas")

    import build_index
    build_index.build()


if __name__ == "__main__":
    main()
