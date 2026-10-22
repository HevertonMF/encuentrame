# Encuéntrame — psicólogos y pacientes

Aplicación web para ayudar a las personas a encontrar al psicólogo que mejor se adapta a su necesidad.

El proyecto tiene dos versiones:

| Versión | Carpeta | Tecnologías |
|---|---|---|
| **Web estática** (demo online) | raíz del repositorio | HTML · CSS · JavaScript (datos en `localStorage`) |
| **Aplicación completa** | [`flask/`](flask/) | Python · Flask · MySQL / MariaDB |

🔗 **Demo de la versión estática:** https://hevertonmf.github.io/encuentrame/

---

## Funcionalidades (versión Flask)

**Pacientes**
- Registro e inicio de sesión con contraseñas cifradas (hash).
- Búsqueda de psicólogos por nombre o tema y filtros por especialidad.
- Envío de solicitudes de primera sesión (contacto por correo o teléfono).
- Página «Mis solicitudes» para ver si el psicólogo ya ha contactado.
- Opción de eliminar la cuenta.

**Psicólogos**
- Registro con número de colegiado (no se puede repetir).
- Panel con las solicitudes recibidas, que se marcan como «contactado».
- Edición del perfil: foto, especialidades, teléfono, presentación y nº de colegiado.
- Los perfiles nuevos quedan **pendientes de aprobación** hasta que los revisa un administrador.

**Administración** (`/admin`)
- Resumen con psicólogos publicados, pendientes, pacientes y solicitudes.
- Aprobar, ocultar o eliminar psicólogos.
- Eliminar pacientes y ver las últimas solicitudes.

**Seguridad**
- Consultas con parámetros (`%s`) para evitar la inyección SQL.
- Todo el texto de los usuarios se escapa antes de mostrarlo.
- Cada usuario solo puede ver y cambiar sus propios datos.

## Base de datos

Cinco tablas principales más la de administradores:

- `psicologos`, `pacientes`, `especialidades`, `psicologo_especialidad` (relación N:M), `solicitudes`
- `administradores`

## Cómo ejecutarlo en local

1. Arranca **MySQL** en XAMPP (o MariaDB en Linux).
2. Crea la base de datos y aplica las migraciones en este orden:

   ```bash
   mysql -u root < flask/basedatos.sql
   mysql -u root < flask/migracion_01.sql
   mysql -u root < flask/migracion_02.sql
   mysql -u root < flask/migracion_03.sql
   ```

3. Instala las librerías y arranca la aplicación:

   ```bash
   pip install flask mysql-connector-python
   cd flask
   python app.py
   ```

4. Abre http://localhost:5000

**Cuentas de prueba** (solo para uso local):
- Psicólogo: `marta.ibanez@ejemplo.com` / `demo1234`
- Administrador: `admin@encuentrame.local` / `admin1234` → http://localhost:5000/entrar?tipo=admin

## Publicarlo en un servidor (PythonAnywhere)

- En la cuenta gratuita no hay MySQL, así que la app usa **SQLite**: crea la base con `python crear_bd_sqlite.py /home/USUARIO/encuentrame.db` y define `ENCUENTRAME_BD_SQLITE` con esa ruta. En local sigue usando MySQL.
- Con un plan de pago se puede usar MySQL con `flask/pythonanywhere.sql` (compatible con MySQL 8).
- Los psicólogos de ejemplo **no tienen contraseña**, así que nadie puede entrar con sus cuentas.
- La base de datos (`*.db`) nunca se sube a GitHub.
- Crea el administrador con `python crear_admin.py`: la contraseña se escribe en la terminal y no se guarda en el código.
- Define estas variables de entorno (nunca las subas a GitHub):
  `ENCUENTRAME_CLAVE`, `ENCUENTRAME_BD_HOST`, `ENCUENTRAME_BD_USUARIO`, `ENCUENTRAME_BD_PASSWORD`, `ENCUENTRAME_BD_NOMBRE`.
- Con `ENCUENTRAME_CLAVE` definida, la cookie de sesión solo viaja por HTTPS.

## Copias de seguridad

- `backup.bat` guarda una copia de la base de datos (y de las fotos) en `backups/`.
- `restaurar.bat` recupera la base de datos desde una de esas copias.
- `ver_datos.py` muestra el contenido de todas las tablas.

---

> Proyecto de estudio del ciclo de Desarrollo de Aplicaciones Multiplataforma (DAM) en CEAC. Los perfiles de psicólogos son ficticios.
