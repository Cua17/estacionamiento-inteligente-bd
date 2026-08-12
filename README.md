# Estacionamiento Inteligente

Detección de espacios, registro de placas y facturación automática con visión
por computadora. Proyecto final del curso **Manejo de Base de Datos**.

Una cámara conectada a un Raspberry Pi lee la placa de cada vehículo que
ingresa a un parqueo, detecta en tiempo real qué espacios están libres u
ocupados, registra cada sesión en una base de datos relacional en la nube, y
calcula automáticamente el cobro por el tiempo estacionado.

Propuesta completa: `Propuesta_Proyecto_Final.pdf` (carpeta del curso).

## Estado por fase

| Fase | Estado |
|---|---|
| 1. Diseño de la base de datos | Hecho |
| 2. Estructura del repositorio | Hecho |
| 3. Prueba de concepto de OCR | Hecho — 4/4 con corrección por formato |
| 4. Detección de ocupación | Hecho — funciona con la webcam de la laptop |
| 6. Sesiones y facturación | Hecho — motor en `scripts/parqueo.py` |
| 7. Dashboard web | Hecho |
| 0. Reset de la Raspberry Pi | Pendiente — falta el lector de microSD |
| 5. Integración con cámara en la Pi | Pendiente — depende de la fase 0 |
| 8. Pruebas en el parqueo real | Pendiente |
| 9. Documentación y entrega final | En curso |

## Arquitectura

```
              Cámara (webcam hoy, cámara de la Pi después)
                            |
                            v
    monitor.py  ── ocupacion.py ──> ¿ocupado o libre por espacio?
        |       └─ vision.py    ──> ¿qué placa es?
        |
        v
    parqueo.py  ──> abre y cierra sesiones, calcula el cobro
        |
        |  protocolo MySQL sobre TLS
        v
    TiDB Cloud · base `estacionamiento_db`
        |
        v
    web/app.py ── reportes.py ──> dashboard en el navegador
```

El monitor **escribe** y el dashboard solo **lee**, así que se pueden correr en
máquinas distintas: el monitor en la Raspberry Pi junto a la cámara, el
dashboard en cualquier laptop.

## Módulos

| Archivo | Qué hace |
|---|---|
| `scripts/monitor.py` | Programa principal: cámara → detección → base de datos |
| `scripts/parqueo.py` | Motor de negocio: sesiones, cobros, estado de espacios |
| `scripts/vision.py` | Lectura de placas: preprocesamiento, OCR y corrección por formato |
| `scripts/ocupacion.py` | Detección de ocupación por densidad de textura |
| `scripts/camara.py` | Acceso a la cámara (Windows y Linux/Raspberry Pi) |
| `scripts/reportes.py` | Consultas de solo lectura para el dashboard |
| `scripts/db.py` | Conexión a TiDB Cloud |
| `web/app.py` | Servidor del dashboard y su API JSON |

Herramientas de apoyo: `configurar_espacios.py` (dibuja las regiones de los
espacios), `capturar_placa.py` (lee placas en vivo), `simulacion_demo.py`
(demo sin cámara), `generar_datos_demo.py` y `reset_demo.py`.

## Base de datos

Definida en [`schema.sql`](schema.sql). Cinco tablas relacionadas:

| Tabla | Contenido |
|---|---|
| `vehiculos` | Una fila por placa detectada. La placa es la llave primaria |
| `espacios` | Cada espacio físico con su estado actual (`libre` / `ocupado`) |
| `tarifas` | Precio por hora, con historial: las tarifas viejas se cierran, no se borran |
| `sesiones` | Qué placa ocupó qué espacio, con hora de entrada y de salida |
| `cobros` | El monto generado al cerrar cada sesión |

Relaciones: `sesiones.placa → vehiculos.placa`, `sesiones.espacio_id →
espacios.id`, `cobros.sesion_id → sesiones.id` (única: un cobro por sesión) y
`cobros.tarifa_id → tarifas.id`.

Índices en `espacios.estado` (para contar libres), `sesiones.placa` (historial
por vehículo) y `sesiones(espacio_id, estado)` (para encontrar la sesión activa
de un espacio, que es la consulta más frecuente del monitor).

## Decisiones de diseño que vale la pena explicar

- **La tarifa nunca se borra, se cierra.** Cambiar el precio inserta una tarifa
  nueva y le pone `vigente_hasta` a la anterior. Así un cobro viejo se puede
  seguir explicando con la tarifa que estaba vigente ese día.
- **Una placa ilegible se registra como `DESCONOCIDA`.** Inventar una placa
  parecida le cobraría a un tercero; es peor que admitir que no se supo.
- **El estado inicial lo manda la base, no la cámara.** Al arrancar, el monitor
  parte de lo que dice la base de datos. Si tomara como estado inicial el
  primer cuadro que ve, un carro ya estacionado al encender el sistema no se
  registraría nunca.
- **El tiempo se calcula en Python, no con `NOW()` del servidor.** Las horas se
  guardan con la hora local de la máquina que corre el monitor, y el servidor
  de TiDB está en otro huso horario: comparar allá inflaba los minutos.
- **Se cobra el minuto empezado** (`ceil`, mínimo 1 minuto), como un parqueo
  real.

## Instalación

1. Crear la base de datos y las tablas:

   ```bash
   cp .env.example .env
   ```

   Llenar `.env` con las credenciales de TiDB Cloud, y después:

   ```bash
   pip install -r requirements.txt
   ```

   ```bash
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

Arrancar el dashboard (en otra terminal) y abrir <http://localhost:5050>:

```bash
python web/app.py
```

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
`.env.example`, una plantilla con valores ficticios.

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

-- Placas que más visitan el parqueo
SELECT placa, COUNT(*) AS visitas
FROM sesiones GROUP BY placa ORDER BY visitas DESC LIMIT 10;

-- Cuánto se cobró con cada tarifa histórica
SELECT t.nombre, t.precio_por_hora, COUNT(*) AS cobros, SUM(c.monto) AS total
FROM cobros c JOIN tarifas t ON t.id = c.tarifa_id
GROUP BY t.id, t.nombre, t.precio_por_hora;
```
