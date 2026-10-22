# Copia de seguridad de la base de datos SQLite (se ejecuta en el servidor)
# - Guarda una copia con la fecha en ~/backups/ y otra llamada encuentrame_ultima.db
# - Borra las copias antiguas y deja solo las últimas 14
# Uso: python3 backup_sqlite.py /home/USUARIO/encuentrame.db

import os
import sqlite3
import sys
from datetime import datetime

origen = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/encuentrame.db")
carpeta = os.path.join(os.path.dirname(os.path.abspath(origen)), "backups")
os.makedirs(carpeta, exist_ok=True)

fecha = datetime.now().strftime("%Y-%m-%d_%H-%M")
destino = os.path.join(carpeta, "encuentrame_" + fecha + ".db")

# Uso la copia de SQLite (es segura aunque alguien esté usando la web en ese momento)
original = sqlite3.connect(origen)
copia = sqlite3.connect(destino)
original.backup(copia)
copia.close()
original.close()

# La última copia también con un nombre fijo (para descargarla fácil)
ultima = os.path.join(carpeta, "encuentrame_ultima.db")
original = sqlite3.connect(destino)
copia = sqlite3.connect(ultima)
original.backup(copia)
copia.close()
original.close()

# Solo los dueños de la cuenta pueden leer las copias
os.chmod(destino, 0o600)
os.chmod(ultima, 0o600)

# Dejo solo las 14 copias más recientes
copias = sorted(f for f in os.listdir(carpeta) if f.startswith("encuentrame_20"))
for viejo in copias[:-14]:
    os.remove(os.path.join(carpeta, viejo))

print("Copia guardada en", destino)
