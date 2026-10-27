# Primero importo las librerías
try:
    import mysql.connector                              # Importo MySQL (lo uso en mi PC)
except ImportError:
    mysql = None                                        # En el servidor uso SQLite y no hace falta
import sqlite3                                          # SQLite (lo uso en el servidor)
from datetime import datetime                           # Para leer las fechas de SQLite
from flask import Flask, request, redirect, session, send_from_directory   # Importo Flask
from werkzeug.security import generate_password_hash, check_password_hash   # Para las contraseñas
from html import escape                                 # Para mostrar texto de BD de forma segura
from urllib.parse import quote                          # Para pasar texto por la URL
import os                                               # Para guardar las fotos
import uuid                                             # Para dar nombres únicos a las fotos
import secrets                                          # Para el código anti-CSRF
import hmac                                             # Para comparar el código de forma segura
import re                                               # Para meter el código en los formularios
import hashlib                                          # Para guardar el hash de los enlaces de recuperación
import json                                             # Para pasar los horarios libres al JavaScript
import smtplib                                          # Para enviar correos (SMTP)
import urllib.request                                   # Para enviar correos por la API de Brevo
from email.message import EmailMessage                  # Para escribir los correos
from datetime import timedelta                          # Para sumar tiempo a una fecha


# Datos de conexión a MySQL
# - En mi PC están en config_local.py (ese archivo NO se sube a GitHub)
# - Si no existe, se leen de variables de entorno
try:
    from config_local import DATOS_BD
except ImportError:
    DATOS_BD = {
        "host": os.environ.get("ENCUENTRAME_BD_HOST", "localhost"),
        "user": os.environ.get("ENCUENTRAME_BD_USUARIO", "encuentrame"),
        "password": os.environ.get("ENCUENTRAME_BD_PASSWORD", ""),
        "database": os.environ.get("ENCUENTRAME_BD_NOMBRE", "encuentrame")
    }


# Si existe ENCUENTRAME_BD_SQLITE (ruta del archivo .db) uso SQLite en vez de MySQL
RUTA_SQLITE = os.environ.get("ENCUENTRAME_BD_SQLITE")

# SQLite guarda las fechas como texto: las convierto en datetime al leerlas
sqlite3.register_converter("TIMESTAMP", lambda valor: datetime.fromisoformat(valor.decode()))
sqlite3.register_adapter(datetime, lambda fecha: fecha.isoformat(" "))


# Cursor de SQLite que acepta %s como MySQL (SQLite usa ?)
class CursorSQLite:

    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, sql, parametros=()):
        return self.cursor.execute(sql.replace("%s", "?"), parametros)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def close(self):
        self.cursor.close()


# Conexión de SQLite que se usa igual que la de MySQL
class ConexionSQLite:

    def __init__(self, ruta):
        self.conexion = sqlite3.connect(ruta, detect_types=sqlite3.PARSE_DECLTYPES)
        self.conexion.execute("PRAGMA foreign_keys = ON")     # Para que funcione ON DELETE CASCADE

    def cursor(self):
        return CursorSQLite(self.conexion.cursor())

    def commit(self):
        self.conexion.commit()

    def rollback(self):
        self.conexion.rollback()

    def close(self):
        self.conexion.close()


# Abro una conexión nueva en cada petición (así no se cae si MySQL la cierra)
def conectar():
    if RUTA_SQLITE:
        return ConexionSQLite(RUTA_SQLITE)
    return mysql.connector.connect(**DATOS_BD)


# Hora actual en España (el servidor está en otra zona horaria)
def ahora():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None, microsecond=0)
    except Exception:
        return datetime.now().replace(microsecond=0)


DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]

# "lun 27/10/2026 · 10:00"
def fecha_bonita(fecha):
    return DIAS[fecha.weekday()] + " " + fecha.strftime("%d/%m/%Y · %H:%M")


# "★★★★☆"
def estrellas_texto(numero):
    numero = int(round(numero))
    return "★" * numero + "☆" * (5 - numero)


# Datos para enviar correos (Gmail). En el servidor vienen de variables de entorno
# y en mi PC pueden estar en config_local.py. Si no hay, no se envía nada.
try:
    from config_local import CORREO
except ImportError:
    CORREO = {
        "usuario": os.environ.get("ENCUENTRAME_CORREO_USUARIO", ""),
        "password": os.environ.get("ENCUENTRAME_CORREO_PASSWORD", "")
    }

# Dirección pública de la web (para los enlaces de los correos)
URL_PUBLICA = os.environ.get("ENCUENTRAME_URL", "https://encuentrame.pythonanywhere.com")


# Envío un correo. Devuelvo True si se ha enviado.
def enviar_correo(destino, asunto, texto):

    # En el servidor gratuito el correo normal (SMTP) está bloqueado:
    # si hay clave de Brevo, envío por su API (HTTPS)
    clave_brevo = os.environ.get("ENCUENTRAME_BREVO_CLAVE", "")
    remitente = os.environ.get("ENCUENTRAME_CORREO_REMITENTE", CORREO.get("usuario", ""))
    if clave_brevo and remitente:
        datos = json.dumps({
            "sender": {"name": "Encuéntrame", "email": remitente},
            "to": [{"email": destino}],
            "subject": asunto,
            "textContent": texto
        }).encode()
        peticion = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=datos,
            headers={"api-key": clave_brevo, "Content-Type": "application/json", "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(peticion, timeout=20) as respuesta:
                return respuesta.status in (200, 201, 202)
        except Exception as error:
            print("No se pudo enviar el correo (Brevo):", type(error).__name__)
            return False

    # Si no, uso Gmail por SMTP (funciona en mi PC)
    if not CORREO.get("usuario") or not CORREO.get("password"):
        return False
    mensaje = EmailMessage()
    mensaje["From"] = "Encuéntrame <" + CORREO["usuario"] + ">"
    mensaje["To"] = destino
    mensaje["Subject"] = asunto
    mensaje.set_content(texto)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as servidor:
            servidor.login(CORREO["usuario"], CORREO["password"])
            servidor.send_message(mensaje)
        return True
    except Exception as error:
        print("No se pudo enviar el correo:", type(error).__name__)
        return False


# Dominios inventados (los perfiles de ejemplo): nunca les envío correos
DOMINIOS_FICTICIOS = ("ejemplo.com", "example.com", "example.org", "prueba.local")


# Aviso por correo a un usuario. No incluyo datos de salud: solo un enlace a la web.
def avisar(destino, asunto, texto):
    destino = (destino or "").strip().lower()
    dominio = destino.rsplit("@", 1)[-1]
    if "@" not in destino or dominio in DOMINIOS_FICTICIOS or dominio.endswith((".local", ".invalid", ".test")):
        return False
    texto += ("\n\n---\nEncuéntrame · " + URL_PUBLICA + "\n"
              "Este correo es automático. Proyecto de estudio: los perfiles de psicólogos son ficticios.")
    return enviar_correo(destino, asunto, texto)


# Ahora creo una aplicación base
# La carpeta "logo" se sirve en /logo
aplicacion = Flask(__name__, static_folder="logo", static_url_path="/logo")

# Clave para firmar la cookie de sesión (login)
# Si existe la variable de entorno ENCUENTRAME_CLAVE la uso; si no, una de desarrollo
aplicacion.secret_key = os.environ.get("ENCUENTRAME_CLAVE", "clave-solo-para-desarrollo")

# La cookie de sesión no se puede leer desde JavaScript ni enviar desde otras webs
aplicacion.config["SESSION_COOKIE_HTTPONLY"] = True
aplicacion.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# En el servidor (cuando existe ENCUENTRAME_CLAVE) la cookie solo viaja por HTTPS
EN_SERVIDOR = "ENCUENTRAME_CLAVE" in os.environ
aplicacion.config["SESSION_COOKIE_SECURE"] = EN_SERVIDOR


# En el servidor, si alguien entra por http lo mando a https
@aplicacion.before_request
def forzar_https():
    if EN_SERVIDOR and request.headers.get("X-Forwarded-Proto") == "http":
        return redirect(request.url.replace("http://", "https://", 1), code=301)


# Con SQLite (en el servidor) hago una copia de seguridad una vez al día
@aplicacion.before_request
def copia_diaria():
    if RUTA_SQLITE:
        try:
            import backup_sqlite
            if backup_sqlite.toca_copia(RUTA_SQLITE):
                backup_sqlite.hacer_copia(RUTA_SQLITE)
        except Exception as error:
            print("No se pudo hacer la copia de seguridad:", error)    # La web sigue funcionando igual


# Y le digo al navegador que use siempre https en esta web
@aplicacion.after_request
def cabeceras_seguridad(respuesta):
    if EN_SERVIDOR:
        respuesta.headers["Strict-Transport-Security"] = "max-age=31536000"
    respuesta.headers["Referrer-Policy"] = "same-origin"          # Los enlaces de recuperación no salen a otras webs
    respuesta.headers["X-Frame-Options"] = "DENY"                 # Nadie puede meter mi web dentro de la suya
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    return respuesta


# -------------------------------------------------
# PROTECCIÓN CSRF
# Cada visitante tiene un código secreto en su sesión. Va escondido en todos
# los formularios y si un POST no lo trae (por ejemplo, desde otra web), lo rechazo.
# -------------------------------------------------

def codigo_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(32)
    return session["csrf"]


@aplicacion.before_request
def comprobar_csrf():
    if request.method == "POST":
        enviado = request.form.get("csrf", "")
        guardado = session.get("csrf", "")
        if not guardado or not hmac.compare_digest(enviado, guardado):
            return cabecera("Formulario caducado — Encuéntrame") + """
<main class="contenedor">
    <div class="caja-acceso">
        <h2>Formulario caducado</h2>
        <p>Por seguridad no hemos podido procesar el formulario. Vuelve atrás, recarga la página e inténtalo de nuevo.</p>
        <a class="boton" href="/">Volver al inicio</a>
    </div>
</main>
""" + pie(), 400


# Meto el código en todos los formularios POST de la página
@aplicacion.after_request
def meter_csrf(respuesta):
    if respuesta.mimetype == "text/html" and not respuesta.direct_passthrough:
        html = respuesta.get_data(as_text=True)
        if '<form method="post"' in html:
            campo = '<input type="hidden" name="csrf" value="' + codigo_csrf() + '">'
            html = re.sub(r'(<form method="post"[^>]*>)', lambda m: m.group(1) + campo, html)
            respuesta.set_data(html)
    return respuesta

# Las fotos de perfil se guardan en la carpeta "fotos" (máximo 2 MB)
CARPETA_FOTOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fotos")
EXTENSIONES_FOTO = ("jpg", "jpeg", "png", "webp")
aplicacion.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


# Devuelvo el usuario que ha iniciado sesión (o None)
# Es un diccionario: {"tipo": "paciente" o "psicologo", "id": ..., "nombre": ...}
def usuario():
    return session.get("usuario")


# -------------------------------------------------
# ESTILOS (los comparten todas las páginas)
# -------------------------------------------------

ESTILOS = """
<style>

    :root{
        --fondo:#FFFFFF;
        --superficie:#F3EEFA;
        --tinta:#3A2A5C;
        --tinta-suave:#5E5378;
        --tinta-gris:#9389A8;
        --morado:#8E6FAE;
        --morado-fuerte:#6E4E9A;
        --lima:#D3E39A;
        --lima-fuerte:#C2D683;
        --borde:rgba(58,42,92,0.12);
        --ok:#3F4A25;
        --ok-fondo:#F1F6DD;
    }

    @media (prefers-color-scheme: dark){
        :root{
            --fondo:#241A38;
            --superficie:#2F2347;
            --tinta:#F3EEFA;
            --tinta-suave:#CBBFE0;
            --tinta-gris:#9C8FB8;
            --morado:#B69BD6;
            --morado-fuerte:#CDB8E6;
            --borde:rgba(243,238,250,0.14);
            --ok:#D3E39A;
            --ok-fondo:#3F4A25;
        }
    }

    *{
        box-sizing:border-box;
    }

    body{
        margin:0;
        font-family:Calibri, 'Carlito', 'Segoe UI', sans-serif;
        background:var(--fondo);
        color:var(--tinta);
        line-height:1.55;
    }

    .contenedor{
        max-width:1100px;
        margin:auto;
        padding:0 20px;
    }


    /* ----------------------------- */
    /* CABECERA                      */
    /* ----------------------------- */

    header{
        border-bottom:1px solid var(--borde);
    }

    .cabecera{
        display:flex;
        align-items:center;
        justify-content:space-between;
        padding:16px 0;
    }

    .logo{
        display:flex;
        align-items:center;
        gap:10px;
        text-decoration:none;
        color:var(--tinta);
        text-transform:uppercase;
        letter-spacing:0.4em;
        font-size:13px;
    }

    .logo img{
        width:38px;
        height:38px;
        border-radius:50%;
        background:#F7F4EE;
    }

    .menu a{
        color:var(--tinta-suave);
        text-decoration:none;
        margin-left:20px;
        font-weight:bold;
        font-size:14px;
    }

    .menu a:hover{
        color:var(--morado-fuerte);
    }


    /* ----------------------------- */
    /* BOTONES                       */
    /* ----------------------------- */

    .boton{
        display:inline-block;
        border:0;
        background:var(--lima);
        color:#3A2A5C;
        padding:12px 26px;
        border-radius:999px;
        font-weight:bold;
        font-size:15px;
        cursor:pointer;
        text-decoration:none;
        font-family:inherit;
    }

    .boton:hover{
        background:var(--lima-fuerte);
    }

    .boton-borde{
        background:transparent;
        border:1px solid rgba(255,255,255,0.75);
        color:white;
    }

    .boton-borde:hover{
        background:rgba(255,255,255,0.12);
    }

    .boton-pequeno{
        padding:8px 16px;
        font-size:13px;
    }


    /* ----------------------------- */
    /* HERO                          */
    /* ----------------------------- */

    .hero{
        margin-top:28px;
        padding:60px 50px;
        border-radius:22px;
        color:white;
        background:linear-gradient(135deg, #7A5A9E 0%, #A07FBE 45%, #6A4C93 100%);
    }

    .hero .mini{
        letter-spacing:0.4em;
        text-transform:uppercase;
        font-size:12px;
        opacity:0.85;
    }

    .hero h1{
        font-size:48px;
        line-height:1.1;
        margin:15px 0;
        max-width:650px;
    }

    .hero p{
        font-size:18px;
        max-width:520px;
        margin-bottom:28px;
    }


    /* ----------------------------- */
    /* PASOS                         */
    /* ----------------------------- */

    .pasos{
        display:grid;
        grid-template-columns:repeat(4,1fr);
        gap:16px;
        margin-top:40px;
    }

    .paso{
        background:var(--superficie);
        border-radius:18px;
        padding:22px;
    }

    .paso .numero{
        width:42px;
        height:42px;
        border-radius:50%;
        background:var(--morado);
        color:white;
        display:flex;
        align-items:center;
        justify-content:center;
        font-weight:bold;
        font-size:19px;
        margin-bottom:14px;
    }

    .paso h3{
        margin:0 0 8px 0;
    }

    .paso p{
        margin:0;
        color:var(--tinta-suave);
    }


    /* ----------------------------- */
    /* BUSCADOR Y FILTROS            */
    /* ----------------------------- */

    main{
        margin:50px auto;
    }

    .titulo-seccion{
        display:flex;
        justify-content:space-between;
        align-items:end;
        margin-bottom:20px;
        gap:20px;
    }

    .titulo-seccion h2{
        margin:0;
        font-size:32px;
    }

    .titulo-seccion p{
        margin:5px 0 0 0;
        color:var(--tinta-suave);
    }

    .contador{
        color:var(--tinta-gris);
        font-size:14px;
        white-space:nowrap;
    }

    #busqueda{
        width:100%;
        padding:12px 18px;
        border-radius:999px;
        border:1px solid var(--borde);
        background:var(--fondo);
        color:var(--tinta);
        font-size:15px;
        font-family:inherit;
        outline:none;
        margin-bottom:14px;
    }

    #busqueda:focus{
        border-color:var(--morado);
    }

    .filtros{
        display:flex;
        flex-wrap:wrap;
        gap:8px;
        margin-bottom:24px;
    }

    .filtro{
        padding:7px 13px;
        border-radius:999px;
        border:1px solid var(--borde);
        background:var(--fondo);
        color:var(--tinta-suave);
        cursor:pointer;
        font-family:inherit;
        font-size:13px;
    }

    .filtro.activo{
        background:var(--lima);
        border-color:var(--lima);
        color:#3A2A5C;
        font-weight:bold;
    }


    /* ----------------------------- */
    /* TARJETAS DE PSICÓLOGOS        */
    /* ----------------------------- */

    #psicologos{
        display:grid;
        grid-template-columns:repeat(auto-fill,minmax(250px,1fr));
        gap:18px;
    }

    article{
        border:1px solid var(--borde);
        border-radius:18px;
        padding:20px;
        display:flex;
        flex-direction:column;
        gap:10px;
        transition:transform 0.2s, box-shadow 0.2s;
    }

    article:hover{
        transform:translateY(-4px);
        box-shadow:0 12px 30px rgba(58,42,92,0.12);
    }

    .cabeza{
        display:flex;
        align-items:center;
        gap:12px;
    }

    .avatar{
        width:46px;
        height:46px;
        border-radius:50%;
        color:white;
        display:flex;
        align-items:center;
        justify-content:center;
        font-weight:bold;
        flex-shrink:0;
    }

    article h3{
        margin:0;
        font-size:17px;
    }

    .etiquetas{
        display:flex;
        flex-wrap:wrap;
        gap:6px;
    }

    .etiqueta{
        font-size:11.5px;
        font-weight:bold;
        padding:4px 9px;
        border-radius:999px;
        background:var(--superficie);
        color:var(--morado-fuerte);
    }

    .bio{
        color:var(--tinta-suave);
        font-size:13.5px;
        margin:0;
        flex:1;
    }

    .vacio{
        display:none;
        text-align:center;
        padding:40px;
        color:var(--tinta-suave);
    }


    /* ----------------------------- */
    /* VENTANA DE SOLICITUD          */
    /* ----------------------------- */

    dialog{
        border:0;
        border-radius:18px;
        padding:28px;
        max-width:520px;
        width:calc(100% - 32px);
        background:var(--fondo);
        color:var(--tinta);
    }

    dialog::backdrop{
        background:rgba(10,14,9,0.55);
    }

    .cerrar{
        float:right;
        border:0;
        background:none;
        font-size:20px;
        cursor:pointer;
        color:var(--tinta);
    }

    .campo{
        margin-bottom:14px;
    }

    .campo label{
        display:block;
        font-size:13px;
        font-weight:bold;
        color:var(--tinta-suave);
        margin-bottom:5px;
    }

    .campo input,
    .campo textarea{
        width:100%;
        padding:10px 12px;
        border:1px solid var(--borde);
        border-radius:9px;
        background:var(--fondo);
        color:var(--tinta);
        font-family:inherit;
        font-size:15px;
    }

    .campo textarea{
        min-height:90px;
        resize:vertical;
    }

    .opciones label{
        display:inline;
        font-weight:normal;
        margin-right:15px;
    }


    /* ----------------------------- */
    /* AVISOS Y SOLICITUDES          */
    /* ----------------------------- */

    .aviso{
        background:var(--ok-fondo);
        color:var(--ok);
        padding:14px 18px;
        border-radius:10px;
        margin-top:20px;
        font-weight:bold;
    }

    .solicitud{
        border:1px solid var(--borde);
        border-radius:18px;
        padding:16px 18px;
        margin-bottom:12px;
    }

    .solicitud .meta{
        color:var(--tinta-suave);
        font-size:13px;
    }

    .estado{
        font-size:11.5px;
        font-weight:bold;
        padding:3px 9px;
        border-radius:999px;
        background:var(--superficie);
        color:var(--morado-fuerte);
    }

    .estado.contactado{
        background:var(--ok-fondo);
        color:var(--ok);
    }

    .selector{
        padding:10px 14px;
        border-radius:999px;
        border:1px solid var(--borde);
        background:var(--fondo);
        color:var(--tinta);
        font-family:inherit;
        font-size:15px;
    }


    /* ----------------------------- */
    /* LOGIN Y REGISTRO              */
    /* ----------------------------- */

    .caja-acceso{
        max-width:480px;
        margin:0 auto;
        border:1px solid var(--borde);
        border-radius:18px;
        padding:28px;
    }

    .caja-acceso h2{
        margin:0 0 18px 0;
    }

    .pestanas{
        display:flex;
        gap:4px;
        background:var(--superficie);
        padding:4px;
        border-radius:999px;
        margin-bottom:22px;
    }

    .pestanas a{
        flex:1;
        text-align:center;
        padding:9px 0;
        border-radius:999px;
        text-decoration:none;
        color:var(--tinta-suave);
        font-weight:bold;
        font-size:14px;
    }

    .pestanas a.activa{
        background:var(--fondo);
        color:var(--tinta);
    }

    .error{
        background:#F8E1E1;
        color:#8A2C2C;
        padding:12px 16px;
        border-radius:10px;
        margin-bottom:16px;
        font-weight:bold;
    }

    .casillas{
        display:flex;
        flex-wrap:wrap;
        gap:8px;
    }

    .casillas label{
        display:inline-flex;
        align-items:center;
        gap:6px;
        padding:6px 11px;
        border:1px solid var(--borde);
        border-radius:999px;
        font-weight:normal;
        font-size:13px;
        color:var(--tinta);
        margin:0;
        cursor:pointer;
    }

    .cambiar{
        text-align:center;
        font-size:14px;
        color:var(--tinta-suave);
        margin:18px 0 0 0;
    }

    .cambiar a{
        color:var(--morado-fuerte);
        font-weight:bold;
    }

    .invitacion{
        margin:50px 0;
        padding:44px 30px;
        border-radius:22px;
        background:var(--superficie);
        text-align:center;
    }

    .invitacion h2{
        margin:0 0 10px 0;
        font-size:30px;
    }

    .invitacion p{
        color:var(--tinta-suave);
        max-width:480px;
        margin:0 auto 24px auto;
    }

    .boton-claro{
        background:var(--fondo);
        border:1px solid var(--borde);
        color:var(--tinta);
        margin-left:8px;
    }

    .boton-claro:hover{
        background:var(--fondo);
        border-color:var(--morado);
    }

    /* Valoraciones */
    .nota{
        font-size:13px;
        color:var(--tinta-suave);
    }

    .nota .estrellas, .estrellas{
        color:#E0A100;
        letter-spacing:1px;
    }

    .opiniones summary{
        cursor:pointer;
        font-size:13px;
        color:var(--morado-fuerte);
        font-weight:bold;
    }

    .opinion{
        font-size:13px;
        color:var(--tinta-suave);
        border-left:3px solid var(--superficie);
        padding:4px 10px;
        margin:8px 0;
    }

    .valorar{
        margin-top:12px;
        padding:14px;
        border-radius:12px;
        background:var(--superficie);
    }

    .valorar .elegir-estrellas{
        display:flex;
        flex-direction:row-reverse;
        justify-content:flex-end;
        gap:2px;
        margin-bottom:8px;
    }

    .valorar .elegir-estrellas input{
        display:none;
    }

    .valorar .elegir-estrellas label{
        font-size:26px;
        color:#C9C2D6;
        cursor:pointer;
    }

    .valorar .elegir-estrellas input:checked ~ label,
    .valorar .elegir-estrellas label:hover,
    .valorar .elegir-estrellas label:hover ~ label{
        color:#E0A100;
    }

    .valorar textarea{
        width:100%;
        min-height:60px;
        padding:8px 10px;
        border:1px solid var(--borde);
        border-radius:9px;
        font-family:inherit;
        background:var(--fondo);
        color:var(--tinta);
    }

    /* Agenda */
    .cita{
        display:inline-block;
        margin-top:6px;
        padding:4px 10px;
        border-radius:999px;
        background:var(--ok-fondo);
        color:var(--ok);
        font-size:13px;
        font-weight:bold;
    }

    .fila-horario{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
        padding:10px 14px;
        border:1px solid var(--borde);
        border-radius:12px;
        margin-bottom:8px;
    }

    .form-linea{
        display:flex;
        flex-wrap:wrap;
        gap:10px;
        align-items:end;
    }

    .form-linea .campo{
        margin:0;
    }

    .campo select{
        width:100%;
        padding:10px 12px;
        border:1px solid var(--borde);
        border-radius:9px;
        background:var(--fondo);
        color:var(--tinta);
        font-family:inherit;
        font-size:15px;
    }

    .no-leido td{
        font-weight:bold;
    }

    .aceptar{
        display:flex !important;
        gap:8px;
        align-items:flex-start;
        font-weight:normal !important;
        color:var(--tinta) !important;
    }

    .aceptar input{
        width:auto !important;
        margin-top:4px;
    }

    .aceptar a, .legal a{
        color:var(--morado-fuerte);
    }

    .legal{
        max-width:760px;
    }

    .legal h3{
        margin:26px 0 6px 0;
    }

    .legal p, .legal li{
        color:var(--tinta-suave);
    }

    .colegiado{
        font-size:12px;
        color:var(--tinta-gris);
    }

    .aviso-pendiente{
        background:#FFF4DC;
        color:#7A5410;
        padding:14px 18px;
        border-radius:10px;
        font-weight:bold;
        margin-bottom:10px;
    }


    /* ----------------------------- */
    /* ADMINISTRACIÓN                */
    /* ----------------------------- */

    .cifras{
        display:grid;
        grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
        gap:14px;
        margin-bottom:34px;
    }

    .cifra{
        background:var(--superficie);
        border-radius:16px;
        padding:18px;
    }

    .cifra strong{
        display:block;
        font-size:32px;
        color:var(--morado-fuerte);
    }

    .cifra span{
        color:var(--tinta-suave);
        font-size:14px;
    }

    .admin h3{
        font-size:22px;
        margin:34px 0 12px 0;
    }

    .tabla-admin{
        overflow-x:auto;
        border:1px solid var(--borde);
        border-radius:16px;
    }

    .tabla-admin table{
        width:100%;
        border-collapse:collapse;
        font-size:14px;
    }

    .tabla-admin th{
        text-align:left;
        background:var(--superficie);
        color:var(--tinta-suave);
        font-size:12px;
        text-transform:uppercase;
        letter-spacing:0.05em;
        padding:10px 12px;
    }

    .tabla-admin td{
        padding:10px 12px;
        border-top:1px solid var(--borde);
        vertical-align:middle;
    }

    .tabla-admin form{
        display:inline;
    }

    .tabla-admin .acciones{
        white-space:nowrap;
    }

    .insignia{
        font-size:11.5px;
        font-weight:bold;
        padding:3px 9px;
        border-radius:999px;
        white-space:nowrap;
    }

    .insignia.si{
        background:var(--ok-fondo);
        color:var(--ok);
    }

    .insignia.no{
        background:#FFF4DC;
        color:#7A5410;
    }

    .boton-mini{
        border:1px solid var(--borde);
        background:var(--fondo);
        color:var(--tinta);
        padding:5px 11px;
        border-radius:999px;
        font-size:12.5px;
        font-weight:bold;
        cursor:pointer;
        font-family:inherit;
    }

    .boton-mini:hover{
        background:var(--superficie);
    }

    .boton-mini.verde{
        background:var(--lima);
        border-color:var(--lima);
        color:#3A2A5C;
    }

    .boton-mini.rojo{
        color:#B03A3A;
    }

    @media(max-width:820px){
        .cifras{
            grid-template-columns:1fr 1fr;
        }
    }

    .enlace-peligro{
        color:#B03A3A !important;
    }

    .boton-peligro{
        background:#B03A3A;
        color:white;
    }

    .boton-peligro:hover{
        background:#8A2C2C;
    }

    .pista{
        font-size:12.5px;
        color:var(--tinta-gris);
        margin-top:5px;
    }


    /* ----------------------------- */
    /* FOOTER                        */
    /* ----------------------------- */

    footer{
        border-top:1px solid var(--borde);
        padding:30px 20px;
        text-align:center;
        font-size:13px;
        color:var(--tinta-gris);
    }


    /* ----------------------------- */
    /* RESPONSIVE                    */
    /* ----------------------------- */

    @media(max-width:820px){

        .pasos{
            grid-template-columns:1fr 1fr;
        }

        .hero{
            padding:40px 26px;
        }

        .hero h1{
            font-size:34px;
        }

    }

    @media(max-width:500px){

        .pasos{
            grid-template-columns:1fr;
        }

        .logo span{
            display:none;
        }

        .menu a{
            margin-left:12px;
            font-size:13px;
        }

        .titulo-seccion{
            flex-direction:column;
            align-items:flex-start;
        }

    }

</style>
"""


# -------------------------------------------------
# FUNCIONES DE AYUDA
# -------------------------------------------------

# Colores para los avatares
COLORES = ["#2A7272", "#0B2A45", "#C8714A", "#4A7FA6", "#8C5A7A", "#5C8A6E"]


# Saco las iniciales del nombre ("Marta Ibáñez" -> "MI")
def iniciales(nombre):
    partes = nombre.split()
    letras = ""
    for parte in partes[:2]:
        letras += parte[0]
    return letras.upper()


# Cada nombre tiene siempre el mismo color
def color(nombre):
    return COLORES[sum(ord(letra) for letra in nombre) % len(COLORES)]


# Círculo con la foto, o con las iniciales si no hay foto
def avatar(nombre, foto, tamano=46):
    medida = f"width:{tamano}px;height:{tamano}px;"
    if foto:
        return f'<img class="avatar" style="{medida}object-fit:cover" src="/fotos/{escape(foto)}" alt="">'
    return f'<div class="avatar" style="{medida}background:{color(nombre)}">{escape(iniciales(nombre))}</div>'


# Parte de arriba de todas las páginas
def cabecera(titulo):

    # El menú cambia según quién haya iniciado sesión
    yo = usuario()
    if yo is None:
        menu = """
            <a href="/entrar?tipo=paciente">Buscar psicólogo</a>
            <a href="/panel">Soy psicólogo/a</a>
            <a href="/contacto">Contacto</a>
            <a href="/entrar">Entrar</a>"""
    elif yo["tipo"] == "admin":
        menu = """
            <a href="/">Ver la web</a>
            <a href="/admin">Administración</a>
            <a href="/salir">Salir</a>"""
    elif yo["tipo"] == "psicologo":
        menu = """
            <a href="/panel">Mi panel</a>
            <a href="/agenda">Mi agenda</a>
            <a href="/perfil">Mi perfil</a>
            <a href="/salir">Salir</a>"""
    else:
        menu = """
            <a href="/#buscar">Buscar psicólogo</a>
            <a href="/mis-solicitudes">Mis solicitudes</a>
            <a href="/contacto">Contacto</a>
            <a href="/salir">Salir (""" + escape(yo["nombre"].split()[0]) + """)</a>"""

    return """
<!doctype html>
<html lang="es">
<head>

    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>""" + titulo + """</title>

    <meta name="description" content="Encuentra al psicólogo que mejor se adapta a lo que estás viviendo: duelo, ansiedad, pareja y más. Proyecto de estudio DAM.">

    <!-- Vista previa al compartir el enlace (LinkedIn, WhatsApp, X...) -->
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Encuéntrame">
    <meta property="og:title" content="Encuéntrame — Encuentra quien te escuche">
    <meta property="og:description" content="Conecta con psicólogos según lo que estás viviendo: duelo, ansiedad, pareja y más.">
    <meta property="og:url" content='""" + URL_PUBLICA + """'>
    <meta property="og:image" content='""" + URL_PUBLICA + """/logo/og-imagen.jpg?v=2'>
    <meta property="og:image:secure_url" content='""" + URL_PUBLICA + """/logo/og-imagen.jpg?v=2'>
    <meta property="og:image:type" content="image/jpeg">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="Encuéntrame: encuentra quien te escuche">
    <meta name="twitter:image" content='""" + URL_PUBLICA + """/logo/og-imagen.jpg?v=2'>
    <meta property="og:locale" content="es_ES">
    <meta name="twitter:card" content="summary_large_image">

    <link rel="icon" type="image/png" href="/logo/favicon-64.png">
    <link href="https://fonts.googleapis.com/css2?family=Carlito:wght@400;700&display=swap" rel="stylesheet">

""" + ESTILOS + """

</head>

<body>

<header>
    <div class="contenedor cabecera">

        <a class="logo" href="/">
            <img src="/logo/favicon-64.png" alt="">
            <span>Encuéntrame</span>
        </a>

        <nav class="menu">""" + menu + """
        </nav>

    </div>
</header>
"""


# Parte de abajo de todas las páginas
def pie():
    return """

<footer>
    © 2026 Encuéntrame · Proyecto de estudio DAM · Los perfiles son ficticios ·
    <a href="/contacto" style="color:inherit">Contacto</a> ·
    <a href="/privacidad" style="color:inherit">Privacidad</a>
</footer>

</body>
</html>
"""


# -------------------------------------------------
# PORTADA (VISITANTES SIN INICIAR SESIÓN)
# -------------------------------------------------

def portada():

    aviso = ""
    if request.args.get("eliminado"):
        aviso = '<div class="aviso">✓ Tu cuenta se ha eliminado. Gracias por usar Encuéntrame.</div>'

    # Si ya ha entrado (psicólogo o administrador), el botón le lleva a su página
    yo = usuario()
    boton_psicologo = "/panel"
    if yo and yo["tipo"] == "admin":
        boton_psicologo = "/admin"

    return cabecera("Encuéntrame — psicólogos y pacientes") + """

<div class="contenedor">

    """ + aviso + """

    <section class="hero">

        <div class="mini">Encuéntrame</div>

        <h1>Encuentra quien te escuche</h1>

        <p>
            Un espacio para conectar con psicólogos según lo que
            estás viviendo ahora mismo: duelo, ansiedad, pareja y más.
        </p>

        <a class="boton" href="/entrar?tipo=paciente">Busco apoyo</a>
        <a class="boton boton-borde" href='""" + boton_psicologo + """'>Soy psicólogo/a</a>

    </section>


    <section class="pasos">

        <div class="paso">
            <div class="numero">1</div>
            <h3>Crea tu cuenta</h3>
            <p>Regístrate como paciente en un minuto.</p>
        </div>

        <div class="paso">
            <div class="numero">2</div>
            <h3>Explora y filtra</h3>
            <p>Busca por nombre o elige una especialidad.</p>
        </div>

        <div class="paso">
            <div class="numero">3</div>
            <h3>Cuéntanos</h3>
            <p>Explica brevemente tu situación.</p>
        </div>

        <div class="paso">
            <div class="numero">4</div>
            <h3>Te contactan</h3>
            <p>Por correo o teléfono, como prefieras.</p>
        </div>

    </section>


    <section class="invitacion">

        <h2>Nuestros psicólogos te esperan</h2>

        <p>Para ver los perfiles de los profesionales y pedir tu primera sesión, entra con tu cuenta de paciente.</p>

        <a class="boton" href="/registro?tipo=paciente">Crear cuenta</a>
        <a class="boton boton-claro" href="/entrar?tipo=paciente">Ya tengo cuenta</a>

    </section>

</div>
""" + pie()


# -------------------------------------------------
# PÁGINA PRINCIPAL
# -------------------------------------------------

@aplicacion.route("/")
def inicio():

    # Solo los pacientes que han iniciado sesión ven la lista de psicólogos
    yo = usuario()
    if yo is None or yo["tipo"] != "paciente":
        return portada()

    # Pido los psicólogos a la base de datos
    conexion = conectar()
    cursor = conexion.cursor()
    # Solo muestro los psicólogos que ha aprobado un administrador
    cursor.execute("SELECT id, nombre, especialidades, bio, foto, numero_colegiado FROM psicologos WHERE aprobado = 1 ORDER BY nombre")
    filas = cursor.fetchall()

    # Nota media y número de valoraciones de cada psicólogo
    cursor.execute("SELECT psicologo_id, AVG(estrellas), COUNT(*) FROM valoraciones GROUP BY psicologo_id")
    notas = {fila[0]: (float(fila[1]), fila[2]) for fila in cursor.fetchall()}

    # Las 3 opiniones más recientes con comentario (sin el nombre del paciente)
    cursor.execute("""
        SELECT psicologo_id, estrellas, comentario
        FROM valoraciones
        WHERE comentario IS NOT NULL AND comentario <> ''
        ORDER BY fecha DESC
    """)
    opiniones = {}
    for fila in cursor.fetchall():
        opiniones.setdefault(fila[0], [])
        if len(opiniones[fila[0]]) < 3:
            opiniones[fila[0]].append(fila)

    # Horas libres de cada psicólogo (solo futuras, máximo 20)
    cursor.execute("""
        SELECT id, psicologo_id, fecha_hora
        FROM horarios
        WHERE solicitud_id IS NULL AND fecha_hora > %s
        ORDER BY fecha_hora
    """, (ahora(),))
    horarios_libres = {}
    for fila in cursor.fetchall():
        horarios_libres.setdefault(fila[1], [])
        if len(horarios_libres[fila[1]]) < 20:
            horarios_libres[fila[1]].append([fila[0], fecha_bonita(fila[2])])

    cursor.close()
    conexion.close()

    # Junto todas las especialidades distintas para los filtros
    todas = []
    for fila in filas:
        for esp in (fila[2] or "").split(","):
            esp = esp.strip()
            if esp and esp not in todas:
                todas.append(esp)
    todas.sort()

    # Si vengo de enviar una solicitud, muestro un aviso
    aviso = ""
    if request.args.get("enviado"):
        aviso = '<div class="aviso">✓ Tu solicitud se envió a ' + escape(request.args.get("enviado")) + '. Te contactará pronto.</div>'
    if request.args.get("horario_ocupado"):
        aviso = '<div class="error" style="margin-top:20px">Esa hora acaba de reservarla otra persona. Elige otra, por favor.</div>'

    # Si un paciente ha iniciado sesión, relleno su nombre y correo en el formulario
    nombre_paciente = ""
    email_paciente = ""
    if yo and yo["tipo"] == "paciente":
        conexion = conectar()
        cursor = conexion.cursor()
        cursor.execute("SELECT nombre, email FROM pacientes WHERE id = %s", (yo["id"],))
        paciente = cursor.fetchone()
        cursor.close()
        conexion.close()
        if paciente:
            nombre_paciente = escape(paciente[0])
            email_paciente = escape(paciente[1])

    cadena = cabecera("Encuéntrame — psicólogos y pacientes") + """

<div class="contenedor">

    """ + aviso + """

    <section class="hero">

        <div class="mini">Encuéntrame</div>

        <h1>Encuentra quien te escuche</h1>

        <p>
            Un espacio para conectar con psicólogos según lo que
            estás viviendo ahora mismo: duelo, ansiedad, pareja y más.
        </p>

        <a class="boton" href="#buscar">Busco apoyo</a>
        <a class="boton boton-borde" href="/panel">Soy psicólogo/a</a>

    </section>


    <section class="pasos">

        <div class="paso">
            <div class="numero">1</div>
            <h3>Explora</h3>
            <p>Mira los perfiles de los profesionales.</p>
        </div>

        <div class="paso">
            <div class="numero">2</div>
            <h3>Filtra</h3>
            <p>Busca por nombre o elige una especialidad.</p>
        </div>

        <div class="paso">
            <div class="numero">3</div>
            <h3>Cuéntanos</h3>
            <p>Explica brevemente tu situación.</p>
        </div>

        <div class="paso">
            <div class="numero">4</div>
            <h3>Te contactan</h3>
            <p>Por correo o teléfono, como prefieras.</p>
        </div>

    </section>


    <main id="buscar">

        <div class="titulo-seccion">

            <div>
                <h2>Nuestros psicólogos</h2>
                <p>Encuentra al profesional que mejor se adapta a ti.</p>
            </div>

            <div class="contador">
                <span id="visibles">""" + str(len(filas)) + """</span> de """ + str(len(filas)) + """ profesionales
            </div>

        </div>


        <input type="search" id="busqueda" placeholder="Buscar por nombre o tema...">


        <div class="filtros">
            <button class="filtro activo" data-esp="">Todas</button>
"""

    # Un botón por especialidad
    for esp in todas:
        cadena += '            <button class="filtro" data-esp="' + escape(esp) + '">' + escape(esp) + '</button>\n'

    cadena += """
        </div>


        <section id="psicologos">
"""


    # Recorro todos los psicólogos
    for fila in filas:

        id_psicologo = fila[0]
        nombre = escape(fila[1])
        especialidades = [e.strip() for e in (fila[2] or "").split(",") if e.strip()]
        bio = escape(fila[3] or "")

        etiquetas = ""
        for esp in especialidades:
            etiquetas += '<span class="etiqueta">' + escape(esp) + '</span>'

        # Nota media y opiniones
        if id_psicologo in notas:
            media, cuantas = notas[id_psicologo]
            texto_nota = ('<span class="estrellas">' + estrellas_texto(media) + '</span> '
                          + f"{media:.1f}".replace(".", ",") + " · " + str(cuantas)
                          + (" opinión" if cuantas == 1 else " opiniones"))
        else:
            texto_nota = "Sin opiniones todavía"

        bloque_opiniones = ""
        if opiniones.get(id_psicologo):
            bloque_opiniones = '<details class="opiniones"><summary>Ver opiniones</summary>'
            for op in opiniones[id_psicologo]:
                bloque_opiniones += ('<div class="opinion"><span class="estrellas">' + estrellas_texto(op[1])
                                     + '</span><br>' + escape(op[2]) + '</div>')
            bloque_opiniones += '</details>'

        # Horas libres para el formulario (en JSON, escapado para el atributo HTML)
        libres = escape(json.dumps(horarios_libres.get(id_psicologo, [])))
        texto_libres = ("📅 " + str(len(horarios_libres[id_psicologo])) + " horas libres"
                        if horarios_libres.get(id_psicologo) else "")

        cadena += f"""

            <article
                class="psicologo"
                data-nombre="{nombre.lower()}"
                data-bio="{bio.lower()}"
                data-especialidades="{escape('|'.join(especialidades))}"
            >

                <div class="cabeza">

                    {avatar(fila[1], fila[4])}

                    <div>
                        <h3>{nombre}</h3>
                        <div class="colegiado">Nº colegiado: {escape(fila[5] or "—")}</div>
                    </div>

                </div>

                <div class="etiquetas">
                    {etiquetas}
                </div>

                <div class="nota">{texto_nota}</div>

                <p class="bio">
                    {bio}
                </p>

                {bloque_opiniones}

                <div class="nota">{texto_libres}</div>

                <button
                    class="boton boton-pequeno"
                    data-id="{id_psicologo}"
                    data-nombre-mostrar="{nombre}"
                    data-horarios="{libres}"
                    onclick="abrirSolicitud(this)"
                >
                    Solicitar primera sesión
                </button>

            </article>
"""


    # Termino el documento HTML
    cadena += """
        </section>

        <div class="vacio" id="vacio">
            No hay psicólogos con este filtro. Prueba con otra búsqueda.
        </div>

    </main>

</div>


<dialog id="ventana">

    <button class="cerrar" onclick="ventana.close()">✕</button>

    <h2 style="margin-top:0">Solicitar sesión</h2>

    <p>Con <strong id="nombre-psicologo"></strong></p>

    <form method="post" action="/solicitud">

        <input type="hidden" name="psicologo_id" id="psicologo-id">

        <div class="campo">
            <label>Tu nombre</label>
            <input type="text" name="nombre" required value='""" + nombre_paciente + """'>
        </div>

        <div class="campo">
            <label>Correo electrónico</label>
            <input type="email" name="email" required value='""" + email_paciente + """'>
        </div>

        <div class="campo">
            <label>Teléfono (opcional)</label>
            <input type="tel" name="telefono">
        </div>

        <div class="campo">
            <label>Cuéntale brevemente tu situación</label>
            <textarea name="resumen" required
                placeholder="Por ejemplo: llevo unas semanas con mucha ansiedad por el trabajo..."></textarea>
        </div>

        <div class="campo">
            <label>Elige una hora (opcional)</label>
            <select name="horario_id" id="horario"></select>
        </div>

        <div class="campo opciones">
            <label style="display:block">Prefiero que me contacten por</label>
            <label><input type="radio" name="contacto" value="email" checked> Correo</label>
            <label><input type="radio" name="contacto" value="telefono"> Teléfono</label>
        </div>

        <button class="boton" style="width:100%">Enviar solicitud</button>

    </form>

</dialog>


<script>

    // -------------------------------
    // BUSCADOR Y FILTROS
    // -------------------------------

    let buscador = document.querySelector("#busqueda");
    let filtros = document.querySelectorAll(".filtro");
    let especialidadElegida = "";


    function filtrar(){

        let texto = buscador.value.toLowerCase();
        let psicologos = document.querySelectorAll(".psicologo");
        let visibles = 0;

        psicologos.forEach(function(psicologo){

            let coincideTexto =
                psicologo.dataset.nombre.includes(texto)
                ||
                psicologo.dataset.bio.includes(texto);

            let coincideEspecialidad =
                especialidadElegida == ""
                ||
                psicologo.dataset.especialidades.split("|").includes(especialidadElegida);

            if(coincideTexto && coincideEspecialidad){
                psicologo.style.display = "flex";
                visibles++;
            }else{
                psicologo.style.display = "none";
            }

        });

        document.querySelector("#visibles").textContent = visibles;
        document.querySelector("#vacio").style.display = visibles == 0 ? "block" : "none";

    }


    buscador.oninput = filtrar;


    filtros.forEach(function(boton){

        boton.onclick = function(){

            filtros.forEach(function(b){ b.classList.remove("activo"); });
            boton.classList.add("activo");

            especialidadElegida = boton.dataset.esp;
            filtrar();

        };

    });


    // -------------------------------
    // VENTANA DE SOLICITUD
    // -------------------------------

    let ventana = document.querySelector("#ventana");

    function abrirSolicitud(boton){

        document.querySelector("#psicologo-id").value = boton.dataset.id;
        document.querySelector("#nombre-psicologo").textContent = boton.dataset.nombreMostrar;

        // Relleno el desplegable con las horas libres de este psicólogo
        let selector = document.querySelector("#horario");
        selector.innerHTML = "";

        let ninguna = document.createElement("option");
        ninguna.value = "";
        ninguna.textContent = "Sin hora concreta (que me propongan una)";
        selector.appendChild(ninguna);

        JSON.parse(boton.dataset.horarios || "[]").forEach(function(hora){
            let opcion = document.createElement("option");
            opcion.value = hora[0];
            opcion.textContent = hora[1];
            selector.appendChild(opcion);
        });

        ventana.showModal();

    }

</script>
""" + pie()


    # Devuelvo todo el HTML
    return cadena


# -------------------------------------------------
# GUARDAR UNA SOLICITUD
# -------------------------------------------------

@aplicacion.route("/solicitud", methods=["POST"])
def solicitud():

    # Solo los pacientes que han iniciado sesión pueden enviar solicitudes
    yo = usuario()
    if yo is None or yo["tipo"] != "paciente":
        return redirect("/entrar?tipo=paciente")

    # Recojo los datos del formulario
    psicologo_id = request.form.get("psicologo_id")
    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip()
    telefono = request.form.get("telefono", "").strip()
    resumen = request.form.get("resumen", "").strip()
    contacto = request.form.get("contacto", "email")

    if contacto not in ("email", "telefono"):
        contacto = "email"

    # Si falta algo, vuelvo al inicio
    if not psicologo_id or not nombre or not email or not resumen:
        return redirect("/#buscar")

    conexion = conectar()
    cursor = conexion.cursor()

    # Compruebo que el psicólogo existe
    cursor.execute("SELECT nombre, email FROM psicologos WHERE id = %s AND aprobado = 1", (psicologo_id,))
    psicologo = cursor.fetchone()

    if psicologo is None:
        cursor.close()
        conexion.close()
        return redirect("/#buscar")

    # Enlazo la solicitud con la cuenta del paciente
    paciente_id = yo["id"]

    # Guardo la solicitud (con %s para evitar inyección SQL)
    cursor.execute(
        "INSERT INTO solicitudes (psicologo_id, paciente_id, nombre_paciente, email_paciente, telefono, resumen, contacto) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (psicologo_id, paciente_id, nombre, email, telefono, resumen, contacto)
    )
    id_solicitud = cursor.lastrowid

    # Si ha elegido una hora, la reservo (solo si sigue libre, es de este psicólogo y es futura)
    horario_id = request.form.get("horario_id", "")
    if horario_id:
        cursor.execute(
            "UPDATE horarios SET solicitud_id = %s "
            "WHERE id = %s AND psicologo_id = %s AND solicitud_id IS NULL AND fecha_hora > %s",
            (id_solicitud, horario_id, psicologo_id, ahora())
        )
        if cursor.rowcount != 1:
            # Otra persona la ha reservado antes: no guardo nada
            conexion.rollback()
            cursor.close()
            conexion.close()
            return redirect("/?horario_ocupado=1#buscar")

    conexion.commit()

    cursor.close()
    conexion.close()

    # Aviso al psicólogo (sin el texto de la solicitud, por privacidad)
    avisar(psicologo[1], "Tienes una nueva solicitud en Encuéntrame",
           "Hola, " + psicologo[0] + ":\n\n"
           "Un paciente te ha enviado una solicitud de primera sesión"
           + (" y ha reservado una de tus horas libres." if horario_id else ".") + "\n\n"
           "Entra en tu panel para verla: " + URL_PUBLICA + "/panel")

    return redirect("/?enviado=" + quote(psicologo[0]))


# -------------------------------------------------
# PANEL DEL PSICÓLOGO
# -------------------------------------------------

@aplicacion.route("/panel")
def panel():

    # Solo entra un psicólogo que haya iniciado sesión
    yo = usuario()
    if yo is None or yo["tipo"] != "psicologo":
        return redirect("/entrar?tipo=psicologo")

    conexion = conectar()
    cursor = conexion.cursor()

    # ¿Su perfil ya está publicado?
    cursor.execute("SELECT aprobado FROM psicologos WHERE id = %s", (yo["id"],))
    aprobado = cursor.fetchone()[0]

    # Solicitudes de este psicólogo
    cursor.execute("""
        SELECT s.id, s.nombre_paciente, s.email_paciente, s.telefono, s.resumen, s.contacto, s.estado, s.fecha,
               h.fecha_hora, v.estrellas, v.comentario
        FROM solicitudes s
        LEFT JOIN horarios h ON h.solicitud_id = s.id
        LEFT JOIN valoraciones v ON v.solicitud_id = s.id
        WHERE s.psicologo_id = %s
        ORDER BY s.fecha DESC
    """, (yo["id"],))
    solicitudes = cursor.fetchall()

    # Mi nota media
    cursor.execute("SELECT AVG(estrellas), COUNT(*) FROM valoraciones WHERE psicologo_id = %s", (yo["id"],))
    mi_nota = cursor.fetchone()

    cursor.close()
    conexion.close()

    resumen_nota = ""
    if mi_nota and mi_nota[1]:
        resumen_nota = ('<p class="nota">Tu valoración media: <span class="estrellas">' + estrellas_texto(float(mi_nota[0]))
                        + '</span> ' + f"{float(mi_nota[0]):.1f}".replace(".", ",") + " (" + str(mi_nota[1])
                        + (" opinión" if mi_nota[1] == 1 else " opiniones") + ')</p>')


    cadena = cabecera("Panel del psicólogo — Encuéntrame") + """

<main class="contenedor">

    <div class="titulo-seccion">
        <div>
            <h2>Hola, """ + escape(yo["nombre"]) + """</h2>
            <p>Estas son las solicitudes que te han enviado. <a href="/agenda">Gestiona tus horas libres en tu agenda</a>.</p>
            """ + resumen_nota + """
        </div>
    </div>
""" + ("" if aprobado else """
    <div class="aviso-pendiente">
        ⏳ Tu perfil está pendiente de aprobación. Cuando un administrador lo revise,
        aparecerás en la página principal y los pacientes podrán escribirte.
    </div>
""") + """
    <div style="margin-top:25px">
"""

    if not solicitudes:
        cadena += '<p class="vacio" style="display:block">Aún no has recibido solicitudes.</p>'

    # Recorro las solicitudes
    for s in solicitudes:

        id_solicitud = s[0]
        contactado = s[6] == "contactado"

        boton = ""
        if not contactado:
            boton = f"""
            <form method="post" action="/contactado/{id_solicitud}">
                <button class="boton boton-pequeno" style="margin-top:10px">Marcar como contactado</button>
            </form>
            """

        cadena += f"""

        <div class="solicitud">

            <div class="meta">
                <strong>{escape(s[1])}</strong> · {s[7].strftime('%d/%m/%Y %H:%M')} ·
                <span class="estado {'contactado' if contactado else ''}">
                    {'Contactado' if contactado else 'Pendiente'}
                </span>
            </div>

            <p>{escape(s[4])}</p>

            <div class="meta">
                ✉ {escape(s[2])}
                {'· ☎ ' + escape(s[3]) if s[3] else ''}
                · Prefiere {'correo' if s[5] == 'email' else 'teléfono'}
            </div>

            {'<span class="cita">📅 Cita: ' + fecha_bonita(s[8]) + '</span>' if s[8] else ''}

            {'<div class="opinion"><span class="estrellas">' + estrellas_texto(s[9]) + '</span> ' + escape(s[10] or '') + '</div>' if s[9] else ''}

            {boton}

        </div>
"""

    cadena += """
    </div>

</main>
""" + pie()

    return cadena


# -------------------------------------------------
# MARCAR UNA SOLICITUD COMO CONTACTADA
# -------------------------------------------------

@aplicacion.route("/contactado/<int:id_solicitud>", methods=["POST"])
def contactado(id_solicitud):

    yo = usuario()
    if yo is None or yo["tipo"] != "psicologo":
        return redirect("/entrar?tipo=psicologo")

    # Solo puede cambiar sus propias solicitudes
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "UPDATE solicitudes SET estado = 'contactado' WHERE id = %s AND psicologo_id = %s AND estado = 'pendiente'",
        (id_solicitud, yo["id"])
    )
    cambiada = cursor.rowcount == 1

    # Correo de la cuenta del paciente (no el que escribió en el formulario)
    paciente = None
    if cambiada:
        cursor.execute("""
            SELECT pa.email, pa.nombre
            FROM solicitudes s
            JOIN pacientes pa ON pa.id = s.paciente_id
            WHERE s.id = %s
        """, (id_solicitud,))
        paciente = cursor.fetchone()

    conexion.commit()
    cursor.close()
    conexion.close()

    if paciente:
        avisar(paciente[0], "Tu psicólogo/a ha respondido a tu solicitud",
               "Hola, " + paciente[1] + ":\n\n"
               + yo["nombre"] + " ha marcado tu solicitud como contactada. "
               "Revisa tu correo y tu teléfono por si te ha escrito.\n\n"
               "Puedes ver tus solicitudes y, si quieres, valorar la atención aquí: " + URL_PUBLICA + "/mis-solicitudes")

    return redirect("/panel")


# -------------------------------------------------
# LOGIN Y REGISTRO
# -------------------------------------------------

# Formulario de entrar / crear cuenta (sirve para pacientes y psicólogos)
def pagina_acceso(modo, tipo, error=""):

    # Lo que ya había escrito el usuario (para no perderlo si hay un error)
    datos = request.form
    def valor(campo):
        return escape(datos.get(campo, ""))

    es_registro = modo == "registro"
    quien = {"paciente": "paciente", "psicologo": "psicólogo/a", "admin": "administrador"}[tipo]

    # El administrador no tiene pestañas ni puede crear cuenta
    pestanas = ""
    if tipo != "admin":
        pestanas = """
        <div class="pestanas">
            <a href="/""" + modo + """?tipo=paciente" class='""" + ("activa" if tipo == "paciente" else "") + """'>Soy paciente</a>
            <a href="/""" + modo + """?tipo=psicologo" class='""" + ("activa" if tipo == "psicologo" else "") + """'>Soy psicólogo/a</a>
        </div>
"""

    cadena = cabecera(("Crear cuenta" if es_registro else "Entrar") + " — Encuéntrame") + """

<main class="contenedor">

    <div class="caja-acceso">
""" + pestanas + """
        <h2>""" + ("Crear cuenta de " if es_registro else "Entrar como ") + quien + """</h2>
"""

    if error:
        cadena += '        <div class="error">' + escape(error) + '</div>\n'
    elif request.args.get("restablecida"):
        cadena += '        <div class="aviso" style="margin:0 0 16px 0">✓ Contraseña cambiada. Ya puedes entrar.</div>\n'

    cadena += """
        <form method="post" action="/""" + modo + """">

            <input type="hidden" name="tipo" value='""" + tipo + """'>
"""

    if es_registro:
        cadena += """
            <div class="campo">
                <label>Nombre completo</label>
                <input type="text" name="nombre" required value='""" + valor("nombre") + """'>
            </div>
"""

    cadena += """
            <div class="campo">
                <label>Correo electrónico</label>
                <input type="email" name="email" required value='""" + valor("email") + """'>
            </div>

            <div class="campo">
                <label>Contraseña</label>
                <input type="password" name="password" required""" + (' minlength="8"' if es_registro else "") + """>
                """ + ('<div class="pista">Mínimo 8 caracteres.</div>' if es_registro else "") + """
            </div>
"""

    # Los psicólogos rellenan también su perfil
    if es_registro and tipo == "psicologo":

        conexion = conectar()
        cursor = conexion.cursor()
        cursor.execute("SELECT id, nombre FROM especialidades ORDER BY nombre")
        especialidades = cursor.fetchall()
        cursor.close()
        conexion.close()

        marcadas = datos.getlist("especialidades")
        casillas = ""
        for esp in especialidades:
            marcada = " checked" if str(esp[0]) in marcadas else ""
            casillas += f'<label><input type="checkbox" name="especialidades" value="{esp[0]}"{marcada}> {escape(esp[1])}</label>\n'

        cadena += """
            <div class="campo">
                <label>Número de colegiado</label>
                <input type="text" name="numero_colegiado" required placeholder="CV-PSI-1234" value='""" + valor("numero_colegiado") + """'>
                <div class="pista">Un administrador lo revisará antes de publicar tu perfil.</div>
            </div>

            <div class="campo">
                <label>Teléfono de contacto</label>
                <input type="tel" name="telefono" value='""" + valor("telefono") + """'>
            </div>

            <div class="campo">
                <label>Especialidades</label>
                <div class="casillas">
                    """ + casillas + """
                </div>
            </div>

            <div class="campo">
                <label>Breve presentación</label>
                <textarea name="bio" placeholder="Cuenta en pocas líneas tu enfoque y experiencia.">""" + valor("bio") + """</textarea>
            </div>
"""

    if es_registro:
        cadena += """
            <div class="campo">
                <label class="aceptar"><input type="checkbox" name="acepto" value="1" required>
                    He leído y acepto la <a href="/privacidad" target="_blank">política de privacidad</a></label>
            </div>
"""

    cadena += """
            <button class="boton" style="width:100%">""" + ("Crear cuenta" if es_registro else "Entrar") + """</button>

        </form>
"""

    if tipo == "admin":
        pass
    elif es_registro:
        cadena += '        <p class="cambiar">¿Ya tienes cuenta? <a href="/entrar?tipo=' + tipo + '">Entrar</a></p>\n'
    else:
        cadena += '        <p class="cambiar"><a href="/olvide?tipo=' + tipo + '">¿Has olvidado tu contraseña?</a></p>\n'
        cadena += '        <p class="cambiar">¿No tienes cuenta? <a href="/registro?tipo=' + tipo + '">Crear cuenta</a></p>\n'

    cadena += """
    </div>

</main>
""" + pie()

    return cadena


# Leo el tipo de usuario de la URL o del formulario ("paciente" por defecto)
# El administrador solo puede entrar, no registrarse
def tipo_elegido(permitir_admin=False):
    tipo = request.values.get("tipo", "paciente")
    validos = ("paciente", "psicologo", "admin") if permitir_admin else ("paciente", "psicologo")
    return tipo if tipo in validos else "paciente"


# Nombre de la tabla de cada tipo de usuario (lista fija, nunca viene del usuario)
TABLAS = {"paciente": "pacientes", "psicologo": "psicologos", "admin": "administradores"}


# Guardo en la sesión quién ha entrado y lo mando a su página
def iniciar_sesion(tipo, id_usuario, nombre):
    session.clear()
    session["usuario"] = {"tipo": tipo, "id": id_usuario, "nombre": nombre}
    destinos = {"psicologo": "/panel", "admin": "/admin", "paciente": "/#buscar"}
    return redirect(destinos[tipo])


# -------------------------------------------------
# LÍMITE DE INTENTOS DE LOGIN
# Si alguien falla 5 veces en 15 minutos (con el mismo correo o desde la misma IP),
# lo bloqueo 15 minutos. Así no se pueden probar miles de contraseñas.
# -------------------------------------------------

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 15
intentos_fallidos = {}          # {clave: [momentos de los fallos]}


# IP real del visitante (en PythonAnywhere viene en una cabecera)
def ip_visitante():
    return request.headers.get("X-Real-IP") or request.remote_addr or "?"


def claves_intento(tipo, email):
    return ["correo:" + tipo + ":" + email, "ip:" + ip_visitante()]


# Borro los fallos antiguos y digo si alguna clave está bloqueada
def esta_bloqueado(claves, maximo=MAX_INTENTOS, minutos=MINUTOS_BLOQUEO):
    momento = datetime.now().timestamp()
    bloqueado = False
    for clave in claves:
        recientes = [t for t in intentos_fallidos.get(clave, []) if momento - t < minutos * 60]
        intentos_fallidos[clave] = recientes
        if len(recientes) >= maximo:
            bloqueado = True
    return bloqueado


def apuntar_fallo(claves):
    for clave in claves:
        intentos_fallidos.setdefault(clave, []).append(datetime.now().timestamp())


@aplicacion.route("/entrar", methods=["GET", "POST"])
def entrar():

    tipo = tipo_elegido(permitir_admin=True)

    if request.method == "GET":
        return pagina_acceso("entrar", tipo)

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    # ¿Demasiados intentos fallidos?
    claves = claves_intento(tipo, email)
    if esta_bloqueado(claves):
        return pagina_acceso("entrar", tipo, "Demasiados intentos fallidos. Espera " + str(MINUTOS_BLOQUEO) + " minutos y vuelve a intentarlo."), 429

    # El nombre de la tabla sale de una lista fija, nunca del usuario
    tabla = TABLAS[tipo]

    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("SELECT id, nombre, password_hash FROM " + tabla + " WHERE email = %s", (email,))
    fila = cursor.fetchone()
    cursor.close()
    conexion.close()

    # Compruebo la contraseña con el hash guardado
    if fila is None or not fila[2] or not check_password_hash(fila[2], password):
        apuntar_fallo(claves)
        return pagina_acceso("entrar", tipo, "Correo o contraseña incorrectos.")

    # Si entra bien, olvido los fallos de ese correo
    intentos_fallidos.pop(claves[0], None)
    return iniciar_sesion(tipo, fila[0], fila[1])


@aplicacion.route("/registro", methods=["GET", "POST"])
def registro():

    tipo = tipo_elegido()

    if request.method == "GET":
        return pagina_acceso("registro", tipo)

    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not nombre or not email:
        return pagina_acceso("registro", tipo, "Rellena el nombre y el correo.")

    if len(password) < 8:
        return pagina_acceso("registro", tipo, "La contraseña debe tener al menos 8 caracteres.")

    if request.form.get("acepto") != "1":
        return pagina_acceso("registro", tipo, "Para crear la cuenta tienes que aceptar la política de privacidad.")

    numero_colegiado = request.form.get("numero_colegiado", "").strip().upper()
    if tipo == "psicologo" and not numero_colegiado:
        return pagina_acceso("registro", tipo, "Escribe tu número de colegiado.")

    tabla = "pacientes" if tipo == "paciente" else "psicologos"

    conexion = conectar()
    cursor = conexion.cursor()

    # Compruebo que el correo no está ya registrado
    cursor.execute("SELECT id FROM " + tabla + " WHERE email = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        conexion.close()
        return pagina_acceso("registro", tipo, "Ya existe una cuenta con ese correo.")

    # El número de colegiado tampoco se puede repetir
    if tipo == "psicologo":
        cursor.execute("SELECT id FROM psicologos WHERE numero_colegiado = %s", (numero_colegiado,))
        if cursor.fetchone():
            cursor.close()
            conexion.close()
            return pagina_acceso("registro", tipo, "Ese número de colegiado ya está registrado.")

    # Nunca guardo la contraseña tal cual, solo su hash
    password_hash = generate_password_hash(password)

    if tipo == "paciente":

        cursor.execute(
            "INSERT INTO pacientes (nombre, email, password_hash, fecha_consentimiento) VALUES (%s, %s, %s, %s)",
            (nombre, email, password_hash, ahora())
        )
        nuevo_id = cursor.lastrowid

    else:

        telefono = request.form.get("telefono", "").strip()
        bio = request.form.get("bio", "").strip()

        # Me quedo solo con especialidades que existen de verdad
        cursor.execute("SELECT id, nombre FROM especialidades")
        existentes = {str(fila[0]): fila[1] for fila in cursor.fetchall()}
        elegidas = [i for i in request.form.getlist("especialidades") if i in existentes]

        # También relleno la columna antigua (separada por comas), que usa la página principal
        texto_especialidades = ",".join(existentes[i] for i in elegidas)

        cursor.execute(
            "INSERT INTO psicologos (nombre, email, numero_colegiado, password_hash, telefono, especialidades, bio, fecha_consentimiento) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (nombre, email, numero_colegiado, password_hash, telefono, texto_especialidades, bio, ahora())
        )

        nuevo_id = cursor.lastrowid
        for i in elegidas:
            cursor.execute(
                "INSERT INTO psicologo_especialidad (psicologo_id, especialidad_id) VALUES (%s, %s)",
                (nuevo_id, i)
            )

    conexion.commit()
    cursor.close()
    conexion.close()

    return iniciar_sesion(tipo, nuevo_id, nombre)


@aplicacion.route("/salir")
def salir():
    session.clear()
    return redirect("/")


# -------------------------------------------------
# MIS SOLICITUDES (PACIENTE)
# -------------------------------------------------

@aplicacion.route("/mis-solicitudes")
def mis_solicitudes():

    yo = usuario()
    if yo is None or yo["tipo"] != "paciente":
        return redirect("/entrar?tipo=paciente")

    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT s.resumen, s.contacto, s.estado, s.fecha, p.nombre, p.foto,
               s.id, h.fecha_hora, v.estrellas, v.comentario
        FROM solicitudes s
        JOIN psicologos p ON p.id = s.psicologo_id
        LEFT JOIN horarios h ON h.solicitud_id = s.id
        LEFT JOIN valoraciones v ON v.solicitud_id = s.id
        WHERE s.paciente_id = %s
        ORDER BY s.fecha DESC
    """, (yo["id"],))
    solicitudes = cursor.fetchall()
    cursor.close()
    conexion.close()

    cadena = cabecera("Mis solicitudes — Encuéntrame") + """

<main class="contenedor">

    <div class="titulo-seccion">
        <div>
            <h2>Mis solicitudes</h2>
            <p>Aquí ves a quién has escrito y si ya te han contactado.</p>
        </div>
    </div>
"""

    if request.args.get("valorado"):
        cadena += '    <div class="aviso" style="margin:0 0 16px 0">✓ Gracias por tu valoración.</div>\n'

    if not solicitudes:
        cadena += """
    <p class="vacio" style="display:block">
        Aún no has enviado ninguna solicitud.<br><br>
        <a class="boton" href="/#buscar">Buscar psicólogo</a>
    </p>
"""

    for s in solicitudes:

        contactado = s[2] == "contactado"

        # Si ya le han contactado, puede valorar (una sola vez)
        bloque_valoracion = ""
        if s[8]:
            bloque_valoracion = ('<div class="opinion">Tu valoración: <span class="estrellas">' + estrellas_texto(s[8])
                                 + '</span> ' + escape(s[9] or "") + '</div>')
        elif contactado:
            radios = ""
            for n in range(5, 0, -1):
                radios += (f'<input type="radio" name="estrellas" value="{n}" id="e{s[6]}_{n}" required>'
                           f'<label for="e{s[6]}_{n}" title="{n} estrellas">★</label>')
            bloque_valoracion = f"""
        <form method="post" action="/valorar/{s[6]}" class="valorar">
            <strong>¿Qué tal te ha ido?</strong>
            <div class="elegir-estrellas">{radios}</div>
            <textarea name="comentario" maxlength="1000" placeholder="Cuéntanos tu experiencia (opcional). No escribas datos personales."></textarea>
            <button class="boton boton-pequeno" style="margin-top:8px">Enviar valoración</button>
        </form>"""

        cadena += f"""

    <div class="solicitud">

        <div class="cabeza">
            {avatar(s[4], s[5], 38)}
            <div class="meta">
                Para <strong>{escape(s[4])}</strong> · {s[3].strftime('%d/%m/%Y %H:%M')} ·
                <span class="estado {'contactado' if contactado else ''}">
                    {'Te ha contactado' if contactado else 'Enviada'}
                </span>
            </div>
        </div>

        <p>{escape(s[0])}</p>

        <div class="meta">Prefieres que te contacten por {'correo' if s[1] == 'email' else 'teléfono'}</div>

        {'<span class="cita">📅 Cita: ' + fecha_bonita(s[7]) + '</span>' if s[7] else ''}

        {bloque_valoracion}

    </div>
"""

    cadena += """
    <p class="cambiar"><a href="/mis-datos">Descargar mis datos</a> · <a class="enlace-peligro" href="/eliminar-cuenta">Eliminar mi cuenta</a></p>

</main>
""" + pie()

    return cadena


# -------------------------------------------------
# EDITAR PERFIL (PSICÓLOGO)
# -------------------------------------------------

# Muestro las fotos guardadas en la carpeta "fotos"
@aplicacion.route("/fotos/<nombre>")
def fotos(nombre):
    return send_from_directory(CARPETA_FOTOS, nombre)


# Si la foto pesa más de 2 MB, Flask corta la petición y vengo aquí
@aplicacion.errorhandler(413)
def foto_grande(error):
    return redirect("/perfil?error=grande")


@aplicacion.route("/perfil", methods=["GET", "POST"])
def perfil():

    yo = usuario()
    if yo is None or yo["tipo"] != "psicologo":
        return redirect("/entrar?tipo=psicologo")

    conexion = conectar()
    cursor = conexion.cursor()

    error = ""
    if request.args.get("error") == "grande":
        error = "La foto es demasiado grande (máximo 2 MB)."

    aviso = ""
    if request.args.get("guardado"):
        aviso = '<div class="aviso" style="margin:0 0 16px 0">✓ Perfil guardado.</div>'

    # Lista de todas las especialidades {id: nombre}
    cursor.execute("SELECT id, nombre FROM especialidades ORDER BY nombre")
    especialidades = cursor.fetchall()
    existentes = {str(fila[0]): fila[1] for fila in especialidades}


    # ---------- Guardar cambios ----------
    if request.method == "POST":

        nombre = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        bio = request.form.get("bio", "").strip()
        elegidas = [i for i in request.form.getlist("especialidades") if i in existentes]

        # Compruebo la foto antes de guardar nada
        archivo = request.files.get("foto")
        extension = ""
        if archivo and archivo.filename:
            extension = archivo.filename.rsplit(".", 1)[-1].lower()
            if extension not in EXTENSIONES_FOTO:
                error = "La foto debe ser JPG, PNG o WEBP."

        if not nombre:
            error = "El nombre no puede estar vacío."

        # Número de colegiado: obligatorio y sin repetir
        numero_colegiado = request.form.get("numero_colegiado", "").strip().upper()
        cursor.execute(
            "SELECT id FROM psicologos WHERE numero_colegiado = %s AND id <> %s",
            (numero_colegiado, yo["id"])
        )
        if not numero_colegiado:
            error = "Escribe tu número de colegiado."
        elif cursor.fetchone():
            error = "Ese número de colegiado ya está registrado."

        if not error:

            # Guardo la foto nueva con un nombre único y borro la anterior
            if extension:
                cursor.execute("SELECT foto FROM psicologos WHERE id = %s", (yo["id"],))
                foto_anterior = cursor.fetchone()[0]

                os.makedirs(CARPETA_FOTOS, exist_ok=True)
                nombre_foto = f"{yo['id']}_{uuid.uuid4().hex[:8]}.{extension}"
                archivo.save(os.path.join(CARPETA_FOTOS, nombre_foto))
                cursor.execute("UPDATE psicologos SET foto = %s WHERE id = %s", (nombre_foto, yo["id"]))

                if foto_anterior and os.path.exists(os.path.join(CARPETA_FOTOS, foto_anterior)):
                    os.remove(os.path.join(CARPETA_FOTOS, foto_anterior))

            # Datos del perfil (también la columna antigua separada por comas)
            cursor.execute(
                "UPDATE psicologos SET nombre = %s, numero_colegiado = %s, telefono = %s, bio = %s, especialidades = %s WHERE id = %s",
                (nombre, numero_colegiado, telefono, bio, ",".join(existentes[i] for i in elegidas), yo["id"])
            )

            # Especialidades: borro las de antes y meto las nuevas
            cursor.execute("DELETE FROM psicologo_especialidad WHERE psicologo_id = %s", (yo["id"],))
            for i in elegidas:
                cursor.execute(
                    "INSERT INTO psicologo_especialidad (psicologo_id, especialidad_id) VALUES (%s, %s)",
                    (yo["id"], i)
                )

            conexion.commit()
            cursor.close()
            conexion.close()

            # Actualizo el nombre guardado en la sesión
            session["usuario"] = {"tipo": "psicologo", "id": yo["id"], "nombre": nombre}

            return redirect("/perfil?guardado=1")


    # ---------- Mostrar el formulario ----------
    cursor.execute("SELECT nombre, email, telefono, bio, foto, numero_colegiado FROM psicologos WHERE id = %s", (yo["id"],))
    datos = cursor.fetchone()
    cursor.execute("SELECT especialidad_id FROM psicologo_especialidad WHERE psicologo_id = %s", (yo["id"],))
    marcadas = [str(fila[0]) for fila in cursor.fetchall()]
    cursor.close()
    conexion.close()

    # Si hubo un error, enseño lo que había escrito
    if request.method == "POST":
        nombre = request.form.get("nombre", "")
        telefono = request.form.get("telefono", "")
        bio = request.form.get("bio", "")
        colegiado = request.form.get("numero_colegiado", "")
        marcadas = request.form.getlist("especialidades")
    else:
        nombre, telefono, bio, colegiado = datos[0], datos[2] or "", datos[3] or "", datos[5] or ""

    casillas = ""
    for esp in especialidades:
        marcada = " checked" if str(esp[0]) in marcadas else ""
        casillas += f'<label><input type="checkbox" name="especialidades" value="{esp[0]}"{marcada}> {escape(esp[1])}</label>\n'

    cadena = cabecera("Mi perfil — Encuéntrame") + """

<main class="contenedor">

    <div class="caja-acceso" style="max-width:560px">

        <h2>Mi perfil</h2>

        """ + aviso + ('<div class="error">' + escape(error) + '</div>' if error else "") + """

        <form method="post" action="/perfil" enctype="multipart/form-data">

            <div class="campo">
                <label>Foto</label>
                <div class="cabeza">
                    """ + avatar(datos[0], datos[4], 64) + """
                    <input type="file" name="foto" accept=".jpg,.jpeg,.png,.webp">
                </div>
                <div class="pista">JPG, PNG o WEBP. Máximo 2 MB.</div>
            </div>

            <div class="campo">
                <label>Nombre completo</label>
                <input type="text" name="nombre" required value='""" + escape(nombre) + """'>
            </div>

            <div class="campo">
                <label>Número de colegiado</label>
                <input type="text" name="numero_colegiado" required value='""" + escape(colegiado) + """'>
            </div>

            <div class="campo">
                <label>Correo electrónico</label>
                <input type="email" value='""" + escape(datos[1]) + """' disabled>
                <div class="pista">Es el correo con el que entras, no se puede cambiar.</div>
            </div>

            <div class="campo">
                <label>Teléfono de contacto</label>
                <input type="tel" name="telefono" value='""" + escape(telefono) + """'>
            </div>

            <div class="campo">
                <label>Especialidades</label>
                <div class="casillas">
                    """ + casillas + """
                </div>
            </div>

            <div class="campo">
                <label>Breve presentación</label>
                <textarea name="bio">""" + escape(bio) + """</textarea>
            </div>

            <button class="boton" style="width:100%">Guardar cambios</button>

        </form>

        <p class="cambiar"><a href="/mis-datos">Descargar mis datos</a> · <a class="enlace-peligro" href="/eliminar-cuenta">Eliminar mi cuenta</a></p>

    </div>

</main>
""" + pie()

    return cadena


# -------------------------------------------------
# ELIMINAR CUENTA (PACIENTE O PSICÓLOGO)
# -------------------------------------------------

@aplicacion.route("/eliminar-cuenta", methods=["GET", "POST"])
def eliminar_cuenta():

    # El administrador no se borra desde aquí (solo pacientes y psicólogos)
    yo = usuario()
    if yo is None or yo["tipo"] == "admin":
        return redirect("/entrar")

    error = ""

    # ---------- Borrar la cuenta ----------
    if request.method == "POST":

        tabla = "pacientes" if yo["tipo"] == "paciente" else "psicologos"

        conexion = conectar()
        cursor = conexion.cursor()

        # Pido la contraseña otra vez para confirmar que es él
        cursor.execute("SELECT password_hash FROM " + tabla + " WHERE id = %s", (yo["id"],))
        fila = cursor.fetchone()

        if fila is None or not check_password_hash(fila[0], request.form.get("password", "")):
            error = "La contraseña no es correcta."
            cursor.close()
            conexion.close()

        else:

            if yo["tipo"] == "paciente":

                # Borro también sus solicitudes (sus datos personales no se quedan en la web)
                cursor.execute("DELETE FROM solicitudes WHERE paciente_id = %s", (yo["id"],))
                cursor.execute("DELETE FROM pacientes WHERE id = %s", (yo["id"],))

            else:

                # Borro su foto del disco
                cursor.execute("SELECT foto FROM psicologos WHERE id = %s", (yo["id"],))
                foto = cursor.fetchone()[0]
                if foto and os.path.exists(os.path.join(CARPETA_FOTOS, foto)):
                    os.remove(os.path.join(CARPETA_FOTOS, foto))

                # Sus solicitudes y especialidades se borran solas (ON DELETE CASCADE)
                cursor.execute("DELETE FROM psicologos WHERE id = %s", (yo["id"],))

            conexion.commit()
            cursor.close()
            conexion.close()

            session.clear()
            return redirect("/?eliminado=1")


    # ---------- Pedir confirmación ----------
    if yo["tipo"] == "paciente":
        que_se_borra = "tu cuenta y todas las solicitudes que has enviado"
        volver = "/mis-solicitudes"
    else:
        que_se_borra = "tu perfil, tu foto y todas las solicitudes que has recibido. Dejarás de aparecer en la web"
        volver = "/perfil"

    cadena = cabecera("Eliminar cuenta — Encuéntrame") + """

<main class="contenedor">

    <div class="caja-acceso">

        <h2>Eliminar mi cuenta</h2>

        """ + ('<div class="error">' + escape(error) + '</div>' if error else "") + """

        <p>Se borrará """ + que_se_borra + """.</p>
        <p><strong>Esta acción no se puede deshacer.</strong></p>

        <form method="post" action="/eliminar-cuenta">

            <div class="campo">
                <label>Escribe tu contraseña para confirmar</label>
                <input type="password" name="password" required>
            </div>

            <button class="boton boton-peligro" style="width:100%">Eliminar mi cuenta para siempre</button>

        </form>

        <p class="cambiar"><a href='""" + volver + """'>Cancelar</a></p>

    </div>

</main>
""" + pie()

    return cadena


# -------------------------------------------------
# PÁGINA DE ADMINISTRACIÓN
# -------------------------------------------------

# ¿Ha entrado un administrador?
def es_admin():
    yo = usuario()
    return yo is not None and yo["tipo"] == "admin"


@aplicacion.route("/admin")
def admin():

    if not es_admin():
        return redirect("/entrar?tipo=admin")

    conexion = conectar()
    cursor = conexion.cursor()

    # Cifras generales
    cursor.execute("""
        SELECT
            (SELECT COUNT(*) FROM psicologos WHERE aprobado = 1),
            (SELECT COUNT(*) FROM psicologos WHERE aprobado = 0),
            (SELECT COUNT(*) FROM pacientes),
            (SELECT COUNT(*) FROM solicitudes WHERE estado = 'pendiente'),
            (SELECT COUNT(*) FROM contactos WHERE leido = 0)
    """)
    cifras = cursor.fetchone()

    # Mensajes de contacto (primero los no leídos)
    cursor.execute("SELECT id, nombre, email, mensaje, fecha, leido FROM contactos ORDER BY leido ASC, fecha DESC LIMIT 50")
    mensajes = cursor.fetchall()

    # Últimas valoraciones
    cursor.execute("""
        SELECT v.id, v.fecha, p.nombre, v.estrellas, v.comentario
        FROM valoraciones v
        JOIN psicologos p ON p.id = v.psicologo_id
        ORDER BY v.fecha DESC
        LIMIT 30
    """)
    valoraciones = cursor.fetchall()

    # Psicólogos: primero los pendientes de aprobar
    cursor.execute("""
        SELECT p.id, p.nombre, p.email, p.numero_colegiado, p.especialidades, p.foto, p.aprobado,
               COUNT(s.id)
        FROM psicologos p
        LEFT JOIN solicitudes s ON s.psicologo_id = p.id
        GROUP BY p.id
        ORDER BY p.aprobado ASC, p.nombre ASC
    """)
    psicologos = cursor.fetchall()

    # Pacientes con el número de solicitudes que han enviado
    cursor.execute("""
        SELECT pa.id, pa.nombre, pa.email, pa.fecha_registro, COUNT(s.id)
        FROM pacientes pa
        LEFT JOIN solicitudes s ON s.paciente_id = pa.id
        GROUP BY pa.id
        ORDER BY pa.fecha_registro DESC
    """)
    pacientes = cursor.fetchall()

    # Últimas solicitudes
    cursor.execute("""
        SELECT s.fecha, s.nombre_paciente, p.nombre, s.estado
        FROM solicitudes s
        JOIN psicologos p ON p.id = s.psicologo_id
        ORDER BY s.fecha DESC
        LIMIT 20
    """)
    solicitudes = cursor.fetchall()

    cursor.close()
    conexion.close()

    aviso = ""
    if request.args.get("hecho"):
        aviso = '<div class="aviso" style="margin:0 0 20px 0">✓ ' + escape(request.args.get("hecho")) + '</div>'

    cadena = cabecera("Administración — Encuéntrame") + """

<main class="contenedor admin">

    <div class="titulo-seccion">
        <div>
            <h2>Administración</h2>
            <p>Revisa los perfiles nuevos y gestiona los usuarios de la web.</p>
        </div>
    </div>

    """ + aviso + f"""

    <div class="cifras">
        <div class="cifra"><strong>{cifras[0]}</strong><span>Psicólogos publicados</span></div>
        <div class="cifra"><strong>{cifras[1]}</strong><span>Pendientes de aprobar</span></div>
        <div class="cifra"><strong>{cifras[2]}</strong><span>Pacientes</span></div>
        <div class="cifra"><strong>{cifras[3]}</strong><span>Solicitudes pendientes</span></div>
        <div class="cifra"><strong>{cifras[4]}</strong><span>Mensajes sin leer</span></div>
    </div>


    <h3>Psicólogos</h3>

    <div class="tabla-admin">
        <table>
            <tr>
                <th>Psicólogo/a</th>
                <th>Nº colegiado</th>
                <th>Especialidades</th>
                <th>Solicitudes</th>
                <th>Estado</th>
                <th>Acciones</th>
            </tr>
"""

    for p in psicologos:

        aprobado = p[6] == 1
        especialidades = escape((p[4] or "").replace(",", ", "))

        cadena += f"""
            <tr>
                <td>
                    <div class="cabeza">
                        {avatar(p[1], p[5], 34)}
                        <div><strong>{escape(p[1])}</strong><br><span class="colegiado">{escape(p[2])}</span></div>
                    </div>
                </td>
                <td>{escape(p[3] or "—")}</td>
                <td>{especialidades}</td>
                <td>{p[7]}</td>
                <td><span class="insignia {'si' if aprobado else 'no'}">{'Publicado' if aprobado else 'Pendiente'}</span></td>
                <td class="acciones">
                    <form method="post" action="/admin/psicologo/{p[0]}/aprobar">
                        <button class="boton-mini {'' if aprobado else 'verde'}">{'Ocultar' if aprobado else 'Aprobar'}</button>
                    </form>
                    <form method="post" action="/admin/psicologo/{p[0]}/eliminar"
                          onsubmit="return confirm('¿Eliminar a este psicólogo y todas sus solicitudes? No se puede deshacer.')">
                        <button class="boton-mini rojo">Eliminar</button>
                    </form>
                </td>
            </tr>
"""

    cadena += """
        </table>
    </div>


    <h3>Pacientes</h3>
"""

    if not pacientes:
        cadena += '    <p class="vacio" style="display:block">Todavía no hay pacientes registrados.</p>\n'
    else:
        cadena += """
    <div class="tabla-admin">
        <table>
            <tr>
                <th>Paciente</th>
                <th>Correo</th>
                <th>Registro</th>
                <th>Solicitudes</th>
                <th>Acciones</th>
            </tr>
"""
        for pa in pacientes:
            cadena += f"""
            <tr>
                <td><strong>{escape(pa[1])}</strong></td>
                <td>{escape(pa[2])}</td>
                <td>{pa[3].strftime('%d/%m/%Y') if pa[3] else '—'}</td>
                <td>{pa[4]}</td>
                <td class="acciones">
                    <form method="post" action="/admin/paciente/{pa[0]}/eliminar"
                          onsubmit="return confirm('¿Eliminar a este paciente y sus solicitudes? No se puede deshacer.')">
                        <button class="boton-mini rojo">Eliminar</button>
                    </form>
                </td>
            </tr>
"""
        cadena += """
        </table>
    </div>
"""

    cadena += """

    <h3>Últimas solicitudes</h3>
"""

    if not solicitudes:
        cadena += '    <p class="vacio" style="display:block">Todavía no hay solicitudes.</p>\n'
    else:
        cadena += """
    <div class="tabla-admin">
        <table>
            <tr>
                <th>Fecha</th>
                <th>Paciente</th>
                <th>Psicólogo/a</th>
                <th>Estado</th>
            </tr>
"""
        for s in solicitudes:
            contactado = s[3] == "contactado"
            cadena += f"""
            <tr>
                <td>{s[0].strftime('%d/%m/%Y %H:%M')}</td>
                <td>{escape(s[1])}</td>
                <td>{escape(s[2])}</td>
                <td><span class="insignia {'si' if contactado else 'no'}">{'Contactado' if contactado else 'Pendiente'}</span></td>
            </tr>
"""
        cadena += """
        </table>
    </div>
"""

    # ---------- Mensajes de contacto ----------
    cadena += """

    <h3>Mensajes de contacto</h3>
"""
    if not mensajes:
        cadena += '    <p class="vacio" style="display:block">Todavía no hay mensajes.</p>\n'
    else:
        cadena += """
    <div class="tabla-admin">
        <table>
            <tr>
                <th>Fecha</th>
                <th>De</th>
                <th>Mensaje</th>
                <th>Acciones</th>
            </tr>
"""
        for m in mensajes:
            boton_leido = ""
            if not m[5]:
                boton_leido = f"""
                    <form method="post" action="/admin/contacto/{m[0]}/leido">
                        <button class="boton-mini verde">Marcar leído</button>
                    </form>"""
            cadena += f"""
            <tr class="{'' if m[5] else 'no-leido'}">
                <td>{m[4].strftime('%d/%m/%Y %H:%M')}</td>
                <td>{escape(m[1])}<br><span class="colegiado">{escape(m[2])}</span></td>
                <td style="font-weight:normal">{escape(m[3])}</td>
                <td class="acciones">
                    {boton_leido}
                    <form method="post" action="/admin/contacto/{m[0]}/eliminar"
                          onsubmit="return confirm('¿Eliminar este mensaje?')">
                        <button class="boton-mini rojo">Eliminar</button>
                    </form>
                </td>
            </tr>
"""
        cadena += """
        </table>
    </div>
"""

    # ---------- Valoraciones ----------
    cadena += """

    <h3>Últimas valoraciones</h3>
"""
    if not valoraciones:
        cadena += '    <p class="vacio" style="display:block">Todavía no hay valoraciones.</p>\n'
    else:
        cadena += """
    <div class="tabla-admin">
        <table>
            <tr>
                <th>Fecha</th>
                <th>Psicólogo/a</th>
                <th>Nota</th>
                <th>Comentario</th>
                <th>Acciones</th>
            </tr>
"""
        for v in valoraciones:
            cadena += f"""
            <tr>
                <td>{v[1].strftime('%d/%m/%Y')}</td>
                <td>{escape(v[2])}</td>
                <td><span class="estrellas">{estrellas_texto(v[3])}</span></td>
                <td>{escape(v[4] or '')}</td>
                <td class="acciones">
                    <form method="post" action="/admin/valoracion/{v[0]}/eliminar"
                          onsubmit="return confirm('¿Eliminar esta valoración?')">
                        <button class="boton-mini rojo">Eliminar</button>
                    </form>
                </td>
            </tr>
"""
        cadena += """
        </table>
    </div>
"""

    cadena += """
</main>
""" + pie()

    return cadena


# Marcar un mensaje de contacto como leído
@aplicacion.route("/admin/contacto/<int:id_mensaje>/leido", methods=["POST"])
def admin_contacto_leido(id_mensaje):
    if not es_admin():
        return redirect("/entrar?tipo=admin")
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("UPDATE contactos SET leido = 1 WHERE id = %s", (id_mensaje,))
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect("/admin?hecho=" + quote("Mensaje marcado como leído."))


# Eliminar un mensaje de contacto
@aplicacion.route("/admin/contacto/<int:id_mensaje>/eliminar", methods=["POST"])
def admin_contacto_eliminar(id_mensaje):
    if not es_admin():
        return redirect("/entrar?tipo=admin")
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM contactos WHERE id = %s", (id_mensaje,))
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect("/admin?hecho=" + quote("Mensaje eliminado."))


# Eliminar una valoración (por ejemplo, si es ofensiva)
@aplicacion.route("/admin/valoracion/<int:id_valoracion>/eliminar", methods=["POST"])
def admin_valoracion_eliminar(id_valoracion):
    if not es_admin():
        return redirect("/entrar?tipo=admin")
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM valoraciones WHERE id = %s", (id_valoracion,))
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect("/admin?hecho=" + quote("Valoración eliminada."))


# Aprobar u ocultar un psicólogo (cambia de 0 a 1 o de 1 a 0)
@aplicacion.route("/admin/psicologo/<int:id_psicologo>/aprobar", methods=["POST"])
def admin_aprobar(id_psicologo):

    if not es_admin():
        return redirect("/entrar?tipo=admin")

    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("UPDATE psicologos SET aprobado = 1 - aprobado WHERE id = %s", (id_psicologo,))
    cursor.execute("SELECT nombre, aprobado, email FROM psicologos WHERE id = %s", (id_psicologo,))
    fila = cursor.fetchone()
    conexion.commit()
    cursor.close()
    conexion.close()

    if fila is None:
        return redirect("/admin")

    if fila[1] == 1:
        avisar(fila[2], "Tu perfil ya está publicado en Encuéntrame",
               "Hola, " + fila[0] + ":\n\n"
               "Hemos revisado tu perfil y ya aparece en la web. Los pacientes ya pueden escribirte.\n\n"
               "Consejo: añade tus horas libres en tu agenda para que puedan reservar: " + URL_PUBLICA + "/agenda")

    texto = fila[0] + (" ya aparece en la web." if fila[1] == 1 else " se ha ocultado de la web.")
    return redirect("/admin?hecho=" + quote(texto))


# Eliminar un psicólogo (sus solicitudes y especialidades se borran solas)
@aplicacion.route("/admin/psicologo/<int:id_psicologo>/eliminar", methods=["POST"])
def admin_eliminar_psicologo(id_psicologo):

    if not es_admin():
        return redirect("/entrar?tipo=admin")

    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("SELECT nombre, foto FROM psicologos WHERE id = %s", (id_psicologo,))
    fila = cursor.fetchone()

    if fila is None:
        cursor.close()
        conexion.close()
        return redirect("/admin")

    # Borro su foto del disco
    if fila[1] and os.path.exists(os.path.join(CARPETA_FOTOS, fila[1])):
        os.remove(os.path.join(CARPETA_FOTOS, fila[1]))

    cursor.execute("DELETE FROM psicologos WHERE id = %s", (id_psicologo,))
    conexion.commit()
    cursor.close()
    conexion.close()

    return redirect("/admin?hecho=" + quote(fila[0] + " se ha eliminado."))


# Eliminar un paciente y sus solicitudes
@aplicacion.route("/admin/paciente/<int:id_paciente>/eliminar", methods=["POST"])
def admin_eliminar_paciente(id_paciente):

    if not es_admin():
        return redirect("/entrar?tipo=admin")

    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("SELECT nombre FROM pacientes WHERE id = %s", (id_paciente,))
    fila = cursor.fetchone()

    if fila is None:
        cursor.close()
        conexion.close()
        return redirect("/admin")

    cursor.execute("DELETE FROM solicitudes WHERE paciente_id = %s", (id_paciente,))
    cursor.execute("DELETE FROM pacientes WHERE id = %s", (id_paciente,))
    conexion.commit()
    cursor.close()
    conexion.close()

    return redirect("/admin?hecho=" + quote(fila[0] + " se ha eliminado."))


# -------------------------------------------------
# CONTACTO
# -------------------------------------------------

@aplicacion.route("/contacto", methods=["GET", "POST"])
def contacto():

    yo = usuario()
    error = ""
    enviado = False

    # Si ha iniciado sesión, relleno su nombre y correo
    nombre_defecto = ""
    email_defecto = ""
    if yo and yo["tipo"] in ("paciente", "psicologo"):
        conexion = conectar()
        cursor = conexion.cursor()
        cursor.execute("SELECT nombre, email FROM " + TABLAS[yo["tipo"]] + " WHERE id = %s", (yo["id"],))
        fila = cursor.fetchone()
        cursor.close()
        conexion.close()
        if fila:
            nombre_defecto, email_defecto = fila

    if request.method == "POST":

        nombre = request.form.get("nombre", "").strip()[:100]
        email = request.form.get("email", "").strip().lower()[:150]
        mensaje = request.form.get("mensaje", "").strip()[:2000]

        # Máximo 5 mensajes por hora desde la misma IP (contra el spam)
        claves = ["contacto:" + ip_visitante()]

        if not nombre or "@" not in email or not mensaje:
            error = "Rellena tu nombre, un correo válido y el mensaje."
        elif request.form.get("acepto") != "1":
            error = "Para enviar el mensaje tienes que aceptar la política de privacidad."
        elif esta_bloqueado(claves, maximo=5, minutos=60):
            error = "Has enviado demasiados mensajes. Inténtalo más tarde."
        else:
            conexion = conectar()
            cursor = conexion.cursor()
            cursor.execute(
                "INSERT INTO contactos (nombre, email, mensaje) VALUES (%s, %s, %s)",
                (nombre, email, mensaje)
            )
            conexion.commit()
            cursor.close()
            conexion.close()
            apuntar_fallo(claves)          # Cuenta como un envío más
            enviado = True

    datos = request.form if (request.method == "POST" and not enviado) else {}

    cadena = cabecera("Contacto — Encuéntrame") + """

<main class="contenedor">

    <div class="caja-acceso" style="max-width:560px">

        <h2>Contacto</h2>
        <p style="color:var(--tinta-suave);margin-top:-6px">¿Tienes una duda, una sugerencia o has encontrado un error? Escríbenos.</p>
"""

    if enviado:
        cadena += """
        <div class="aviso" style="margin:0 0 16px 0">✓ Mensaje enviado. Gracias por escribirnos.</div>
        <a class="boton" href="/">Volver al inicio</a>
"""
    else:
        if error:
            cadena += '        <div class="error">' + escape(error) + '</div>\n'
        cadena += """
        <form method="post" action="/contacto">

            <div class="campo">
                <label>Tu nombre</label>
                <input type="text" name="nombre" required maxlength="100" value='""" + escape(datos.get("nombre", nombre_defecto)) + """'>
            </div>

            <div class="campo">
                <label>Correo electrónico</label>
                <input type="email" name="email" required maxlength="150" value='""" + escape(datos.get("email", email_defecto)) + """'>
            </div>

            <div class="campo">
                <label>Mensaje</label>
                <textarea name="mensaje" required maxlength="2000">""" + escape(datos.get("mensaje", "")) + """</textarea>
                <div class="pista">No escribas datos de salud ni información personal sensible.</div>
            </div>

            <div class="campo">
                <label class="aceptar"><input type="checkbox" name="acepto" value="1" required>
                    He leído y acepto la <a href="/privacidad" target="_blank">política de privacidad</a></label>
            </div>

            <button class="boton" style="width:100%">Enviar mensaje</button>

        </form>
"""

    cadena += """
    </div>

</main>
""" + pie()

    return cadena


# -------------------------------------------------
# RECUPERAR LA CONTRASEÑA
# -------------------------------------------------

# Guardo solo el hash del código del enlace (si alguien ve la base de datos, no puede usarlo)
def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


@aplicacion.route("/olvide", methods=["GET", "POST"])
def olvide():

    tipo = tipo_elegido()
    mensaje = ""
    error = ""

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        claves = ["olvide:" + ip_visitante(), "olvide:" + email]

        if esta_bloqueado(claves, maximo=3, minutos=60):
            error = "Has pedido demasiados enlaces. Inténtalo dentro de una hora."
        else:
            apuntar_fallo(claves)

            conexion = conectar()
            cursor = conexion.cursor()
            cursor.execute("SELECT id, nombre FROM " + TABLAS[tipo] + " WHERE email = %s", (email,))
            fila = cursor.fetchone()

            if fila:
                # Anulo los enlaces anteriores y creo uno nuevo (1 hora, un solo uso)
                token = secrets.token_urlsafe(32)
                cursor.execute(
                    "UPDATE recuperaciones SET usado = 1 WHERE tipo = %s AND usuario_id = %s AND usado = 0",
                    (tipo, fila[0])
                )
                cursor.execute(
                    "INSERT INTO recuperaciones (tipo, usuario_id, token_hash, expira) VALUES (%s, %s, %s, %s)",
                    (tipo, fila[0], hash_token(token), ahora() + timedelta(hours=1))
                )
                conexion.commit()

                # En el servidor uso la dirección fija (no la que manda el navegador)
                base = URL_PUBLICA if EN_SERVIDOR else request.host_url.rstrip("/")
                enlace = base + "/restablecer/" + token

                texto = ("Hola, " + fila[1] + ":\n\n"
                         "Has pedido cambiar tu contraseña de Encuéntrame. Abre este enlace (caduca en 1 hora):\n\n"
                         + enlace + "\n\n"
                         "Si no lo has pedido tú, ignora este correo: tu contraseña no cambiará.")

                if not enviar_correo(email, "Cambiar tu contraseña de Encuéntrame", texto) and not EN_SERVIDOR:
                    # En mi PC, si no hay correo configurado, enseño el enlace en la terminal
                    print("[SOLO EN LOCAL] Enlace para cambiar la contraseña:", enlace)

            cursor.close()
            conexion.close()

            # Siempre el mismo mensaje: así nadie puede saber qué correos están registrados
            mensaje = "Si existe una cuenta con ese correo, te hemos enviado un enlace para cambiar la contraseña. Revisa también la carpeta de spam."

    quien = "paciente" if tipo == "paciente" else "psicólogo/a"

    cadena = cabecera("Recuperar contraseña — Encuéntrame") + """

<main class="contenedor">

    <div class="caja-acceso">

        <h2>¿Has olvidado tu contraseña?</h2>
        <p style="color:var(--tinta-suave);margin-top:-6px">Cuenta de """ + quien + """. Te enviaremos un enlace a tu correo.</p>
"""

    if mensaje:
        cadena += '        <div class="aviso" style="margin:0 0 16px 0">✓ ' + escape(mensaje) + '</div>\n'
    else:
        if error:
            cadena += '        <div class="error">' + escape(error) + '</div>\n'
        cadena += """
        <form method="post" action="/olvide">
            <input type="hidden" name="tipo" value='""" + tipo + """'>
            <div class="campo">
                <label>Correo electrónico</label>
                <input type="email" name="email" required>
            </div>
            <button class="boton" style="width:100%">Enviar enlace</button>
        </form>
"""

    cadena += """
        <p class="cambiar"><a href="/entrar?tipo=""" + tipo + """">Volver a entrar</a></p>

    </div>

</main>
""" + pie()

    return cadena


@aplicacion.route("/restablecer/<token>", methods=["GET", "POST"])
def restablecer(token):

    conexion = conectar()
    cursor = conexion.cursor()

    # Busco el enlace: tiene que existir, no estar usado y no haber caducado
    cursor.execute(
        "SELECT id, tipo, usuario_id FROM recuperaciones WHERE token_hash = %s AND usado = 0 AND expira > %s",
        (hash_token(token), ahora())
    )
    fila = cursor.fetchone()

    if fila is None or fila[1] not in ("paciente", "psicologo"):
        cursor.close()
        conexion.close()
        return cabecera("Enlace no válido — Encuéntrame") + """
<main class="contenedor">
    <div class="caja-acceso">
        <h2>Enlace no válido</h2>
        <p>Este enlace ha caducado o ya se ha usado. Puedes pedir uno nuevo.</p>
        <a class="boton" href="/olvide">Pedir otro enlace</a>
    </div>
</main>
""" + pie(), 400

    id_recuperacion, tipo, usuario_id = fila
    error = ""

    if request.method == "POST":

        password = request.form.get("password", "")
        repetida = request.form.get("password2", "")

        if len(password) < 8:
            error = "La contraseña debe tener al menos 8 caracteres."
        elif password != repetida:
            error = "Las dos contraseñas no coinciden."
        else:
            cursor.execute(
                "UPDATE " + TABLAS[tipo] + " SET password_hash = %s WHERE id = %s",
                (generate_password_hash(password), usuario_id)
            )
            cursor.execute("UPDATE recuperaciones SET usado = 1 WHERE id = %s", (id_recuperacion,))
            cursor.execute("SELECT email FROM " + TABLAS[tipo] + " WHERE id = %s", (usuario_id,))
            correo = cursor.fetchone()
            conexion.commit()
            cursor.close()
            conexion.close()

            # Quito el bloqueo de intentos de ese correo
            if correo:
                intentos_fallidos.pop("correo:" + tipo + ":" + correo[0], None)

            session.clear()
            return redirect("/entrar?tipo=" + tipo + "&restablecida=1")

    cursor.close()
    conexion.close()

    cadena = cabecera("Nueva contraseña — Encuéntrame") + """

<main class="contenedor">

    <div class="caja-acceso">

        <h2>Nueva contraseña</h2>
""" + ('        <div class="error">' + escape(error) + '</div>\n' if error else "") + """
        <form method="post" action="/restablecer/""" + escape(token) + """">
            <div class="campo">
                <label>Nueva contraseña</label>
                <input type="password" name="password" required minlength="8">
                <div class="pista">Mínimo 8 caracteres.</div>
            </div>
            <div class="campo">
                <label>Repite la contraseña</label>
                <input type="password" name="password2" required minlength="8">
            </div>
            <button class="boton" style="width:100%">Guardar contraseña</button>
        </form>

    </div>

</main>
""" + pie()

    return cadena


# -------------------------------------------------
# VALORAR A UN PSICÓLOGO (PACIENTE)
# -------------------------------------------------

@aplicacion.route("/valorar/<int:id_solicitud>", methods=["POST"])
def valorar(id_solicitud):

    yo = usuario()
    if yo is None or yo["tipo"] != "paciente":
        return redirect("/entrar?tipo=paciente")

    try:
        estrellas = int(request.form.get("estrellas", "0"))
    except ValueError:
        estrellas = 0
    comentario = request.form.get("comentario", "").strip()[:1000]

    if estrellas < 1 or estrellas > 5:
        return redirect("/mis-solicitudes")

    conexion = conectar()
    cursor = conexion.cursor()

    # La solicitud tiene que ser suya, estar contactada y no tener valoración todavía
    cursor.execute("""
        SELECT s.psicologo_id
        FROM solicitudes s
        LEFT JOIN valoraciones v ON v.solicitud_id = s.id
        WHERE s.id = %s AND s.paciente_id = %s AND s.estado = 'contactado' AND v.id IS NULL
    """, (id_solicitud, yo["id"]))
    fila = cursor.fetchone()

    if fila:
        cursor.execute(
            "INSERT INTO valoraciones (solicitud_id, psicologo_id, paciente_id, estrellas, comentario) "
            "VALUES (%s, %s, %s, %s, %s)",
            (id_solicitud, fila[0], yo["id"], estrellas, comentario)
        )
        conexion.commit()

    cursor.close()
    conexion.close()

    return redirect("/mis-solicitudes" + ("?valorado=1" if fila else ""))


# -------------------------------------------------
# AGENDA DEL PSICÓLOGO
# -------------------------------------------------

@aplicacion.route("/agenda", methods=["GET", "POST"])
def agenda():

    yo = usuario()
    if yo is None or yo["tipo"] != "psicologo":
        return redirect("/entrar?tipo=psicologo")

    error = ""
    aviso = ""

    conexion = conectar()
    cursor = conexion.cursor()

    # ---------- Añadir una hora libre ----------
    if request.method == "POST":
        try:
            fecha_hora = datetime.strptime(
                request.form.get("fecha", "") + " " + request.form.get("hora", ""), "%Y-%m-%d %H:%M"
            )
        except ValueError:
            fecha_hora = None

        if fecha_hora is None:
            error = "Elige una fecha y una hora válidas."
        elif fecha_hora <= ahora():
            error = "La hora tiene que ser en el futuro."
        elif fecha_hora > ahora() + timedelta(days=365):
            error = "Solo puedes añadir horas para el próximo año."
        else:
            cursor.execute(
                "SELECT id FROM horarios WHERE psicologo_id = %s AND fecha_hora = %s",
                (yo["id"], fecha_hora)
            )
            if cursor.fetchone():
                error = "Ya tienes esa hora en tu agenda."
            else:
                cursor.execute(
                    "INSERT INTO horarios (psicologo_id, fecha_hora) VALUES (%s, %s)",
                    (yo["id"], fecha_hora)
                )
                conexion.commit()
                aviso = "Hora añadida: " + fecha_bonita(fecha_hora)

    if request.args.get("borrada"):
        aviso = "Hora eliminada."

    # ---------- Mis horas futuras ----------
    cursor.execute("""
        SELECT h.id, h.fecha_hora, s.nombre_paciente
        FROM horarios h
        LEFT JOIN solicitudes s ON s.id = h.solicitud_id
        WHERE h.psicologo_id = %s AND h.fecha_hora > %s
        ORDER BY h.fecha_hora
    """, (yo["id"], ahora()))
    horas = cursor.fetchall()

    cursor.close()
    conexion.close()

    manana = (ahora() + timedelta(days=1)).strftime("%Y-%m-%d")

    cadena = cabecera("Mi agenda — Encuéntrame") + """

<main class="contenedor">

    <div class="titulo-seccion">
        <div>
            <h2>Mi agenda</h2>
            <p>Añade las horas en las que puedes atender. Los pacientes podrán elegir una al pedir la primera sesión.</p>
        </div>
    </div>
"""

    if aviso:
        cadena += '    <div class="aviso" style="margin:0 0 16px 0">✓ ' + escape(aviso) + '</div>\n'
    if error:
        cadena += '    <div class="error">' + escape(error) + '</div>\n'

    cadena += """
    <form method="post" action="/agenda" class="form-linea" style="margin-bottom:26px">
        <div class="campo">
            <label>Día</label>
            <input type="date" name="fecha" required min='""" + manana + """' value='""" + manana + """'>
        </div>
        <div class="campo">
            <label>Hora</label>
            <input type="time" name="hora" required step="900" value="10:00">
        </div>
        <button class="boton">Añadir hora libre</button>
    </form>
"""

    if not horas:
        cadena += '    <p class="vacio" style="display:block">Todavía no tienes horas libres en tu agenda.</p>\n'

    for h in horas:
        if h[2]:
            estado = '<span class="insignia si">Reservada por ' + escape(h[2]) + '</span>'
            accion = ""
        else:
            estado = '<span class="insignia no">Libre</span>'
            accion = f"""
            <form method="post" action="/agenda/{h[0]}/eliminar">
                <button class="boton-mini rojo">Quitar</button>
            </form>"""
        cadena += f"""
    <div class="fila-horario">
        <div><strong>{fecha_bonita(h[1])}</strong> &nbsp; {estado}</div>
        {accion}
    </div>
"""

    cadena += """
</main>
""" + pie()

    return cadena


# Quitar una hora libre (solo si es mía y nadie la ha reservado)
@aplicacion.route("/agenda/<int:id_horario>/eliminar", methods=["POST"])
def agenda_eliminar(id_horario):

    yo = usuario()
    if yo is None or yo["tipo"] != "psicologo":
        return redirect("/entrar?tipo=psicologo")

    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "DELETE FROM horarios WHERE id = %s AND psicologo_id = %s AND solicitud_id IS NULL",
        (id_horario, yo["id"])
    )
    conexion.commit()
    cursor.close()
    conexion.close()

    return redirect("/agenda?borrada=1")


# -------------------------------------------------
# POLÍTICA DE PRIVACIDAD
# -------------------------------------------------

@aplicacion.route("/privacidad")
def privacidad():
    return cabecera("Política de privacidad — Encuéntrame") + """

<main class="contenedor legal">

    <h2>Política de privacidad</h2>
    <p><strong>Encuéntrame es un proyecto de estudio</strong> del ciclo de Desarrollo de Aplicaciones Multiplataforma (DAM).
    Los perfiles de psicólogos son ficticios. Por favor, <strong>no escribas datos de salud reales</strong> ni información sensible.</p>

    <h3>¿Quién es el responsable?</h3>
    <p>Heverton Marques, estudiante de DAM, como autor del proyecto. Contacto: <a href="mailto:encuentrame.psi@gmail.com">encuentrame.psi@gmail.com</a>
    o el <a href="/contacto">formulario de contacto</a>.</p>

    <h3>¿Qué datos guardamos?</h3>
    <ul>
        <li><strong>Pacientes:</strong> nombre, correo, contraseña (solo cifrada, nunca en texto), las solicitudes que envías (con el teléfono si lo escribes), tus valoraciones y la fecha en que aceptaste esta política.</li>
        <li><strong>Psicólogos:</strong> nombre, correo, teléfono, número de colegiado, especialidades, presentación, foto, horas de la agenda y la fecha en que aceptaste esta política.</li>
        <li><strong>Formulario de contacto:</strong> nombre, correo y mensaje.</li>
    </ul>

    <h3>¿Para qué?</h3>
    <p>Solo para que la web funcione: poner en contacto a pacientes y psicólogos, gestionar las citas y las valoraciones, y responder a los mensajes de contacto.
    No vendemos ni cedemos los datos y no hay publicidad.</p>

    <h3>¿Con qué base legal?</h3>
    <p>Tu consentimiento, que das al crear la cuenta o al enviar el formulario de contacto. Puedes retirarlo en cualquier momento eliminando tu cuenta.</p>

    <h3>¿Quién más trata los datos?</h3>
    <ul>
        <li><strong>PythonAnywhere</strong> (Anaconda Inc.): servidor donde está alojada la web y la base de datos.</li>
        <li><strong>Brevo</strong>: envío de los correos automáticos (avisos y recuperación de contraseña). Los correos no incluyen el texto de tus solicitudes.</li>
    </ul>

    <h3>¿Cuánto tiempo?</h3>
    <p>Mientras tengas la cuenta. Si la eliminas, se borran tus datos, tus solicitudes y tus valoraciones. Las copias de seguridad se renuevan y se borran en unos 14 días.</p>

    <h3>Tus derechos</h3>
    <ul>
        <li><strong>Acceso y portabilidad:</strong> descarga todos tus datos desde «Descargar mis datos» (en Mis solicitudes o en Mi perfil).</li>
        <li><strong>Rectificación:</strong> los psicólogos pueden editar su perfil; para otros cambios, escríbenos.</li>
        <li><strong>Supresión:</strong> elimina tu cuenta desde la propia web en cualquier momento.</li>
        <li>Puedes reclamar ante la <a href="https://www.aepd.es" target="_blank" rel="noopener">Agencia Española de Protección de Datos</a>.</li>
    </ul>

    <h3>Cookies</h3>
    <p>Solo usamos una cookie técnica, necesaria para mantener tu sesión iniciada y proteger los formularios. No usamos cookies de publicidad ni de análisis.</p>

    <h3>Seguridad</h3>
    <p>La web funciona siempre con HTTPS, las contraseñas se guardan cifradas y cada usuario solo puede ver sus propios datos.</p>

    <p style="margin-top:30px;font-size:13px">Última actualización: octubre de 2026.</p>

</main>
""" + pie()


# -------------------------------------------------
# DESCARGAR MIS DATOS (derecho de acceso y portabilidad)
# -------------------------------------------------

# Paso una fila de la base de datos a un diccionario que se pueda guardar en JSON
def fila_a_dict(columnas, fila):
    datos = {}
    for nombre, valor in zip(columnas, fila):
        datos[nombre] = valor.isoformat(" ") if isinstance(valor, datetime) else valor
    return datos


@aplicacion.route("/mis-datos")
def mis_datos():

    yo = usuario()
    if yo is None or yo["tipo"] not in ("paciente", "psicologo"):
        return redirect("/entrar")

    conexion = conectar()
    cursor = conexion.cursor()

    def consulta(columnas, sql, parametros):
        cursor.execute(sql, parametros)
        return [fila_a_dict(columnas, fila) for fila in cursor.fetchall()]

    # Nunca incluyo el hash de la contraseña
    if yo["tipo"] == "paciente":
        cuenta = consulta(["nombre", "email", "telefono", "fecha_registro", "fecha_consentimiento"],
                          "SELECT nombre, email, telefono, fecha_registro, fecha_consentimiento FROM pacientes WHERE id = %s", (yo["id"],))
        datos = {
            "tipo_de_cuenta": "paciente",
            "cuenta": cuenta[0] if cuenta else {},
            "solicitudes": consulta(
                ["psicologo", "nombre", "email", "telefono", "resumen", "contacto", "estado", "fecha", "cita"],
                """SELECT p.nombre, s.nombre_paciente, s.email_paciente, s.telefono, s.resumen, s.contacto, s.estado, s.fecha, h.fecha_hora
                   FROM solicitudes s JOIN psicologos p ON p.id = s.psicologo_id
                   LEFT JOIN horarios h ON h.solicitud_id = s.id
                   WHERE s.paciente_id = %s ORDER BY s.fecha""", (yo["id"],)),
            "valoraciones": consulta(
                ["psicologo", "estrellas", "comentario", "fecha"],
                """SELECT p.nombre, v.estrellas, v.comentario, v.fecha
                   FROM valoraciones v JOIN psicologos p ON p.id = v.psicologo_id
                   WHERE v.paciente_id = %s ORDER BY v.fecha""", (yo["id"],))
        }
    else:
        cuenta = consulta(["nombre", "email", "numero_colegiado", "telefono", "especialidades", "bio", "foto", "aprobado", "fecha_registro", "fecha_consentimiento"],
                          """SELECT nombre, email, numero_colegiado, telefono, especialidades, bio, foto, aprobado, fecha_registro, fecha_consentimiento
                             FROM psicologos WHERE id = %s""", (yo["id"],))
        datos = {
            "tipo_de_cuenta": "psicologo",
            "cuenta": cuenta[0] if cuenta else {},
            "agenda": consulta(["fecha_hora", "reservada"],
                               "SELECT fecha_hora, solicitud_id IS NOT NULL FROM horarios WHERE psicologo_id = %s ORDER BY fecha_hora", (yo["id"],)),
            "solicitudes_recibidas": consulta(
                ["paciente", "email", "telefono", "resumen", "contacto", "estado", "fecha"],
                """SELECT nombre_paciente, email_paciente, telefono, resumen, contacto, estado, fecha
                   FROM solicitudes WHERE psicologo_id = %s ORDER BY fecha""", (yo["id"],)),
            "valoraciones_recibidas": consulta(["estrellas", "comentario", "fecha"],
                                               "SELECT estrellas, comentario, fecha FROM valoraciones WHERE psicologo_id = %s ORDER BY fecha", (yo["id"],))
        }

    cursor.close()
    conexion.close()

    datos["descargado"] = ahora().isoformat(" ")
    respuesta = aplicacion.response_class(
        json.dumps(datos, ensure_ascii=False, indent=2, default=str),
        mimetype="application/json"
    )
    respuesta.headers["Content-Disposition"] = "attachment; filename=mis-datos-encuentrame.json"
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


# Ejecuto la aplicación
if __name__ == "__main__":

    aplicacion.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
