"""
Pruebas de leer_placa_por_consenso(): que exija que la misma placa
aparezca en dos cuadros distintos antes de aceptarla, y que use lectura
completa si la rápida no alcanza el consenso.

Uso:
    python scripts/test_consenso.py
"""

import unittest
from unittest.mock import patch

from monitor import leer_placa_por_consenso


class TestConsenso(unittest.TestCase):
    def test_acepta_cuando_dos_cuadros_dan_la_misma_placa(self):
        cuadros = iter(["cuadro1", "cuadro2", "cuadro3"])
        with patch("monitor.leer_placa_rapido", return_value="P123ABC"):
            resultado = leer_placa_por_consenso(
                lambda: next(cuadros, None), zona_placa=None, intentos=5,
                intentos_completos=0,
            )
        self.assertEqual(resultado, "P123ABC")

    def test_descarta_si_nunca_hay_dos_lecturas_iguales(self):
        placas = iter(["P123ABC", "P456DEF", "M789GHJ", None, None])
        cuadros = iter(["c1", "c2", "c3", "c4", "c5"])
        with patch("monitor.leer_placa_rapido", side_effect=lambda *a, **k: next(placas)):
            resultado = leer_placa_por_consenso(
                lambda: next(cuadros, None), zona_placa=None, intentos=5,
                intentos_completos=0,
            )
        self.assertIsNone(resultado)

    def test_usa_lectura_completa_en_los_ultimos_intentos(self):
        # 3 intentos rápidos (todos fallan) + 2 completos (el 2do da consenso
        # porque el 1er intento completo ya había leído "P123ABC" una vez).
        cuadros = iter(["c1", "c2", "c3", "c4", "c5"])
        with patch("monitor.leer_placa_rapido", return_value=None) as rapido, \
             patch("monitor.leer_placa_del_cuadro", return_value="P123ABC") as completo:
            resultado = leer_placa_por_consenso(
                lambda: next(cuadros, None), zona_placa=None, intentos=5,
                intentos_completos=2, coincidencias=2,
            )
        self.assertEqual(resultado, "P123ABC")
        self.assertEqual(rapido.call_count, 3)
        self.assertEqual(completo.call_count, 2)

    def test_se_detiene_si_la_camara_deja_de_dar_cuadros(self):
        with patch("monitor.leer_placa_rapido", return_value=None):
            resultado = leer_placa_por_consenso(
                lambda: None, zona_placa=None, intentos=5, intentos_completos=0,
            )
        self.assertIsNone(resultado)


if __name__ == "__main__":
    unittest.main()
