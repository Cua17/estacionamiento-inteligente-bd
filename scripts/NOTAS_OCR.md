# Notas de la prueba de concepto de OCR (Fase 3)

## Qué se probó
Como todavía no hay cámara ni fotos reales de placas, se generaron 4 imágenes
sintéticas de placas (`generar_placas_prueba.py`, formato Costa Rica: 3 letras
+ 3 números) y se corrió el mismo pipeline que se usará en la Raspberry Pi:
escala de grises → upscale 2x → umbral binario → Tesseract OCR (`test_ocr.py`).

## Resultado
**3 de 4 placas leídas correctamente** (75%).

| Placa esperada | Leída | Resultado |
|---|---|---|
| BGZ123 | BGZ123 | OK |
| CPL482 | CPL482 | OK |
| HKM356 | HKM356 | OK |
| SJO907 | S0907 | Falló — confundió la letra `O` con el número `0` |

## Limitación conocida
La confusión `O` ↔ `0` (y en general `I`/`1`, `S`/`5`, `B`/`8`) es un problema
documentado en reconocimiento de placas: son caracteres visualmente casi
idénticos y depende de la fuente/cámara. Con texto sintético (fuente Arial)
ya aparece; con fotos reales (más ruido, ángulo, luz) es aún más común.

## Cómo se piensa mitigar en fases siguientes
- **Post-procesamiento por posición**: en el formato de placa costarricense
  las primeras 3 posiciones son siempre letras y las últimas 3 siempre
  números — se puede forzar la corrección (ej. si Tesseract devuelve `0` en
  una posición que debe ser letra, corregirlo a `O`, y viceversa).
- **Mejor preprocesamiento** una vez haya fotos reales: probar distintos
  `--psm` de Tesseract y evaluar EasyOCR como alternativa (usa un modelo de
  deep learning en vez de reglas, suele ser más robusto en fotos reales,
  aunque más pesado para correr en la Pi).
- Validar el número de caracteres esperado (6) y re-intentar con otra
  configuración si no calza.

## Por qué igual se considera una prueba de concepto válida
El objetivo de esta fase no era conseguir 100% de precisión, sino comprobar
que el pipeline (cámara → imagen → preprocesamiento → Tesseract → texto)
funciona de punta a punta y corre sin errores. Eso quedó demostrado. El
tuning de precisión es trabajo de la Fase 4 en adelante, con fotos reales.
