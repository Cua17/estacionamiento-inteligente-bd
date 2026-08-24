"""
Monitor del parqueo: el programa principal del sistema.

Junta las tres piezas en un solo bucle continuo:

    cámara  ->  detección de ocupación  ->  base de datos
                        +
                 OCR de la placa (al entrar un vehículo)

Cuando un espacio pasa de libre a ocupado, lee la placa e inserta una
sesión. Cuando pasa de ocupado a libre, cierra la sesión y genera el
cobro. El dashboard web lee esa misma base y refleja todo en vivo.

Este es el script que va a correr en la Raspberry Pi. En la laptop corre
exactamente igual, solo cambia de qué cámara lee.

Uso:
    python scripts/monitor.py                 # con ventana de video
    python scripts/monitor.py --sin-ventana   # headless (para la Pi por SSH)
    python scripts/monitor.py --simular       # sin cámara: teclas 1-4 ocupan/liberan

Controles (con ventana):
    q / ESC : salir
    p       : leer la placa del cuadro actual y mostrarla (sin tocar la BD)
"""

import argparse
import queue
import threading
import time
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import parqueo
from camara import abrir_camara, hay_camara_pi
from ocupacion import (
    EstadoEstable,
    cargar_config,
    capturar_referencias_completas,
    evaluar_espacios,
    evaluar_espacios_combinado,
)
from vision import formato_valido, leer_placa, leer_placa_de_archivo

RAIZ = Path(__file__).resolve().parent.parent

VERDE = (74, 222, 128)
ROJO = (113, 113, 248)
GRIS = (150, 150, 150)
NEGRO = (0, 0, 0)

SEGUNDOS_ENTRE_LECTURAS = 0.15

# Cada cuánto imprime las diferencias de color con --depurar-color.
SEGUNDOS_ENTRE_REPORTES = 2.0

# Cuántos cuadros extra se intentan leer si el primero no dio una placa válida.
INTENTOS_DE_PLACA = 12

# Si una lectura de placa esperó más que esto en la cola, se descarta: el
# vehículo de esa entrada ya no está frente a la cámara, así que leer ahora
# daría la placa del que entró después (o ninguna).
#
# TIENE que ser mayor que SEGUNDOS_MAXIMOS_POR_PLACA (más abajo, 28s): si
# fuera menor, una entrada en cola se descartaría por "vieja" antes de que
# la de adelante termine de procesarse, aunque el vehículo siguiera ahí
# esperando su turno -- que es exactamente el bug que este número existe
# para evitar. 40s = 28s del que está adelante + margen real de espera.
SEGUNDOS_PARA_DESCARTAR_OCR = 40

# Cuántos cuadros recientes se guardan para leerles la placa. A ~0.15s por
# vuelta del bucle, 20 cuadros son unos 3 segundos de historial: alcanza
# para cubrir desde que el vehículo aparece hasta que se confirma la
# entrada.
CUADROS_DE_HISTORIAL = 20


def marca_de_tiempo():
    return datetime.now().strftime("%H:%M:%S")


def registrar(mensaje):
    print(f"[{marca_de_tiempo()}] {mensaje}")


# Cuánto se agranda la región de un espacio antes de buscarle la placa,
# como fracción de su ancho/alto por cada lado.
#
# Hace falta porque en el kit impreso la placa mide LO MISMO de ancho que
# el espacio (6.2cm los dos): si el vehículo no queda perfectamente
# centrado, la placa se sale del rectángulo y el recorte la corta. Pasó de
# verdad -- el recorte guardado para diagnóstico mostraba "?123ABC", con la
# P cortada contra el borde, y por eso ninguna lectura calzaba con el
# formato de 7 caracteres.
MARGEN_ZONA_PLACA = 0.5


def ensanchar_region(region, ancho_cuadro, alto_cuadro, margen=MARGEN_ZONA_PLACA):
    """Agranda una región un `margen` por lado, sin salirse del cuadro."""
    x, y, ancho, alto = region
    dx, dy = int(ancho * margen), int(alto * margen * 0.25)
    x0, y0 = max(0, x - dx), max(0, y - dy)
    x1 = min(ancho_cuadro, x + ancho + dx)
    y1 = min(alto_cuadro, y + alto + dy)
    return [x0, y0, max(1, x1 - x0), max(1, y1 - y0)]


def leer_placa_del_cuadro(cuadro, zona_placa=None):
    """
    Intenta leer una placa del cuadro.

    Si la config define una 'zona_placa', se recorta solo esa parte (es
    mucho más confiable que buscar en toda la imagen). Devuelve None si lo
    leído no calza con el formato guatemalteco: es preferible registrar el
    vehículo como DESCONOCIDA que inventar una placa equivocada y cobrarle
    a otra persona.
    """
    recorte = cuadro
    if zona_placa:
        x, y, ancho, alto = zona_placa
        recorte = cuadro[y:y + alto, x:x + ancho]
        if recorte.size == 0:
            recorte = cuadro

    placa = leer_placa(recorte)
    return placa if formato_valido(placa) else None


def leer_placa_rapido(cuadro, zona_placa=None):
    """Versión liviana, pensada para correr sobre muchos cuadros seguidos."""
    recorte = cuadro
    if zona_placa:
        x, y, ancho, alto = zona_placa
        recorte = cuadro[y:y + alto, x:x + ancho]
        if recorte.size == 0:
            recorte = cuadro
    placa = leer_placa(recorte, rapido=True)
    return placa if formato_valido(placa) else None


# Techo de tiempo para leer UNA placa. Existe para que una lectura difícil
# no le robe el turno a la siguiente: la cola del OCR es de un solo hilo, y
# una lectura que falla prueba todas las combinaciones (candidatos ×
# binarizaciones × modos de Tesseract), que en la Pi llegó a tardar 35
# segundos. En ese rato entró un vehículo a OTRO espacio y su lectura se
# descartó por vieja sin haberse intentado nunca: un falso positivo
# terminaba costando la placa de una entrada legítima. Con el techo, la
# lectura difícil se rinde y libera el hilo.
#
# El número sale de medir en la Pi real, no de la laptop (que es mucho más
# rápida): UN cuadro sin candidatos con forma de placa -- cae al camino de
# respaldo (buscar en toda la imagen) -- tarda 9.3s ahí. Con el techo
# anterior (8s) cortaba a la mitad del PRIMER cuadro, sin darle tiempo ni a
# terminar un intento. 28s da margen para ~2-3 cuadros difíciles seguidos
# (el caso real que se quiere resolver) y sigue siendo mucho menor que los
# 35s sin techo que causaban el problema original. Una lectura que SÍ
# encuentra la placa es rápida (~1s, medido) porque corta apenas dos
# binarizaciones coinciden -- este techo casi nunca se activa en el caso
# feliz, solo en el difícil.
SEGUNDOS_MAXIMOS_POR_PLACA = 28.0


def leer_placa_por_consenso(cuadros, zona_placa, coincidencias=2,
                            intentos_completos=4,
                            limite_segundos=SEGUNDOS_MAXIMOS_POR_PLACA):
    """
    Solo da por buena una placa si la lee IGUAL en dos cuadros distintos.

    Sin esto, el OCR devuelve la primera lectura que tenga forma de placa
    (una letra, tres dígitos, tres letras) aunque sea ruido interpretado mal,
    y el sistema termina inventando una placa que no se parece a la real.
    Exigir que dos cuadros independientes coincidan descarta casi todo ese
    ruido: acertar dos veces el mismo error es mucho menos probable que
    acertarlo una.

    `cuadros` es una LISTA de cuadros ya capturados, no una forma de pedir
    cuadros nuevos, y la diferencia es todo el asunto: el vehículo solo
    está frente a la cámara en el momento de entrar. Cuando esta función
    pedía cuadros en vivo, para cuando le tocaba correr (después de
    confirmar el cambio y de escribir en la base) el vehículo muchas veces
    ya se había ido, y el OCR terminaba leyendo el piso vacío. Ahora recibe
    los cuadros guardados de ese momento.

    Los últimos `intentos_completos` cuadros se leen con el pipeline
    completo: más lento por cuadro, pero mucho más probable que acierte en
    cuadros difíciles (poca luz, placa chica). Esto corre en un hilo
    aparte, así que el video no se ve afectado.
    """
    votos = Counter()
    vence_en = time.monotonic() + limite_segundos
    intentos_rapidos = max(0, len(cuadros) - intentos_completos)
    for numero_intento, cuadro in enumerate(cuadros):
        if cuadro is None:
            continue
        if time.monotonic() > vence_en:
            registrar(f"   se acabó el tiempo de lectura tras {numero_intento} cuadros")
            break
        if numero_intento < intentos_rapidos:
            placa = leer_placa_rapido(cuadro, zona_placa)
        else:
            placa = leer_placa_del_cuadro(cuadro, zona_placa)
        if placa:
            votos[placa] += 1
            if votos[placa] >= coincidencias:
                return placa

    if votos:
        mejor, veces = votos.most_common(1)[0]
        registrar(f"   lectura descartada por falta de consenso: '{mejor}' apareció {veces} vez/veces")
    return None


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


def dibujar_overlay(cuadro, resultados, espacios, zona_placa=None):
    """Dibuja el estado de cada espacio sobre el video, para ver qué está detectando."""
    vista = cuadro.copy()
    libres = sum(1 for r in resultados if not r["ocupado"])

    for resultado, espacio in zip(resultados, espacios):
        x, y, ancho, alto = espacio["region"]
        color = ROJO if resultado["ocupado"] else VERDE
        etiqueta = f"{resultado['etiqueta']}: {'OCUPADO' if resultado['ocupado'] else 'LIBRE'}"

        cv2.rectangle(vista, (x, y), (x + ancho, y + alto), color, 2)
        (ancho_texto, alto_texto), _ = cv2.getTextSize(etiqueta, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(vista, (x, y - alto_texto - 8), (x + ancho_texto + 8, y), color, -1)
        cv2.putText(vista, etiqueta, (x + 4, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, NEGRO, 1, cv2.LINE_AA)
        cv2.putText(vista, f"{resultado['densidad']:.2f}", (x + 4, y + alto - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

    if zona_placa:
        x, y, ancho, alto = zona_placa
        cv2.rectangle(vista, (x, y), (x + ancho, y + alto), GRIS, 1)
        cv2.putText(vista, "zona placa", (x + 4, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, GRIS, 1, cv2.LINE_AA)

    resumen = f"{libres}/{len(resultados)} libres"
    cv2.rectangle(vista, (8, 8), (150, 34), NEGRO, -1)
    cv2.putText(vista, resumen, (14, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.6, VERDE, 1, cv2.LINE_AA)
    return vista


def procesar_cambio(conexion, etiqueta, ocupado, cuadro, zona_placa,
                    placa_fija=None, leer_placa_fn=None):
    """Traduce un cambio de estado confirmado en una operación de base de datos."""
    if ocupado:
        if placa_fija:
            placa = placa_fija
        elif leer_placa_fn is not None:
            placa = leer_placa_fn()
        else:
            placa = leer_placa_del_cuadro(cuadro, zona_placa) if cuadro is not None else None
        if placa is None:
            placa = "DESCONOCIDA"
            registrar(f"{etiqueta}: vehículo detectado, placa NO legible -> se registra como DESCONOCIDA")
        else:
            registrar(f"{etiqueta}: placa leída {placa}")
    else:
        placa = None

    try:
        resultado = parqueo.sincronizar_espacio(conexion, etiqueta, ocupado, placa)
    except parqueo.EspacioNoExiste:
        registrar(f"AVISO: el espacio '{etiqueta}' está en config_espacios.json pero no en la base de datos.")
        return

    if resultado:
        registrar(resultado)


SEGUNDOS_DE_CALENTAMIENTO = 3.0
CUADROS_PARA_LA_REFERENCIA = 10


def capturar_cuadro_de_referencia(camara,
                                  segundos_calentamiento=SEGUNDOS_DE_CALENTAMIENTO,
                                  cuadros=CUADROS_PARA_LA_REFERENCIA):
    """
    Cuadro de "parqueo vacío" contra el que se compara todo en --por-color.

    NO se puede usar el primer cuadro que entrega la cámara. La OV5647 (y
    cualquier cámara con auto-exposición y balance de blancos automáticos)
    arranca con ganancias por defecto y tarda unos segundos en converger:
    los primeros cuadros salen más oscuros y con otro tinte que los que
    vendrán después. Si la referencia se toma de ahí, cuando el AE/AWB se
    acomoda cambia el color de TODO el cuadro, la diferencia contra la
    referencia se dispara sin que haya entrado ningún vehículo, y los
    espacios empiezan a marcarse OCUPADO solos (pasó de verdad: A1
    oscilando OCUPADO/LIBRE con el parqueo vacío).

    Por eso: primero se descartan cuadros durante unos segundos para que la
    cámara se estabilice, y recién después se toma la referencia como la
    MEDIANA de varios cuadros -- la mediana ignora el ruido del sensor y
    cualquier cuadro suelto que haya salido raro.
    """
    fin_calentamiento = time.monotonic() + segundos_calentamiento
    while time.monotonic() < fin_calentamiento:
        camara.read()

    capturados = []
    for _ in range(cuadros):
        ok, cuadro = camara.read()
        if ok and cuadro is not None:
            capturados.append(cuadro)

    if not capturados:
        raise RuntimeError("No se pudo leer un cuadro de referencia de la cámara.")

    return np.median(np.stack(capturados), axis=0).astype(np.uint8)


def bucle_camara(args, conexion, espacios, zona_placa):
    usar_pi_camera = args.camara_pi or hay_camara_pi()
    if usar_pi_camera:
        registrar("Usando la cámara CSI de la Raspberry Pi (picamera2).")
    camara = abrir_camara(args.camara, ancho=args.ancho, alto=args.alto,
                          usar_pi_camera=usar_pi_camera)

    referencias_color = None
    if args.por_color:
        # Modo alternativo para demos con fondo controlado (una hoja
        # blanca): en vez de contar bordes/detalle, compara el color de
        # cada zona contra esta referencia de "vacío". Por eso ES
        # OBLIGATORIO que el parqueo esté vacío en este momento -- el
        # primer cuadro que se lea queda grabado como el "libre" contra el
        # que se compara todo lo demás.
        registrar("Modo --por-color: capturando referencia con el parqueo VACÍO...")
        cuadro_referencia = capturar_cuadro_de_referencia(camara)
        referencias_color = capturar_referencias_completas(cuadro_referencia, espacios)
        registrar("Referencia capturada. Ocupado = cambia el color Y la textura (la sombra sola no basta).")

    estado_inicial = parqueo.estado_actual_de_espacios(conexion)
    estable = EstadoEstable(
        lecturas_para_confirmar=args.confirmaciones,
        estado_inicial=estado_inicial,
    )
    ocupados_al_iniciar = [e for e, ocupado in estado_inicial.items() if ocupado]
    registrar(f"Monitoreando {len(espacios)} espacios. Ctrl+C para detener.")
    registrar(
        f"Estado inicial según la base de datos: "
        f"{', '.join(ocupados_al_iniciar) if ocupados_al_iniciar else 'todos libres'}"
    )

    # DOS hilos, no uno, y esto importa mucho:
    #
    #   - `trabajos`     -> cambios de estado (entrada/salida). Rápido y
    #                       crítico: es lo que el tablero tiene que reflejar
    #                       al instante.
    #   - `trabajos_ocr` -> lectura de placas. Lento (en la Pi, hasta medio
    #                       minuto) y "mejor esfuerzo": si falla, la sesión
    #                       igual queda registrada como DESCONOCIDA.
    #
    # Antes los dos compartían un solo hilo, y el resultado era que una
    # SALIDA detectada mientras se leía la placa de la entrada anterior se
    # quedaba encolada hasta que el OCR terminara -- el tablero tardaba
    # ~30 segundos en mostrar que el espacio se había liberado, aunque la
    # cámara lo hubiera detectado al instante. Separarlos es lo que hace
    # que el estado nunca espere al OCR.
    proximo_reporte = 0.0

    # Dónde buscar la placa de cada espacio. El vehículo que acaba de entrar
    # a A3 está, por definición, dentro del rectángulo de A3: recortar ahí
    # es muchísimo mejor que buscar en el cuadro entero.
    #
    # Sin esto el OCR nunca leyó una sola placa en la Pi. Con `zona_placa`
    # en None (la config generada con --rejilla no trae entrada "PLACA"),
    # leer_placa() recibía los 640x480 completos, donde la placa impresa es
    # papel blanco sobre la hoja blanca del parqueo: el localizador por
    # contorno casi no ve ese borde blanco-sobre-blanco, y la red de
    # seguridad por zona brillante se queda con la hoja entera. Tesseract
    # terminaba leyendo los rótulos "A1 A2 A3 A4" y ninguna placa.
    # Recortando la región del espacio, la placa pasa de ser una manchita
    # del cuadro a ocupar buena parte del recorte, y _agrandar() la lleva a
    # un tamaño que Tesseract sí puede leer.
    region_por_espacio = {e["etiqueta"]: e["region"] for e in espacios}

    trabajos = queue.Queue()
    trabajos_ocr = queue.Queue()

    # Historial corto de cuadros recientes. Cuando se confirma una entrada,
    # el vehículo ya lleva un par de segundos frente a la cámara (hacen
    # falta varias lecturas seguidas para confirmar), así que estos cuadros
    # SÍ lo tienen. Leer la placa de acá y no del video en vivo es lo que
    # evita que el OCR termine mirando el piso vacío porque el vehículo se
    # fue mientras se procesaba la entrada.
    cuadros_recientes = deque(maxlen=CUADROS_DE_HISTORIAL)

    def _con_conexion_viva(conexion):
        """
        TiDB cierra las conexiones que estuvieron inactivas un buen rato
        (ej. mientras no entraba ni salía ningún vehículo). Sin esto, cada
        tarea siguiente fallaba con "MySQL Connection not available" para
        siempre, hasta reiniciar el monitor a mano.
        """
        conexion.ping(reconnect=True, attempts=3, delay=1)
        return conexion

    def trabajador_estado():
        """
        Escribe en la base los cambios de ocupación. Solo eso: nada lento
        corre acá adentro.

        Nunca descarta un cambio: cada entrada y cada salida se encolan y se
        procesan en orden. (Antes se salteaban los cambios de un espacio que
        ya tenía trabajo en curso, y eso hacía que una salida ocurrida
        mientras se leía la placa se perdiera y el espacio quedara marcado
        como ocupado hasta el siguiente ciclo completo.)
        """
        conexion_hilo = parqueo.conectar_parqueo()
        try:
            while True:
                tarea = trabajos.get()
                if tarea is None:
                    return
                etiqueta, ocupado, cuadro_del_cambio, cuadros_del_cambio = tarea
                try:
                    _con_conexion_viva(conexion_hilo)
                    inicio = time.monotonic()
                    procesar_cambio(conexion_hilo, etiqueta, ocupado, cuadro_del_cambio,
                                    zona_placa, leer_placa_fn=lambda: None)
                    registrar(f"   ({(time.monotonic() - inicio) * 1000:.0f} ms hasta la base de datos)")

                    if ocupado:
                        # Se delega la placa al otro hilo y se sigue de largo.
                        # Van los cuadros guardados del momento de la entrada:
                        # son los que tienen el vehículo enfrente.
                        trabajos_ocr.put((etiqueta, time.monotonic(), cuadros_del_cambio))
                except Exception as error:
                    # Un error puntual (ej. un hipo de red con la base de datos)
                    # no debe tumbar el monitor: se avisa y se sigue.
                    registrar(f"ERROR al procesar '{etiqueta}': {error}")
                finally:
                    trabajos.task_done()
        finally:
            conexion_hilo.close()

    def trabajador_ocr():
        """
        Lee la placa de las entradas y corrige la sesión ya abierta.

        Corre en su propio hilo y con su propia conexión, así que puede
        tardar lo que tarde sin frenar el registro de entradas y salidas.
        """
        conexion_hilo = parqueo.conectar_parqueo()
        try:
            while True:
                tarea = trabajos_ocr.get()
                if tarea is None:
                    return
                etiqueta, encolado_en, cuadros = tarea
                try:
                    # Si mientras tanto se acumularon varias lecturas
                    # pendientes, las viejas ya no sirven: el vehículo de
                    # esa entrada probablemente ya se fue. Mejor saltearla y
                    # atender la más reciente.
                    if time.monotonic() - encolado_en > SEGUNDOS_PARA_DESCARTAR_OCR:
                        registrar(f"{etiqueta}: lectura de placa descartada por vieja")
                        continue

                    zona = zona_placa
                    if not zona and cuadros is not None and len(cuadros):
                        alto_c, ancho_c = cuadros[0].shape[:2]
                        region = region_por_espacio.get(etiqueta)
                        if region:
                            zona = ensanchar_region(region, ancho_c, alto_c)
                    placa = leer_placa_por_consenso(cuadros, zona)
                    if placa:
                        _con_conexion_viva(conexion_hilo)
                        if parqueo.actualizar_placa_de_sesion(conexion_hilo, etiqueta, placa):
                            registrar(f"{etiqueta}: placa leída -> {placa}")
                    else:
                        registrar(f"{etiqueta}: placa no legible tras varios intentos, queda DESCONOCIDA")
                        # Se guarda el cuadro que SE INTENTÓ leer, no el de
                        # ahora: guardar el actual mostraba el piso vacío y
                        # no decía nada de por qué falló la lectura.
                        fallido = cuadros[0] if cuadros else None
                        guardar_para_diagnostico(fallido, etiqueta)
                        # Y además EL RECORTE que se le pasó al OCR: es lo
                        # único que contesta "¿la placa se veía legible ahí
                        # adentro?", que es la pregunta que importa cuando
                        # falla la lectura.
                        if fallido is not None and zona:
                            x, y, ancho, alto = zona
                            guardar_para_diagnostico(fallido[y:y + alto, x:x + ancho],
                                                     f"{etiqueta}_recorte")
                except Exception as error:
                    registrar(f"ERROR leyendo la placa de '{etiqueta}': {error}")
                finally:
                    trabajos_ocr.task_done()
        finally:
            conexion_hilo.close()

    hilo = threading.Thread(target=trabajador_estado, daemon=True)
    hilo.start()
    hilo_ocr = threading.Thread(target=trabajador_ocr, daemon=True)
    hilo_ocr.start()

    try:
        while True:
            ok, cuadro = camara.read()
            if not ok:
                registrar("La cámara dejó de responder; reintentando...")
                time.sleep(1)
                continue

            cuadros_recientes.append(cuadro)
            if referencias_color is not None:
                resultados = evaluar_espacios_combinado(
                    cuadro, espacios, referencias_color,
                    umbral_color=args.umbral_color,
                    umbral_textura=args.umbral_textura,
                )
            else:
                resultados = evaluar_espacios(cuadro, espacios)

            # Diagnóstico: imprime la diferencia real de cada espacio contra
            # su referencia. Sirve para elegir el umbral mirando números en
            # vez de a ojo -- con el parqueo vacío todas deberían quedar
            # bien por debajo del umbral, y con un vehículo puesto, bien
            # por encima.
            if args.depurar_color and time.monotonic() >= proximo_reporte:
                proximo_reporte = time.monotonic() + SEGUNDOS_ENTRE_REPORTES
                registrar("   " + "  ".join(
                    f"{r['etiqueta']} col={r['densidad']:6.2f} tex={r.get('textura', 0):.3f}"
                    f"{'*' if r['ocupado'] else ' '}"
                    for r in resultados
                ) + f"  (umbrales col>={args.umbral_color} y tex>={args.umbral_textura})")
            for resultado in resultados:
                cambio = estable.actualizar(resultado["etiqueta"], resultado["ocupado"])
                if cambio is not None:
                    registrar(f"{resultado['etiqueta']}: {'OCUPADO' if cambio else 'LIBRE'} detectado")
                    # Se copia el historial AHORA (no se pasa el deque, que
                    # el bucle va a seguir pisando con cuadros nuevos donde
                    # el vehículo ya no está). Se toma uno de cada dos para
                    # que las lecturas sean de instantes distintos y el
                    # consenso signifique algo.
                    #
                    # OJO: solo se toman los últimos `lecturas_para_confirmar`
                    # cuadros del historial, NO todo el deque. La confirmación
                    # de EstadoEstable garantiza que esos últimos N cuadros
                    # tuvieron el mismo veredicto (ocupado) N veces seguidas
                    # -- son los únicos de los que se puede asegurar que el
                    # vehículo ya estaba ahí. El resto del historial (hasta
                    # CUADROS_DE_HISTORIAL, más largo que la ventana mínima de
                    # confirmación) puede ser de ANTES de que el vehículo
                    # llegara. Pasarlo entero contaminaba tanto el diagnóstico
                    # guardado como la votación del OCR con cuadros de la
                    # mesa vacía (visto en vivo: el .png guardado para
                    # revisar no tenía ningún carrito, con el objeto puesto
                    # y detectado hacía más de 30 segundos).
                    recientes = list(cuadros_recientes)[-estable.lecturas_para_confirmar:]
                    instantaneas = [c.copy() for c in recientes[::-2]]
                    trabajos.put((resultado["etiqueta"], cambio, cuadro.copy(), instantaneas))

            if not args.sin_ventana:
                cv2.imshow("Monitor del parqueo  |  q=salir  p=leer placa",
                           dibujar_overlay(cuadro, resultados, espacios, zona_placa))
                tecla = cv2.waitKey(1) & 0xFF
                if tecla in (ord("q"), 27):
                    break
                if tecla == ord("p"):
                    placa = leer_placa_del_cuadro(cuadro, zona_placa)
                    registrar(f"Lectura manual de placa: {placa or 'no se reconoció un formato válido'}")
            else:
                time.sleep(SEGUNDOS_ENTRE_LECTURAS)
    finally:
        trabajos.put(None)
        trabajos_ocr.put(None)
        camara.release()
        cv2.destroyAllWindows()


def bucle_simulado(conexion, espacios, zona_placa, placas_por_espacio):
    """
    Modo sin cámara: se escriben los números de espacio para ocuparlos o
    liberarlos a mano. Sirve para probar toda la cadena (sesiones, cobros,
    dashboard) cuando no hay cámara disponible.
    """
    etiquetas = [e["etiqueta"] for e in espacios]
    ocupados = {etiqueta: False for etiqueta in etiquetas}

    print("\nModo simulado (sin cámara).")
    print(f"Espacios: {', '.join(f'{i + 1}={e}' for i, e in enumerate(etiquetas))}")
    print("Escribí el número de un espacio + ENTER para ocuparlo/liberarlo. 'q' para salir.\n")

    while True:
        entrada = input("espacio> ").strip().lower()
        if entrada in ("q", "salir", "exit"):
            break
        if not entrada.isdigit() or not 1 <= int(entrada) <= len(etiquetas):
            print(f"Escribí un número del 1 al {len(etiquetas)}, o 'q'.")
            continue

        etiqueta = etiquetas[int(entrada) - 1]
        ocupados[etiqueta] = not ocupados[etiqueta]
        procesar_cambio(
            conexion, etiqueta, ocupados[etiqueta], None, zona_placa,
            placa_fija=placas_por_espacio.get(etiqueta),
        )


def main():
    parser = argparse.ArgumentParser(description="Monitor del parqueo: cámara -> ocupación -> base de datos")
    parser.add_argument("--camara", type=int, default=0, help="Índice de la cámara (default: 0)")
    parser.add_argument("--camara-pi", action="store_true",
                        help="Forzar el uso de la cámara CSI de la Raspberry Pi "
                             "(por defecto se detecta sola)")
    parser.add_argument("--sin-ventana", action="store_true",
                        help="No abrir ventana de video (para correr por SSH en la Raspberry Pi)")
    parser.add_argument("--simular", action="store_true",
                        help="Sin cámara: ocupar/liberar espacios desde el teclado")
    parser.add_argument("--confirmaciones", type=int, default=8,
                        help="Lecturas seguidas para confirmar un cambio (default: 8)")
    parser.add_argument("--por-color", action="store_true",
                        help="Detectar ocupación por cambio de color contra una referencia "
                             "capturada al arrancar (con el parqueo VACÍO), en vez de por "
                             "textura/bordes. Pensado para demos con fondo controlado (una "
                             "hoja blanca); para el parqueo real conviene el modo por defecto.")
    parser.add_argument("--depurar-color", action="store_true",
                        help="Imprimir cada 2s la diferencia de color medida en cada espacio "
                             "contra su referencia. Para elegir el umbral con números reales.")
    parser.add_argument("--umbral-color", type=float, default=25.0,
                        help="Cuánto tiene que cambiar el color para contar como ocupado (default: 25)")
    parser.add_argument("--umbral-textura", type=float, default=0.030,
                        help="Cuánto tiene que cambiar la textura para contar como ocupado "
                             "(default: 0.030). Es lo que distingue un vehículo de una sombra.")
    # 1296x972, no 640x480. Medido con la placa real frente a la cámara: a
    # 640x480 la placa ocupa ~80 px de ancho, el localizador no encuentra
    # NINGÚN candidato y cada intento de lectura tarda 6-14 s buscando a
    # ciegas. A 1296x972 la misma placa ocupa ~160 px, aparece 1 candidato y
    # la lectura baja a ~650 ms. Subir más no ayuda: a 2592x1944 vuelve a
    # empeorar (9-17 s y lecturas basura), así que 1296x972 es el punto
    # justo, no simplemente "lo más alto posible".
    parser.add_argument("--ancho", type=int, default=1296,
                        help="Ancho de captura (default: 1296)")
    parser.add_argument("--alto", type=int, default=972,
                        help="Alto de captura (default: 972)")
    args = parser.parse_args()

    try:
        espacios = cargar_config()
    except FileNotFoundError as error:
        raise SystemExit(str(error))

    # La zona de la placa es opcional: se guarda como un espacio con
    # etiqueta "PLACA" en la config si se quiere acotar dónde buscarla.
    zona_placa = next(
        (e["region"] for e in espacios if e["etiqueta"].upper() == "PLACA"), None
    )
    espacios = [e for e in espacios if e["etiqueta"].upper() != "PLACA"]

    # En modo simulado no hay cámara para leer placas, así que se le asigna
    # a cada espacio una de las placas de prueba (leídas por OCR de verdad,
    # no escritas a mano) para que la demo muestre placas reales.
    placas_por_espacio = {}
    if args.simular:
        imagenes = sorted((RAIZ / "test_images").glob("*.png"))
        for espacio, imagen in zip(espacios, imagenes):
            try:
                placa = leer_placa_de_archivo(imagen)
                if formato_valido(placa):
                    placas_por_espacio[espacio["etiqueta"]] = placa
            except FileNotFoundError:
                pass

    conexion = parqueo.conectar_parqueo()
    try:
        if args.simular:
            bucle_simulado(conexion, espacios, zona_placa, placas_por_espacio)
        else:
            bucle_camara(args, conexion, espacios, zona_placa)
    except KeyboardInterrupt:
        print()
        registrar("Detenido por el usuario.")
    finally:
        conexion.close()


if __name__ == "__main__":
    main()
