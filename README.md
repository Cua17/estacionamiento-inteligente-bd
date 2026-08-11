# Estacionamiento Inteligente — Detección de Espacios, Registro de Placas y Facturación Automática

Proyecto final del curso **Manejo de Base de Datos**.

Un Raspberry Pi con cámara lee la placa de cada vehículo que ingresa a un
parqueo, detecta en tiempo real qué espacios están libres u ocupados,
registra cada sesión de estacionamiento en una base de datos relacional en
la nube, y calcula automáticamente el cobro según el tiempo estacionado.

Ver la propuesta completa en `Propuesta_Proyecto_Final.pdf` (carpeta del curso).

## Estado actual del proyecto

| Fase | Estado |
|---|---|
| 0. Reset y preparación de la Raspberry Pi | 🔲 En progreso |
| 1. Diseño de la base de datos | ✅ Hecho |
| 2. Estructura del repositorio | ✅ Hecho |
| 3. Prueba de concepto de OCR de placas | 🔲 En progreso |
| 4. Detección de ocupación de espacios | ⬜ Pendiente |
| 5. Integración cámara + Raspberry Pi | ⬜ Pendiente (falta conseguir cámara) |
| 6. Lógica de sesiones y facturación | ⬜ Pendiente |
| 7. Interfaz web de disponibilidad | ⬜ Pendiente |
| 8. Pruebas end-to-end (modelo a escala → parqueo real) | ⬜ Pendiente |
| 9. Documentación y entrega final | ⬜ Pendiente |

## Arquitectura planeada

```
   Cámara (Pi Camera / USB)
          │
          ▼
   Raspberry Pi 4 — Python + OpenCV
     ├── Lectura de placa (OCR)
     └── Detección de ocupación por espacio
          │  MySQL protocol sobre TLS
          ▼
   TiDB Cloud Starter — base `estacionamiento_db`
          │
          ▼
   Página web simple — disponibilidad en tiempo real
```

## Base de datos

Definida en [`schema.sql`](schema.sql), 5 tablas conectadas entre sí:

- **`vehiculos`** — cada placa detectada, una fila por placa (llave primaria).
- **`espacios`** — cada espacio físico del parqueo, con su estado actual (`libre` / `ocupado`).
- **`tarifas`** — precio por hora vigente, con historial (no se borran las viejas).
- **`sesiones`** — qué placa ocupó qué espacio, hora de entrada y de salida.
- **`cobros`** — el monto generado al cerrar cada sesión, según la tarifa vigente.

Relaciones: `sesiones.placa → vehiculos.placa`, `sesiones.espacio_id → espacios.id`,
`cobros.sesion_id → sesiones.id` (única, un cobro por sesión), `cobros.tarifa_id → tarifas.id`.

## Instalación

1. Crear la base de datos y las tablas:

   ```bash
   cp .env.example .env
   # llenar .env con las credenciales del cluster de TiDB Cloud
   pip install -r requirements.txt
   python scripts/init_db.py
   ```

2. (Cuando la Raspberry Pi esté lista) instalar Tesseract OCR y las dependencias
   de visión por computadora — ver `scripts/README.md` cuando exista.

## Manejo de credenciales

Igual que en el proyecto de sismos del mismo curso: las credenciales viven en
`.env` (gitignoreado, nunca se sube) y `.env.example` es la plantilla pública.
En la nube (si luego se automatiza algo con GitHub Actions) irían como
GitHub Secrets.

## Consultas de ejemplo

```sql
-- Espacios disponibles ahora mismo
SELECT etiqueta FROM espacios WHERE estado = 'libre';

-- Sesiones activas (vehículos actualmente estacionados)
SELECT s.placa, e.etiqueta, s.hora_entrada
FROM sesiones s
JOIN espacios e ON e.id = s.espacio_id
WHERE s.estado = 'activa';

-- Recaudación total por día
SELECT DATE(fecha_cobro) AS dia, SUM(monto) AS total
FROM cobros
GROUP BY dia
ORDER BY dia DESC;

-- Placas que más visitan el parqueo
SELECT placa, COUNT(*) AS visitas
FROM sesiones
GROUP BY placa
ORDER BY visitas DESC
LIMIT 10;
```
