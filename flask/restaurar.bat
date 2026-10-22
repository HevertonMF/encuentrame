@echo off
REM Restaura la base de datos desde una copia de la carpeta "backups"
REM Uso: restaurar.bat backups\encuentrame_2026-10-06_20-38.sql

cd /d "%~dp0"
if "%~1"=="" (
    echo Indica el archivo de copia. Copias disponibles:
    dir /b backups\*.sql
    pause
    exit /b 1
)

echo Se va a SUSTITUIR la base de datos "encuentrame" por %1
set /p OK=Escribe SI para continuar:
if /i not "%OK%"=="SI" exit /b 1

"C:\xampp\mysql\bin\mysql.exe" -u root -e "DROP DATABASE IF EXISTS encuentrame;"
"C:\xampp\mysql\bin\mysql.exe" -u root --default-character-set=utf8mb4 < "%~1"
"C:\xampp\mysql\bin\mysql.exe" -u root -e "GRANT ALL PRIVILEGES ON encuentrame.* TO 'encuentrame'@'localhost'; FLUSH PRIVILEGES;"
echo Base de datos restaurada.
pause
