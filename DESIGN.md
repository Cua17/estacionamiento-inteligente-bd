---
name: Registro de Estacionamiento
description: Un libro de caja en tinta oscura, reglado en los dos ejes, legible proyectado en un aula.
colors:
  tinta-fondo: "#0d100f"
  tinta-banda: "#171d1a"
  tinta: "#e9e7df"
  tinta-media: "#a3aba7"
  tinta-tenue: "#7a827e"
  rojo: "#e0685c"
  rojo-hondo: "#b8463c"
  rojo-velo: "rgba(224, 104, 92, 0.12)"
  filete: "rgba(233, 231, 223, 0.20)"
  filete-firme: "rgba(233, 231, 223, 0.36)"
  filete-columna: "rgba(233, 231, 223, 0.10)"
typography:
  display:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia, serif"
    fontSize: "5.25rem"
    fontWeight: 600
    lineHeight: 0.85
    letterSpacing: "-0.04em"
    fontFeature: "tnum 1, lnum 1"
  headline:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia, serif"
    fontSize: "1.875rem"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia, serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.02em"
    fontFeature: "tnum 1, lnum 1"
  body:
    fontFamily: "Segoe UI, system-ui, -apple-system, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  caption:
    fontFamily: "Segoe UI, system-ui, -apple-system, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Segoe UI, system-ui, -apple-system, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.12em"
  label-seccion:
    fontFamily: "Segoe UI, system-ui, -apple-system, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.16em"
  monto-cierre:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia, serif"
    fontSize: "2.25rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.02em"
    fontFeature: "tnum 1, lnum 1"
  concepto-cierre:
    fontFamily: "Segoe UI, system-ui, -apple-system, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.06em"
  subtotal:
    fontFamily: "Segoe UI, system-ui, -apple-system, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
    fontFeature: "tnum 1, lnum 1"
  aviso:
    fontFamily: "Segoe UI, system-ui, -apple-system, Helvetica Neue, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  eje-svg:
    fontFamily: "Segoe UI, system-ui, -apple-system, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "normal"
    fontFeature: "tnum 1, lnum 1"
  comando:
    fontFamily: "ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.8125em"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  none: "0"
  pastilla: "6px"
  punto: "50%"
spacing:
  paso: "4px"
  paso-2: "8px"
  paso-3: "12px"
  paso-4: "16px"
  paso-6: "24px"
  paso-8: "32px"
  paso-11: "44px"
  paso-14: "56px"
  paso-16: "64px"
components:
  renglon-libro:
    backgroundColor: "transparent"
    textColor: "{colors.tinta}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "{spacing.paso-3}"
  renglon-libro-alterno:
    backgroundColor: "{colors.tinta-banda}"
  renglon-libro-libre:
    textColor: "{colors.tinta-tenue}"
  encabezado-columna:
    backgroundColor: "transparent"
    textColor: "{colors.tinta-media}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "8px 12px"
  marca-margen:
    backgroundColor: "transparent"
    width: "4px"
    height: "100%"
  marca-margen-abierta:
    backgroundColor: "{colors.rojo}"
  aviso:
    backgroundColor: "{colors.rojo-velo}"
    textColor: "{colors.rojo}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "12px 16px"
  sello-punto:
    backgroundColor: "transparent"
    rounded: "{rounded.punto}"
    size: "9px"
  sello-punto-caido:
    backgroundColor: "{colors.rojo}"
    textColor: "{colors.rojo}"
    rounded: "{rounded.punto}"
    size: "9px"
  cierre-total:
    textColor: "{colors.rojo}"
    typography: "{typography.title}"
    rounded: "{rounded.none}"
    padding: "16px 0 12px"
  saldo-lleno:
    textColor: "{colors.rojo}"
    typography: "{typography.display}"
---

# Design System: Registro de Estacionamiento

## Overview

**Creative North Star: "El Libro de Caja"**

Esta es una superficie de operación construida como un libro contable, no como un panel de tarjetas. Cada vehículo, cada sesión y cada quetzal es un asiento en un renglón reglado que se agrega y nunca se borra. La estructura de la página son filetes y columnas: no hay tarjetas, no hay cajas redondeadas, no hay sombras. Donde un dashboard genérico agruparía en contenedores, este alinea en renglones y deja que la retícula del reglado haga todo el trabajo de separación.

La escena manda sobre el gusto. Esta pantalla se proyecta en un aula y se lee de lejos, y un proyector aplasta las diferencias sutiles: por eso el reglado va más firme de lo que se vería bien en una laptop (bandas al 6% de delta y no al 2%, filetes al 20-36% y no al 10%), y por eso la escala de tipo arranca en 17px con piso duro de 13px. Cuando la escala subió y el primer viewport se caía por debajo del pliegue, el espacio se recuperó del ritmo vertical, nunca achicando la tipografía. La misma regla gobierna la adaptación: a pantallas angostas se colapsan columnas de detalle, el texto no se encoge.

El color es casi todo ausencia de color. Tres niveles de tinta sobre un fondo oscuro con deriva verde (el fantasma del papel continuo rayado) hacen toda la jerarquía; el rojo de libro contable es la única tinta de acento y aparece solo donde hay dinero, un asiento abierto o una falla. Rechazos confirmados: la retícula de tarjetas redondeadas con número grande, el gráfico de líneas decorativo, y las barras sueltas para la ocupación por hora (el eje de 24 horas es una sola línea continua de tinta).

**Key Characteristics:**
- Reglado en los dos ejes como única estructura: renglones firmes, columnas tenues, cero tarjetas
- Fondo tinta oscura con deriva verde; bandas alternas al 6% de delta
- Rojo de libro contable como única tinta de acento
- Cifras tabulares en todas partes: los dígitos se apilan columna sobre columna
- Escala de tipo dimensionada para proyección, con piso de 13px
- Superficie plana: sin sombras, sin radios, sin elevación
- Un solo momento de movimiento en toda la página

## Colors

Una paleta de tinta sobre papel oscuro: tres grises medidos contra el fondo y un solo rojo contable que solo se gasta en dinero, asientos abiertos y fallas.

### Primary
- **Rojo de Libro Contable** (`{colors.rojo}`): la única tinta de acento. Marca montos en quetzales, la marca de margen de un asiento abierto, el perfil y el pico del campo de horas, el total del mes, el saldo cero de parqueo lleno, el caret y el anillo de foco.
- **Rojo Hondo** (`{colors.rojo-hondo}`): el rojo asentado. Filetes del aviso de estado y fondo de `::selection`. Nunca se usa como color de texto.
- **Velo de Rojo** (`{colors.rojo-velo}`): el rojo casi transparente. Fondo del aviso, relleno del área bajo el perfil de horas, y color de arranque de la animación de asiento.

### Neutral
- **Tinta de Fondo** (`{colors.tinta-fondo}`): el papel. Negro con deriva verde, nunca negro puro. Fondo de toda la página y borde del pulgar de la barra de desplazamiento.
- **Banda Alterna** (`{colors.tinta-banda}`): el fantasma del papel continuo. Fondo de los renglones pares de cada libro, al 6% de delta contra el fondo para sobrevivir a un proyector.
- **Tinta** (`{colors.tinta}`): la tinta plena, 15.4:1 contra el fondo. Cuerpo de texto, títulos, cifras, y el dato de un renglón ocupado.
- **Tinta Media** (`{colors.tinta-media}`): la tinta de rótulo, 8.1:1. Encabezados de columna, folio, rótulos en versalitas, escalas del campo de horas, estados vacíos.
- **Tinta Tenue** (`{colors.tinta-tenue}`): la tinta pálida, 4.8:1. Renglones libres, notas de sección, detalles de la sumatoria, procedencia, placa sin identificar.
- **Filete** (`{colors.filete}`): el renglón normal. Borde inferior de cada fila del libro.
- **Filete Firme** (`{colors.filete-firme}`): el renglón fuerte. Cierre de cabecera, encabezados de columna, base del campo de horas, doble raya de cierre, pulgar de la barra de desplazamiento.
- **Filete de Columna** (`{colors.filete-columna}`): el reglado vertical. Separadores entre columnas, guías y divisores del campo de horas.

### Named Rules

**La Regla de Una Sola Tinta.** El rojo significa exactamente tres cosas: hay dinero, hay un asiento abierto, o algo falló. Nunca se usa para decorar, para jerarquizar títulos ni para diferenciar secciones. Si una superficie nueva quiere rojo y no está mostrando ninguna de esas tres cosas, la respuesta es tinta media.

**La Regla del Contraste Proyectado.** Todo color de texto sale de los tres niveles de tinta y ninguno baja de 4.5:1 contra el fondo. Ningún gris nuevo entra al sistema sin su ratio medido; la pantalla se proyecta y el contraste real siempre baja.

**La Regla de la Forma Antes que el Color.** Un estado nunca se distingue solo por color. Conexión viva es un punto hueco, conexión caída es un punto relleno; asiento abierto es una marca de margen entintada, renglón libre es margen sin tinta. El color confirma lo que la forma ya dijo.

## Typography

**Display Font:** Iowan Old Style, con Palatino Linotype / Palatino / Book Antiqua / Georgia como respaldo (en Windows resuelve a Palatino Linotype, verificado por ancho de avance)
**Body Font:** Segoe UI, con system-ui / -apple-system / Helvetica Neue / Arial como respaldo
**Mono Font:** ui-monospace, con Cascadia Mono / Consolas como respaldo; solo para nombres de comando dentro de estados vacíos

**Character:** Una serif de libro para las cifras que mandan y los títulos, una sans de sistema para todo lo que es dato y rótulo. La serif le da a los números el peso de un asiento escrito; la sans mantiene el registro legible a densidad de tabla. Ambas pilas tienen figuras tabulares verificadas (ancho de avance idéntico entre `1111111111` y `0000000000`). Se usa pila de sistema y no una cara self-hosted por decisión declarada: esta es una superficie Operate, donde la pila de sistema y las caras de trabajo están explícitamente permitidas.

### Hierarchy
- **Display** (serif, 600, 84px, 0.85, -0.04em, tabular): el saldo de espacios libres. Una sola instancia por pantalla; es la cifra que se lee desde el fondo del aula.
- **Headline** (serif, 600, 30px, 1.15, -0.015em): el título del libro en la cabecera.
- **Title** (serif, 600, 28px, -0.02em, tabular): los montos de la sumatoria. El total de cierre sube a 36px y se entinta de rojo.
- **Body** (sans, 400, 17px, 1.5): celdas del libro y texto corrido. Punto de partida de la escala; deliberadamente por encima de los 15-16px habituales de un panel.
- **Caption** (sans, 400, 14px): notas de sección, detalles de la sumatoria, procedencia, rótulo del sello. Texto de prosa limitado a 70ch.
- **Label** (sans, 600, 13px, 0.12em, versalitas): encabezados de columna de todas las tablas.
- **Label de Sección** (sans, 600, 14px, 0.16em, versalitas): los títulos `h2` de cada sección del libro.

Escala completa en uso, en px: 13, 14, 15, 16, 17, 20, 28, 30, 36, 84.

### Named Rules

**La Regla del Piso de 13px.** Ningún texto baja de 13px, en ninguna pantalla, en ningún estado. La escena es una proyección de aula y ese es el límite de legibilidad medido, no una preferencia.

**La Regla de la Cifra Tabular.** Todo número que se pueda comparar con el número de arriba lleva `tabular-nums lining-nums`: montos, tiempos, placas, saldos, escalas del gráfico. Una cifra proporcional en una columna rompe el libro.

**La Regla de la Serif para Cifras.** La serif se reserva para el título y para números que son un resultado (saldo, montos de sumatoria). Los datos de renglón van en sans. Mezclar las dos dentro de una misma columna está prohibido.

## Layout

Una sola hoja centrada de 1180px máximo, con 32px de aire lateral y 64px de aire inferior. Todo el ritmo vertical se construye con múltiplos del paso base de 4px: 8, 12, 16, 24, 32, 44, 56, 64. Las secciones se separan con 44px, el pie con 56px.

La composición es una columna de secciones apiladas, cada una con un encabezado en versalitas a la izquierda y una nota tenue a la derecha, seguida de un libro a todo el ancho. La cabecera es una excepción deliberada: título y folio a la izquierda, saldo alineado a la derecha en una retícula de dos columnas con la cifra dominante ocupando ambas filas. El primer viewport (cabecera + registro de espacios + campo de horas) está medido para entrar en 900px de alto con 20px de holgura.

La adaptación es estructural, no fluida. En el único punto de corte (780px) el aire lateral baja a 16px, la cabecera se apila a la izquierda y se ocultan las columnas de detalle de cada libro (la cuarta del registro de espacios, la sexta de la bitácora). La tipografía no se encoge: la única excepción son las cifras de exhibición, que bajan de 84 a 64px, el título de 30 a 24px y los montos de sumatoria de 28/36 a 22/28px, porque a ese ancho ya no caben en su renglón.

### Named Rules

**La Regla del Colapso Estructural.** Cuando el ancho no alcanza, se quitan columnas; no se encoge el texto. En un panel operativo el tamaño de lectura tiene que quedarse quieto.

**La Regla del Paso de 4px.** Todo espaciado sale de `calc(var(--paso) * N)`. Un valor de espaciado escrito a mano no entra al sistema.

## Elevation & Depth

El sistema es plano por definición: **no hay una sola sombra en toda la construcción**. Un libro de caja no tiene profundidad, tiene reglado. La separación se consigue con tres recursos y ninguno más: filetes horizontales entre renglones, filetes verticales entre columnas, y bandas alternas al 6% de delta contra el fondo. La única variación tonal de superficie que existe es esa banda; no hay capas, ni contenedores elevados, ni desenfoques de fondo.

El peso relativo se comunica por firmeza de filete, no por altura: filete tenue para columnas, filete normal para renglones, filete firme para cierres de sección, y doble raya de 3px reservada para un único elemento en toda la página.

### Named Rules

**La Regla de la Página Plana.** Cero `box-shadow`, cero `filter: drop-shadow`, cero gradientes de superficie. Si un elemento nuevo necesita separarse de lo que tiene alrededor, se separa con un filete o con una banda.

**La Regla de la Doble Raya.** La doble raya de 3px significa "este total cierra" y está reservada al total del mes. Un subtotal (como la suma de los movimientos a la vista) lleva filete simple. Gastar la doble raya en algo que no cierra vacía el gesto.

## Shapes

Todo es cuadrado. El radio por defecto del sistema es 0 y no hay excepciones para contenido: ni tablas, ni el aviso de estado, ni el campo de horas, ni ningún bloque de texto llevan esquinas redondeadas. Las dos únicas curvas de la construcción son funcionales y microscópicas: el punto del sello de conexión (círculo de 9px, `50%`) y el pulgar de la barra de desplazamiento (6px).

El vocabulario de forma se reduce a líneas: filete de 1px para renglones y columnas, filete de 2px para el cierre de cabecera y el pie, doble raya de 3px para el total que cierra, y una barra vertical sólida de 4px como marca de margen. Los bordes se aplican por lado (`border-bottom`, `border-right`, `border-top`), nunca como caja completa: un contorno de cuatro lados construiría una tarjeta, que es exactamente lo que este mundo rechaza.

## Components

### Libro (tabla reglada)
El componente central; toda la información tabular del proyecto vive en uno.
- **Forma:** sin radio, `border-collapse: collapse`, ancho completo.
- **Encabezados:** versalitas de 13px en tinta media, alineados a la izquierda salvo las columnas numéricas, cerrados con filete firme.
- **Celdas:** 12px de relleno, `vertical-align: baseline`, filete normal debajo, filete de columna a la derecha en toda columna que no sea la de marca ni la última.
- **Bandas:** los renglones pares llevan fondo de banda alterna.
- **Estados de fila:** `ocupado` lleva la placa y el espacio en tinta plena; `libre` baja toda la fila a tinta tenue con el espacio en tinta media.
- **Columnas numéricas:** alineadas a la derecha y siempre con figuras tabulares.

### Marca de Margen
La primera columna de cada libro es una franja de 4px sin relleno que hace de marca de margen. Entintada de rojo significa asiento abierto (espacio ocupado, o movimiento de salida); sin tinta significa renglón en blanco, como en un libro de verdad. Alto mínimo de 3rem para que la marca sobreviva a un renglón corto.

### Saldo (cifra dominante)
- **Composición:** retícula de dos columnas; la cifra ocupa ambas filas a la izquierda, con "de N" y el rótulo en versalitas apilados a la derecha, alineados por línea de base.
- **Cifra:** serif de 84px, peso 600, interlínea 0.85, tabular.
- **Estado lleno:** cuando el saldo es cero, la cifra se entinta de rojo (`saldo--lleno`). Es el único cambio; no aparece ningún elemento nuevo.
- **Accesibilidad:** el bloque es `aria-live="polite"` y solo se reescribe cuando el valor cambió.

### Aviso de Estado
- **Estilo:** franja a todo el ancho con velo de rojo de fondo y filete de rojo hondo arriba y abajo, sin filetes laterales y sin radio. Texto en rojo a 16px.
- **Comportamiento:** `role="alert"`, oculto por defecto. Aparece recién a la segunda lectura fallida seguida, para que un parpadeo de red no interrumpa una demostración.

### Sumatoria
Bloque de conceptos a la izquierda y montos alineados en una sola columna a la derecha, con ancho máximo de 560px para que los quetzales se apilen dígito sobre dígito. Cada concepto puede llevar un detalle en tinta tenue debajo. La fila de cierre lleva relleno superior extra, concepto en versalitas, monto en rojo a 36px y la doble raya que cierra el total. El pie de la bitácora usa la misma alineación pero con filete simple y rótulo en versalitas de 13px: es un subtotal, no un cierre.

### Sello de Conexión
- **Estilo:** punto de 9px con borde de 2px y el texto de procedencia al lado, en caption de 14px.
- **Viva:** punto hueco con borde en tinta media; texto en tinta media con la hora de la última lectura.
- **Caída:** punto relleno de rojo con borde de rojo; toda la línea se entinta de rojo y el texto conserva la hora del último dato bueno.
- **Regla:** la diferencia entre los dos estados es de forma (hueco vs. relleno) antes que de color, porque proyectado el color solo no alcanza.

### Campo de Horas
Gráfico de área en SVG a todo el ancho, con perfil escalonado continuo sobre un eje de 24 horas. El área se rellena con velo de rojo, el perfil es una línea de rojo de 2px con uniones redondeadas, y los picos del máximo se marcan con un círculo lleno de 4px con `<title>` accesible. Las guías y los divisores cada 6 horas usan filete de columna; la línea base usa filete firme. Las etiquetas de hora van cada 3 horas en tinta media a 15px, y la franja de la hora actual sube a tinta plena con peso 600. Una hora sin sesiones es un valle sobre la base, nunca un hueco.

### Estado Vacío
Celda a todo el ancho de la tabla con 24px de relleno vertical, texto en tinta media a 16px, y el comando exacto a ejecutar en mono al 0.8125em. El estado vacío enseña qué hacer; nunca es solo "sin datos".

### Superficies del Navegador
Tematizadas explícitamente y parte del sistema: `::selection` en rojo hondo sobre blanco, `caret-color` en rojo, `:focus-visible` con contorno de 2px en rojo y 2px de separación, barra de desplazamiento fina con pulgar en filete firme sobre pista transparente.

### Movimiento
Un solo momento en toda la página: el keyframe `asentar`, de 260ms con `cubic-bezier(0.16, 1, 0.3, 1)`, que arranca desde velo de rojo y 2px arriba y aterriza en transparente sin desplazamiento. Se aplica únicamente al renglón cuyo contenido cambió, identificado por una llave estable del movimiento (no por su índice en la lista), y se anula por completo bajo `prefers-reduced-motion`.

**La Regla del Único Momento.** El proyecto tiene una sola animación y es el asiento de un renglón. No hay transiciones de hover, ni fundidos de entrada, ni animación de carga. Una superficie nueva que quiera movimiento tiene que justificar por qué el asiento no le sirve.

## Do's and Don'ts

### Do:
- **Do** construir toda estructura nueva con filetes y columnas: renglón firme arriba, filete de 1px entre filas, filete de columna entre columnas.
- **Do** aplicar figuras tabulares (`tabular-nums lining-nums`) a cualquier cifra que se compare verticalmente.
- **Do** medir el ratio de contraste de cualquier tono nuevo contra el fondo y descartarlo si no llega a 4.5:1.
- **Do** distinguir estados por forma antes que por color, y confirmar con color después.
- **Do** derivar todo espaciado de `calc(var(--paso) * N)` con el paso de 4px.
- **Do** resolver la falta de ancho quitando columnas de detalle y dejando la tipografía quieta.
- **Do** escribir estados vacíos que enseñen el comando o la acción exacta que falta.
- **Do** anular cualquier movimiento bajo `prefers-reduced-motion`.

### Don't:
- **Don't** meter tarjetas: nada de contorno de cuatro lados, nada de radio sobre un bloque de contenido, nada de retícula de recuadros del mismo tamaño.
- **Don't** agregar sombras, gradientes de superficie ni desenfoques de fondo; el sistema no tiene elevación.
- **Don't** gastar el rojo en decoración, jerarquía de títulos o diferenciación de secciones: solo dinero, asiento abierto o falla.
- **Don't** bajar ningún texto de 13px, ni siquiera en pantallas angostas.
- **Don't** usar la doble raya de 3px en algo que no sea un total que cierra.
- **Don't** representar series temporales con barras sueltas: el eje de horas es una línea continua y una hora en cero es un valle, no un hueco.
- **Don't** agregar una segunda animación; el asiento de renglón es el único momento de movimiento del proyecto.
- **Don't** usar emojis ni iconos de glifo tipográfico en la interfaz; la marca de margen, el punto del sello y el SVG del campo de horas son el vocabulario gráfico completo.
