# markdown-to-docx (Formato_GIRS)

Convierte documentos Markdown (estilo GitHub) a Word (.docx) respetando la plantilla corporativa `templates/Formato_GIRS.docx`.

Objetivos no negociables (diseño):

- Estilos corporativos exactos (Heading 1-4, Normal, Caption, etc.)
- Índice (TOC) nativo de Word (actualizable con "Actualizar campos")
- Lista de figuras y lista de tablas nativas de Word
- Numeración nativa de figuras y tablas (campos `SEQ`)
- Referencias cruzadas nativas (campos `REF`)
- Citas y bibliografía nativas de Word (campos `CITATION` y `BIBLIOGRAPHY` + `customXml` de fuentes)
- Snippets de código como figuras (PNG con resaltado y números de línea)

La salida queda lista para abrir en Word y actualizar campos (`Ctrl+A` luego `F9`).

## Requisitos

- Python 3.10+
- Pandoc en PATH
- Node.js en PATH
  - Para Mermaid: `mmdc` (mermaid-cli) disponible.
    - Recomendado: `npm install` (usa `package.json`) y el CLI usará `node_modules/.bin/mmdc`
    - Alternativa: `npm i -g @mermaid-js/mermaid-cli`
    - Último recurso: `npx -y @mermaid-js/mermaid-cli` (puede descargar dependencias)
- Microsoft Word (solo para actualizar campos al abrir; el CLI no usa COM)

## Estructura sugerida del repo

- `docs/report.md` (tu documento fuente)
- `meta.yaml` (metadata para portada)
- `references/sources.yaml` (fuentes bibliográficas para Word)
- `docs/assets/images/` (imágenes locales)
- `templates/Formato_GIRS.docx` (plantilla corporativa)

Ejemplo completo en `examples/example-report/`.

Ver `docs/markdown-schema.md`.

Soporta figuras con Mermaid, imágenes locales y snippets de código si se marcan con `<!--figure ...-->`.

## Instalación (dev)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .

# Mermaid renderer (opcional pero recomendado)
npm install
```

## Uso

Validar el Markdown (ids, referencias, citas):

```bash
md2docx validate examples/example-report/example-report.md --sources examples/example-report/sources.yaml
```

Generar DOCX:

```bash
md2docx build examples/example-report/example-report.md \
  --template templates/Formato_GIRS.docx \
  --meta examples/example-report/meta.yaml \
  --sources examples/example-report/sources.yaml \
  --output build/example-report.docx
```

Si `md2docx` no está en tu PATH, usa:

```bash
python -m md2docx.cli build examples/example-report/example-report.md \
  --meta examples/example-report/meta.yaml \
  --sources examples/example-report/sources.yaml \
  --output build/example-report.docx
```

Luego abre `build/example-report.docx` y ejecuta "Actualizar campos".

## Uso con Docker

Construir la imagen:

```bash
docker build -t md2docx:local .
```

Generar DOCX (monta el repo en `/work`):

Linux/macOS (Bash):

```bash
docker run --rm \
  -v "$(pwd):/work" \
  --user "$(id -u):$(id -g)" \
  md2docx:local build \
  examples/example-report/example-report.md \
  --template templates/Formato_GIRS.docx \
  --meta examples/example-report/meta.yaml \
  --sources examples/example-report/sources.yaml \
  --output build/example-report.docx
```

Windows (PowerShell):

```bash
docker run --rm -v "${PWD}:/work" md2docx:local build \
  examples/example-report/example-report.md \
  --template templates/Formato_GIRS.docx \
  --meta examples/example-report/meta.yaml \
  --sources examples/example-report/sources.yaml \
  --output build/example-report.docx
```

Si la ruta no se monta, usa la ruta absoluta con backslashes:

```bash
docker run --rm -v "C:\\Users\\<usuario>\\ruta\\al\\repo:/work" md2docx:local build \
  examples/example-report/example-report.md \
  --template templates/Formato_GIRS.docx \
  --meta examples/example-report/meta.yaml \
  --sources examples/example-report/sources.yaml \
  --output build/example-report.docx
```

## Skills (para autores/agents)

El repositorio incluye guías ("agent skills") para producir Markdown compatible:

- `skills/markdown-authoring.md`
- `skills/validator-checks.md`

El comando `md2docx validate` aplica estas reglas automáticamente.
