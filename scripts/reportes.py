"""
Consultas de lectura para el dashboard.

Están separadas de parqueo.py a propósito: parqueo.py opera (abre y cierra
sesiones, cobra) y este módulo solo lee y resume. Nada de acá modifica la
base de datos.

Todas las horas se formatean del lado de Python y no con DATE_FORMAT del
servidor: hora_entrada y hora_salida se guardan con la hora local de la
máquina que corre el monitor, y el servidor de TiDB está en otro huso
horario, así que formatear allá mostraría horas corridas.
"""

from datetime import date, datetime

HORAS_DEL_DIA = 24


def _hhmm(momento):
    return momento.strftime("%H:%M") if momento else None


def espacios(cursor):
    """Cada espacio con su estado y, si está ocupado, quién lo ocupa y desde cuándo."""
    cursor.execute("""
        SELECT e.etiqueta, e.estado, s.placa, s.hora_entrada
        FROM espacios e
        LEFT JOIN sesiones s ON s.espacio_id = e.id AND s.estado = 'activa'
        ORDER BY e.etiqueta
    """)
    ahora = datetime.now()
    filas = []
    for etiqueta, estado, placa, hora_entrada in cursor.fetchall():
        minutos = None
        if hora_entrada:
            minutos = max(0, int((ahora - hora_entrada).total_seconds() // 60))
        filas.append({
            "etiqueta": etiqueta,
            "ocupado": estado == "ocupado",
            "placa": placa,
            "desde": _hhmm(hora_entrada),
            "minutos": minutos,
        })
    return filas


def movimientos(cursor, limite=12):
    """
    Bitácora de entradas y salidas, lo más reciente primero.

    Una sesión genera dos movimientos: la entrada cuando se abre y la salida
    cuando se cierra. Se arman en Python (en vez de un UNION en SQL) para
    poder ordenar por la hora local ya convertida.
    """
    cursor.execute("""
        SELECT s.placa, e.etiqueta, s.hora_entrada, s.hora_salida,
               c.minutos_totales, c.monto
        FROM sesiones s
        JOIN espacios e ON e.id = s.espacio_id
        LEFT JOIN cobros c ON c.sesion_id = s.id
        ORDER BY s.id DESC
        LIMIT %s
    """, (limite,))

    eventos = []
    for placa, etiqueta, hora_entrada, hora_salida, minutos, monto in cursor.fetchall():
        eventos.append({
            "tipo": "entrada",
            "momento": hora_entrada,
            "hora": _hhmm(hora_entrada),
            "placa": placa,
            "espacio": etiqueta,
            "minutos": None,
            "monto": None,
        })
        if hora_salida:
            eventos.append({
                "tipo": "salida",
                "momento": hora_salida,
                "hora": _hhmm(hora_salida),
                "placa": placa,
                "espacio": etiqueta,
                "minutos": minutos,
                "monto": float(monto) if monto is not None else None,
            })

    eventos.sort(key=lambda e: e["momento"], reverse=True)
    for evento in eventos:
        del evento["momento"]
    return eventos[:limite]


def recaudacion(cursor):
    """Totales cobrados hoy y en el mes en curso, más el conteo de sesiones cerradas."""
    hoy = date.today()
    cursor.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN DATE(s.hora_salida) = %s THEN c.monto END), 0),
            COUNT(CASE WHEN DATE(s.hora_salida) = %s THEN 1 END),
            COALESCE(SUM(CASE WHEN YEAR(s.hora_salida) = %s AND MONTH(s.hora_salida) = %s
                              THEN c.monto END), 0),
            COUNT(CASE WHEN YEAR(s.hora_salida) = %s AND MONTH(s.hora_salida) = %s THEN 1 END)
        FROM cobros c
        JOIN sesiones s ON s.id = c.sesion_id
    """, (hoy, hoy, hoy.year, hoy.month, hoy.year, hoy.month))
    total_dia, sesiones_dia, total_mes, sesiones_mes = cursor.fetchone()
    return {
        "dia": float(total_dia),
        "sesiones_dia": int(sesiones_dia),
        "mes": float(total_mes),
        "sesiones_mes": int(sesiones_mes),
    }


def ocupacion_por_hora(cursor):
    """
    Cuántas sesiones estuvieron activas en cada hora del día, sobre todo el
    histórico registrado.

    Una sesión que va de 08:40 a 11:05 cuenta en las horas 8, 9, 10 y 11: lo
    que interesa es en qué franjas el parqueo estuvo ocupado, no a qué hora
    exacta entró cada carro.
    """
    cursor.execute("SELECT hora_entrada, hora_salida FROM sesiones")
    ahora = datetime.now()
    conteo = [0] * HORAS_DEL_DIA

    for hora_entrada, hora_salida in cursor.fetchall():
        fin = hora_salida or ahora
        if fin < hora_entrada:
            continue
        primera = hora_entrada.hour
        # Si la sesión cruza la medianoche, se recorta al final del día de
        # entrada: repartir una sesión entre dos días distorsionaría el perfil.
        ultima = fin.hour if fin.date() == hora_entrada.date() else HORAS_DEL_DIA - 1
        for hora in range(primera, ultima + 1):
            conteo[hora] += 1

    return conteo


def tarifa(cursor):
    cursor.execute("""
        SELECT nombre, precio_por_hora FROM tarifas
        WHERE vigente_hasta IS NULL
        ORDER BY vigente_desde DESC LIMIT 1
    """)
    fila = cursor.fetchone()
    if fila is None:
        return None
    nombre, precio = fila
    return {"nombre": nombre, "precio_por_hora": float(precio)}


def totales_historicos(cursor):
    """Conteos de todo el histórico, para dar contexto a los números del día."""
    cursor.execute("SELECT COUNT(*) FROM vehiculos")
    vehiculos = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sesiones")
    sesiones = cursor.fetchone()[0]
    return {"vehiculos": int(vehiculos), "sesiones": int(sesiones)}


def estado_completo(conexion, medios=None, lentos=None):
    """
    Arma todo lo que el dashboard necesita mostrar.

    Cada consulta es un viaje de ida y vuelta al servidor en Tokio (~300 ms),
    así que se pueden pasar ya calculadas las partes que no cambian en cada
    refresco. Lo único que se consulta siempre es la ocupación de los
    espacios, que es justo lo que tiene que verse al instante.
    """
    cursor = conexion.cursor()
    try:
        lista_espacios = espacios(cursor)
        datos = {
            "espacios": lista_espacios,
            "libres": sum(1 for e in lista_espacios if not e["ocupado"]),
            "total": len(lista_espacios),
            "actualizado": datetime.now().strftime("%H:%M:%S"),
        }
        datos.update(medios if medios is not None else partes_medias(conexion, cursor))
        datos.update(lentos if lentos is not None else partes_lentas(conexion, cursor))
    finally:
        cursor.close()
    return datos


def partes_medias(conexion, cursor=None):
    """Cambian solo cuando entra o sale un vehículo."""
    propio = cursor is None
    cursor = cursor or conexion.cursor()
    try:
        return {
            "movimientos": movimientos(cursor),
            "recaudacion": recaudacion(cursor),
        }
    finally:
        if propio:
            cursor.close()


def partes_lentas(conexion, cursor=None):
    """Lo que se puede refrescar cada tantos segundos sin que se note."""
    propio = cursor is None
    cursor = cursor or conexion.cursor()
    try:
        return {
            "ocupacion_por_hora": ocupacion_por_hora(cursor),
            "tarifa": tarifa(cursor),
            "totales": totales_historicos(cursor),
        }
    finally:
        if propio:
            cursor.close()
