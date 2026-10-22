# Primero importo la librería
import mysql.connector

# Me conecto con las credenciales correctas
connection = mysql.connector.connect(
  host='localhost',
  user='encuentrame',
  password='Encuentrame123$',
  database='encuentrame'
)

# Creo un cursor
cursor = connection.cursor()

################### LISTA DE TABLAS ################
tablas = ["psicologos", "pacientes", "especialidades", "psicologo_especialidad", "solicitudes"]

################### PIDO TODOS LOS DATOS DE CADA TABLA ################
for tabla in tablas:

  print("\n==================", tabla.upper(), "==================")

  cursor.execute("SELECT * FROM " + tabla)
  filas = cursor.fetchall()

  # Nombres de las columnas
  columnas = [columna[0] for columna in cursor.description]
  print(columnas)

  for fila in filas:
    print(fila)

  print("Total de filas:", len(filas))

# Todo lo que se abre se debe cerrar
cursor.close()
connection.close()
