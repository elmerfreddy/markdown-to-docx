# Skill: Prompt template (generar Markdown compatible)

Usa este prompt con un agente si quieres que el contenido salga 100% compatible con `md2docx`.

```
Escribe un documento en Markdown (GFM) con estas reglas:

- Headings máximo 4 niveles (#, ##, ###, ####)
- Para cualquier figura numerada:
  - Antes de la figura agrega: <!--figure id=<id> title="<título>" source="<fuente>"-->
  - Luego agrega o una imagen ![](ruta) o un bloque ```mermaid
  - Para snippet de código usa fence ```<lenguaje>
- Para cualquier tabla numerada:
  - Antes de la tabla agrega: <!--table id=<id> title="<título>" source="<fuente>"-->
  - La tabla debe ser pipe table simple
- Para referencias cruzadas usa @fig:<id> y @tab:<id>
- Para citas usa [@TAG] (puede ser múltiple: [@TAG1; @TAG2] o [-@TAG])

Devuelve solo el Markdown.
```
