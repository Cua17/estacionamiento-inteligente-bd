# Contexto del proyecto — para retomar en otra sesión de Claude

Este archivo existe para que una sesión nueva de Claude Code (o vos mismo)
pueda retomar el proyecto sin haber estado en la conversación donde se
construyó. Léelo entero antes de tocar código.

## Qué es esto

Proyecto final del curso **Manejo de Base de Datos** (docente: Victor
Vargas). Propuesta original en
`C:\Users\jdcua\OneDrive\Universidad\2026 - Ciclo 2\Manejo de Base de Datos\Propuesta_Proyecto_Final.pdf`.

Un Raspberry Pi con cámara lee la placa de cada vehículo que entra a un
parqueo, detecta por visión por computadora qué espacios están libres u
ocupados, registra cada sesión en una base de datos relacional en la nube
(TiDB Cloud), y calcula el cobro automáticamente al salir.

**Para la verdad de producto completa** (usuarios, objetivo, principios de
diseño del sistema), leer `PRODUCT.md` en la raíz del repo — lo generó la
skill `impeccable` y sigue vigente.

## Dónde está todo

| Qué | Dónde |
|---|---|
| Repo de código (este) | `C:\Users\jdcua\dev\estacionamiento-inteligente-bd` |
| GitHub | https://github.com/Cua17/estacionamiento-inteligente-bd (**privado**) |
| Propuesta del proyecto (PDF/Word) | OneDrive, ruta de arriba — **carpeta separada**, no es este repo |
| Guía privada de demo | `DEMO.md` en este repo — **gitignored**, nunca se sube |

## Estado por fase

| Fase | Estado |
|---|---|
| 1. Diseño de la base de datos | ✅ Hecho |
| 2. Estructura del repositorio | ✅ Hecho |
| 3. Prueba de concepto de OCR | ✅ Hecho — ver `scripts/NOTAS_OCR.md` (desactualizado: ver "OCR" abajo, se reescribió la localización) |
| 4. Detección de ocupación | ✅ Hecho — funciona con webcam y con la cámara de la Pi |
| 6. Sesiones y facturación | ✅ Hecho — tarifa por rangos con monto fijo (ver "Tarifas" abajo) |
| 7. Dashboard web | ✅ Hecho — **migrado de Flask a Django**, con login y roles (Admin/Operador), sin registro público. `web/` (Flask) todavía existe en paralelo hasta el corte final |
| **0. Reset de la Raspberry Pi** | ✅ Hecho — 12 de agosto |
| **5. Cámara en la Pi** | ✅ **Hecho el 19-20 de agosto** — Camera Module v1 (OV5647) conectada y detectada. Hizo falta `dtoverlay=ov5647` explícito en `/boot/firmware/config.txt` (el auto-detect no la reconocía sola) |
| OCR en vivo, localización + perspectiva | ✅ Hecho — ver "OCR" abajo |
| Red del día de la demo (hotspot) | ✅ Hecho — 20 de agosto, probado de punta a punta (SSH + TiDB) con el hotspot real |
| 8. Pruebas en el parqueo real | 🔲 Pendiente |
| 9. Documentación y entrega final | 🔲 Pendiente |

**Documento para entender todo el proyecto de punta a punta** (pensado
para prepararse antes de la presentación): `GUIA_DE_ESTUDIO.md`.

## Dónde quedamos (sesión del 19-20 de agosto) — LEER ANTES DE SEGUIR

Sesión larga probando con la Pi real y carritos de juguete con placas
pegadas (parqueo simulado en una mesa, no el real todavía). Encontramos y
arreglamos varios bugs reales, en este orden:

1. **La cámara no se detectaba** → el cable estaba sucio/mal asentado, y
   además hacía falta `dtoverlay=ov5647` explícito (el auto-detect no
   reconoce bien este sensor viejo). Ya anotado en el runbook.
2. **La detección de ocupación por textura (`evaluar_espacios`) no
   funcionaba** con carritos de juguete sobre una hoja blanca — la
   densidad bajaba en vez de subir (el filtro de ruido borraba el detalle
   fino del carrito, y muy cerca la cámara de foco fijo se desenfocaba).
   Se agregó `evaluar_espacios_por_color` como alternativa (flag
   `--por-color` en monitor.py), que compara contra una referencia de
   "vacío" capturada al arrancar. **Para el parqueo real** (asfalto,
   carros de tamaño real) hay que evaluar si hace falta o si la de
   textura ya alcanza — no se probó todavía con condiciones reales.
3. **El dashboard tardaba ~30s en reflejar una salida** → el OCR corría
   en el mismo hilo que escribía el estado. Se separó en dos hilos.
4. **El OCR no leía nada** → `recortar_zona_brillante` agarraba la hoja
   blanca entera en vez de la placa. Se reescribió la localización
   (forma + relación de aspecto) con corrección de perspectiva. Medido:
   0/5 → 5/5 en escenas de prueba realistas (`test_scenes/`).
5. **El OCR seguía sin leer nada, con carrito puesto 10s** → mirando las
   fotos de `debug_placas/` se vio que el OCR estaba leyendo el cuadro
   EN VIVO, y para cuando le tocaba correr (después de confirmar+escribir
   el estado) el carrito ya no estaba. Se agregó un buffer de los últimos
   ~3s de cuadros; el OCR ahora lee de ahí, no del video en vivo.
6. **`KeyError` que tumbaba el monitor al arrancar** → `EstadoEstable`
   revienta si la PRIMERA lectura de la cámara contradice a la base (pasó
   porque había sesiones de prueba que quedaron abiertas). Arreglado.

**Continuación, misma sesión, 20 de agosto por la mañana:**

- **Red del día de la demo: ✅ probada de punta a punta.** La Pi se
  conectó al hotspot del celular del usuario (SSID "iPhone") con
  `nmcli device wifi connect`, quedó guardada como red conocida
  (`nmcli connection show` la lista junto a la de casa), y con laptop +
  Pi las dos en el hotspot se confirmó SSH y conexión a TiDB Cloud
  (`db.conectar()`) funcionando. Un detalle real que apareció: justo
  después de cambiarse de red, el DNS de la Pi tardó unos segundos en
  acomodarse (`Unknown MySQL server host` una vez, después funcionó) — al
  llegar el día de la demo, darle a la Pi unos 5-10 segundos después de
  que el hotspot esté activo antes de esperar que la base responda.
- **Se probó mostrar el parqueo en un iPad y se descartó.** La pantalla
  daba mucho reflejo/glare para la cámara (se veía la silueta de quien
  sacaba la foto reflejada sobre los espacios) y el fondo oscuro salía
  lavado por la sobreexposición. Se volvió a papel impreso, que ya sabíamos
  que funciona sin ese problema. El PDF del iPad queda en
  `materiales_demo/parqueo_ipad_descartado.pdf` por si se retoma con mejor
  control de luz.
- **Kit impreso nuevo, ya armado por el usuario**: `materiales_demo/kit_impresion.pdf`
  (generado con `materiales_demo/generar_kit_impresion.py`). Página 1: los
  4 espacios A1-A4, fondo blanco, **6.2cm de ancho cada uno**. Página 2: 6
  placas para recortar (`P123ABC`, `M456DEF`, `C789GHJ`, `P456DEF`,
  `M234KLM`, `C321XYZ`), **del mismo ancho que un espacio (6.2cm)** —
  se probaron más chicas primero (3.4cm) y se agrandaron a propósito:
  a 640x480 más grande es mejor para el OCR. Ya impreso, recortado, y
  pegado a los carritos de juguete.

**Lo último que quedó SIN CONFIRMAR — literal, seguir por acá:**

Después del fix del `KeyError` (commit `7d83051`), se dieron los 3 pasos
para retomar la prueba (sync de `ocupacion.py`, `reset_demo.py`,
reiniciar `monitor.py --sin-ventana --por-color`), pero la sesión se
desvió hacia el hotspot y el kit impreso antes de confirmar que se
ejecutaron. Retomar exactamente así:

1. Confirmar/repetir el sync: `scp -i ~/.ssh/id_ed25519_parqueo_pi scripts/ocupacion.py cua@parqueo-pi.local:~/estacionamiento-inteligente-bd/scripts/`
2. En la Pi: `cd ~/estacionamiento-inteligente-bd/scripts && python reset_demo.py`
   (⚠️ irreversible, borra sesiones/cobros/vehículos de prueba — es lo que
   se quiere para arrancar limpio)
3. Acomodar el kit impreso (ya armado) frente a la cámara, espacios vacíos
4. `python monitor.py --sin-ventana --por-color`
5. Poner un carrito con placa pegada, **dejarlo quieto ~20 segundos**
   (no 10 — el buffer necesita ver varios cuadros con el vehículo
   presente), sacarlo, revisar el log: ¿dice "placa leída -> XXXXXXX" o
   sigue en "placa no legible"?

**Antes de la presentación real** (fase 8), hay dos preguntas abiertas:
- ¿La detección por color (`--por-color`) sirve para el parqueo real, o
  hace falta volver a la de textura (`evaluar_espacios`, sin el flag)
  porque el fondo ya no es una hoja blanca controlada? Probar los dos ahí.
- Si el OCR sigue sin leer alguna placa incluso con el buffer nuevo,
  quedó pendiente implementar "guardar la mejor lectura como sin
  confirmar" en vez de solo DESCONOCIDA — se lo prometí al usuario si el
  buffer no alcanzaba.

## OCR de placas

Reescrito el 19-20 de agosto (`scripts/vision.py`):
- `localizar_candidatos_placa()` busca cuadriláteros con relación de
  aspecto 1.6-6.0 (descarta los recuadros del parqueo, que son más altos
  que anchos) en vez de "la zona más brillante del cuadro".
- `enderezar()` corrige la perspectiva con las 4 esquinas del candidato.
- `leer_placa()` vota entre binarizaciones (2 coincidencias) en vez de
  devolver la primera lectura con forma de placa válida.
- Banco de pruebas nuevo que imita la demo real (no recortes limpios):
  `scripts/generar_escenas_prueba.py` + `scripts/test_escenas.py`.
  Medido: 0/5 → 5/5 aciertos, 3924ms → ~400ms por lectura.
- En `monitor.py`: el OCR corre en su propio hilo (no bloquea el estado)
  y lee de un buffer de los últimos ~20 cuadros (~3s), no del video en
  vivo — ver punto 5 de "Dónde quedamos" arriba.

## Tarifas

Cambiaron dos veces en la misma sesión. La vigente ahora es **por rangos
con monto fijo** (no precio por hora prorrateado):

```
menos de 15 min   gratis
15 a 60 min       Q15
1 a 5 horas       Q35
más de 5 horas    Q35 + Q10 por cada hora empezada de más
```

Estos números son un punto de partida razonable puesto por el usuario,
**no son tarifas oficiales verificadas de ningún parqueo de Guatemala**.
Se cambian desde `/admin/` → Tarifas (crear una tarifa nueva cierra la
vigente sola, vía `TarifaAdmin.save_model`) sin tocar código.

Cálculo en `scripts/parqueo.py::calcular_monto_por_tramos` (al cerrar la
sesión) y espejado en `dashboard/static/dashboard/dashboard.js::cobroCorrido`
(estimado en vivo). Verificado que dan lo mismo en los 900 minutos de 1
min a 15 h — si se toca uno, hay que tocar el otro igual.

Tabla `tarifa_tramos`: `(tarifa_id, desde_minuto, monto_fijo,
precio_por_hora_adicional)`. El `precio_por_hora_adicional` solo se usa en
el último tramo (el abierto); en los del medio va en 0.

## Cuentas del dashboard Django

**No hay registro público** (decisión explícita del usuario, 19-20 de
agosto): `/registro` no existe, no hay enlace en el login. Las cuentas se
crean con `python manage.py crear_operador <usuario>` (rol Operador) o
desde `/admin/` a mano (para promover a Admin). La cuenta Admin del
usuario ya existe, no se tocó.

## Infraestructura

### TiDB Cloud (base de datos)
- Proyecto: `estacionamiento-inteligente` — **cluster propio**, separado del
  cluster `sismos-db` de otra tarea del mismo curso (comparten organización,
  nada más).
- Cluster: `estacionamiento-db`, plan Starter (gratis), región AWS Tokio.
- Base: `estacionamiento_db`, 5 tablas (`vehiculos`, `espacios`, `tarifas`,
  `sesiones`, `cobros`) — definidas en `schema.sql`.
- Credenciales en `.env` (gitignored). Plantilla en `.env.example`.
- **Importante de rendimiento**: el servidor está en Tokio, cada consulta
  cuesta ~300-350ms de solo latencia de red. Ver la sección de bugs abajo.
- Tarifa vigente ahora mismo: **Q5.00/hora** (la vieja, Q1000, quedó cerrada
  en el historial con `vigente_hasta`, nunca se borró).
- Espacios: `A1`, `A2`, `A3`, `A4`.

### Raspberry Pi
- Hostname: `parqueo-pi.local` (resuelve por mDNS, no hace falta IP fija).
- Usuario: `cua`, con **sudo sin contraseña** ya configurado
  (`/etc/sudoers.d/010_cua-nopasswd`).
- Acceso SSH: **solo por llave pública**, contraseña deshabilitada en el
  servidor. Llave privada en
  `C:\Users\jdcua\.ssh\id_ed25519_parqueo_pi` (en esta laptop Windows).
  Conectarse así:
  ```bash
  ssh -i ~/.ssh/id_ed25519_parqueo_pi cua@parqueo-pi.local
  ```
- SO: Raspberry Pi OS Lite 64-bit (Debian 13 "trixie"), recién reseteada y
  actualizada el 12 de agosto de 2026.
- Software instalado: Python 3.13, git, Tesseract OCR 5.5.0, OpenCV +
  librerías gráficas del sistema.
- El proyecto está copiado en `~/estacionamiento-inteligente-bd` en la Pi,
  con su propio venv (`venv/`) y su propio `.env` (mismas credenciales de
  TiDB). **Si el código cambia en la laptop, hay que volver a copiarlo** —
  no hay git configurado en la Pi, se usó `scp` directo. Ver "Cómo
  sincronizar con la Pi" más abajo.
- Alimentación: el cargador USB-C que tiene el usuario alcanza sin
  problemas (`vcgencmd get_throttled` dio `0x0`, sin subvoltaje).
- **Apagar siempre con `sudo shutdown -h now` antes de desenchufar** —
  nunca cortar la corriente en frío (riesgo de corromper la SD).

## Arquitectura del código

```
Cámara (webcam en laptop / cámara USB o Pi Camera cuando llegue)
        │
        ▼
monitor.py ──┬── ocupacion.py   → ¿libre u ocupado por espacio? (textura + umbral adaptativo)
             └── vision.py      → ¿qué placa es? (OCR con Tesseract + corrección de formato)
        │
        ▼
parqueo.py   → abre/cierra sesiones, calcula el cobro (NO sabe nada de cámaras)
        │  autocommit, protocolo MySQL sobre TLS
        ▼
TiDB Cloud · base `estacionamiento_db`
        │
        ▼
web_django/ (Django, ORM) → dashboard en el navegador (localhost:5051)
   con login, roles (Admin/Operador) y panel /admin/
```

`web/` (Flask) todavía existe con el mismo dashboard de solo lectura, sin
login — se mantiene en paralelo hasta que `web_django/` quede confirmado
como reemplazo definitivo (ver Tarea 8 del plan de Django).

**Principio de diseño clave**: `parqueo.py` es el único que toca la base de
datos para escribir. `monitor.py` corre en la Pi/laptop y escribe.
`web/app.py` corre en cualquier lado y solo lee — nunca escribe. Se pueden
correr en máquinas separadas sin coordinarse.

### Módulos, uno por responsabilidad

| Archivo | Qué hace |
|---|---|
| `scripts/monitor.py` | Programa principal: cámara → detección → base de datos. Corre el OCR y la escritura en un **hilo aparte** para que el video nunca se congele |
| `scripts/parqueo.py` | Motor de negocio: sesiones, cobros, estado de espacios |
| `scripts/vision.py` | OCR de placas — robusto (ver detalle abajo), pensado para cámara en vivo |
| `scripts/ocupacion.py` | Detección de ocupación por densidad de textura + filtro anti-parpadeo (`EstadoEstable`) |
| `scripts/camara.py` | Abre la cámara, distinto backend según Windows/Linux |
| `scripts/db.py` | Conexión a TiDB — **con `autocommit=True`**, ver bugs abajo |
| `scripts/reportes.py` | Consultas de solo lectura para el dashboard, separadas por qué tan seguido cambian |
| `web/app.py` | Servidor Flask del dashboard + API `/api/estado`, con conexión reusada y cache por capas |
| `web/templates/dashboard.html` + `web/static/dashboard.{css,js}` | El dashboard. Diseño "libro de caja" documentado en `DESIGN.md` |

### Herramientas de apoyo
- `scripts/configurar_espacios.py` — dibuja/genera las regiones de los
  espacios sobre el cuadro de la cámara. `--rejilla N` genera N regiones
  automáticas sin dibujar (útil para probar rápido); sin esa opción, se
  arrastra el mouse sobre la ventana de video.
- `scripts/capturar_placa.py` — lee placas en vivo desde la cámara, sin
  tocar la base de datos (para probar el OCR solo).
- `scripts/simulacion_demo.py` — demo narrada sin cámara, lee una imagen
  guardada.
- `scripts/generar_datos_demo.py` / `scripts/reset_demo.py` — llenar la
  base con datos plausibles / dejarla limpia.
- `scripts/test_ocr.py` — mide el acierto del OCR contra `test_images/`.

## Decisiones de diseño (para no reinventarlas ni contradecirlas)

- **La tarifa nunca se borra, se cierra** con `vigente_hasta` — un cobro
  viejo tiene que poder explicarse con la tarifa que regía ese día.
- **Placa ilegible → `DESCONOCIDA`**, nunca se inventa una — cobrarle a la
  placa equivocada es peor que no saberla.
- **El estado inicial lo manda la base de datos, no la cámara** — si al
  arrancar el monitor un espacio ya está ocupado según la base, no se toma
  el primer cuadro de la cámara como "estado inicial" (eso nunca
  registraría ese vehículo).
- **El tiempo se calcula en Python, no con `NOW()` del servidor** — TiDB
  está en otro huso horario que la máquina que corre el monitor.
- **Se cobra el minuto empezado** (`ceil`, mínimo 1 minuto), como un
  parqueo real.
- **Formato de placa de Guatemala**: 1 letra + 3 dígitos + 3 letras
  (ej. `P123ABC`). Se usa para corregir confusiones típicas de OCR (4↔A,
  5↔S, etc.) sabiendo qué posición debe ser letra y cuál dígito.
- **El dashboard nunca miente sobre datos viejos**: si se cae la conexión a
  la base, avisa en rojo y rotula la hora de la última lectura buena, en
  vez de mostrar números viejos como si fueran de ahora.
- **Diseño visual**: "libro de caja / papel continuo" en tinta oscura,
  filetes como única estructura (sin tarjetas). Sistema completo registrado
  en `DESIGN.md` — consultarlo antes de cualquier cambio visual nuevo.

## Bugs reales encontrados y resueltos (para no repetirlos)

Estos aparecieron todos la noche antes de una presentación, bajo presión de
tiempo — vale la pena leerlos antes de tocar `monitor.py`, `db.py` o
`web/app.py` de nuevo:

1. **El video se congelaba** al detectar un cambio: el OCR corría dentro
   del bucle de la cámara. Se movió a un hilo aparte con una cola
   (`queue.Queue`).
2. **Un espacio quedaba pegado en OCUPADO**: la primera versión del hilo
   descartaba el cambio a LIBRE si llegaba mientras el OCR seguía leyendo la
   entrada anterior. Arreglado: la cola nunca descarta cambios, se procesan
   todos en orden.
3. **El dashboard tardaba 100+ segundos en reflejar un cambio** (bug grave):
   al reusar una conexión a TiDB sin `autocommit`, la conexión quedaba
   leyendo la misma "foto" de la base para siempre (aislamiento
   REPEATABLE READ de MySQL/TiDB). Arreglado con `autocommit=True` en
   `db.py`. **Cualquier conexión nueva que se abra en este proyecto debe
   llevar `autocommit=True`.**
4. **El polling del dashboard se amontonaba**: usaba `setInterval` con un
   intervalo más corto que lo que tardaba cada respuesta, así que las
   peticiones se acumulaban y el atraso crecía sin parar. Arreglado
   encadenando con `setTimeout` (nunca hay dos peticiones en vuelo).
5. **El OCR "inventaba" placas**: aceptaba la primera lectura que tuviera
   *forma* de placa válida aunque fuera ruido. Mitigado (parcialmente,
   revisar si hace falta reforzar) reescribiendo `vision.py` para probar
   varias binarizaciones y buscar el patrón dentro del texto crudo.
6. **La lectura en vivo le erraba a los dígitos con frecuencia** (18 de
   agosto): `monitor.py` tenía escrita `leer_placa_por_consenso()` (exige
   que la misma placa se lea igual en dos cuadros distintos) pero **nunca
   se llamaba** — la lectura real hacía un solo intento sobre un cuadro
   estático con el pipeline reducido. Arreglado conectándola al hilo
   trabajador usando `ultimo_cuadro` como fuente de cuadros frescos, con
   fallback a lectura completa si la rápida no logra consenso. Además se
   encontró (con `test_ocr.py`, sin relación a este bug) que la foto de
   referencia real ahora falla un dígito (`P123ABC` → `P423ABC`) que la
   corrección por formato no puede arreglar porque es un dígito mal leído
   como *otro dígito*, no como una letra — pendiente de revisar con fotos
   reales de la cámara de la Pi.

**Limitación conocida, no es un bug**: la detección→dashboard tarda
~4 segundos de punta a punta. Es la latencia real de red a Tokio (varias
consultas × ~350ms cada una), no algo roto. Si se quiere bajar más, hay que
reescribir las consultas para que viajen agrupadas (no se hizo por falta de
tiempo antes de la presentación).

## Cómo correr todo

```bash
cd C:\Users\jdcua\dev\estacionamiento-inteligente-bd
```

Dashboard Django, con login y roles (una terminal):
```bash
cd web_django
python manage.py runserver 5051
```
→ http://localhost:5051 (primera vez: `python manage.py crear_grupos` y
crear una cuenta Admin, ver `GUIA_DE_ESTUDIO.md` sección 8)

Dashboard viejo en Flask, sin login (todavía en paralelo):
```bash
python web/app.py
```
→ http://localhost:5050

Monitor con cámara (otra terminal):
```bash
python scripts/configurar_espacios.py        # primera vez, o si se movió la cámara
python scripts/monitor.py
```
(en la Pi con la cámara CSI conectada, se detecta sola; `--camara-pi` la
fuerza si hiciera falta)

Sin cámara (para probar el motor de negocio solo):
```bash
python scripts/monitor.py --simular
```

Dejar la base limpia / con datos de ejemplo:
```bash
python scripts/reset_demo.py
python scripts/generar_datos_demo.py
```

## Cómo sincronizar cambios con la Raspberry Pi

No hay git en la Pi todavía — se copió el proyecto una vez con `scp`. Si el
código cambió en la laptop y hay que actualizarlo en la Pi:

```bash
cd C:\Users\jdcua\dev\estacionamiento-inteligente-bd
scp -i ~/.ssh/id_ed25519_parqueo_pi -r scripts web schema.sql requirements.txt \
  cua@parqueo-pi.local:~/estacionamiento-inteligente-bd/
```

(No hace falta copiar `.env` de nuevo, ya está ahí. Si `requirements.txt`
cambió, correr `./venv/bin/pip install -r requirements.txt` en la Pi por
SSH.)

## Qué falta / próximos pasos sugeridos

1. **Conseguir una cámara para la Pi** (USB webcam o Pi Camera Module) —
   es el único bloqueador real. El profesor ya confirmó que por ahora
   alcanza con la webcam de la laptop para las entregas intermedias.
2. Cuando llegue la cámara: correr `configurar_espacios.py` en la Pi
   (por SSH con `ssh -X` si hace falta ver la ventana, o físicamente con un
   monitor conectado un momento), y arrancar `monitor.py --sin-ventana`
   ahí — es el mismo código, no hay nada que reescribir.
3. Si da tiempo, revisar el punto 5 de bugs (agrupar las consultas del
   dashboard para bajar de ~4s a menos).
4. Fase 8: probar en el parqueo real de la universidad.
5. Fase 9: documentación final / informe para la entrega.

## Cosas de la interfaz que el usuario pidió explícitamente (no revertir sin preguntar)

- Sin emojis en la interfaz.
- Tonos oscuros en el dashboard.
- Todo el texto de cara al usuario, en español.
- El párrafo de "procedencia de los datos" al pie del dashboard se sacó a
  pedido explícito (quedaba muy largo en pantalla).
