/*
  El libro se lleva solo: consulta el estado cada pocos segundos y reescribe
  los renglones que cambiaron.

  Se consulta por fetch en vez de recargar la página entera con un
  meta-refresh: una recarga completa parpadea y pierde la posición del
  scroll, que proyectado en un aula se nota muchísimo. Así solo se reescribe
  lo que cambió, y el renglón que cambia se puede asentar con un movimiento.
*/

const INTERVALO_MS = 3000;
const LECTURAS_FALLIDAS_PARA_AVISAR = 2;

const $ = (id) => document.getElementById(id);

let huellas = new Map();   // clave estable de renglón -> huella de su contenido
let fallosSeguidos = 0;
let ultimoExito = null;
let primeraCarga = true;

/* ── Formato ──────────────────────────────────────────────────────── */

/* La placa viene de OCR sobre una imagen. Hoy vision.py la filtra a A-Z0-9,
   pero eso es una garantía de otro módulo, no de este: si mañana se acepta
   otro formato, este archivo no se puede volver una inyección de HTML. */
const escapar = (valor) => String(valor ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));

const quetzales = (valor) =>
  "Q" + Number(valor).toLocaleString("es-GT", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

function duracion(minutos) {
  if (minutos === null || minutos === undefined) return "—";
  if (minutos < 60) return `${minutos} min`;
  const horas = Math.floor(minutos / 60);
  const resto = minutos % 60;
  return resto === 0 ? `${horas} h` : `${horas} h ${resto} min`;
}

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

function fechaLarga() {
  return new Date().toLocaleDateString("es-GT", {
    day: "2-digit", month: "long", year: "numeric",
  });
}

/* Cobro acumulado de una sesión que sigue abierta: lo que pagaría si el
   vehículo saliera en este momento. Se cobra el minuto empezado, igual que
   en parqueo.py, para que la pantalla no prometa un número distinto al que
   la base va a guardar. */
function cobroCorrido(minutos, precioPorHora) {
  if (minutos === null || precioPorHora === null) return null;
  return (Math.max(1, Math.ceil(minutos)) * precioPorHora) / 60;
}

function marcarSiCambio(clave, huella) {
  const cambio = !primeraCarga && huellas.get(clave) !== huella;
  huellas.set(clave, huella);
  return cambio ? "asentando" : "";
}

function celdaPlaca(placa) {
  if (placa === "DESCONOCIDA") {
    return '<span class="placa placa--desconocida">sin identificar</span>';
  }
  return `<span class="placa">${escapar(placa)}</span>`;
}

/* ── Renglones ────────────────────────────────────────────────────── */

function pintarEspacios(datos) {
  const cuerpo = $("cuerpo-espacios");
  const precio = datos.tarifa ? datos.tarifa.precio_por_hora : null;

  if (!datos.espacios.length) {
    cuerpo.innerHTML = `<tr><td colspan="6" class="vacio">
      No hay espacios dados de alta. Corré <code>python scripts/init_db.py</code>
      para crear la tabla con los espacios iniciales.</td></tr>`;
    return;
  }

  cuerpo.innerHTML = datos.espacios.map((espacio) => {
    const cobro = espacio.ocupado ? cobroCorrido(espacio.minutos, precio) : null;
    const clase = marcarSiCambio(
      "e:" + espacio.etiqueta,
      [espacio.ocupado, espacio.placa, espacio.desde].join("|"),
    );

    return `<tr class="${espacio.ocupado ? "ocupado" : "libre"} ${clase}">
      <td class="col-marca"><span class="marca ${espacio.ocupado ? "marca--activa" : ""}"></span></td>
      <td class="espacio">${escapar(espacio.etiqueta)}</td>
      <td>${espacio.ocupado ? celdaPlaca(espacio.placa) : "—"}</td>
      <td class="num">${escapar(espacio.desde ?? "—")}</td>
      <td class="num">${espacio.ocupado ? duracion(espacio.minutos) : "—"}</td>
      <td class="num ${cobro === null ? "monto--nulo" : "monto"}">
        ${cobro === null ? "—" : quetzales(cobro)}</td>
    </tr>`;
  }).join("");

  const ocupados = datos.total - datos.libres;
  $("nota-registro").textContent = ocupados === 0
    ? "Ningún vehículo adentro"
    : plural(ocupados, "vehículo adentro", "vehículos adentro");
}

function pintarBitacora(datos) {
  const cuerpo = $("cuerpo-bitacora");
  const pie = $("pie-bitacora");

  if (!datos.movimientos.length) {
    cuerpo.innerHTML = `<tr><td colspan="7" class="vacio">
      <strong>Todavía no hay movimientos.</strong><br>
      Cada entrada y cada salida que detecte la cámara se va a ir anotando acá.
      Para generar uno ahora, corré <code>python scripts/monitor.py --simular</code>
      o <code>python scripts/simulacion_demo.py</code>.</td></tr>`;
    pie.innerHTML = "";
    return;
  }

  cuerpo.innerHTML = datos.movimientos.map((mov) => {
    const esSalida = mov.tipo === "salida";
    // La llave identifica al movimiento en sí, no su posición en la lista:
    // si fuera el índice, un movimiento nuevo correría todos los demás y
    // se animarían las doce filas en vez de la que realmente entró.
    const clase = marcarSiCambio(
      ["m", mov.tipo, mov.hora, mov.placa, mov.espacio].join(":"),
      "presente",
    );

    return `<tr class="${clase}">
      <td class="col-marca"><span class="marca ${esSalida ? "marca--activa" : ""}"></span></td>
      <td class="num">${escapar(mov.hora)}</td>
      <td>${esSalida ? "Salida" : "Entrada"}</td>
      <td>${celdaPlaca(mov.placa)}</td>
      <td class="espacio">${escapar(mov.espacio)}</td>
      <td class="num">${duracion(mov.minutos)}</td>
      <td class="num ${mov.monto === null ? "monto--nulo" : "monto"}">
        ${mov.monto === null ? "—" : quetzales(mov.monto)}</td>
    </tr>`;
  }).join("");

  const sumaVisible = datos.movimientos.reduce((total, mov) => total + (mov.monto ?? 0), 0);
  pie.innerHTML = `<tr class="pie-suma">
    <td></td><td colspan="5">Suma de los movimientos a la vista</td>
    <td class="num total">${quetzales(sumaVisible)}</td>
  </tr>`;
}

/* ── Campo de ocupación por hora ──────────────────────────────────── */

function pintarCampoHoras(conteo) {
  const ANCHO = 1000, ALTO = 210;
  const MARGEN_IZQ = 44, MARGEN_DER = 10, MARGEN_SUP = 14, MARGEN_INF = 32;
  const util = ANCHO - MARGEN_IZQ - MARGEN_DER;
  const alto = ALTO - MARGEN_SUP - MARGEN_INF;
  const paso = util / 24;
  const tope = Math.max(1, ...conteo);
  const horaActual = new Date().getHours();

  const x = (hora) => MARGEN_IZQ + hora * paso;
  const y = (valor) => MARGEN_SUP + alto - (valor / tope) * alto;

  // Perfil escalonado continuo: cada hora es un tramo plano y las horas en
  // cero bajan hasta la base pero siguen siendo parte de la misma línea.
  // Un hueco diría "no hubo dato"; un valle dice "hubo cero sesiones".
  const puntos = [];
  conteo.forEach((valor, hora) => {
    puntos.push(`${x(hora).toFixed(1)},${y(valor).toFixed(1)}`);
    puntos.push(`${x(hora + 1).toFixed(1)},${y(valor).toFixed(1)}`);
  });

  const base = MARGEN_SUP + alto;
  const area = `M${MARGEN_IZQ},${base} L${puntos.join(" L")} L${x(24).toFixed(1)},${base} Z`;
  const perfil = `M${puntos.join(" L")}`;

  const niveles = [...new Set([0, Math.round(tope / 2), tope])];
  const guias = niveles.map((nivel) => `
    <line class="${nivel === 0 ? "base" : "guia"}"
          x1="${MARGEN_IZQ}" y1="${y(nivel).toFixed(1)}"
          x2="${ANCHO - MARGEN_DER}" y2="${y(nivel).toFixed(1)}" />
    <text class="escala" x="${MARGEN_IZQ - 10}" y="${(y(nivel) + 5).toFixed(1)}"
          text-anchor="end">${nivel}</text>`).join("");

  const divisores = conteo.map((_, hora) => hora % 6 === 0 && hora > 0
    ? `<line class="divisor-hora" x1="${x(hora).toFixed(1)}" y1="${MARGEN_SUP}"
             x2="${x(hora).toFixed(1)}" y2="${base}" />`
    : "").join("");

  const picos = conteo.map((valor, hora) => valor === tope && valor > 0
    ? `<circle class="pico" cx="${(x(hora) + paso / 2).toFixed(1)}" cy="${y(valor).toFixed(1)}" r="4">
         <title>${String(hora).padStart(2, "0")}:00 — ${plural(valor, "sesión", "sesiones")}</title>
       </circle>`
    : "").join("");

  const etiquetas = conteo.map((_, hora) => {
    if (hora % 3 !== 0) return "";
    const viva = hora === horaActual - (horaActual % 3);
    return `<text class="marca-hora ${viva ? "marca-hora--viva" : ""}"
              x="${(x(hora) + paso / 2).toFixed(1)}" y="${ALTO - 10}"
              text-anchor="middle">${String(hora).padStart(2, "0")}</text>`;
  }).join("");

  $("campo-horas").innerHTML = `
    <svg viewBox="0 0 ${ANCHO} ${ALTO}" role="img"
         aria-label="Sesiones activas por hora del día, de las 00 a las 23 horas. Máximo: ${tope}.">
      ${guias}${divisores}
      <path class="area" d="${area}" />
      <path class="perfil" d="${perfil}" />
      ${picos}${etiquetas}
    </svg>`;
}

/* ── Sumas y sello ────────────────────────────────────────────────── */

function pintarPie(datos) {
  const r = datos.recaudacion;
  // Las tres filas cuadran: hoy + resto del mes = total del mes. Antes eran
  // tres cifras sueltas sin relación declarada entre sí.
  const resto = Math.max(0, r.mes - r.dia);
  const sesionesResto = Math.max(0, r.sesiones_mes - r.sesiones_dia);

  $("suma-dia").textContent = quetzales(r.dia);
  $("suma-resto").textContent = quetzales(resto);
  $("suma-mes").textContent = quetzales(r.mes);

  $("detalle-dia").textContent = plural(r.sesiones_dia, "sesión cerrada", "sesiones cerradas");
  $("detalle-resto").textContent = plural(sesionesResto, "sesión cerrada", "sesiones cerradas");
  $("detalle-mes").textContent = plural(r.sesiones_mes, "sesión cerrada", "sesiones cerradas");

  $("procedencia").textContent =
    `Los ${datos.totales.sesiones} registros de este libro los escribió el monitor ` +
    `(scripts/monitor.py) sobre ${plural(datos.totales.vehiculos, "placa distinta", "placas distintas")}. ` +
    `Mientras el sistema no esté instalado en el parqueo real, las sesiones provienen de pruebas: ` +
    `los vehículos son de prueba, pero los tiempos y los montos los calculó el mismo código que se usará en producción.`;
}

function pintarCabecera(datos) {
  $("folio-fecha").textContent = fechaLarga();
  $("folio-tarifa").textContent = datos.tarifa ? quetzales(datos.tarifa.precio_por_hora) : "sin definir";
  $("saldo-libres").textContent = datos.libres;
  $("saldo-total").textContent = datos.total;
  document.querySelector(".saldo").classList.toggle("saldo--lleno", datos.libres === 0);
}

function marcarConexion(viva, actualizado) {
  const sello = document.querySelector(".sello");
  sello.classList.toggle("sello--viva", viva);
  sello.classList.toggle("sello--caida", !viva);

  if (viva) {
    $("sello-texto").textContent = `Leyendo de TiDB Cloud · última lectura ${actualizado}`;
  } else {
    const desde = ultimoExito ? ` Último dato bueno: ${ultimoExito}.` : "";
    $("sello-texto").textContent = `Sin conexión con la base de datos.${desde}`;
  }
}

function mostrarAviso(texto) {
  const aviso = $("aviso");
  if (!texto) { aviso.hidden = true; return; }
  $("aviso-texto").textContent = texto;
  aviso.hidden = false;
}

/* ── Ciclo ────────────────────────────────────────────────────────── */

async function actualizar() {
  try {
    const respuesta = await fetch("/api/estado", { cache: "no-store" });
    if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
    const datos = await respuesta.json();
    if (datos.error) throw new Error(datos.error);

    pintarCabecera(datos);
    pintarEspacios(datos);
    pintarCampoHoras(datos.ocupacion_por_hora);
    pintarBitacora(datos);
    pintarPie(datos);

    fallosSeguidos = 0;
    ultimoExito = datos.actualizado;
    primeraCarga = false;
    marcarConexion(true, datos.actualizado);
    mostrarAviso(null);
  } catch (error) {
    fallosSeguidos += 1;
    // Un fallo suelto puede ser un parpadeo de red; recién al segundo se
    // avisa, para no alarmar en medio de una demostración por una lectura.
    if (fallosSeguidos >= LECTURAS_FALLIDAS_PARA_AVISAR) {
      marcarConexion(false);
      mostrarAviso(
        "No se pudo leer de la base de datos. Los números de abajo son la " +
        "última lectura buena, no el estado de ahora. Revisá la conexión a " +
        "internet y que las credenciales del archivo .env sigan siendo válidas."
      );
    }
  }
}

actualizar();
setInterval(actualizar, INTERVALO_MS);
