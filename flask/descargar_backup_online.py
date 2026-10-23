# Descarga a mi PC la última copia de la base de datos de la web online
# - Usa la API de PythonAnywhere con mi token (archivo token_pythonanywhere.txt, NO se sube a GitHub)
# - Guarda la copia en la carpeta backups/ con la fecha
# Uso: python descargar_backup_online.py

import os
import urllib.request
import urllib.error
from datetime import datetime

USUARIO = "encuentrame"
ARCHIVO_REMOTO = "/home/" + USUARIO + "/backups/encuentrame_ultima.db"

carpeta = os.path.dirname(os.path.abspath(__file__))
ruta_token = os.path.join(carpeta, "token_pythonanywhere.txt")

if not os.path.exists(ruta_token):
    print("Falta el archivo token_pythonanywhere.txt con tu API token de PythonAnywhere.")
    print("Lo consigues en PythonAnywhere -> Account -> API token.")
    raise SystemExit

import re

with open(ruta_token) as archivo:
    texto = archivo.read()

# El token son 40 caracteres hexadecimales (así funciona aunque se pegue el ejemplo entero)
encontrado = re.search(r"\b[0-9a-f]{40}\b", texto)
if not encontrado:
    print("No encuentro el token en token_pythonanywhere.txt (deben ser 40 letras y números).")
    raise SystemExit
token = encontrado.group(0)

url = "https://www.pythonanywhere.com/api/v0/user/" + USUARIO + "/files/path" + ARCHIVO_REMOTO
peticion = urllib.request.Request(url, headers={"Authorization": "Token " + token})

# Si algo falla, enseño solo el tipo de error (nunca el token)
try:
    with urllib.request.urlopen(peticion, timeout=60) as respuesta:
        datos = respuesta.read()
except urllib.error.HTTPError as error:
    print("PythonAnywhere ha respondido con el error", error.code, "(¿token caducado o borrado?)")
    raise SystemExit
except Exception as error:
    print("No se pudo descargar la copia:", type(error).__name__)
    raise SystemExit

os.makedirs(os.path.join(carpeta, "backups"), exist_ok=True)
destino = os.path.join(carpeta, "backups", "online_" + datetime.now().strftime("%Y-%m-%d_%H-%M") + ".db")
with open(destino, "wb") as archivo:
    archivo.write(datos)

print("Copia descargada en", destino, "(" + str(len(datos)) + " bytes)")
