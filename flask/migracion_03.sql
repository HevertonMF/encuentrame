/* Migración 03: número de colegiado, aprobación de perfiles y administradores
   - Solo AÑADE tablas y columnas, no borra nada
   - Se puede ejecutar varias veces sin problemas */

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

/* Administrador de prueba: admin@encuentrame.local / admin1234 */
INSERT IGNORE INTO administradores (nombre, email, password_hash) VALUES
('Administrador', 'admin@encuentrame.local',
 'scrypt:32768:8:1$mQlVUAyQXHYgR3ts$9748b5c631575229c99c5cbfd7ad194d71e72a810cbd8b2e0b056ab01db90c2a088525811b12ef2fcafb5c0449a2b08a63bef56407fbdd05803e786c01d93188');
