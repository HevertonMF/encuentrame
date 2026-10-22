# Encuéntrame — psicólogos y pacientes

Aplicación web para ayudar a las personas a encontrar al psicólogo que mejor se adapta a su necesidad.

## 🚀 Pruébala online

👉 **https://encuentrame.pythonanywhere.com**

**Cómo probarla:**

1. **Como paciente:** pulsa *Busco apoyo → Crear cuenta*. Al entrar verás a los psicólogos: búscalos por especialidad y envía una solicitud. En *Mis solicitudes* verás su estado.
2. **Como psicólogo/a:** crea una cuenta en la pestaña *Soy psicólogo/a* con un número de colegiado inventado (por ejemplo `TEST-1234`). Tu perfil quedará **pendiente de aprobación** hasta que lo revise el administrador.

> ⚠️ Es un proyecto de estudio: los psicólogos son ficticios. **No uses tu contraseña habitual ni escribas datos personales reales.** Puedes eliminar tu cuenta cuando quieras desde la propia web.

---

## Versiones

| Versión | Carpeta | Tecnologías |
|---|---|---|
| **Aplicación completa** (online) | [`flask/`](flask/) | Python · Flask · MySQL (local) / SQLite (servidor) |
| **Prototipo estático** | raíz del repositorio | HTML · CSS · JavaScript (datos en `localStorage`) — [ver demo](https://hevertonmf.github.io/encuentrame/) |

## Funcionalidades

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
- Ninguna contraseña ni clave está en el código: se leen de `config_local.py` (que no se sube) o de variables de entorno.
- Contraseñas guardadas con hash (werkzeug).
- Consultas con parámetros (`%s`) para evitar la inyección SQL.
- Todo el texto de los usuarios se escapa antes de mostrarlo.
- Protección **CSRF**: todos los formularios llevan un código secreto de la sesión.
- Cookies de sesión `HttpOnly`, `SameSite=Lax` y, en el servidor, solo por HTTPS (con redirección automática).
- Cada usuario solo puede ver y cambiar sus propios datos.

## Base de datos

- `psicologos`, `pacientes`, `especialidades`, `psicologo_especialidad` (relación N:M), `solicitudes`
- `administradores`

## Cómo ejecutarlo en local (MySQL / XAMPP)

1. En `flask/basedatos.sql` cambia `CAMBIA_ESTA_CONTRASEÑA` por una contraseña tuya.
2. Copia `flask/config_local.ejemplo.py` como `flask/config_local.py` y pon la misma contraseña.
3. Crea la base de datos y aplica las migraciones:

   ```bash
   mysql -u root < flask/basedatos.sql
   mysql -u root < flask/migracion_01.sql
   mysql -u root < flask/migracion_02.sql
   mysql -u root < flask/migracion_03.sql
   ```

4. Instala las librerías, crea tu administrador y arranca la aplicación:

   ```bash
   pip install flask mysql-connector-python
   cd flask
   python crear_admin.py
   python app.py
   ```

5. Abre http://localhost:5000 (administración: http://localhost:5000/entrar?tipo=admin)

## Publicarlo en un servidor (PythonAnywhere)

- En la cuenta gratuita no hay MySQL, así que la app usa **SQLite**: crea la base con `python crear_bd_sqlite.py /home/USUARIO/encuentrame.db` y define `ENCUENTRAME_BD_SQLITE` con esa ruta.
- Con un plan de pago se puede usar MySQL con `flask/pythonanywhere.sql` (compatible con MySQL 8).
- Define `ENCUENTRAME_CLAVE` con una clave aleatoria (por ejemplo leída de un archivo privado del servidor).
- Crea el administrador con `python crear_admin.py`.
- Los psicólogos de ejemplo **no tienen contraseña**: nadie puede entrar con sus cuentas.
- La base de datos (`*.db`) y `config_local.py` nunca se suben a GitHub.

## Copias de seguridad (local)

- `backup.bat` guarda una copia de la base de datos (y de las fotos) en `backups/`.
- `restaurar.bat` recupera la base de datos desde una de esas copias.
- `ver_datos.py` muestra el contenido de todas las tablas.

---

> Proyecto de estudio del ciclo de Desarrollo de Aplicaciones Multiplataforma (DAM) en CEAC. Los perfiles de psicólogos son ficticios.
