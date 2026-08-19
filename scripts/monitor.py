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
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2

import parqueo
from camara import abrir_camara, hay_camara_pi
from ocupacion import EstadoEstable, cargar_config, evaluar_espacios
from vision import formato_valido, leer_placa, leer_placa_de_archivo

RAIZ = Path(__file__).resolve().parent.parent

VERDE = (74, 222, 128)
ROJO = (113, 113, 248)
GRIS = (150, 150, 150)
NEGRO = (0, 0, 0)

SEGUNDOS_ENTRE_LECTURAS = 0.15

# Cuántos cuadros extra se intentan leer si el primero no dio una placa válida.
INTENTOS_DE_PLACA = 12


def marca_de_tiempo():
    return datetime.now().strftime("%H:%M:%S")


def registrar(mensaje):
    print(f"[{marca_de_tiempo()}] {mensaje}")


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


def leer_placa_por_consenso(obtener_cuadro, zona_placa, intentos=INTENTOS_DE_PLACA,
                            coincidencias=2, intentos_completos=4):
    """
    Solo da por buena una placa si la lee IGUAL en dos cuadros distintos.

    Sin esto, el OCR devuelve la primera lectura que tenga forma de placa
    (una letra, tres dígitos, tres letras) aunque sea ruido interpretado mal,
    y el sistema termina inventando una placa que no se parece a la real.
    Exigir que dos cuadros independientes coincidan descarta casi todo ese
    ruido: acertar dos veces el mismo error es mucho menos probable que
    acertarlo una.

    Los primeros `intentos - intentos_completos` intentos usan la lectura
    rápida (menos variantes de binarización, para no atrasar el video). Si
    ninguno logra consenso, los últimos `intentos_completos` cambian a la
    lectura completa sobre cuadros frescos: más lenta por intento, pero
    mucho más probable que acierte en cuadros difíciles (poca luz, placa
    chica). Esto ya corre en el hilo aparte, así que el video no se ve
    afectado.
    """
    votos = Counter()
    intentos_rapidos = max(0, intentos - intentos_completos)
    for numero_intento in range(intentos):
        cuadro = obtener_cuadro()
        if cuadro is None:
            break
        if numero_intento < intentos_rapidos:
            placa = leer_placa_rapido(cuadro, zona_placa)
        else:
            placa = leer_placa_del_cuadro(cuadro, zona_placa)
        if placa:
            votos[placa] += 1
            if votos[placa] >= coincidencias:
                return placa
        time.sleep(0.05)

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


def bucle_camara(args, conexion, espacios, zona_placa):
    usar_pi_camera = args.camara_pi or hay_camara_pi()
    if usar_pi_camera:
        registrar("Usando la cámara CSI de la Raspberry Pi (picamera2).")
    camara = abrir_camara(args.camara, usar_pi_camera=usar_pi_camera)
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

    # El OCR y la escritura en la base tardan cientos de milisegundos. Si eso
    # corriera dentro del bucle de video, la imagen se congelaría cada vez que
    # entra o sale un vehículo -- que es justo el momento en que uno quiere
    # verla. Por eso el trabajo pesado se hace en un hilo aparte y el bucle
    # de video nunca se bloquea.
    trabajos = queue.Queue()
    ultimo_cuadro = {"imagen": None}

    def trabajador():
        """
        Escribe en la base los cambios que le manda el bucle de video.

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
                etiqueta, ocupado, cuadro_del_cambio = tarea
                try:
                    inicio = time.monotonic()
                    # El estado se escribe primero y sin esperar al OCR: el
                    # tablero tiene que reaccionar al instante.
                    procesar_cambio(conexion_hilo, etiqueta, ocupado, cuadro_del_cambio,
                                    zona_placa, leer_placa_fn=lambda: None)
                    registrar(f"   ({(time.monotonic() - inicio) * 1000:.0f} ms hasta la base de datos)")

                    # Recién después, y solo si no hay más cambios esperando,
                    # se intenta leer la placa. Si llega otro cambio mientras
                    # tanto, tiene prioridad: el estado importa más que la placa.
                    #
                    # Se usa leer_placa_por_consenso() en vez de un solo intento
                    # sobre cuadro_del_cambio (que quedó estático en el instante
                    # de la transición): pide varios cuadros FRESCOS a través de
                    # ultimo_cuadro (que el bucle de video sigue actualizando) y
                    # exige que la misma placa se repita antes de aceptarla. Un
                    # solo intento sobre un cuadro fijo es lo que hacía que el
                    # OCR le errara a los dígitos con cualquier frecuencia.
                    if ocupado and trabajos.empty():
                        placa = leer_placa_por_consenso(
                            lambda: ultimo_cuadro["imagen"], zona_placa)
                        if placa and parqueo.actualizar_placa_de_sesion(
                                conexion_hilo, etiqueta, placa):
                            registrar(f"{etiqueta}: placa leída -> {placa}")
                        elif not placa:
                            registrar(f"{etiqueta}: placa no legible tras varios intentos, queda DESCONOCIDA")
                            guardar_para_diagnostico(ultimo_cuadro["imagen"], etiqueta)
                except Exception as error:
                    # Un error puntual (ej. un hipo de red con la base de datos)
                    # no debe tumbar el monitor: se avisa y se sigue.
                    registrar(f"ERROR al procesar '{etiqueta}': {error}")
                finally:
                    trabajos.task_done()
        finally:
            conexion_hilo.close()

    hilo = threading.Thread(target=trabajador, daemon=True)
    hilo.start()

    try:
        while True:
            ok, cuadro = camara.read()
            if not ok:
                registrar("La cámara dejó de responder; reintentando...")
                time.sleep(1)
                continue

            ultimo_cuadro["imagen"] = cuadro
            resultados = evaluar_espacios(cuadro, espacios)
            for resultado in resultados:
                cambio = estable.actualizar(resultado["etiqueta"], resultado["ocupado"])
                if cambio is not None:
                    registrar(f"{resultado['etiqueta']}: {'OCUPADO' if cambio else 'LIBRE'} detectado")
                    trabajos.put((resultado["etiqueta"], cambio, cuadro.copy()))

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
