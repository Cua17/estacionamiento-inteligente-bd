# Cómo correr la demo (sin cámara todavía)

## La idea de fondo

El pipeline real es: **cámara → imagen → OCR → base de datos**. Como todavía
no hay cámara conectada, en vez del primer paso le pasamos al script una
imagen ya tomada (una placa sintética de prueba, en `test_images/`). De ahí
en adelante — OCR, base de datos, cobro — es exactamente el mismo código
que correrá con la cámara real en la Fase 5. No es una maqueta aparte.

## Paso 1 — Abrí dos terminales, ambas en la carpeta del proyecto

```bash
cd C:\Users\jdcua\dev\estacionamiento-inteligente-bd
```

## Paso 2 — Terminal 1: encendé el dashboard

```bash
python web/app.py
```

Dejalo corriendo. Abrí en el navegador: **http://localhost:5050**
Vas a ver 4 casillas verdes, "4 de 4 espacios disponibles". Dejá esta
ventana a la vista durante toda la demo — es lo que ve el profesor cambiar
en vivo.

## Paso 3 — Terminal 2: corré la simulación

```bash
python scripts/simulacion_demo.py
```

Esto:
1. "Captura" un vehículo — en realidad abre `test_images/BGZ123.png` (una
   placa sintética que generamos nosotros, formato Costa Rica).
2. Le lee la placa con Tesseract OCR.
3. La registra y abre una sesión en el espacio `A1` (queda OCUPADO — mirá
   el dashboard, cambia solo).
4. Espera a que presiones **ENTER** — ese es el momento en que decís
   "ahora simulamos que el carro se retira".
5. Al presionar ENTER: cierra la sesión, calcula el cobro con la tarifa
   real guardada en la base, y lo inserta. El espacio vuelve a LIBRE y el
   cobro aparece en la tabla de abajo del dashboard.

## Cómo "meterle" una placa distinta (para que no sea siempre la misma)

El script acepta parámetros:

```bash
python scripts/simulacion_demo.py --placa test_images/CPL482.png --espacio A2
```

Ya tenés 4 placas de prueba listas en `test_images/`: `BGZ123`, `CPL482`,
`SJO907`, `HKM356`. Podés correr la simulación varias veces seguidas, cada
vez con una placa y un espacio distintos, para que se vea que no es un
truco de una sola vez.

## Si querés una placa con OTRO texto (ej. con tu nombre, o el del profesor)

Editá `scripts/generar_placas_prueba.py`, en la lista `PLACAS_PRUEBA`
agregá el texto que quieras (formato: 3 letras + espacio + 3 números, para
que se parezca a una placa real), y corré:

```bash
python scripts/generar_placas_prueba.py
```

Te genera el `.png` nuevo en `test_images/`, listo para usarlo con
`--placa`.

## Si querés usar una FOTO real en vez de una sintética

Sacale una foto con el celular a una placa impresa (o real), pasala a esta
PC, y usala igual:

```bash
python scripts/simulacion_demo.py --placa "C:\ruta\a\tu\foto.jpg" --espacio A3
```

Ojo: las sintéticas están probadas y funcionan bien (3/4 en la prueba de
concepto). Una foto real puede leerse peor todavía porque no hemos ajustado
el preprocesamiento para fotos con luz/ángulo variable — eso es trabajo de
la Fase 4. Si vas a arriesgarte con una foto real en la demo, probala ANTES
en privado para no llevarte una sorpresa en vivo.

## Para dejar todo limpio antes de la demo real (o para practicar de nuevo)

```bash
python scripts/reset_demo.py
```

Pone todos los espacios en libre y borra las sesiones/cobros de prueba,
sin tocar las tarifas. Corré esto la noche antes o la mañana de la entrega,
después de haber practicado, para que el profesor vea el sistema arrancar
"limpio" (4 de 4 libres) en vez de con datos de tus pruebas.

## Respaldo: mostrar la base de datos real (por si te lo piden)

Consola de TiDB Cloud → proyecto `estacionamiento-inteligente` → cluster
`estacionamiento-db` → **SQL Editor**:

```sql
SELECT * FROM sesiones ORDER BY id DESC;
SELECT * FROM cobros ORDER BY id DESC;
```

## Guion sugerido para el profesor

1. Mostrás el dashboard: "esto lee en vivo de una base de datos en la nube".
2. Corrés la simulación, narrás en voz alta lo que hace cada paso mientras
   se imprime en pantalla.
3. Señalás el dashboard cuando el espacio cambia de color.
4. Presionás ENTER, mostrás el cobro calculado.
5. Cerrás con: "la cámara y el Raspberry Pi son la única pieza que falta
   conectar — toda la lógica de negocio ya funciona de punta a punta
   contra una base de datos real en la nube."
