/* Migración 02: contraseña de prueba para los psicólogos de ejemplo
   - Contraseña: demo1234 (hash generado con werkzeug, el mismo que usa app.py)
   - Solo cambia los que todavía no tienen contraseña */

USE encuentrame;

UPDATE psicologos
SET password_hash = 'scrypt:32768:8:1$zLTvmDSX5tCUIM5R$fbdd34f41aa6a7020e30f5944e55b37d0a15a4a6b2aeba6f41e8fa7c05de13960ccfdd800d398d416ef5bca6bef6fde22bd24bdca94e10e5fbc523ca8bc159dc'
WHERE password_hash IS NULL;
