/* Migración 03: número de colegiado, aprobación de perfiles y administradores
   - Solo AÑADE tablas y columnas, no borra nada
   - Se puede ejecutar varias veces sin problemas
   - El administrador se crea aparte con crear_admin.py */

USE encuentrame;


/* Número de colegiado del psicólogo (no se puede repetir) */
ALTER TABLE psicologos
    ADD COLUMN IF NOT EXISTS numero_colegiado VARCHAR(30) NULL UNIQUE AFTER email;

/* Los perfiles nuevos esperan a que un administrador los apruebe */
ALTER TABLE psicologos
    ADD COLUMN IF NOT EXISTS aprobado TINYINT(1) NOT NULL DEFAULT 0;

/* Los 16 psicólogos de ejemplo ya estaban publicados: los apruebo
   y les pongo un número de colegiado ficticio (CV-PSI-1001, CV-PSI-1002...) */
UPDATE psicologos SET aprobado = 1 WHERE id <= 16;

UPDATE psicologos
SET numero_colegiado = CONCAT('CV-PSI-', 1000 + id)
WHERE id <= 16 AND numero_colegiado IS NULL;


/* Tabla de administradores */
CREATE TABLE IF NOT EXISTS administradores (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

/* El administrador se crea con: python crear_admin.py
   (la contraseña se escribe en la terminal y no se guarda en el código) */
