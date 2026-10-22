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

    def close(self):
        self.conexion.close()


# Abro una conexión nueva en cada petición (así no se cae si MySQL la cierra)
def conectar():
    if RUTA_SQLITE:
        return ConexionSQLite(RUTA_SQLITE)
    return mysql.connector.connect(**DATOS_BD)


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


# Y le digo al navegador que use siempre https en esta web
@aplicacion.after_request
def cabeceras_seguridad(respuesta):
    if EN_SERVIDOR:
        respuesta.headers["Strict-Transport-Security"] = "max-age=31536000"
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
        grid-template-columns:repeat(4,1fr);
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
            <a href="/#buscar">Buscar psicólogo</a>
            <a href="/panel">Soy psicólogo/a</a>
            <a href="/entrar">Entrar</a>"""
    elif yo["tipo"] == "admin":
        menu = """
            <a href="/">Ver la web</a>
            <a href="/admin">Administración</a>
            <a href="/salir">Salir</a>"""
    elif yo["tipo"] == "psicologo":
        menu = """
            <a href="/panel">Mi panel</a>
            <a href="/perfil">Mi perfil</a>
            <a href="/salir">Salir</a>"""
    else:
        menu = """
            <a href="/#buscar">Buscar psicólogo</a>
            <a href="/mis-solicitudes">Mis solicitudes</a>
            <a href="/salir">Salir (""" + escape(yo["nombre"].split()[0]) + """)</a>"""

    return """
<!doctype html>
<html lang="es">
<head>

    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>""" + titulo + """</title>

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
    © 2026 Encuéntrame · Proyecto de estudio DAM · Los perfiles son ficticios
</footer>

</body>
</html>
"""


# -------------------------------------------------
# PÁGINA PRINCIPAL
# -------------------------------------------------

@aplicacion.route("/")
def inicio():

    # Pido los psicólogos a la base de datos
    conexion = conectar()
    cursor = conexion.cursor()
    # Solo muestro los psicólogos que ha aprobado un administrador
    cursor.execute("SELECT id, nombre, especialidades, bio, foto, numero_colegiado FROM psicologos WHERE aprobado = 1 ORDER BY nombre")
    filas = cursor.fetchall()
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
    if request.args.get("eliminado"):
        aviso = '<div class="aviso">✓ Tu cuenta se ha eliminado. Gracias por usar Encuéntrame.</div>'

    # Si un paciente ha iniciado sesión, relleno su nombre y correo en el formulario
    nombre_paciente = ""
    email_paciente = ""
    yo = usuario()
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

                <p class="bio">
                    {bio}
                </p>

                <button
                    class="boton boton-pequeno"
                    data-id="{id_psicologo}"
                    data-nombre-mostrar="{nombre}"
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
    cursor.execute("SELECT nombre FROM psicologos WHERE id = %s AND aprobado = 1", (psicologo_id,))
    psicologo = cursor.fetchone()

    if psicologo is None:
        cursor.close()
        conexion.close()
        return redirect("/#buscar")

    # Si el paciente ha iniciado sesión, enlazo la solicitud con su cuenta
    yo = usuario()
    paciente_id = yo["id"] if yo and yo["tipo"] == "paciente" else None

    # Guardo la solicitud (con %s para evitar inyección SQL)
    cursor.execute(
        "INSERT INTO solicitudes (psicologo_id, paciente_id, nombre_paciente, email_paciente, telefono, resumen, contacto) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (psicologo_id, paciente_id, nombre, email, telefono, resumen, contacto)
    )
    conexion.commit()

    cursor.close()
    conexion.close()

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
        SELECT id, nombre_paciente, email_paciente, telefono, resumen, contacto, estado, fecha
        FROM solicitudes
        WHERE psicologo_id = %s
        ORDER BY fecha DESC
    """, (yo["id"],))
    solicitudes = cursor.fetchall()

    cursor.close()
    conexion.close()


    cadena = cabecera("Panel del psicólogo — Encuéntrame") + """

<main class="contenedor">

    <div class="titulo-seccion">
        <div>
            <h2>Hola, """ + escape(yo["nombre"]) + """</h2>
            <p>Estas son las solicitudes que te han enviado.</p>
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
        "UPDATE solicitudes SET estado = 'contactado' WHERE id = %s AND psicologo_id = %s",
        (id_solicitud, yo["id"])
    )
    conexion.commit()
    cursor.close()
    conexion.close()

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
                <input type="password" name="password" required""" + (' minlength="6"' if es_registro else "") + """>
                """ + ('<div class="pista">Mínimo 6 caracteres.</div>' if es_registro else "") + """
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

    cadena += """
            <button class="boton" style="width:100%">""" + ("Crear cuenta" if es_registro else "Entrar") + """</button>

        </form>
"""

    if tipo == "admin":
        pass
    elif es_registro:
        cadena += '        <p class="cambiar">¿Ya tienes cuenta? <a href="/entrar?tipo=' + tipo + '">Entrar</a></p>\n'
    else:
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


@aplicacion.route("/entrar", methods=["GET", "POST"])
def entrar():

    tipo = tipo_elegido(permitir_admin=True)

    if request.method == "GET":
        return pagina_acceso("entrar", tipo)

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

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
        return pagina_acceso("entrar", tipo, "Correo o contraseña incorrectos.")

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

    if len(password) < 6:
        return pagina_acceso("registro", tipo, "La contraseña debe tener al menos 6 caracteres.")

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
            "INSERT INTO pacientes (nombre, email, password_hash) VALUES (%s, %s, %s)",
            (nombre, email, password_hash)
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
            "INSERT INTO psicologos (nombre, email, numero_colegiado, password_hash, telefono, especialidades, bio) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (nombre, email, numero_colegiado, password_hash, telefono, texto_especialidades, bio)
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
        SELECT s.resumen, s.contacto, s.estado, s.fecha, p.nombre, p.foto
        FROM solicitudes s
        JOIN psicologos p ON p.id = s.psicologo_id
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

    if not solicitudes:
        cadena += """
    <p class="vacio" style="display:block">
        Aún no has enviado ninguna solicitud.<br><br>
        <a class="boton" href="/#buscar">Buscar psicólogo</a>
    </p>
"""

    for s in solicitudes:

        contactado = s[2] == "contactado"

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

    </div>
"""

    cadena += """
    <p class="cambiar"><a class="enlace-peligro" href="/eliminar-cuenta">Eliminar mi cuenta</a></p>

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

        <p class="cambiar"><a class="enlace-peligro" href="/eliminar-cuenta">Eliminar mi cuenta</a></p>

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
            (SELECT COUNT(*) FROM solicitudes WHERE estado = 'pendiente')
    """)
    cifras = cursor.fetchone()

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

    cadena += """
</main>
""" + pie()

    return cadena


# Aprobar u ocultar un psicólogo (cambia de 0 a 1 o de 1 a 0)
@aplicacion.route("/admin/psicologo/<int:id_psicologo>/aprobar", methods=["POST"])
def admin_aprobar(id_psicologo):

    if not es_admin():
        return redirect("/entrar?tipo=admin")

    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("UPDATE psicologos SET aprobado = 1 - aprobado WHERE id = %s", (id_psicologo,))
    cursor.execute("SELECT nombre, aprobado FROM psicologos WHERE id = %s", (id_psicologo,))
    fila = cursor.fetchone()
    conexion.commit()
    cursor.close()
    conexion.close()

    if fila is None:
        return redirect("/admin")

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


# Ejecuto la aplicación
if __name__ == "__main__":

    aplicacion.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
