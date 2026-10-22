# Crea la base de datos SQLite de Encuéntrame (para el servidor)
# - Crea las tablas y mete los datos de ejemplo de pythonanywhere.sql
# - Si el archivo ya existe NO hace nada (así nunca se borran datos)
# Uso: python crear_bd_sqlite.py encuentrame.db

import os
import sqlite3
import sys

ruta = sys.argv[1] if len(sys.argv) > 1 else "encuentrame.db"

if os.path.exists(ruta):
    print("La base de datos", ruta, "ya existe. No hago nada.")
    raise SystemExit

# Tablas (igual que en MySQL, adaptadas a SQLite)
TABLAS = """
CREATE TABLE psicologos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT NOT NULL,
    email             TEXT NOT NULL UNIQUE,
    numero_colegiado  TEXT UNIQUE,
    telefono          TEXT,
    especialidades    TEXT,
    bio               TEXT,
    password_hash     TEXT,
    foto              TEXT,
    fecha_registro    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    aprobado          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE pacientes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    telefono        TEXT,
    fecha_registro  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE especialidades (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL UNIQUE
);

CREATE TABLE psicologo_especialidad (
    psicologo_id     INTEGER NOT NULL,
    especialidad_id  INTEGER NOT NULL,
    PRIMARY KEY (psicologo_id, especialidad_id),
    FOREIGN KEY (psicologo_id)    REFERENCES psicologos(id)     ON DELETE CASCADE,
    FOREIGN KEY (especialidad_id) REFERENCES especialidades(id) ON DELETE CASCADE
);

CREATE TABLE solicitudes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    psicologo_id     INTEGER NOT NULL,
    paciente_id      INTEGER,
    nombre_paciente  TEXT NOT NULL,
    email_paciente   TEXT NOT NULL,
    telefono         TEXT,
    resumen          TEXT NOT NULL,
    contacto         TEXT DEFAULT 'email' CHECK (contacto IN ('email', 'telefono')),
    estado           TEXT DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'contactado')),
    fecha            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (psicologo_id) REFERENCES psicologos(id) ON DELETE CASCADE,
    FOREIGN KEY (paciente_id)  REFERENCES pacientes(id)  ON DELETE SET NULL
);

CREATE TABLE administradores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL
);
"""

# Los datos de ejemplo son los mismos que en pythonanywhere.sql (desde el primer INSERT)
carpeta = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(carpeta, "pythonanywhere.sql"), encoding="utf-8") as archivo:
    texto = archivo.read()
datos = texto[texto.index("INSERT INTO"):]

conexion = sqlite3.connect(ruta)
conexion.executescript(TABLAS + datos)
conexion.commit()

cursor = conexion.cursor()
cursor.execute("SELECT COUNT(*) FROM psicologos")
print("Base de datos creada en", ruta, "con", cursor.fetchone()[0], "psicólogos de ejemplo.")
conexion.close()
