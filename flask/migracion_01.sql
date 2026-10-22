/* Migración 01: amplío la base de datos de Encuéntrame
   - Solo AÑADE tablas y columnas, no borra nada (app.py sigue funcionando)
   - Se puede ejecutar varias veces sin problemas */

USE encuentrame;


/* Tabla de pacientes */
CREATE TABLE IF NOT EXISTS pacientes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    telefono        VARCHAR(30),
    fecha_registro  DATETIME DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;


/* Psicólogos: añado contraseña, foto y fecha de registro */
ALTER TABLE psicologos
    ADD COLUMN IF NOT EXISTS password_hash  VARCHAR(255) NULL,
    ADD COLUMN IF NOT EXISTS foto           VARCHAR(255) NULL,      /* ruta de la imagen */
    ADD COLUMN IF NOT EXISTS fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP;


/* Tabla de especialidades */
CREATE TABLE IF NOT EXISTS especialidades (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    nombre  VARCHAR(60) NOT NULL UNIQUE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

INSERT IGNORE INTO especialidades (nombre) VALUES
('Acompañamiento en enfermedad'), ('Adicciones'), ('Ansiedad'), ('Ansiedad social'),
('Ataques de pánico'), ('Autoestima'), ('Control de impulsos'), ('Depresión'),
('Duelo'), ('Estrés y burnout'), ('Fobias'), ('Sexualidad'), ('TDAH'), ('TOC'),
('Terapia de pareja'), ('Terapia infantil'), ('Trastornos alimentarios'),
('Trastornos del sueño'), ('Trauma');


/* Relación N:M entre psicólogos y especialidades */
CREATE TABLE IF NOT EXISTS psicologo_especialidad (
    psicologo_id     INT NOT NULL,
    especialidad_id  INT NOT NULL,
    PRIMARY KEY (psicologo_id, especialidad_id),
    FOREIGN KEY (psicologo_id)    REFERENCES psicologos(id)     ON DELETE CASCADE,
    FOREIGN KEY (especialidad_id) REFERENCES especialidades(id) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

/* Paso las especialidades que estaban separadas por comas a la nueva tabla */
INSERT IGNORE INTO psicologo_especialidad (psicologo_id, especialidad_id)
SELECT p.id, e.id
FROM psicologos p
JOIN especialidades e ON FIND_IN_SET(e.nombre, p.especialidades) > 0;


/* Solicitudes: enlazo con el paciente (opcional, para no romper las antiguas) */
ALTER TABLE solicitudes
    ADD COLUMN IF NOT EXISTS paciente_id INT NULL AFTER psicologo_id;

ALTER TABLE solicitudes
    ADD CONSTRAINT fk_solicitud_paciente FOREIGN KEY IF NOT EXISTS (paciente_id)
        REFERENCES pacientes(id) ON DELETE SET NULL;
