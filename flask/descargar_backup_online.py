# Descarga a mi PC la última copia de la base de datos de la web online
# - Usa la API de PythonAnywhere con mi token (archivo token_pythonanywhere.txt, NO se sube a GitHub)
# - Guarda la copia en la carpeta backups/ con la fecha
# Uso: python descargar_backup_online.py

import os
import urllib.request
from datetime import datetime

USUARIO = "encuentrame"
ARCHIVO_REMOTO = "/home/" + USUARIO + "/backups/encuentrame_ultima.db"

carpeta = os.path.dirname(os.path.abspath(__file__))
ruta_token = os.path.join(carpeta, "token_pythonanywhere.txt")

if not os.path.exists(ruta_token):
    print("Falta el archivo token_pythonanywhere.txt con tu API token de PythonAnywhere.")
    print("Lo consigues en PythonAnywhere -> Account -> API token.")
    raise SystemExit

with open(ruta_token) as archivo:
    token = archivo.read().strip()

url = "https://www.pythonanywhere.com/api/v0/user/" + USUARIO + "/files/path" + ARCHIVO_REMOTO
peticion = urllib.request.Request(url, headers={"Authorization": "Token " + token})

with urllib.request.urlopen(peticion) as respuesta:
    datos = respuesta.read()

os.makedirs(os.path.join(carpeta, "backups"), exist_ok=True)
destino = os.path.join(carpeta, "backups", "online_" + datetime.now().strftime("%Y-%m-%d_%H-%M") + ".db")
with open(destino, "wb") as archivo:
    archivo.write(datos)

print("Copia descargada en", destino, "(" + str(len(datos)) + " bytes)")
