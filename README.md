# Estacionamiento Inteligente

Detección de espacios, reconocimiento de placas y facturación automática con
visión por computadora, sobre una base de datos relacional en la nube.
Proyecto final del curso **Manejo de Base de Datos**.

Una cámara conectada a una Raspberry Pi lee la placa de cada vehículo que
ingresa a un parqueo, detecta en tiempo real qué espacios están libres u
ocupados, registra cada sesión en una base de datos relacional (TiDB Cloud,
compatible con MySQL) y calcula automáticamente el cobro por el tiempo
estacionado, sin intervención manual.

Propuesta completa del proyecto: `Propuesta_Proyecto_Final.pdf` (carpeta del
curso).

## Estado por fase

| Fase | Estado |
|---|---|
| 1. Diseño de la base de datos | Hecho |
| 2. Estructura del repositorio | Hecho |
| 3. Prueba de concepto de OCR | Hecho — 4/4 con corrección por formato |
| 4. Detección de ocupación | Hecho — funciona con webcam y con cámara de Pi |
| 5. Integración de cámara en la Raspberry Pi | Hecho |
| 6. Sesiones y facturación | Hecho — motor de tarifas por tramos |
| 7. Dashboard web | Hecho — Django, con autenticación y roles |
| 8. Pruebas en el parqueo real | Pendiente — único bloqueador: montar la cámara en el parqueo real de la universidad |
| 9. Documentación y entrega final | Hecho |

## Valor comercial

El sistema automatiza por completo el control de un parqueo pequeño o mediano
con una sola cámara y un Raspberry Pi, sin instalar barrera, boletera ni
sensores por espacio:

- **Costo de entrada bajo.** Un sistema de barrera con boletera y sensores
  individuales por espacio requiere hardware dedicado por cada punto de
  control. Este sistema reemplaza todo eso con una cámara y un equipo de
  cómputo de placa reducida (~US$50-80), lo que lo pone al alcance de
  parqueos que hoy no llevan ningún control digital.
- **Dato adicional que un sistema de barrera no genera.** Al identificar cada
  vehículo por placa, la base de datos permite análisis que un sistema de
  boletos no puede ofrecer: frecuencia de visita, vehículos recurrentes,
  ocupación por franja horaria — información con valor para decisiones de
  precio y de operación del negocio.
- **Costo operativo reducido.** La base de datos vive en la nube (TiDB Cloud,
  plan gratuito hasta 25 GiB, compatible con el protocolo MySQL), así que no
  hay servidor de base de datos que instalar ni mantener en sitio. El mismo
  código corre sin cambios en una laptop (desarrollo/pruebas) o en la
  Raspberry Pi (producción en el punto de operación).
- **Facturación sin margen de error humano.** El cobro se calcula
  automáticamente por tramos de tiempo al cerrar cada sesión — elimina el
  cálculo manual en la salida y el riesgo de fuga de ingreso por error o
  criterio del operador.
- **Mercado objetivo.** Parqueos pequeños y medianos en Guatemala que hoy
  llevan el control a mano o no lo llevan — el mismo problema que resuelve
  cualquier sistema de gestión de parqueos comercial, a una fracción del
  costo de instalación.

## Arquitectura

```
              Cámara (webcam en desarrollo, cámara CSI en la Raspberry Pi)
                            |
                            v
    monitor.py  ── ocupacion.py ──> ¿ocupado o libre por espacio?
        |       └─ vision.py    ──> ¿qué placa es?
        |         (cada uno en su propio hilo; el video nunca se bloquea)
        v
    parqueo.py  ──> abre y cierra sesiones, calcula el cobro por tramos
        |
        |  protocolo MySQL sobre TLS
        v
    TiDB Cloud · base `estacionamiento_db`
        |
        v
    web_django/ (Django + ORM) ──> dashboard con login y roles (Admin/Operador)
```

`monitor.py` es el único componente que **escribe** en la base de datos; el
dashboard solo **lee**. Esto permite correr el monitor en la Raspberry Pi,
junto a la cámara, y el dashboard en cualquier otra máquina, sin coordinación
entre ambos.

## Historial técnico

Resumen de los problemas de ingeniería resueltos durante el desarrollo,
en orden cronológico por área:

**Reconocimiento óptico de caracteres (OCR) de placas** — `scripts/vision.py`
- Localización del candidato a placa por geometría: se buscan cuadriláteros
  con relación de aspecto entre 1.6 y 6.0 (en vez de "la región más brillante
  del cuadro", que confundía la placa con otras superficies claras).
- Corrección de perspectiva de los 4 vértices del candidato antes de pasarlo
  al motor de OCR (Tesseract).
- Lectura por votación entre varias binarizaciones de la imagen, exigiendo
  coincidencia entre al menos 2, en vez de aceptar la primera lectura con
  forma válida.
- Corrección posterior por formato: la placa guatemalteca sigue un patrón
  fijo (1 letra + 3 dígitos + 3 letras, ej. `P123ABC`), lo que permite
  corregir confusiones típicas del OCR (`4`↔`A`, `5`↔`S`) sabiendo qué
  posición debe ser letra y cuál dígito. Resultado medido: 3/4 → 4/4 aciertos
  sobre el set de prueba (`scripts/NOTAS_OCR.md`).
- Banco de pruebas con escenas sintéticas que imitan condiciones reales de
  cámara (ángulo, tamaño, iluminación): 0/5 → 5/5 aciertos tras la reescritura
  de la localización, y el tiempo de lectura bajó de ~3924ms a ~400ms por
  intento.
- Lectura por consenso: sobre un flujo de video en vivo, se exige que la
  misma placa se lea igual en más de un cuadro consecutivo antes de darla por
  válida, reduciendo falsos positivos frente a una sola lectura ruidosa.

**Detección de ocupación de espacios** — `scripts/ocupacion.py`
- Detección primaria por densidad de textura con umbral adaptativo.
- Filtro anti-parpadeo (`EstadoEstable`) para no abrir y cerrar sesiones por
  una lectura momentáneamente ruidosa.
- Método alternativo por diferencia de color contra una referencia de
  "espacio vacío" capturada al iniciar el monitor (`--por-color`), evaluado
  como respaldo cuando el fondo real no ofrece suficiente contraste de
  textura.

**Motor de facturación** — `scripts/parqueo.py`
- Tarifa por tramos con monto fijo (no proporcional por hora): gratis antes
  de 15 minutos, monto fijo de 15 a 60 minutos, monto fijo de 1 a 5 horas, y
  cargo adicional por cada hora empezada de más allá de 5 horas.
- El cálculo se replica en el cliente (`dashboard.js`) para mostrar el cobro
  corrido en vivo mientras la sesión sigue abierta; verificado que ambas
  implementaciones (Python y JavaScript) coinciden en todo el rango de 1
  minuto a 15 horas.
- Las tarifas nunca se eliminan, se cierran con una fecha de vigencia — un
  cobro histórico siempre puede explicarse con la tarifa vigente el día que
  se generó.

**Concurrencia y resiliencia de la base de datos** — `scripts/monitor.py`,
`scripts/db.py`
- El OCR corre en un hilo separado del bucle de captura de video, comunicado
  por una cola (`queue.Queue`) que nunca descarta cambios de estado — se
  procesan todos en orden, evitando que un espacio quede "pegado" en un
  estado incorrecto mientras el OCR sigue trabajando.
- Conexión a TiDB con `autocommit=True`: sin esto, una conexión reusada bajo
  aislamiento `REPEATABLE READ` (por defecto en MySQL/TiDB) seguía leyendo la
  misma foto de la base indefinidamente, provocando que el dashboard tardara
  más de 100 segundos en reflejar un cambio real.
- Reconexión activa si TiDB cierra la conexión por inactividad, y
  `CONN_HEALTH_CHECKS` habilitado en Django para el mismo propósito del lado
  del dashboard.
- Actualización del dashboard por sondeo encadenado (`setTimeout` tras cada
  respuesta) en vez de `setInterval` de intervalo fijo, evitando que las
  peticiones se amontonen si una tarda más que el intervalo configurado.
- Latencia de red documentada, no oculta: el clúster de TiDB Cloud está en la
  región de Tokio, con ~300-350ms por consulta; la latencia de punta a punta
  entre una detección y su reflejo en el dashboard es de ~4 segundos por esa
  razón de infraestructura, no por una falla de diseño.

**Plataforma web** — `web/` → `web_django/`
- Migración del dashboard de Flask (solo lectura, sin autenticación) a
  Django, agregando autenticación y dos roles (Admin/Operador) sin registro
  público de cuentas — las cuentas se crean por comando de administración o
  desde el panel `/admin/`. El rol Operador no ve tarifas ni totales de
  recaudación, solo el estado operativo de los espacios.

**Despliegue en Raspberry Pi**
- Raspberry Pi OS Lite 64-bit (Debian 13), con la misma base de código que
  corre en la laptop de desarrollo — la única diferencia entre entornos es el
  origen de la imagen de cámara (webcam vs. cámara CSI de la Pi).
- Acceso remoto restringido a autenticación por llave pública (contraseña
  deshabilitada en el servidor), operación sin pantalla (`--sin-ventana`).

## Base de datos

Definida en [`schema.sql`](schema.sql). Cinco tablas relacionadas:

| Tabla | Contenido |
|---|---|
| `vehiculos` | Una fila por placa detectada. La placa es la llave primaria |
| `espacios` | Cada espacio físico con su estado actual (`libre` / `ocupado`) |
| `tarifas` | Tarifa vigente con historial: las tarifas viejas se cierran, no se borran |
| `tarifa_tramos` | Tramos de cobro de cada tarifa: `(tarifa_id, desde_minuto, monto_fijo, precio_por_hora_adicional)` |
| `sesiones` | Qué placa ocupó qué espacio, con hora de entrada y de salida |
| `cobros` | El monto generado al cerrar cada sesión |

Relaciones: `sesiones.placa → vehiculos.placa`, `sesiones.espacio_id →
espacios.id`, `cobros.sesion_id → sesiones.id` (única: un cobro por sesión),
`cobros.tarifa_id → tarifas.id` y `tarifa_tramos.tarifa_id → tarifas.id`.

Índices en `espacios.estado` (para contar libres), `sesiones.placa`
(historial por vehículo) y `sesiones(espacio_id, estado)` (para encontrar la
sesión activa de un espacio, la consulta más frecuente del monitor).

## Servicio de hosting elegido

**[TiDB Cloud Starter](https://tidbcloud.com/)** (de PingCAP), con su **SQL
Editor** web como gestor de la base de datos — el equivalente a phpMyAdmin.

| Criterio | TiDB Cloud Starter |
|---|---|
| Costo | Gratis permanente, sin tarjeta de crédito |
| Almacenamiento | 25 GiB |
| Gestor web | SQL Editor integrado en la consola (crear tablas, consultar, ver resultados) |
| Compatibilidad | Habla el protocolo MySQL: misma sintaxis SQL y mismo driver de Python |
| Conexión remota | Sí, cifrada con TLS |
| Respaldo institucional | PingCAP, empresa establecida; TiDB es un proyecto open source con +40k estrellas en GitHub |

## Decisiones de diseño que vale la pena explicar

- **La tarifa nunca se borra, se cierra.** Cambiar el precio inserta una
  tarifa nueva y le pone `vigente_hasta` a la anterior. Así un cobro viejo se
  puede seguir explicando con la tarifa que estaba vigente ese día.
- **Una placa ilegible se registra como `DESCONOCIDA`.** Inventar una placa
  parecida le cobraría a un tercero; es peor que admitir que no se supo.
- **El estado inicial lo manda la base, no la cámara.** Al arrancar, el
  monitor parte de lo que dice la base de datos. Si tomara como estado
  inicial el primer cuadro que ve, un vehículo ya estacionado al encender el
  sistema no se registraría nunca.
- **El tiempo se calcula en Python, no con `NOW()` del servidor.** El
  servidor de TiDB está en otro huso horario que la máquina que corre el
  monitor; comparar allá inflaba los minutos calculados.
- **Se cobra el minuto empezado** (`ceil`, mínimo 1 minuto), como un parqueo
  real.
- **Toda conexión nueva a la base debe usar `autocommit=True`.** Ver
  "Concurrencia y resiliencia" arriba — es la causa raíz de uno de los bugs
  más costosos del proyecto y una convención que debe respetarse en
  cualquier código nuevo que abra conexión.
- **Formato de placa de Guatemala**: 1 letra + 3 dígitos + 3 letras (ej.
  `P123ABC`). Se usa activamente para corregir confusiones típicas del OCR.

## Módulos

| Archivo | Qué hace |
|---|---|
| `scripts/monitor.py` | Programa principal: cámara → detección → base de datos, con el OCR en su propio hilo |
| `scripts/parqueo.py` | Motor de negocio: sesiones, cobros por tramos, estado de espacios |
| `scripts/vision.py` | OCR de placas: localización geométrica, corrección de perspectiva, votación y corrección por formato |
| `scripts/ocupacion.py` | Detección de ocupación por textura (o por color, alternativa) con filtro anti-parpadeo |
| `scripts/camara.py` | Acceso a la cámara (webcam en Windows/Linux, cámara CSI en Raspberry Pi) |
| `scripts/reportes.py` | Consultas de solo lectura para el dashboard |
| `scripts/db.py` | Conexión a TiDB Cloud, con `autocommit=True` |
| `web/app.py` | Dashboard original en Flask, solo lectura, sin autenticación |
| `web_django/` | Dashboard en Django: autenticación, roles (Admin/Operador), panel `/admin/` |

Herramientas de apoyo: `configurar_espacios.py` (define las regiones de los
espacios sobre el cuadro de la cámara), `capturar_placa.py` (lee placas en
vivo sin tocar la base), `simulacion_demo.py` (demo sin cámara),
`generar_datos_demo.py` / `reset_demo.py` (poblar o limpiar datos de prueba),
`test_ocr.py` / `test_escenas.py` / `test_ocupacion.py` / `test_tarifas.py`
(pruebas automatizadas por módulo).

## Instalación

1. Crear la base de datos y las tablas:

   ```bash
   cp .env.example .env
   ```

   Llenar `.env` con las credenciales de TiDB Cloud, y después:

   ```bash
   pip install -r requirements.txt
   python scripts/init_db.py
   ```

2. Instalar Tesseract OCR:
   - Windows: `winget install UB-Mannheim.TesseractOCR`
   - Raspberry Pi / Debian: `sudo apt install tesseract-ocr`

## Uso

Definir dónde está cada espacio dentro del cuadro de la cámara:

```bash
python scripts/configurar_espacios.py
```

Arrancar el monitor:

```bash
python scripts/monitor.py
```

Dashboard con autenticación y roles (recomendado), en otra terminal:

```bash
cd web_django
python manage.py migrate
python manage.py crear_grupos
python manage.py crear_operador <usuario>   # o crear una cuenta Admin desde /admin/
python manage.py runserver 5051
```
→ <http://localhost:5051>

Dashboard original en Flask, sin autenticación:

```bash
python web/app.py
```
→ <http://localhost:5050>

Probar sin cámara:

```bash
python scripts/monitor.py --simular
```

En la Raspberry Pi, sin pantalla:

```bash
python scripts/monitor.py --sin-ventana
```

## Manejo de credenciales

Las credenciales nunca están en el código ni en el historial de git: viven en
`.env`, que está listado en `.gitignore`. El repositorio solo incluye
`.env.example`, una plantilla con valores ficticios. El acceso a la
Raspberry Pi está restringido a autenticación por llave pública.

## Consultas de ejemplo

```sql
USE estacionamiento_db;

-- Espacios disponibles ahora mismo
SELECT etiqueta FROM espacios WHERE estado = 'libre';

-- Vehículos actualmente adentro
SELECT s.placa, e.etiqueta, s.hora_entrada
FROM sesiones s
JOIN espacios e ON e.id = s.espacio_id
WHERE s.estado = 'activa';

-- Recaudación por día
SELECT DATE(fecha_cobro) AS dia, SUM(monto) AS total
FROM cobros GROUP BY dia ORDER BY dia DESC;

-- Placas que más visitan el parqueo (dato que un sistema de barrera no puede dar)
SELECT placa, COUNT(*) AS visitas
FROM sesiones GROUP BY placa ORDER BY visitas DESC LIMIT 10;

-- Cuánto se cobró con cada tarifa histórica
SELECT t.id, COUNT(*) AS cobros, SUM(c.monto) AS total
FROM cobros c JOIN tarifas t ON t.id = c.tarifa_id
GROUP BY t.id;
```
