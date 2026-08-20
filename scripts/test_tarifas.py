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

# Los mismos tramos que instala migrar_tarifa_por_tramos.py:
#   0-15 min   gratis
#   15-60 min  Q5.00/hora
#   60-120 min Q7.00/hora
#   120+ min   Q10.00/hora
TRAMOS = [(0, 0.00), (15, 5.00), (60, 7.00), (120, 10.00)]


class TestTramos(unittest.TestCase):
    def test_menos_de_15_minutos_es_gratis(self):
        for minutos in (1, 5, 14, 15):
            monto, cobrables = calcular_monto_por_tramos(TRAMOS, minutos)
            self.assertEqual(monto, 0.0, f"{minutos} min deberían ser gratis")

    def test_media_hora_cobra_solo_los_minutos_pasados_de_15(self):
        # 30 min = 15 gratis + 15 min a Q5/h = 15/60 * 5 = Q1.25
        monto, cobrables = calcular_monto_por_tramos(TRAMOS, 30)
        self.assertEqual(cobrables, 30)
        self.assertEqual(monto, 1.25)

    def test_una_hora_exacta(self):
        # 60 min = 15 gratis + 45 min a Q5/h = 45/60 * 5 = Q3.75
        monto, _ = calcular_monto_por_tramos(TRAMOS, 60)
        self.assertEqual(monto, 3.75)

    def test_dos_horas_cruza_al_tramo_mas_caro(self):
        # 120 min = 15 gratis + 45 a Q5 (3.75) + 60 a Q7 (7.00) = Q10.75
        monto, _ = calcular_monto_por_tramos(TRAMOS, 120)
        self.assertEqual(monto, 10.75)

    def test_tres_horas_usa_el_ultimo_tramo_abierto(self):
        # 180 min = 3.75 + 7.00 + 60 min a Q10/h (10.00) = Q20.75
        monto, _ = calcular_monto_por_tramos(TRAMOS, 180)
        self.assertEqual(monto, 20.75)

    def test_se_cobra_el_minuto_empezado(self):
        # 30.2 min se redondea hacia arriba a 31, igual que antes
        monto, cobrables = calcular_monto_por_tramos(TRAMOS, 30.2)
        self.assertEqual(cobrables, 31)

    def test_el_monto_nunca_baja_al_quedarse_mas_tiempo(self):
        anterior = -1.0
        for minutos in range(0, 400, 7):
            monto, _ = calcular_monto_por_tramos(TRAMOS, minutos)
            self.assertGreaterEqual(
                monto, anterior,
                f"a los {minutos} min el cobro bajó, eso no puede pasar")
            anterior = monto

    def test_una_tarifa_plana_sigue_funcionando_igual_que_antes(self):
        """La firma vieja (un solo precio por hora) tiene que dar lo mismo."""
        plano = [(0, 5.00)]
        for minutos in (1, 17, 60, 133):
            por_tramos, _ = calcular_monto_por_tramos(plano, minutos)
            viejo, _ = calcular_monto(5.00, minutos)
            self.assertEqual(por_tramos, viejo, f"difieren a los {minutos} min")

    def test_sin_tramos_no_revienta(self):
        monto, cobrables = calcular_monto_por_tramos([], 45)
        self.assertEqual(monto, 0.0)
        self.assertEqual(cobrables, 45)


if __name__ == "__main__":
    unittest.main()
