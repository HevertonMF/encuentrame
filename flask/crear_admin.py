# Crea un administrador en la base de datos
# La contraseña se escribe en la terminal y nunca se guarda en el código
# Uso: python crear_admin.py

from getpass import getpass
from werkzeug.security import generate_password_hash
from app import conectar

nombre = input("Nombre del administrador: ").strip()
email = input("Correo del administrador: ").strip().lower()
password = getpass("Contraseña (no se ve al escribir): ")

if len(password) < 8:
    print("La contraseña debe tener al menos 8 caracteres.")
    raise SystemExit

conexion = conectar()
cursor = conexion.cursor()
cursor.execute(
    "INSERT INTO administradores (nombre, email, password_hash) VALUES (%s, %s, %s)",
    (nombre, email, generate_password_hash(password))
)
conexion.commit()
cursor.close()
conexion.close()

print("Administrador creado. Entra en /entrar?tipo=admin")
