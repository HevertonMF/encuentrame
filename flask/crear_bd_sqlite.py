# Crea o actualiza la base de datos SQLite de Encuéntrame (para el servidor)
# - Si NO existe: crea todas las tablas y mete los datos de ejemplo de pythonanywhere.sql
# - Si YA existe: solo añade las tablas nuevas que falten (nunca borra datos)
# Uso: python crear_bd_sqlite.py encuentrame.db

import os
import sqlite3
import sys

ruta = sys.argv[1] if len(sys.argv) > 1 else "encuentrame.db"

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
    aprobado          INTEGER NOT NULL DEFAULT 0,
    fecha_consentimiento TIMESTAMP
);

CREATE TABLE pacientes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    telefono        TEXT,
    fecha_registro  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_consentimiento TIMESTAMP
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

# Tablas nuevas (contacto, recuperar contraseña, valoraciones y agenda)
# Llevan IF NOT EXISTS para poder añadirlas a una base que ya existe
TABLAS_NUEVAS = """
CREATE TABLE IF NOT EXISTS contactos (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT NOT NULL,
    email    TEXT NOT NULL,
    mensaje  TEXT NOT NULL,
    leido    INTEGER NOT NULL DEFAULT 0,
    fecha    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recuperaciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT NOT NULL,
    usuario_id  INTEGER NOT NULL,
    token_hash  TEXT NOT NULL UNIQUE,
    expira      TIMESTAMP NOT NULL,
    usado       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS valoraciones (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id  INTEGER NOT NULL UNIQUE,
    psicologo_id  INTEGER NOT NULL,
    paciente_id   INTEGER,
    estrellas     INTEGER NOT NULL CHECK (estrellas BETWEEN 1 AND 5),
    comentario    TEXT,
    fecha         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,
    FOREIGN KEY (psicologo_id) REFERENCES psicologos(id)  ON DELETE CASCADE,
    FOREIGN KEY (paciente_id)  REFERENCES pacientes(id)   ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS horarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    psicologo_id  INTEGER NOT NULL,
    fecha_hora    TIMESTAMP NOT NULL,
    solicitud_id  INTEGER UNIQUE,
    UNIQUE (psicologo_id, fecha_hora),
    FOREIGN KEY (psicologo_id) REFERENCES psicologos(id)  ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE SET NULL
);
"""

# Si la base ya existe, solo añado las tablas nuevas
if os.path.exists(ruta):
    conexion = sqlite3.connect(ruta)
    conexion.executescript(TABLAS_NUEVAS)

    # Columnas nuevas (SQLite no tiene ADD COLUMN IF NOT EXISTS: miro antes si existen)
    for tabla in ("pacientes", "psicologos"):
        columnas = [fila[1] for fila in conexion.execute("PRAGMA table_info(" + tabla + ")")]
        if "fecha_consentimiento" not in columnas:
            conexion.execute("ALTER TABLE " + tabla + " ADD COLUMN fecha_consentimiento TIMESTAMP")

    conexion.commit()
    conexion.close()
    print("La base de datos", ruta, "ya existía: he añadido las tablas nuevas que faltaban.")
    raise SystemExit

# Los datos de ejemplo son los mismos que en pythonanywhere.sql (desde el primer INSERT)
carpeta = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(carpeta, "pythonanywhere.sql"), encoding="utf-8") as archivo:
    texto = archivo.read()
datos = texto[texto.index("INSERT INTO"):]

conexion = sqlite3.connect(ruta)
conexion.executescript(TABLAS + TABLAS_NUEVAS + datos)
conexion.commit()

cursor = conexion.cursor()
cursor.execute("SELECT COUNT(*) FROM psicologos")
print("Base de datos creada en", ruta, "con", cursor.fetchone()[0], "psicólogos de ejemplo.")
conexion.close()
