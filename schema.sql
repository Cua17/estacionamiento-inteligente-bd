-- Estructura de la base de datos para el proyecto final
-- "Estacionamiento Inteligente: Detección de Espacios, Registro de Placas
--  y Facturación Automática con Visión por Computadora"
-- Curso: Manejo de Base de Datos
-- Motor: TiDB Cloud Starter (compatible con el protocolo y la sintaxis de MySQL)
--
-- Ejecutar este script desde el SQL Editor de la consola web de TiDB Cloud,
-- o con scripts/init_db.py (ver README).

-- ─────────────────────────────────────────────────────────────────────────
-- 1) VEHICULOS: cada placa detectada por el sistema, una sola vez por placa.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vehiculos (
    placa               VARCHAR(15)  NOT NULL PRIMARY KEY,  -- placa leída por OCR (normalizada, sin espacios)
    primera_deteccion   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- primera vez que el sistema vio esta placa
    notas               VARCHAR(255) NULL                   -- uso libre (ej. "cliente frecuente")
);

-- ─────────────────────────────────────────────────────────────────────────
-- 2) ESPACIOS: cada espacio físico del parqueo, identificado individualmente.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS espacios (
    id                  INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    etiqueta            VARCHAR(10)  NOT NULL UNIQUE,       -- identificador visible del espacio, ej. "A1", "A2"
    estado              ENUM('libre', 'ocupado') NOT NULL DEFAULT 'libre',
    actualizado_en      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_estado (estado)  -- para consultar rápido "cuántos espacios libres hay ahora"
);

-- ─────────────────────────────────────────────────────────────────────────
-- 3) TARIFAS: el precio por hora vigente. Se guarda historial, no se borra.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tarifas (
    id                  INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nombre              VARCHAR(50)   NOT NULL,             -- ej. "Tarifa estándar"
    precio_por_hora     DECIMAL(8,2)  NOT NULL,
    vigente_desde       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    vigente_hasta       DATETIME      NULL,                 -- NULL = todavía vigente

    INDEX idx_vigencia (vigente_desde, vigente_hasta)
);

-- ─────────────────────────────────────────────────────────────────────────
-- 3b) TARIFA_TRAMOS: el precio escalonado de cada tarifa.
--
-- Un parqueo real no cobra un precio plano: da unos minutos de gracia y
-- después sube el precio por hora mientras más tiempo se queda el vehículo.
-- Cada fila dice "desde este minuto, la hora vale tanto", y rige hasta que
-- empieza el tramo siguiente; el último queda abierto.
--
-- Está en su propia tabla (y no como columnas de `tarifas`) porque la
-- cantidad de tramos es variable: una tarifa puede tener dos escalones y
-- otra cinco. Así también queda historial: al cerrar una tarifa, sus tramos
-- se conservan y un cobro viejo se puede seguir explicando.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tarifa_tramos (
    id                  INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tarifa_id           INT           NOT NULL,
    desde_minuto        INT           NOT NULL,   -- desde qué minuto acumulado aplica
    precio_por_hora     DECIMAL(8,2)  NOT NULL,   -- 0.00 = tramo gratis

    FOREIGN KEY (tarifa_id) REFERENCES tarifas(id),

    -- Dos tramos de la misma tarifa no pueden empezar en el mismo minuto:
    -- sería ambiguo cuál precio aplicar.
    UNIQUE KEY uq_tarifa_desde (tarifa_id, desde_minuto)
);

-- ─────────────────────────────────────────────────────────────────────────
-- 4) SESIONES: cada vez que una placa ocupa un espacio, de entrada a salida.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sesiones (
    id                  INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
    placa               VARCHAR(15)   NOT NULL,
    espacio_id          INT           NOT NULL,
    hora_entrada        DATETIME      NOT NULL,
    hora_salida         DATETIME      NULL,                 -- NULL mientras la sesión sigue activa
    estado              ENUM('activa', 'cerrada') NOT NULL DEFAULT 'activa',

    FOREIGN KEY (placa) REFERENCES vehiculos(placa),
    FOREIGN KEY (espacio_id) REFERENCES espacios(id),

    INDEX idx_placa (placa),
    INDEX idx_espacio_estado (espacio_id, estado)  -- para encontrar rápido "la sesión activa de este espacio"
);

-- ─────────────────────────────────────────────────────────────────────────
-- 5) COBROS: el monto generado al cerrar cada sesión.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cobros (
    id                  INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sesion_id           INT           NOT NULL UNIQUE,      -- una sesión genera como máximo un cobro
    tarifa_id           INT           NOT NULL,
    minutos_totales     INT           NOT NULL,
    monto               DECIMAL(10,2) NOT NULL,
    fecha_cobro         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (sesion_id) REFERENCES sesiones(id),
    FOREIGN KEY (tarifa_id) REFERENCES tarifas(id)
);

-- ─────────────────────────────────────────────────────────────────────────
-- Datos iniciales de ejemplo: espacios y una tarifa vigente.
-- Ajustar la cantidad de espacios al modelo real que se use en la demo.
-- ─────────────────────────────────────────────────────────────────────────
INSERT IGNORE INTO espacios (etiqueta) VALUES ('A1'), ('A2'), ('A3'), ('A4');

-- precio_por_hora queda como precio de referencia de la tarifa (el del
-- tramo principal); el cobro real se calcula con tarifa_tramos.
INSERT IGNORE INTO tarifas (id, nombre, precio_por_hora) VALUES (1, 'Tarifa estándar', 5.00);

-- Escalonado: 15 min de gracia, después el precio por hora va subiendo.
INSERT IGNORE INTO tarifa_tramos (tarifa_id, desde_minuto, precio_por_hora) VALUES
    (1,   0,  0.00),   -- primeros 15 minutos: gratis
    (1,  15,  5.00),   -- de 15 min a 1 hora
    (1,  60,  7.00),   -- segunda hora
    (1, 120, 10.00);   -- de la tercera hora en adelante
