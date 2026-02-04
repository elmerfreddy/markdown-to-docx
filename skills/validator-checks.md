# Skill: Validator checks (md2docx validate)

El comando `md2docx validate` debe fallar si:

- Hay `@fig:<id>` o `@tab:<id>` que no exista
- Hay citas `[@TAG]`, `[@TAG1; @TAG2]` o `[-@TAG]` sin fuente en el archivo
  pasado con `--sources` (ejemplo: `examples/example-report/sources.yaml`)
- Hay ids duplicados en figuras/tablas
- Hay Mermaid ` ```mermaid ` sin una directiva `<!--figure ...-->` inmediatamente antes

Y debe advertir si:

- Falta `meta.yaml` o faltan campos comunes
- Una figura o tabla no tiene `source` (si se desactiva el modo estricto)
