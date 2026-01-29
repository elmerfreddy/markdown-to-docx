# Diseno tecnico (md2docx)

Este documento describe como funciona el CLI `md2docx` para cumplir los requisitos de Formato_GIRS.

## Objetivo

Entrada: Markdown tipo GitHub (GFM) con:

- Mermaid
- tablas simples
- imagenes locales
- citas
- referencias cruzadas

Salida: `.docx` que respeta `templates/Formato_GIRS.docx` y usa mecanismos nativos de Word:

- TOC (indice) actualizable
- lista de figuras / lista de tablas (Table of Figures) actualizable
- numeracion de figuras/tablas (SEQ)
- referencias cruzadas (REF)
- citas y bibliografia (CITATION / BIBLIOGRAPHY + customXml Sources)

## Enfoque

La generacion se hace en 2 fases:

1) Pandoc convierte el contenido (Markdown -> DOCX) usando estilos de la plantilla como `--reference-doc`.
2) Se arma el DOCX final sobre la plantilla corporativa:
   - se conserva portada + TOC + lista de figuras + seccion de Referencias
   - se inserta el cuerpo generado por pandoc
   - se convierten marcadores a campos nativos (SEQ/REF/CITATION)
   - se actualiza `customXml/item1.xml` con las fuentes bibliograficas

## Preprocesamiento Markdown

El autor escribe Markdown limpio para GitHub.
El CLI lo transforma a un Markdown "pandoc-friendly" temporal con marcadores.

Directivas:

- `<!--figure id=... title=... source=...-->`
- `<!--table id=... title=... source=...-->`

Marcadores internos (no se escriben manualmente):

- `[[MD2DOCX_CAPTION_FIG:<id>|<titulo>]]`
- `[[MD2DOCX_CAPTION_TAB:<id>|<titulo>]]`
- `[[MD2DOCX_REF:fig:<id>]]` / `[[MD2DOCX_REF:tab:<id>]]`
- `[[MD2DOCX_CITATION:<tag>]]`

Mermaid se renderiza a PNG antes de llamar a pandoc.

## Ensamble DOCX

Se abre la plantilla como ZIP (DOCX = zip) y se modifica a nivel OpenXML:

- `word/document.xml`:
  - se llena portada (title/subtitle/author/date)
  - se inserta lista de tablas (`TOC \\c "Tabla"`) si no existe
  - se reemplaza el contenido de ejemplo por el cuerpo de pandoc
  - se reemplazan marcadores por campos Word:
    - caption: `Figura {SEQ Figura}. ...` / `Tabla {SEQ Tabla}. ...`
    - refs: `{REF fig_<id> \\h}` / `{REF tab_<id> \\h}`
    - citas: `{CITATION TAG \\l 12298}` dentro de un SDT de cita
- `word/_rels/document.xml.rels`:
  - se agregan relaciones para imagenes e hipervinculos del cuerpo
- `word/media/*`:
  - se copian imagenes del docx generado por pandoc, renombradas para no colisionar
- `word/styles.xml` y `word/numbering.xml`:
  - se copian desde el docx de pandoc para mantener listas correctas
- `customXml/item1.xml`:
  - se regenera con fuentes desde `references/sources.yaml`

## Actualizacion de campos

El CLI no ejecuta Word.
Despues de generar el `.docx`, abre el documento y ejecuta:

- `Ctrl+A`
- `F9`

Esto actualiza:

- indice (TOC)
- lista de figuras y tablas
- numeracion (SEQ)
- referencias cruzadas (REF)
- citas y bibliografia

Nota de autor:

- Evita agregar una seccion "Referencias" en el Markdown. La plantilla ya la incluye (Heading1 + campo `BIBLIOGRAPHY`).

## Mermaid

Para render Mermaid localmente se requiere `mmdc`.

Opciones:

- Instalar global: `npm i -g @mermaid-js/mermaid-cli`
- Instalar en el repo: `npm install` (lee `package.json`) y el CLI buscara `node_modules/.bin/mmdc`
