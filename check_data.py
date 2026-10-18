#!/usr/bin/env python3
"""
Revisa peliculas/*.json en busca de fichas sospechosas de estar mal enlazadas
con TMDB (enrich.py se queda con el primer resultado de búsqueda, y a veces
ese primer resultado no es la película que visteis).

Uso:
  python3 check_data.py

No modifica nada: solo imprime lo que conviene revisar a mano. Para corregir
una ficha, busca la película en imdb.com, y en peliculas/<slug>.json pon su
"imdb_id" y deja "tmdb_id" a null. enrich.py la resolverá por ese ID exacto.
"""

import difflib
import glob
import json
import os
import unicodedata

PELICULAS_DIR = "peliculas"
# Umbral de parecido entre el título de la lista y el que devolvió TMDB.
UMBRAL_TITULO = 0.6
# Las fichas del archivo son sobre todo cine de repertorio: una película muy
# reciente y con nota muy baja suele ser un enlace equivocado.
ANIO_RECIENTE = 2020
NOTA_BAJA = 5.0
# En los findes se ven largometrajes: un metraje de cortometraje delata que
# la ficha apunta a otra cosa (a un corto homónimo, normalmente).
DURACION_MINIMA = 45


def normaliza(texto):
    texto = unicodedata.normalize("NFD", texto or "").encode("ascii", "ignore").decode()
    return "".join(c for c in texto.lower() if c.isalnum() or c == " ").strip()


def parecido(a, b):
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def anio_de_findes(base):
    """Año de cada finde, sacado de data.json (fecha_sort = 'AAAA-MM')."""
    with open(os.path.join(base, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    anios = {}
    for finde in data:
        sort = finde.get("fecha_sort") or ""
        if sort[:4].isdigit():
            anios[finde["numero"]] = int(sort[:4])
    return anios


def revisar():
    base = os.path.dirname(os.path.abspath(__file__))
    findes_anio = anio_de_findes(base)
    titulo_dudoso, sin_datos, recientes_flojas, imposibles = [], [], [], []
    muy_cortas = []

    for ruta in sorted(glob.glob(os.path.join(base, PELICULAS_DIR, "*.json"))):
        if os.path.basename(ruta) == "index.json":
            continue
        with open(ruta, encoding="utf-8") as f:
            m = json.load(f)

        slug = m.get("slug") or os.path.basename(ruta)[:-5]
        titulo = m.get("titulo")

        if not m.get("tmdb_id"):
            # Con imdb_id ya está resuelta a mano: solo falta rellenarla.
            sin_datos.append((slug, titulo, m.get("imdb_id")))
            continue

        propio = normaliza(titulo)
        mejor = max(
            parecido(propio, normaliza(m.get("titulo_es"))),
            parecido(propio, normaliza(m.get("titulo_original"))),
        )
        if mejor < UMBRAL_TITULO:
            titulo_dudoso.append((round(mejor, 2), slug, titulo, m.get("titulo_es"),
                                  m.get("year"), m.get("director")))

        try:
            anio = int(m.get("year") or 0)
            nota = float(m.get("tmdb_rating") or 10)
        except (TypeError, ValueError):
            continue
        if anio >= ANIO_RECIENTE and nota < NOTA_BAJA:
            recientes_flojas.append((slug, titulo, anio, nota, m.get("director")))

        try:
            minutos = int(str(m.get("runtime") or "").split()[0])
        except (ValueError, IndexError):
            minutos = None
        if minutos is not None and minutos < DURACION_MINIMA:
            muy_cortas.append((slug, titulo, minutos, m.get("year"), m.get("director")))

        # Nadie pudo ver en 2010 una película estrenada en 2023: si pasa,
        # la ficha está enlazada a otra película.
        vistos = [findes_anio[n] for n in (m.get("findes") or []) if n in findes_anio]
        if anio and vistos and anio > min(vistos):
            imposibles.append((slug, titulo, anio, min(vistos), m.get("titulo_es"),
                               m.get("director")))

    def bloque(titulo, filas, formato):
        print(f"\n{titulo} ({len(filas)})")
        print("─" * 70)
        if not filas:
            print("  nada que revisar")
        for fila in filas:
            print("  " + formato(fila))

    imposibles.sort(key=lambda r: r[2] - r[3], reverse=True)
    bloque(
        "Imposibles: la película es posterior al finde en que se vio",
        imposibles,
        lambda r: f"{r[0]:<34} «{r[1]}» → «{r[4]}» ({r[2]}, {r[5]}) — visto en un finde de {r[3]}",
    )

    muy_cortas.sort(key=lambda r: r[2])
    bloque(
        f"Duran menos de {DURACION_MINIMA} min: ¿es un corto homónimo?",
        muy_cortas,
        lambda r: f"{r[0]:<34} «{r[1]}» → {r[2]} min ({r[3]}, {r[4]})",
    )

    titulo_dudoso.sort()
    bloque(
        "Títulos que no se parecen al de TMDB",
        titulo_dudoso,
        lambda r: f"[{r[0]:.2f}] {r[1]:<34} «{r[2]}» → «{r[3]}» ({r[4]}, {r[5]})",
    )
    bloque(
        f"Recientes (≥{ANIO_RECIENTE}) con nota baja (<{NOTA_BAJA})",
        recientes_flojas,
        lambda r: f"{r[0]:<34} «{r[1]}» → {r[2]}, ★{r[3]} ({r[4]})",
    )
    listas = [r for r in sin_datos if r[2]]
    perdidas = [r for r in sin_datos if not r[2]]
    bloque(
        "Resueltas por IMDb, pendientes de rellenar (ejecuta enrich.py)",
        listas,
        lambda r: f"{r[0]:<34} «{r[1]}» → {r[2]}",
    )
    bloque(
        "Sin identificar: hay que buscarlas a mano",
        perdidas,
        lambda r: f"{r[0]:<34} «{r[1]}»",
    )

    # Las preguntas de quiz.json apuntan a fichas por slug; si una ficha se
    # renombra, la pregunta se queda sin cartel y la web la descarta.
    with open(os.path.join(base, "quiz.json"), encoding="utf-8") as f:
        quiz = json.load(f)
    huerfanas = [q for q in quiz if q.get("pelicula_slug") and not os.path.exists(
        os.path.join(base, PELICULAS_DIR, q["pelicula_slug"] + ".json"))]
    bloque(
        "Preguntas de quiz.json sin ficha",
        huerfanas,
        lambda q: f"{q['pelicula_slug']:<34} {q['pregunta']}",
    )

    print("\nOjo: muchos de estos son falsos positivos (subtítulos, títulos")
    print("originales en otro idioma…). Es una lista para mirar, no para borrar.")


if __name__ == "__main__":
    revisar()
