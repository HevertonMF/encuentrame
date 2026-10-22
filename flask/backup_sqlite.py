# Copia de seguridad de la base de datos SQLite (se usa en el servidor)
# - Guarda una copia con la fecha en backups/ y otra llamada encuentrame_ultima.db
# - Borra las copias antiguas y deja solo las últimas 14
# - app.py la llama sola una vez al día; también se puede ejecutar a mano:
#   python3 backup_sqlite.py /home/USUARIO/encuentrame.db

import os
import sqlite3
import sys
from datetime import datetime


# Copio una base SQLite en otra (es segura aunque alguien esté usando la web)
def copiar(origen, destino):
    original = sqlite3.connect(origen)
    copia = sqlite3.connect(destino)
    original.backup(copia)
    copia.close()
    original.close()
    os.chmod(destino, 0o600)          # Solo el dueño de la cuenta puede leerla


def hacer_copia(origen):

    carpeta = os.path.join(os.path.dirname(os.path.abspath(origen)), "backups")
    os.makedirs(carpeta, exist_ok=True)
    os.chmod(carpeta, 0o700)

    destino = os.path.join(carpeta, "encuentrame_" + datetime.now().strftime("%Y-%m-%d_%H-%M") + ".db")
    copiar(origen, destino)

    # La última copia también con un nombre fijo (para descargarla fácil)
    copiar(destino, os.path.join(carpeta, "encuentrame_ultima.db"))

    # Dejo solo las 14 copias más recientes
    copias = sorted(f for f in os.listdir(carpeta) if f.startswith("encuentrame_20"))
    for viejo in copias[:-14]:
        os.remove(os.path.join(carpeta, viejo))

    return destino


# ¿La última copia tiene más de 24 horas (o no existe)?
def toca_copia(origen):
    ultima = os.path.join(os.path.dirname(os.path.abspath(origen)), "backups", "encuentrame_ultima.db")
    if not os.path.exists(ultima):
        return True
    horas = (datetime.now().timestamp() - os.path.getmtime(ultima)) / 3600
    return horas >= 24


if __name__ == "__main__":
    origen = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/encuentrame.db")
    print("Copia guardada en", hacer_copia(origen))
