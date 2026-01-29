# Skill: Authoring Markdown for Formato_GIRS

Objetivo: escribir Markdown que se vea bien en GitHub y sea convertible a Word usando `templates/Formato_GIRS.docx`.

Reglas:

- Headings:
  - Usa `#` a `####` (max 4 niveles)
- Figuras numeradas:
  - Siempre precede la figura con `<!--figure ...-->`
  - Campos obligatorios: `id`, `title`, `source`
  - Para Mermaid: fence ` ```mermaid ` inmediatamente despues de la directiva
  - Para imagen: `![](ruta/relativa.png)` inmediatamente despues de la directiva
- Tablas numeradas:
  - Siempre precede la tabla con `<!--table ...-->`
  - Campos obligatorios: `id`, `title`, `source`
  - La tabla debe ser una Markdown pipe table simple
- Referencias cruzadas:
  - Usa `@fig:<id>` y `@tab:<id>` en el texto
- Citas:
  - Usa `[@TAG]` en el texto
  - Define `TAG` en `references/sources.yaml`

Recomendaciones:

- Mantener `id` en minusculas y con guiones (ej: `arquitectura-backend`)
- Preferir imagenes PNG
