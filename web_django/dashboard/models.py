"""
Modelos de solo lectura sobre las 5 tablas de negocio (managed=False:
Django nunca las crea ni las altera, ya existen y las escribe
parqueo.py). Reflejan exactamente schema.sql -- si el schema cambia, este
archivo se actualiza a mano.
"""

from django.db import models


class Vehiculo(models.Model):
    placa = models.CharField(max_length=15, primary_key=True)
    primera_deteccion = models.DateTimeField()
    notas = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "vehiculos"

    def __str__(self):
        return self.placa


class Espacio(models.Model):
    etiqueta = models.CharField(max_length=10, unique=True)
    estado = models.CharField(max_length=10)  # 'libre' | 'ocupado'
    actualizado_en = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "espacios"
        ordering = ["etiqueta"]

    def __str__(self):
        return self.etiqueta


class Tarifa(models.Model):
    nombre = models.CharField(max_length=50)
    precio_por_hora = models.DecimalField(max_digits=8, decimal_places=2)
    vigente_desde = models.DateTimeField()
    vigente_hasta = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "tarifas"

    def __str__(self):
        return f"{self.nombre} (Q{self.precio_por_hora}/h)"


class Sesion(models.Model):
    placa = models.CharField(max_length=15)
    espacio = models.ForeignKey(
        Espacio, on_delete=models.DO_NOTHING, db_column="espacio_id",
        related_name="sesiones",
    )
    hora_entrada = models.DateTimeField()
    hora_salida = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=10)  # 'activa' | 'cerrada'

    class Meta:
        managed = False
        db_table = "sesiones"

    def __str__(self):
        return f"{self.placa} en {self.espacio_id}"


class Cobro(models.Model):
    sesion = models.OneToOneField(
        Sesion, on_delete=models.DO_NOTHING, db_column="sesion_id",
        related_name="cobro",
    )
    tarifa = models.ForeignKey(Tarifa, on_delete=models.DO_NOTHING, db_column="tarifa_id")
    minutos_totales = models.IntegerField()
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_cobro = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "cobros"
