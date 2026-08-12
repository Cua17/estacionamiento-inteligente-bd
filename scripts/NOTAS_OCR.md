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

| Placa esperada | OCR crudo | Con corrección | Resultado |
|---|---|---|---|
| C789GHJ | C789GHJ | C789GHJ | OK |
| M234KLM | M234KLM | M234KLM | OK |
| P123ABC (foto real) | P123ABC | P123ABC | OK |
| P456DEF | PAS6DEF | P456DEF | OK tras corregir |

**Sin corrección por formato: 3/4 (75%). Con corrección: 4/4 (100%).**

La corrección está implementada en `vision.py` (`corregir_por_formato`) y es
justamente la mitigación que la primera versión de estas notas dejó anotada
como pendiente. Aprovecha que el formato guatemalteco es fijo: la posición 0
y las posiciones 4 a 6 son siempre letras, y las posiciones 1 a 3 siempre
dígitos. Si Tesseract devuelve `PAS6DEF`, se sabe que la `A` y la `S` caen en
posiciones que deben ser numéricas, y se traducen a `4` y `5`.

**No hay que sobrevender ese 100%**: son 4 imágenes, tres de ellas sintéticas
y en condiciones ideales. Sirve para demostrar que el pipeline funciona y que
el conocimiento del dominio mejora la precisión de forma medible; no para
afirmar que el sistema acierta siempre en la calle.

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

## La limitación de fondo (no es un bug, es cómo funciona el OCR)
La confusión `4` ↔ `A` y `5` ↔ `S` es un problema documentado en
reconocimiento de caracteres: son formas visualmente parecidas en fuentes
bold, y depende de la fuente, la cámara y la resolución. Con fotos reales
(más ruido, ángulo, luz) puede ser igual o más frecuente. La corrección por
formato la compensa, pero no la elimina: si el OCR se equivoca en una
posición donde el carácter equivocado también es válido —una letra por otra
letra— el formato no lo puede detectar.

## Mitigaciones

Ya implementadas en `vision.py`:

- **Corrección por posición**: descrita arriba. Es lo que llevó el resultado
  de 3/4 a 4/4.
- **Validación de formato** (`formato_valido`): si la lectura no calza con
  `[A-Z]\d{3}[A-Z]{3}`, el monitor la descarta y registra el vehículo como
  `DESCONOCIDA` en vez de guardar una placa dudosa. Cobrarle a la placa
  equivocada es peor que admitir que no se supo cuál era.

Pendientes para cuando haya fotos de la cámara real:

- Probar distintos `--psm` de Tesseract con imágenes con luz y ángulo
  variables, y evaluar EasyOCR como alternativa (modelo de deep learning en
  vez de reglas; suele ser más robusto en fotos reales, aunque más pesado
  para correr en la Pi).
- Tomar varias lecturas del mismo vehículo en cuadros seguidos y quedarse
  con la que más se repita, en vez de confiar en una sola captura.

## Qué quedó demostrado
Que el pipeline (imagen → preprocesamiento → Tesseract → corrección → texto)
funciona de punta a punta, incluso con una foto real, y que agregarle
conocimiento del dominio —el formato de la placa guatemalteca— mejora la
precisión de forma medible y reproducible. Lo que falta es validarlo con
fotos tomadas por la cámara en el parqueo, con luz y ángulos variables.

Para reproducir la medición:

```bash
python scripts/test_ocr.py
```
