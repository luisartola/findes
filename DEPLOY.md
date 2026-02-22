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
