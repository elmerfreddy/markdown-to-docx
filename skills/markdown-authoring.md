# Skill: Authoring Markdown for Formato_GIRS

Objetivo: escribir Markdown que se vea bien en GitHub y sea convertible a Word usando `templates/Formato_GIRS.docx`.

Reglas:

- Headings:
  - Usa `#` a `####` (máx 4 niveles)
- Figuras numeradas:
  - Siempre precede la figura con `<!--figure ...-->`
  - Campos obligatorios: `id`, `title`, `source`
  - Para Mermaid: fence ` ```mermaid ` inmediatamente después de la directiva
  - Para imagen: `![](ruta/relativa.png)` inmediatamente después de la directiva
- Tablas numeradas:
  - Siempre precede la tabla con `<!--table ...-->`
  - Campos obligatorios: `id`, `title`, `source`
  - La tabla debe ser una Markdown pipe table simple
- Referencias cruzadas:
  - Usa `@fig:<id>` y `@tab:<id>` en el texto
- Citas:
  - Usa `[@TAG]` en el texto
  - Para múltiples citas usa `[@TAG1; @TAG2]` o `[-@TAG]`
  - Define `TAG` en el archivo de fuentes que pases con `--sources`
    (ejemplo: `examples/example-report/sources.yaml`)

Recomendaciones:

- Mantener `id` en minúsculas y con guiones (ej: `arquitectura-backend`)
- Preferir imágenes PNG

Ejemplo completo: `examples/example-report/`
