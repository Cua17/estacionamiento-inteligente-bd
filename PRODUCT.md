# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Dos audiencias, hoy con pesos muy distintos:

- **Primaria hoy: el docente evaluador** (Victor Vargas, curso Manejo de Base de
  Datos). Ve el sistema proyectado en clase, a distancia, durante minutos, y
  juzga si la base de datos relacional está bien diseñada y realmente viva.
  Toda decisión de diseño se mide contra esta escena.
- **Objetivo del producto: el administrador de un parqueo pequeño o mediano**
  en Guatemala, que hoy lleva el control a mano o no lo lleva. Necesita saber
  cuántos espacios hay libres, quién está adentro y cuánto se recaudó.

El conductor que entra al parqueo es beneficiario del sistema (ve la
disponibilidad), pero no es quien usa este dashboard.

## Product Purpose

Automatizar por completo un parqueo con una sola cámara y un Raspberry Pi:
leer la placa de cada vehículo que entra, detectar por visión por computadora
qué espacios están libres u ocupados, registrar cada sesión de estacionamiento
en una base de datos relacional en la nube, y calcular el cobro automáticamente
al salir.

Éxito para el curso: que se vea el sistema funcionando de punta a punta contra
una base de datos real, no una maqueta.
Éxito para el producto: que un parqueo sin ningún control automatizado pueda
tenerlo sin instalar barreras, tiquetes ni sensores.

## Positioning

Solo depende de una cámara y un Raspberry Pi: no hay barrera, ni tiquetera, ni
sensor por espacio. Eso lo pone a un costo que un parqueo pequeño puede pagar,
y de paso le da algo que los sistemas de barrera no le dan: el registro por
placa, que permite saber qué vehículos vuelven y con qué frecuencia.

## Operating Context

- El monitor (`scripts/monitor.py`) corre en la Raspberry Pi junto a la cámara,
  en el parqueo, sin pantalla, y escribe directo a la base en la nube.
- El dashboard se abre aparte, en la laptop, y solo lee de esa misma base.
- Para la entrega, el docente pidió ver una señal de que funciona ("un hola
  mundo"), no solo código en un repositorio.
- La demo final se hará en el parqueo real de la universidad. Mientras tanto se
  prueba con la webcam de la laptop y placas impresas.
- Moneda: quetzal (Q). Tarifa vigente en la base: Q5.00/hora.
- Formato de placa: Guatemala, 1 letra + 3 dígitos + 3 letras (ej. P123ABC).

## Capabilities and Constraints

Funciona hoy:

- Base de datos relacional en TiDB Cloud (compatible MySQL), 5 tablas:
  `vehiculos`, `espacios`, `tarifas`, `sesiones`, `cobros`.
- OCR de placas con Tesseract, con corrección por el formato guatemalteco.
- Detección de ocupación por densidad de textura con umbral adaptativo, con
  filtro anti-parpadeo para no abrir y cerrar sesiones falsas.
- Cálculo de cobro prorrateado por minuto, cobrando el minuto empezado.

Restricciones:

- Todavía no hay cámara externa: se usa la webcam de la laptop.
- El cobro solo puede calcularse cuando la sesión se cierra; antes de eso no
  existe monto, solo tiempo transcurrido.
- Si la placa no se lee con un formato válido, el vehículo se registra como
  `DESCONOCIDA` en vez de inventar una placa (cobrarle a la placa equivocada
  sería peor que no saberla).
- La hora se calcula del lado de Python, no con `NOW()` del servidor: el
  servidor de TiDB está en otro huso horario.

## Brand Commitments

- El dashboard va en tonos oscuros (pedido explícito del usuario).
- Sin emojis en la interfaz (pedido explícito).
- Todo el texto de cara al usuario, en español.

## Evidence on Hand

- Base de datos real y en vivo en TiDB Cloud, proyecto `estacionamiento-inteligente`.
- 4 placas de prueba en `test_images/`, tres sintéticas y una foto real de
  referencia de placa guatemalteca (`P123ABC`).
- Prueba de OCR medida: 3/4 con OCR crudo, 4/4 aplicando corrección por formato.
- Propuesta formal del proyecto en `Propuesta_Proyecto_Final.pdf`.
- No hay todavía datos de un parqueo real en operación: todo lo que muestra el
  dashboard proviene de sesiones generadas en pruebas.

## Product Principles

1. **Lo que se muestra tiene que haber pasado de verdad.** Los números salen de
   la base de datos, no de valores de ejemplo escritos en el código.
2. **No inventar identidad de un vehículo.** Ante una lectura dudosa, se
   registra `DESCONOCIDA`; una placa equivocada le cobra a un tercero.
3. **La base de datos es la que manda, no la cámara.** Al arrancar, el sistema
   parte del estado guardado y la cámara lo corrige, no al revés.
4. **El mismo código corre en la laptop y en la Raspberry Pi.** Lo único que
   cambia es de dónde sale la imagen.
5. **Cada limitación se documenta en vez de esconderse.** Es un proyecto de
   curso: explicar por qué algo falla vale tanto como que funcione.

## Accessibility & Inclusion

El dashboard se proyecta en un aula y se lee a distancia: el tamaño de texto y
el contraste tienen que aguantar esa escena, no solo una laptop de cerca.
