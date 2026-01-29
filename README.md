# markdown-to-docx (Formato_GIRS)

Convierte documentos Markdown (estilo GitHub) a Word (.docx) respetando la plantilla corporativa `templates/Formato_GIRS.docx`.

Objetivos no negociables (diseno):

- Estilos corporativos exactos (Heading 1-4, Normal, Caption, etc.)
- Indice (TOC) nativo de Word (actualizable con "Actualizar campos")
- Lista de figuras y lista de tablas nativas de Word
- Numeracion nativa de figuras y tablas (campos `SEQ`)
- Referencias cruzadas nativas (campos `REF`)
- Citas y bibliografia nativas de Word (campos `CITATION` y `BIBLIOGRAPHY` + `customXml` de fuentes)

La salida queda lista para abrir en Word y actualizar campos (`Ctrl+A` luego `F9`).

## Requisitos

- Python 3.10+
- Pandoc en PATH
- Node.js en PATH
  - Para Mermaid: `mmdc` (mermaid-cli) disponible.
    - Recomendado: `npm install` (usa `package.json`) y el CLI usara `node_modules/.bin/mmdc`
    - Alternativa: `npm i -g @mermaid-js/mermaid-cli`
    - Ultimo recurso: `npx -y @mermaid-js/mermaid-cli` (puede descargar dependencias)
- Microsoft Word (solo para actualizar campos al abrir; el CLI no usa COM)

## Estructura sugerida del repo

- `docs/report.md` (tu documento fuente)
- `meta.yaml` (metadata para portada)
- `references/sources.yaml` (fuentes bibliograficas para Word)
- `docs/assets/images/` (imagenes locales)
- `templates/Formato_GIRS.docx` (plantilla corporativa)

Ver `docs/markdown-schema.md`.

## Instalacion (dev)

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
md2docx validate docs/example-report.md --sources references/sources.yaml
```

Generar DOCX:

```bash
md2docx build docs/example-report.md \
  --template templates/Formato_GIRS.docx \
  --meta meta.yaml \
  --sources references/sources.yaml \
  --output build/example-report.docx
```

Si `md2docx` no esta en tu PATH, usa:

```bash
python -m md2docx.cli build docs/example-report.md --output build/example-report.docx
```

Luego abre `build/example-report.docx` y ejecuta "Actualizar campos".

## Skills (para autores/agents)

El repositorio incluye guias ("agent skills") para producir Markdown compatible:

- `skills/markdown-authoring.md`
- `skills/validator-checks.md`

El comando `md2docx validate` aplica estas reglas automaticamente.
