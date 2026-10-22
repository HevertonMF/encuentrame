/* Base de datos de Encuéntrame para PythonAnywhere (MySQL 8)
   - Ejecútalo en la consola MySQL de PythonAnywhere, dentro de tu base de datos
   - Crea las tablas y mete los psicólogos de ejemplo (sin contraseña: nadie puede entrar con sus cuentas)
   - El administrador se crea aparte con crear_admin.py (así su contraseña no está en el código) */

CREATE TABLE psicologos (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    nombre            VARCHAR(100) NOT NULL,
    email             VARCHAR(150) NOT NULL UNIQUE,
    numero_colegiado  VARCHAR(30) NULL UNIQUE,
    telefono          VARCHAR(30),
    especialidades    VARCHAR(255),
    bio               TEXT,
    password_hash     VARCHAR(255) NULL,
    foto              VARCHAR(255) NULL,
    fecha_registro    DATETIME DEFAULT CURRENT_TIMESTAMP,
    aprobado          TINYINT(1) NOT NULL DEFAULT 0
) CHARACTER SET utf8mb4;

CREATE TABLE pacientes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    telefono        VARCHAR(30),
    fecha_registro  DATETIME DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4;

CREATE TABLE especialidades (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    nombre  VARCHAR(60) NOT NULL UNIQUE
) CHARACTER SET utf8mb4;

CREATE TABLE psicologo_especialidad (
    psicologo_id     INT NOT NULL,
    especialidad_id  INT NOT NULL,
    PRIMARY KEY (psicologo_id, especialidad_id),
    FOREIGN KEY (psicologo_id)    REFERENCES psicologos(id)     ON DELETE CASCADE,
    FOREIGN KEY (especialidad_id) REFERENCES especialidades(id) ON DELETE CASCADE
) CHARACTER SET utf8mb4;

CREATE TABLE solicitudes (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    psicologo_id     INT NOT NULL,
    paciente_id      INT NULL,
    nombre_paciente  VARCHAR(100) NOT NULL,
    email_paciente   VARCHAR(150) NOT NULL,
    telefono         VARCHAR(30),
    resumen          TEXT NOT NULL,
    contacto         ENUM('email','telefono') DEFAULT 'email',
    estado           ENUM('pendiente','contactado') DEFAULT 'pendiente',
    fecha            DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (psicologo_id) REFERENCES psicologos(id) ON DELETE CASCADE,
    FOREIGN KEY (paciente_id)  REFERENCES pacientes(id)  ON DELETE SET NULL
) CHARACTER SET utf8mb4;

CREATE TABLE administradores (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL
) CHARACTER SET utf8mb4;


INSERT INTO especialidades (id, nombre) VALUES
(1, 'Acompañamiento en enfermedad'),
(2, 'Adicciones'),
(3, 'Ansiedad'),
(4, 'Ansiedad social'),
(5, 'Ataques de pánico'),
(6, 'Autoestima'),
(7, 'Control de impulsos'),
(8, 'Depresión'),
(9, 'Duelo'),
(10, 'Estrés y burnout'),
(11, 'Fobias'),
(12, 'Sexualidad'),
(13, 'TDAH'),
(14, 'TOC'),
(15, 'Terapia de pareja'),
(16, 'Terapia infantil'),
(17, 'Trastornos alimentarios'),
(18, 'Trastornos del sueño'),
(19, 'Trauma');

INSERT INTO psicologos (id, nombre, email, numero_colegiado, telefono, especialidades, bio, password_hash, aprobado) VALUES
(1, 'Marta Ibáñez', 'marta.ibanez@ejemplo.com', 'CV-PSI-1001', '+34 611 222 333', 'Depresión,Duelo,Trauma', 'Trabajo desde un enfoque cercano y sin prisas, acompañando procesos de pérdida y duelo. Más de diez años ayudando a personas a atravesar momentos difíciles.', NULL, 1),
(2, 'Diego Fonseca', 'diego.fonseca@ejemplo.com', 'CV-PSI-1002', '+34 622 333 444', 'Ansiedad,Estrés y burnout,Trastornos del sueño', 'Especializado en ansiedad y estrés laboral. Utilizo herramientas prácticas para que notes cambios desde las primeras sesiones.', NULL, 1),
(3, 'Laura Campos', 'laura.campos@ejemplo.com', 'CV-PSI-1003', '+34 633 444 555', 'Terapia de pareja,Autoestima', 'Acompaño a parejas e individuos a mejorar su comunicación y su relación consigo mismos, en un espacio sin juicios.', NULL, 1),
(4, 'Marta Sánchez', 'marta.sanchez@ejemplo.com', 'CV-PSI-1004', '+34 644 555 666', 'Trastornos alimentarios,Autoestima', 'Trabajo con un enfoque integrador para trastornos de la conducta alimentaria y la imagen corporal, desde la autocompasión.', NULL, 1),
(5, 'Javier Romero', 'javier.romero@ejemplo.com', 'CV-PSI-1005', '+34 655 666 777', 'Adicciones,Control de impulsos', 'Especialista en adicciones y control de impulsos, con un enfoque práctico y sin juicios.', NULL, 1),
(6, 'Elena Vidal', 'elena.vidal@ejemplo.com', 'CV-PSI-1006', '+34 666 777 888', 'Ansiedad,Fobias,Ataques de pánico', 'Uso técnicas de exposición gradual y respiración para reducir crisis de ansiedad y fobias.', NULL, 1),
(7, 'Rubén Castillo', 'ruben.castillo@ejemplo.com', 'CV-PSI-1007', '+34 677 888 999', 'Terapia infantil,TDAH', 'Trabajo con niños y adolescentes en problemas de conducta y TDAH junto con sus familias.', NULL, 1),
(8, 'Sofía Navarro', 'sofia.navarro@ejemplo.com', 'CV-PSI-1008', '+34 688 999 000', 'Trastornos del sueño,Ansiedad', 'Combino técnicas de higiene del sueño y manejo del estrés para mejorar el descanso.', NULL, 1),
(9, 'Pablo Herrera', 'pablo.herrera@ejemplo.com', 'CV-PSI-1009', '+34 699 000 111', 'Trauma,Duelo', 'Especializado en trauma y EMDR, acompañando procesos de recuperación a tu propio ritmo.', NULL, 1),
(10, 'Isabel Domínguez', 'isabel.dominguez@ejemplo.com', 'CV-PSI-1010', '+34 610 111 222', 'Autoestima,Ansiedad social', 'Ayudo a construir una autoestima sólida y a superar la ansiedad en las relaciones sociales.', NULL, 1),
(11, 'Andrés Molina', 'andres.molina@ejemplo.com', 'CV-PSI-1011', '+34 621 222 333', 'Estrés y burnout', 'Trabajo con profesionales que sienten agotamiento y quieren recuperar el equilibrio.', NULL, 1),
(12, 'Cristina Ortega', 'cristina.ortega@ejemplo.com', 'CV-PSI-1012', '+34 632 333 444', 'Depresión,Duelo', 'Acompaño con empatía procesos de tristeza profunda y pérdida hacia una vida con sentido.', NULL, 1),
(13, 'Miguel Ángel Torres', 'miguelangel.torres@ejemplo.com', 'CV-PSI-1013', '+34 643 444 555', 'Terapia de pareja,Sexualidad', 'Especialista en terapia de pareja y sexualidad, con un enfoque respetuoso y directo.', NULL, 1),
(14, 'Paula Cabrera', 'paula.cabrera@ejemplo.com', 'CV-PSI-1014', '+34 654 555 666', 'Ansiedad,TOC', 'Trabajo con TOC y ansiedad usando terapia cognitivo-conductual basada en evidencia.', NULL, 1),
(15, 'Natalia Reyes', 'natalia.reyes@ejemplo.com', 'CV-PSI-1015', '+34 676 777 888', 'Terapia infantil,Ansiedad', 'Especialista en psicología infantil, ayudo a niños a gestionar sus emociones de forma sana.', NULL, 1),
(16, 'Beatriz Serrano', 'beatriz.serrano@ejemplo.com', 'CV-PSI-1016', '+34 698 999 000', 'Duelo,Acompañamiento en enfermedad', 'Ofrezco un espacio seguro para procesar pérdidas y enfermedades con calma y respeto.', NULL, 1);

INSERT INTO psicologo_especialidad (psicologo_id, especialidad_id) VALUES
(1, 8),
(1, 9),
(1, 19),
(2, 3),
(2, 10),
(2, 18),
(3, 6),
(3, 15),
(4, 6),
(4, 17),
(5, 2),
(5, 7),
(6, 3),
(6, 5),
(6, 11),
(7, 13),
(7, 16),
(8, 3),
(8, 18),
(9, 9),
(9, 19),
(10, 4),
(10, 6),
(11, 10),
(12, 8),
(12, 9),
(13, 12),
(13, 15),
(14, 3),
(14, 14),
(15, 3),
(15, 16),
(16, 1),
(16, 9);
