"""
Django asume el driver MySQLdb (mysqlclient), que necesita compilar
extensiones en C. PyMySQL es puro Python y se hace pasar por MySQLdb con
esta llamada -- se hace acá porque __init__.py del paquete de settings se
importa antes que cualquier otra cosa de Django.
"""
import pymysql

pymysql.install_as_MySQLdb()
pymysql.version_info = (1, 4, 6, "final", 0)  # Django valida esta tupla al conectar
