"""
Llena la base con un día de actividad plausible, para que el dashboard tenga
algo que mostrar en una demostración.

Los datos son inventados en el sentido de que esos vehículos no existieron,
pero NO son filas escritas a mano: pasan por las mismas funciones de
parqueo.py que usa el monitor real, así que las sesiones y los cobros se
calculan con la misma lógica y la misma tarifa. Si el cálculo estuviera mal,
acá también saldría mal.

Uso:
    python scripts/generar_datos_demo.py
    python scripts/generar_datos_demo.py --sesiones 20
"""

import argparse
import random
from datetime import datetime, timedelta

import parqueo

# Placas con formato guatemalteco válido (1 letra + 3 dígitos + 3 letras).
PLACAS = [
    "P123ABC", "P456DEF", "C789GHJ", "M234KLM", "P871QRS",
    "C305TUV", "P642WXY", "M118BCD", "P957FGH", "C264JKL",
]

# Un parqueo real no se llena parejo: hay pico de entrada en la mañana y
# otro al mediodía. Estos pesos por hora hacen que el perfil de ocupación
# se parezca a eso en vez de quedar plano.
PESO_POR_HORA = {
    6: 1, 7: 4, 8: 8, 9: 7, 10: 5, 11: 5, 12: 8, 13: 7,
    14: 5, 15: 4, 16: 4, 17: 5, 18: 3, 19: 2, 20: 1,
}


def hora_de_entrada_aleatoria(hoy):
    horas = list(PESO_POR_HORA)
    hora = random.choices(horas, weights=[PESO_POR_HORA[h] for h in horas])[0]
    return hoy.replace(hour=hora, minute=random.randint(0, 59), second=0, microsecond=0)


def main():
    parser = argparse.ArgumentParser(description="Genera actividad de demostración")
    parser.add_argument("--sesiones", type=int, default=14, help="Sesiones a crear (default: 14)")
    parser.add_argument("--activas", type=int, default=2,
                        help="Cuántas quedan abiertas al final (default: 2)")
    parser.add_argument("--semilla", type=int, default=7,
                        help="Semilla aleatoria, para poder repetir el mismo set")
    args = parser.parse_args()

    random.seed(args.semilla)
    ahora = datetime.now()
    hoy = ahora.replace(microsecond=0)

    conexion = parqueo.conectar_parqueo()
    cursor = conexion.cursor()
    etiquetas = [fila[1] for fila in parqueo.listar_espacios(cursor)]
    cursor.close()

    if not etiquetas:
        raise SystemExit("No hay espacios en la base. Corré primero: python scripts/init_db.py")

    creadas = 0
    for _ in range(args.sesiones):
        entrada = hora_de_entrada_aleatoria(hoy)
        if entrada >= ahora:
            continue
        # Estadías cortas son lo normal; alguna larga da variedad al perfil.
        minutos = random.choice([18, 25, 34, 47, 52, 65, 78, 95, 120, 150])
        salida = entrada + timedelta(minutes=minutos)
        if salida > ahora:
            continue

        cursor = conexion.cursor()
        libre = parqueo.primer_espacio_libre(cursor)
        cursor.close()
        if libre is None:
            continue

        placa = random.choice(PLACAS)
        sesion_id = parqueo.abrir_sesion(conexion, placa, libre[1], hora_entrada=entrada)
        parqueo.cerrar_sesion(conexion, sesion_id, hora_salida=salida)
        creadas += 1

    # Deja algunas sesiones abiertas para que el registro no se vea vacío.
    abiertas = 0
    for _ in range(args.activas):
        cursor = conexion.cursor()
        libre = parqueo.primer_espacio_libre(cursor)
        cursor.close()
        if libre is None:
            break
        entrada = ahora - timedelta(minutes=random.randint(8, 70))
        parqueo.abrir_sesion(conexion, random.choice(PLACAS), libre[1], hora_entrada=entrada)
        abiertas += 1

    conexion.close()
    print(f"Listo: {creadas} sesiones cerradas con su cobro y {abiertas} sesiones abiertas.")
    print("Para volver a dejar la base limpia: python scripts/reset_demo.py")


if __name__ == "__main__":
    main()
