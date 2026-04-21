## Resumen

Describa brevemente qué cambia y por qué.

## Alcance

1. Módulo o pantalla afectada:
2. Tipo de cambio: formulario, lista, tabla inline, validación, layout, flujo
3. Riesgo principal:

## Validación realizada

1. `manage.py check`
2. Tests ejecutados:
3. Validación manual realizada:

## Checklist de formularios y listas

Marcar solo si aplica a este PR.

- [ ] Revisé `docs/forms-and-lists-spec.md` antes de implementar.
- [ ] Usé `docs/form-scaffold.md` o seguí una pantalla canónica equivalente.
- [ ] El formulario usa `proc-form`, `form-feedback`, `widget-box` y `form_actions.html`.
- [ ] Los errores de servidor y cliente se ven con el mismo estilo.
- [ ] El orden de validación JS coincide con el orden visual del formulario.
- [ ] Los campos obligatorios están alineados entre label, `required` del formulario y validación JS.
- [ ] Si usa Tom Select, el foco inicial y el foco de error van al control visual correcto.
- [ ] El foco inicial no abre dropdown accidentalmente.
- [ ] Si hay tabla inline, la validación es por fila y no solo por celda.
- [ ] Si hay tabla inline, las filas vacías nuevas no quedan marcadas como error por defecto.
- [ ] Si hay tabla inline, las filas parciales sí quedan marcadas como error completo.
- [ ] Si hay tabla inline, el bloque completo se marca cuando existe una fila inválida.
- [ ] El botón de eliminar/restaurar usa `line_delete_button.html` o replica exactamente su contrato visual.
- [ ] El estado restaurar se ve en verde y el eliminar en rojo.

## Evidencia visual

Adjuntar capturas o GIF si el PR cambia:

1. foco inicial
2. errores visuales
3. tabla inline
4. botón eliminar/restaurar

## Notas adicionales

Incluya decisiones, deudas conocidas o puntos a revisar en QA.