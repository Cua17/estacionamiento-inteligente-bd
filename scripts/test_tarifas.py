"""
Pruebas del cálculo de cobro por tramos.

Es la parte del sistema que toca dinero, así que se prueba sola, sin base
de datos: calcular_monto_por_tramos() recibe los tramos ya leídos y
devuelve el monto.

Uso:
    python scripts/test_tarifas.py
"""

import unittest

from parqueo import calcular_monto, calcular_monto_por_tramos

# Los mismos tramos que instala migrar_tarifa_por_tramos.py.
# Cada tramo es (desde_minuto, monto_fijo, precio_por_hora_adicional):
#   menos de 15 min  gratis
#   15 a 60 min      Q15 fijo
#   1 a 5 horas      Q35 fijo
#   más de 5 horas   Q35 + Q10 por cada hora empezada de más
TRAMOS = [
    (0, 0.00, 0.00),
    (15, 15.00, 0.00),
    (60, 35.00, 0.00),
    (300, 35.00, 10.00),
]


class TestTramos(unittest.TestCase):
    def test_menos_de_15_minutos_es_gratis(self):
        for minutos in (1, 5, 14):
            monto, _ = calcular_monto_por_tramos(TRAMOS, minutos)
            self.assertEqual(monto, 0.0, f"{minutos} min deberían ser gratis")

    def test_de_15_a_60_minutos_son_15_quetzales_fijos(self):
        for minutos in (15, 20, 40, 59):
            monto, _ = calcular_monto_por_tramos(TRAMOS, minutos)
            self.assertEqual(monto, 15.0, f"a los {minutos} min debería cobrar Q15")

    def test_de_1_a_5_horas_son_35_quetzales_fijos(self):
        for minutos in (60, 90, 180, 299):
            monto, _ = calcular_monto_por_tramos(TRAMOS, minutos)
            self.assertEqual(monto, 35.0, f"a los {minutos} min debería cobrar Q35")

    def test_a_las_5_horas_exactas_sigue_siendo_35(self):
        """El tramo abierto arranca en Q35 -- no debe haber un salto raro."""
        monto, _ = calcular_monto_por_tramos(TRAMOS, 300)
        self.assertEqual(monto, 35.0)

    def test_pasadas_las_5_horas_suma_10_por_hora_empezada(self):
        # 5h01 -> primera hora empezada de más
        self.assertEqual(calcular_monto_por_tramos(TRAMOS, 301)[0], 45.0)
        # 6h00 -> sigue siendo una hora de más
        self.assertEqual(calcular_monto_por_tramos(TRAMOS, 360)[0], 45.0)
        # 6h01 -> segunda hora empezada
        self.assertEqual(calcular_monto_por_tramos(TRAMOS, 361)[0], 55.0)
        # 8h00 -> tres horas de más
        self.assertEqual(calcular_monto_por_tramos(TRAMOS, 480)[0], 65.0)

    def test_los_saltos_entre_tramos_caen_donde_deben(self):
        """El minuto exacto del cambio importa: es donde se discute un cobro."""
        self.assertEqual(calcular_monto_por_tramos(TRAMOS, 14)[0], 0.0)
        self.assertEqual(calcular_monto_por_tramos(TRAMOS, 15)[0], 15.0)
        self.assertEqual(calcular_monto_por_tramos(TRAMOS, 59)[0], 15.0)
        self.assertEqual(calcular_monto_por_tramos(TRAMOS, 60)[0], 35.0)
        self.assertEqual(calcular_monto_por_tramos(TRAMOS, 299)[0], 35.0)
        self.assertEqual(calcular_monto_por_tramos(TRAMOS, 300)[0], 35.0)

    def test_se_cobra_el_minuto_empezado(self):
        # 14.2 min se redondea hacia arriba a 15 -> ya entra al tramo de Q15
        monto, cobrables = calcular_monto_por_tramos(TRAMOS, 14.2)
        self.assertEqual(cobrables, 15)
        self.assertEqual(monto, 15.0)

    def test_el_monto_nunca_baja_al_quedarse_mas_tiempo(self):
        anterior = -1.0
        for minutos in range(0, 900, 3):
            monto, _ = calcular_monto_por_tramos(TRAMOS, minutos)
            self.assertGreaterEqual(
                monto, anterior,
                f"a los {minutos} min el cobro bajó, eso no puede pasar")
            anterior = monto

    def test_sin_tramos_no_revienta(self):
        monto, cobrables = calcular_monto_por_tramos([], 45)
        self.assertEqual(monto, 0.0)
        self.assertEqual(cobrables, 45)

    def test_la_tarifa_plana_vieja_sigue_disponible(self):
        """calcular_monto() se mantiene por compatibilidad."""
        monto, cobrables = calcular_monto(5.00, 60)
        self.assertEqual(monto, 5.0)
        self.assertEqual(cobrables, 60)


if __name__ == "__main__":
    unittest.main()
