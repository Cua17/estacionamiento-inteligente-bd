"""
Pruebas del filtro anti-parpadeo (EstadoEstable).

Uso:
    python scripts/test_ocupacion.py
"""

import unittest

from ocupacion import EstadoEstable


class TestEstadoEstable(unittest.TestCase):
    def test_no_confirma_un_cambio_con_una_sola_lectura(self):
        estable = EstadoEstable(lecturas_para_confirmar=3, estado_inicial={"A1": False})
        self.assertIsNone(estable.actualizar("A1", True))

    def test_confirma_despues_de_n_lecturas_seguidas(self):
        estable = EstadoEstable(lecturas_para_confirmar=3, estado_inicial={"A1": False})
        self.assertIsNone(estable.actualizar("A1", True))
        self.assertIsNone(estable.actualizar("A1", True))
        self.assertTrue(estable.actualizar("A1", True))

    def test_una_lectura_contraria_reinicia_la_cuenta(self):
        """Un parpadeo en medio no debe dejar el contador a mitad de camino."""
        estable = EstadoEstable(lecturas_para_confirmar=3, estado_inicial={"A1": False})
        estable.actualizar("A1", True)
        estable.actualizar("A1", True)
        estable.actualizar("A1", False)      # parpadeo: vuelve al estado confirmado
        self.assertIsNone(estable.actualizar("A1", True))
        self.assertIsNone(estable.actualizar("A1", True))
        self.assertTrue(estable.actualizar("A1", True))

    def test_la_camara_puede_contradecir_a_la_base_desde_la_primera_lectura(self):
        """
        El caso que reventaba: la base dice que el espacio está ocupado (una
        sesión que quedó abierta) y la cámara lo ve libre desde el primer
        cuadro. _confirmado venía sembrado desde la base pero _candidato
        arrancaba vacío, así que la primera discrepancia daba KeyError y
        tumbaba el monitor entero.
        """
        estable = EstadoEstable(lecturas_para_confirmar=2, estado_inicial={"A1": True})
        self.assertIsNone(estable.actualizar("A1", False))   # antes: KeyError
        self.assertFalse(estable.actualizar("A1", False))    # confirma el cambio a libre

    def test_espacio_que_no_venia_en_el_estado_inicial(self):
        estable = EstadoEstable(lecturas_para_confirmar=2, estado_inicial={})
        self.assertIsNone(estable.actualizar("A9", True))    # se adopta esta lectura
        self.assertIsNone(estable.actualizar("A9", False))
        self.assertFalse(estable.actualizar("A9", False))

    def test_los_espacios_no_se_pisan_entre_si(self):
        estable = EstadoEstable(lecturas_para_confirmar=2,
                                estado_inicial={"A1": False, "A2": False})
        estable.actualizar("A1", True)
        self.assertIsNone(estable.actualizar("A2", True))    # A2 arranca su propia cuenta
        self.assertTrue(estable.actualizar("A1", True))


if __name__ == "__main__":
    unittest.main()
