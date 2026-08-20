"""
Pruebas de leer_placa_por_consenso(): que exija que la misma placa
aparezca en dos cuadros distintos antes de aceptarla, y que use lectura
completa en los últimos cuadros si la rápida no alcanzó el consenso.

Uso:
    python scripts/test_consenso.py
"""

import unittest
from unittest.mock import patch

from monitor import leer_placa_por_consenso


class TestConsenso(unittest.TestCase):
    def test_acepta_cuando_dos_cuadros_dan_la_misma_placa(self):
        with patch("monitor.leer_placa_rapido", return_value="P123ABC"):
            resultado = leer_placa_por_consenso(
                ["c1", "c2", "c3"], zona_placa=None, intentos_completos=0)
        self.assertEqual(resultado, "P123ABC")

    def test_descarta_si_nunca_hay_dos_lecturas_iguales(self):
        placas = iter(["P123ABC", "P456DEF", "M789GHJ", None, None])
        with patch("monitor.leer_placa_rapido", side_effect=lambda *a, **k: next(placas)):
            resultado = leer_placa_por_consenso(
                ["c1", "c2", "c3", "c4", "c5"], zona_placa=None, intentos_completos=0)
        self.assertIsNone(resultado)

    def test_usa_lectura_completa_en_los_ultimos_cuadros(self):
        with patch("monitor.leer_placa_rapido", return_value=None) as rapido, \
             patch("monitor.leer_placa_del_cuadro", return_value="P123ABC") as completo:
            resultado = leer_placa_por_consenso(
                ["c1", "c2", "c3", "c4", "c5"], zona_placa=None,
                intentos_completos=2, coincidencias=2)
        self.assertEqual(resultado, "P123ABC")
        self.assertEqual(rapido.call_count, 3)
        self.assertEqual(completo.call_count, 2)

    def test_sin_cuadros_no_revienta(self):
        with patch("monitor.leer_placa_rapido", return_value=None):
            self.assertIsNone(
                leer_placa_por_consenso([], zona_placa=None, intentos_completos=0))

    def test_saltea_los_cuadros_vacios(self):
        """La cámara puede no haber entregado imagen en algún instante."""
        with patch("monitor.leer_placa_rapido", return_value="P123ABC") as rapido:
            resultado = leer_placa_por_consenso(
                [None, "c1", None, "c2"], zona_placa=None, intentos_completos=0)
        self.assertEqual(resultado, "P123ABC")
        self.assertEqual(rapido.call_count, 2)

    def test_lee_los_cuadros_que_le_dan_y_no_pide_otros(self):
        """
        El punto del cambio: los cuadros vienen del momento de la entrada.
        Si esta función pidiera cuadros en vivo, leería el piso vacío cuando
        el vehículo ya se fue.
        """
        vistos = []

        def espia(cuadro, _zona):
            vistos.append(cuadro)
            return None

        with patch("monitor.leer_placa_rapido", side_effect=espia), \
             patch("monitor.leer_placa_del_cuadro", side_effect=espia):
            leer_placa_por_consenso(["a", "b", "c"], zona_placa=None, intentos_completos=1)

        self.assertEqual(vistos, ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
