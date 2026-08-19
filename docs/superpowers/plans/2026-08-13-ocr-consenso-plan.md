# OCR en vivo por consenso — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que la lectura de placas en vivo use varios cuadros y exija
consenso antes de aceptar una placa, en vez del intento único sobre un
cuadro estático que usa hoy.

**Architecture:** `scripts/monitor.py` ya tiene escrita
`leer_placa_por_consenso()` pero nunca se llama. Se conecta esa función al
hilo trabajador, usando `ultimo_cuadro` (que el bucle de video ya
actualiza en cada iteración) como fuente de cuadros frescos. Se agrega un
fallback a la lectura completa si la rápida no logra consenso, y se
guarda a disco cualquier intento que termine en DESCONOCIDA para poder
depurarlo después con fotos reales.

**Tech Stack:** Python, OpenCV, pytesseract (sin dependencias nuevas).

## Global Constraints

- No se toca `vision.py` ni el formato de placa guatemalteco — el
  problema está en cuántos cuadros se leen, no en el algoritmo de OCR en
  sí.
- No se agregan dependencias nuevas (nada de EasyOCR por ahora — ver
  "Qué no se hace").
- Todo texto de cara al usuario/logs en español, sin emojis (consistente
  con el resto del proyecto).

---

## Diagnóstico (para quien retome esto sin contexto)

`scripts/monitor.py` define `leer_placa_por_consenso()` (línea ~96):
lee hasta `INTENTOS_DE_PLACA=12` cuadros y solo acepta una placa si la
misma lectura se repite 2 veces. **Esta función no se llama desde
ningún lado del código** (confirmado con
`grep -rn leer_placa_por_consenso .` — un solo resultado: la propia
definición).

Lo que sí corre hoy, dentro de `trabajador()` (línea ~234):

```python
if ocupado and trabajos.empty():
    placa = leer_placa_rapido(cuadro_del_cambio, zona_placa)
```

`cuadro_del_cambio` es el cuadro estático capturado en el instante de la
transición (`cuadro.copy()` en el bucle de video, línea 267). Es decir:
**un solo intento, sobre un solo cuadro, con la variante "rápida" del
pipeline** (2 binarizaciones × 2 modos de Tesseract, contra las 6
binarizaciones × 3 modos del pipeline completo). Eso explica lecturas
inconsistentes de dígitos: no hay ni repetición de cuadros ni consenso
real, solo el requisito de "calzar con el formato" (`formato_valido`),
que una lectura mal hecha puede cumplir igual (forma correcta, dígito
equivocado).

## File Structure

- Modificar: `scripts/monitor.py` — conectar el consenso, agregar
  fallback a lectura completa, agregar guardado de diagnóstico.
- Crear: `scripts/test_consenso.py` — pruebas con `unittest` (stdlib, sin
  dependencia nueva) para `leer_placa_por_consenso()`, siguiendo la
  convención de scripts ejecutables ya usada en `test_ocr.py`.
- Modificar: `.gitignore` — agregar `debug_placas/`.

---

### Task 1: Conectar el consenso al hilo trabajador

**Files:**
- Modify: `scripts/monitor.py:96-123` (función `leer_placa_por_consenso`)
- Modify: `scripts/monitor.py:234-240` (dentro de `trabajador()`)
- Test: `scripts/test_consenso.py`

**Interfaces:**
- Consumes: `leer_placa_rapido(cuadro, zona_placa)` y
  `leer_placa_del_cuadro(cuadro, zona_placa)` (ya existen, sin cambios de
  firma).
- Produces: `leer_placa_por_consenso(obtener_cuadro, zona_placa, intentos=12, coincidencias=2, intentos_completos=4) -> str | None`
  — mismo nombre y misma firma base que ya existía, se le agrega el
  parámetro `intentos_completos` con default, así que cualquier llamador
  viejo (no hay ninguno hoy) seguiría funcionando igual.

- [ ] **Step 1: Escribir el test que falla, para la función tal como está hoy**

Crear `scripts/test_consenso.py`:

```python
"""
Pruebas de leer_placa_por_consenso(): que exija que la misma placa
aparezca en dos cuadros distintos antes de aceptarla, y que use lectura
completa si la rápida no alcanza el consenso.

Uso:
    python scripts/test_consenso.py
"""

import unittest
from unittest.mock import patch

from monitor import leer_placa_por_consenso


class TestConsenso(unittest.TestCase):
    def test_acepta_cuando_dos_cuadros_dan_la_misma_placa(self):
        cuadros = iter(["cuadro1", "cuadro2", "cuadro3"])
        with patch("monitor.leer_placa_rapido", return_value="P123ABC"):
            resultado = leer_placa_por_consenso(
                lambda: next(cuadros, None), zona_placa=None, intentos=5,
                intentos_completos=0,
            )
        self.assertEqual(resultado, "P123ABC")

    def test_descarta_si_nunca_hay_dos_lecturas_iguales(self):
        placas = iter(["P123ABC", "P456DEF", "M789GHJ", None, None])
        cuadros = iter(["c1", "c2", "c3", "c4", "c5"])
        with patch("monitor.leer_placa_rapido", side_effect=lambda *a, **k: next(placas)):
            resultado = leer_placa_por_consenso(
                lambda: next(cuadros, None), zona_placa=None, intentos=5,
                intentos_completos=0,
            )
        self.assertIsNone(resultado)

    def test_usa_lectura_completa_en_los_ultimos_intentos(self):
        # 3 intentos rápidos (todos fallan) + 2 completos (el 2do da consenso
        # porque el 1er intento completo ya había leído "P123ABC" una vez).
        cuadros = iter(["c1", "c2", "c3", "c4", "c5"])
        with patch("monitor.leer_placa_rapido", return_value=None) as rapido, \
             patch("monitor.leer_placa_del_cuadro", return_value="P123ABC") as completo:
            resultado = leer_placa_por_consenso(
                lambda: next(cuadros, None), zona_placa=None, intentos=5,
                intentos_completos=2, coincidencias=2,
            )
        self.assertEqual(resultado, "P123ABC")
        self.assertEqual(rapido.call_count, 3)
        self.assertEqual(completo.call_count, 2)

    def test_se_detiene_si_la_camara_deja_de_dar_cuadros(self):
        with patch("monitor.leer_placa_rapido", return_value=None):
            resultado = leer_placa_por_consenso(
                lambda: None, zona_placa=None, intentos=5, intentos_completos=0,
            )
        self.assertIsNone(resultado)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correrlo y confirmar que falla**

Run: `cd scripts && python test_consenso.py -v`
Expected: `test_usa_lectura_completa_en_los_ultimos_intentos` falla
(`TypeError: leer_placa_por_consenso() got an unexpected keyword argument
'intentos_completos'`) — la función todavía no soporta ese parámetro. Los
otros dos tests de consenso puro ya deberían pasar, porque esa parte ya
estaba bien escrita.

- [ ] **Step 3: Agregar el fallback a lectura completa**

Reemplazar la función completa en `scripts/monitor.py` (líneas 96-123):

```python
def leer_placa_por_consenso(obtener_cuadro, zona_placa, intentos=INTENTOS_DE_PLACA,
                            coincidencias=2, intentos_completos=4):
    """
    Solo da por buena una placa si la lee IGUAL en dos cuadros distintos.

    Sin esto, el OCR devuelve la primera lectura que tenga forma de placa
    (una letra, tres dígitos, tres letras) aunque sea ruido interpretado mal,
    y el sistema termina inventando una placa que no se parece a la real.
    Exigir que dos cuadros independientes coincidan descarta casi todo ese
    ruido: acertar dos veces el mismo error es mucho menos probable que
    acertarlo una.

    Los primeros `intentos - intentos_completos` intentos usan la lectura
    rápida (menos variantes de binarización, para no atrasar el video). Si
    ninguno logra consenso, los últimos `intentos_completos` cambian a la
    lectura completa sobre cuadros frescos: más lenta por intento, pero
    mucho más probable que acierte en cuadros difíciles (poca luz, placa
    chica). Esto ya corre en el hilo aparte, así que el video no se ve
    afectado.
    """
    votos = Counter()
    intentos_rapidos = max(0, intentos - intentos_completos)
    for numero_intento in range(intentos):
        cuadro = obtener_cuadro()
        if cuadro is None:
            break
        if numero_intento < intentos_rapidos:
            placa = leer_placa_rapido(cuadro, zona_placa)
        else:
            placa = leer_placa_del_cuadro(cuadro, zona_placa)
        if placa:
            votos[placa] += 1
            if votos[placa] >= coincidencias:
                return placa
        time.sleep(0.05)

    if votos:
        mejor, veces = votos.most_common(1)[0]
        registrar(f"   lectura descartada por falta de consenso: '{mejor}' apareció {veces} vez/veces")
    return None
```

- [ ] **Step 4: Correr los tests y confirmar que pasan**

Run: `cd scripts && python test_consenso.py -v`
Expected: 4/4 `OK`

- [ ] **Step 5: Conectar la función al hilo trabajador**

En `scripts/monitor.py`, dentro de `trabajador()` (reemplazar líneas
234-240):

```python
                    if ocupado and trabajos.empty():
                        placa = leer_placa_por_consenso(
                            lambda: ultimo_cuadro["imagen"], zona_placa)
                        if placa and parqueo.actualizar_placa_de_sesion(
                                conexion_hilo, etiqueta, placa):
                            registrar(f"{etiqueta}: placa leída -> {placa}")
                        elif not placa:
                            registrar(f"{etiqueta}: placa no legible tras varios intentos, queda DESCONOCIDA")
                            guardar_para_diagnostico(ultimo_cuadro["imagen"], etiqueta)
```

(La función `guardar_para_diagnostico` se agrega en la Tarea 2 — dejar
este llamado ya escrito acá y completarlo ahí.)

- [ ] **Step 6: Probar manualmente con la webcam**

Run: `python scripts/monitor.py` (con la laptop, cámara apuntando a una
placa de prueba de `test_images/` impresa o mostrada en el celular)

Expected: al "ocupar" un espacio, en la consola aparece
`placa leída -> XXXXXXX` en vez de una sola lectura instantánea — vas a
notar que tarda un poco más (hasta ~1 segundo) en confirmar la placa,
porque ahora prueba varios cuadros. Eso es lo esperado.

- [ ] **Step 7: Commit**

```bash
git add scripts/monitor.py scripts/test_consenso.py
git commit -m "Usar consenso de varios cuadros para leer placas en vivo

La lectura en vivo hacia un solo intento sobre un cuadro estático con el
pipeline reducido. leer_placa_por_consenso() ya existia pero nunca se
llamaba. Ahora se conecta usando ultimo_cuadro como fuente de cuadros
frescos, y se agrega fallback a lectura completa si la rapida no logra
consenso en los primeros intentos.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Guardar diagnóstico cuando una placa queda DESCONOCIDA

**Motivación:** para poder mejorar el OCR hace falta ver ejemplos reales
de dónde falla — hoy no queda ningún rastro de esos cuadros. Guardar la
imagen (no hay dato personal más allá de la placa del vehículo, mismo
nivel de sensibilidad que ya maneja el proyecto) permite revisar después
qué salió mal: ¿la placa estaba muy chica?, ¿había mala luz?, ¿el recorte
de zona_placa está mal ajustado?

**Files:**
- Modify: `scripts/monitor.py` (agregar función + import de `cv2` ya
  presente)
- Modify: `.gitignore`

**Interfaces:**
- Produces: `guardar_para_diagnostico(cuadro, etiqueta) -> None`

- [ ] **Step 1: Agregar la función**

En `scripts/monitor.py`, cerca de `leer_placa_por_consenso`:

```python
CARPETA_DIAGNOSTICO = RAIZ / "debug_placas"


def guardar_para_diagnostico(cuadro, etiqueta):
    """
    Guarda el cuadro en disco cuando una placa queda DESCONOCIDA.

    Sirve para juntar ejemplos reales de fallas y revisarlos después
    (¿placa muy chica?, ¿mala luz?, ¿mal recortada la zona_placa?). No se
    sube a git (ver .gitignore) — son fotos del parqueo real.
    """
    if cuadro is None:
        return
    CARPETA_DIAGNOSTICO.mkdir(exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = CARPETA_DIAGNOSTICO / f"{etiqueta}_{marca}.png"
    cv2.imwrite(str(ruta), cuadro)
    registrar(f"   cuadro guardado para revisar: {ruta.name}")
```

- [ ] **Step 2: Agregar la carpeta al .gitignore**

Agregar esta línea a `.gitignore`:

```
debug_placas/
```

- [ ] **Step 3: Probar manualmente**

Run: `python scripts/monitor.py`, tapar la cámara o mostrar algo que no
sea una placa válida al "ocupar" un espacio.

Expected: aparece `debug_placas/A1_20260813_153000.png` (o la etiqueta
que corresponda) con el cuadro guardado.

- [ ] **Step 4: Commit**

```bash
git add scripts/monitor.py .gitignore
git commit -m "Guardar el cuadro cuando una placa queda DESCONOCIDA

Para juntar ejemplos reales de fallas del OCR y poder revisarlos despues,
en vez de perder la evidencia apenas se descarta la lectura.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-review

- **Cobertura del diagnóstico**: el único hallazgo (consenso escrito pero
  no conectado) queda resuelto en la Tarea 1; la Tarea 2 es el
  complemento para poder seguir mejorando con datos reales.
- **Placeholders**: ninguno — todo el código de las tareas es completo y
  ejecutable.
- **Consistencia de tipos**: `leer_placa_por_consenso` mantiene la misma
  firma que ya usaban los tests que se escriben en la Tarea 1; no hay
  otro lugar del código que la llame todavía (por eso nunca se rompe
  nada existente).

## Qué NO se hace acá (para no volar el plazo)

- **No se agrega EasyOCR.** Es una alternativa real (mencionada en
  `NOTAS_OCR.md`), pero es un modelo de deep learning pesado para correr
  en una Pi sin poder probarlo primero en el hardware real. Si después de
  probar con la cámara real el consenso no alcanza, es la siguiente carta
  a jugar — no ahora.
- **No se cambian los umbrales de `ocupacion.py`** — el reporte del
  usuario fue específicamente sobre placas mal leídas, no sobre
  detección de ocupación.
