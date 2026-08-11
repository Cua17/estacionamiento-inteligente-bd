# Notas de la prueba de concepto de OCR (Fase 3)

## Qué se probó
Como todavía no hay cámara conectada, se probó contra 4 imágenes:
- 3 placas sintéticas generadas por `generar_placas_prueba.py`, formato de
  Guatemala (1 letra de categoría + 3 dígitos + 3 letras: `P456DEF`,
  `C789GHJ`, `M234KLM`).
- 1 foto de referencia real de una placa guatemalteca
  (`Placa_vehicular_de_Guatemala.png`, placa `P123ABC`).

Pipeline probado (el mismo que se usará en la Raspberry Pi):
escala de grises → umbral binario → Tesseract OCR (`test_ocr.py`).

## Resultado
**3 de 4 placas leídas correctamente (75%)**, incluyendo la foto real.

| Placa esperada | Leída | Resultado |
|---|---|---|
| C789GHJ | C789GHJ | OK |
| M234KLM | M234KLM | OK |
| P123ABC (foto real) | P123ABC | OK |
| P456DEF | PAS6DEF | Falló — confundió el número `4` con `A` y el `5` con `S` |

## Dos problemas reales que aparecieron (y cómo se resolvieron)

1. **Las placas sintéticas generadas se cortaban en los bordes.** Con un
   tamaño de letra fijo, texto de 7 caracteres (ej. `M234KLM`) se salía del
   lienzo y la primera/última letra quedaban físicamente cortadas en la
   imagen — el OCR no tenía la culpa, la imagen de entrada ya venía mal.
   Se corrigió haciendo que `generar_placas_prueba.py` ajuste el tamaño de
   letra automáticamente para que el texto siempre quepa dentro del lienzo.

2. **El marco/borde negro alrededor de la placa confundía a Tesseract**,
   que agregaba caracteres fantasma (ej. una "I" al inicio) al interpretar
   el borde como parte del texto. Se quitó el borde de las imágenes
   sintéticas: en el pipeline real, el paso de "aislar la región de la
   placa" (Fase 4) ya se encarga de recortar solo el texto antes de
   mandarlo a OCR, así que estas imágenes simulan justamente esa región ya
   recortada, sin marco.

## Limitación que queda (no es un bug, es una limitación real de OCR)
La confusión `4` ↔ `A` y `5` ↔ `S` es un problema documentado en
reconocimiento de caracteres: son formas visualmente parecidas en fuentes
bold, y depende de la fuente/cámara/resolución. Con fotos reales (más
ruido, ángulo, luz) puede ser igual o más frecuente.

## Cómo se piensa mitigar en fases siguientes
- **Post-procesamiento por posición**: en el formato de placa guatemalteco
  la primera posición siempre es letra y las siguientes 3 siempre son
  dígitos — se puede forzar la corrección según la posición esperada.
- **Mejor preprocesamiento** una vez haya fotos reales de la cámara:
  probar distintos `--psm` de Tesseract y evaluar EasyOCR como alternativa
  (modelo de deep learning en vez de reglas, suele ser más robusto en
  fotos reales, aunque más pesado para correr en la Pi).
- Validar el número de caracteres esperado (7) y re-intentar con otra
  configuración si no calza.

## Por qué igual se considera una prueba de concepto válida
El objetivo de esta fase no era conseguir 100% de precisión, sino comprobar
que el pipeline (imagen → preprocesamiento → Tesseract → texto) funciona de
punta a punta, incluso con una foto real. Eso quedó demostrado. El tuning
de precisión es trabajo de la Fase 4 en adelante, con fotos de la cámara.
