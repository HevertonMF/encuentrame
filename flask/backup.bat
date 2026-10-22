@echo off
REM Hace una copia de seguridad de la base de datos en la carpeta "backups"
REM Uso: doble clic, o "backup.bat" desde la terminal

cd /d "%~dp0"
if not exist backups mkdir backups

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set FECHA=%%i

"C:\xampp\mysql\bin\mysqldump.exe" -u root --default-character-set=utf8mb4 --routines --databases encuentrame > "backups\encuentrame_%FECHA%.sql"

if %errorlevel%==0 (
    echo Copia guardada en backups\encuentrame_%FECHA%.sql
) else (
    echo ERROR: no se pudo hacer la copia. Esta MySQL encendido en XAMPP?
)

REM Las fotos de perfil no estan en la base de datos, las copio aparte
if exist fotos (
    xcopy fotos "backups\fotos_%FECHA%\" /E /I /Q /Y >nul
    echo Fotos copiadas en backups\fotos_%FECHA%
)
pause
