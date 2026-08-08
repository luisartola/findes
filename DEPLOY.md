# Findes Precríticos – Despliegue

## 1. Crear el repo en GitHub

```bash
gh repo create finde-pres --public --source=. --push
```

## 2. Activar GitHub Pages

Ve a **Settings → Pages** del repo:

- **Source**: `Deploy from a branch`
- **Branch**: `main` / `/ (root)`
- Pulsa **Save**

## 3. Configurar DNS en tu proveedor de dominio

Añade un registro CNAME en la zona DNS de `precriticas.com`:

| Tipo  | Nombre  | Valor                    |
|-------|---------|--------------------------|
| CNAME | `findes` | `<tu-usuario>.github.io` |

## 4. Verificar en GitHub

Una vez propagado el DNS (puede tardar minutos o hasta 24h):

- En **Settings → Pages** verás `findes.precriticas.com` como custom domain
- Marca **Enforce HTTPS** cuando esté disponible

## Notas

- El fichero `CNAME` en la raíz del repo le indica a GitHub Pages qué dominio servir.
- `robots.txt` y la meta `noindex` impiden que Google indexe el sitio.
- Para desarrollo local: `npx serve -l 3000`

## Mantenimiento de los datos

Las fichas viven en `peliculas/<slug>.json`, una por película. La web **no**
las lee sueltas: carga `peliculas/index.json`, que las trae todas en una sola
petición. Por eso, después de tocar cualquier ficha hay que regenerar el índice:

```bash
python3 build_index.py
```

`enrich.py` ya lo llama al terminar, así que solo hace falta a mano si editas
un JSON directamente.

### Rellenar datos desde TMDB

```bash
python3 enrich.py <TMDB_BEARER_TOKEN>
```

Solo toca las películas sin `tmdb_id`, así que es seguro repetirlo. Al elegir
entre los resultados de TMDB puntúa por parecido del título y descarta los
estrenos posteriores al finde en que se vio la película.

### Revisar enlaces dudosos

```bash
python3 check_data.py
```

Lista fichas que probablemente apunten a la película equivocada. La sección
«Imposibles» son errores seguros: la ficha es posterior al finde en que se vio.
Para rehacerlas:

```bash
python3 enrich.py <TOKEN> --rehacer-imposibles
```

O una en concreto: `python3 enrich.py <TOKEN> --rehacer la-caza`

### Corregir una película mal enlazada

Cuando TMDB ha devuelto otra película, la forma segura de arreglarlo es por
IMDb: busca la ficha correcta en imdb.com, copia el `tt…` de la URL y en
`peliculas/<slug>.json` pon

```json
"imdb_id": "tt0060223",
"tmdb_id": null
```

La siguiente ejecución de `enrich.py` la resolverá por ese ID exacto en vez
de buscarla por título. Es lo que se ha hecho con las 11 fichas que estaban
enlazadas a la película equivocada.

## El Quiz

Tiene dos modos:

- **Precríticos**: las preguntas se generan solas a partir de `data.json` y de
  las fichas, así que salen distintas cada ronda y se actualizan solas cuando
  añadís un finde. No hay nada que mantener.
- **Cine general**: preguntas de verdadero/falso escritas a mano en
  `quiz.json`. Para añadir más, añade objetos a ese fichero.
