/* Migración 04: contacto, recuperar contraseña, valoraciones y agenda
   - Solo AÑADE tablas nuevas, no borra nada
   - Se puede ejecutar varias veces sin problemas */

USE encuentrame;


/* Mensajes del formulario de contacto */
CREATE TABLE IF NOT EXISTS contactos (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    nombre   VARCHAR(100) NOT NULL,
    email    VARCHAR(150) NOT NULL,
    mensaje  TEXT NOT NULL,
    leido    TINYINT(1) NOT NULL DEFAULT 0,
    fecha    DATETIME DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;


/* Enlaces para recuperar la contraseña
   - Guardo solo el hash del código (si alguien ve la tabla no puede usarlo)
   - Caducan en 1 hora y solo sirven una vez */
CREATE TABLE IF NOT EXISTS recuperaciones (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    tipo        VARCHAR(20) NOT NULL,              /* paciente o psicologo */
    usuario_id  INT NOT NULL,
    token_hash  CHAR(64) NOT NULL UNIQUE,
    expira      DATETIME NOT NULL,
    usado       TINYINT(1) NOT NULL DEFAULT 0
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;


/* Valoraciones de los pacientes (una por solicitud ya contactada) */
CREATE TABLE IF NOT EXISTS valoraciones (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    solicitud_id  INT NOT NULL UNIQUE,
    psicologo_id  INT NOT NULL,
    paciente_id   INT NULL,
    estrellas     TINYINT NOT NULL,
    comentario    TEXT,
    fecha         DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,
    FOREIGN KEY (psicologo_id) REFERENCES psicologos(id)  ON DELETE CASCADE,
    FOREIGN KEY (paciente_id)  REFERENCES pacientes(id)   ON DELETE SET NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;


/* Agenda: horas libres de cada psicólogo
   - Si solicitud_id tiene valor, la hora está reservada */
CREATE TABLE IF NOT EXISTS horarios (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    psicologo_id  INT NOT NULL,
    fecha_hora    DATETIME NOT NULL,
    solicitud_id  INT NULL UNIQUE,
    UNIQUE (psicologo_id, fecha_hora),
    FOREIGN KEY (psicologo_id) REFERENCES psicologos(id)  ON DELETE CASCADE,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE SET NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
