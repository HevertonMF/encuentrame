/* Migración 05: fecha en la que el usuario aceptó la política de privacidad (RGPD)
   - Solo AÑADE columnas, no borra nada
   - Se puede ejecutar varias veces sin problemas
   - Las cuentas antiguas quedan sin fecha (NULL) */

USE encuentrame;

ALTER TABLE pacientes
    ADD COLUMN IF NOT EXISTS fecha_consentimiento DATETIME NULL;

ALTER TABLE psicologos
    ADD COLUMN IF NOT EXISTS fecha_consentimiento DATETIME NULL;
