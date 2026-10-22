/* Creo la base de datos y el usuario */
CREATE DATABASE IF NOT EXISTS encuentrame
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'encuentrame'@'localhost' IDENTIFIED BY 'Encuentrame123$';
GRANT ALL PRIVILEGES ON encuentrame.* TO 'encuentrame'@'localhost';
FLUSH PRIVILEGES;

USE encuentrame;


/* Tabla de psicólogos */
CREATE TABLE IF NOT EXISTS psicologos (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    telefono        VARCHAR(30),
    especialidades  VARCHAR(255),          /* separadas por comas */
    bio             TEXT
);


/* Tabla de solicitudes que envían los pacientes */
CREATE TABLE IF NOT EXISTS solicitudes (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    psicologo_id     INT NOT NULL,
    nombre_paciente  VARCHAR(100) NOT NULL,
    email_paciente   VARCHAR(150) NOT NULL,
    telefono         VARCHAR(30),
    resumen          TEXT NOT NULL,
    contacto         ENUM('email','telefono') DEFAULT 'email',
    estado           ENUM('pendiente','contactado') DEFAULT 'pendiente',
    fecha            DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (psicologo_id) REFERENCES psicologos(id) ON DELETE CASCADE
);


/* Datos de ejemplo (perfiles ficticios) */
INSERT INTO psicologos (nombre, email, telefono, especialidades, bio) VALUES
('Marta Ibáñez', 'marta.ibanez@ejemplo.com', '+34 611 222 333', 'Duelo,Depresión,Trauma',
 'Trabajo desde un enfoque cercano y sin prisas, acompañando procesos de pérdida y duelo. Más de diez años ayudando a personas a atravesar momentos difíciles.'),
('Diego Fonseca', 'diego.fonseca@ejemplo.com', '+34 622 333 444', 'Ansiedad,Estrés y burnout,Trastornos del sueño',
 'Especializado en ansiedad y estrés laboral. Utilizo herramientas prácticas para que notes cambios desde las primeras sesiones.'),
('Laura Campos', 'laura.campos@ejemplo.com', '+34 633 444 555', 'Terapia de pareja,Autoestima',
 'Acompaño a parejas e individuos a mejorar su comunicación y su relación consigo mismos, en un espacio sin juicios.'),
('Marta Sánchez', 'marta.sanchez@ejemplo.com', '+34 644 555 666', 'Trastornos alimentarios,Autoestima',
 'Trabajo con un enfoque integrador para trastornos de la conducta alimentaria y la imagen corporal, desde la autocompasión.'),
('Javier Romero', 'javier.romero@ejemplo.com', '+34 655 666 777', 'Adicciones,Control de impulsos',
 'Especialista en adicciones y control de impulsos, con un enfoque práctico y sin juicios.'),
('Elena Vidal', 'elena.vidal@ejemplo.com', '+34 666 777 888', 'Ansiedad,Fobias,Ataques de pánico',
 'Uso técnicas de exposición gradual y respiración para reducir crisis de ansiedad y fobias.'),
('Rubén Castillo', 'ruben.castillo@ejemplo.com', '+34 677 888 999', 'Terapia infantil,TDAH',
 'Trabajo con niños y adolescentes en problemas de conducta y TDAH junto con sus familias.'),
('Sofía Navarro', 'sofia.navarro@ejemplo.com', '+34 688 999 000', 'Trastornos del sueño,Ansiedad',
 'Combino técnicas de higiene del sueño y manejo del estrés para mejorar el descanso.'),
('Pablo Herrera', 'pablo.herrera@ejemplo.com', '+34 699 000 111', 'Trauma,Duelo',
 'Especializado en trauma y EMDR, acompañando procesos de recuperación a tu propio ritmo.'),
('Isabel Domínguez', 'isabel.dominguez@ejemplo.com', '+34 610 111 222', 'Autoestima,Ansiedad social',
 'Ayudo a construir una autoestima sólida y a superar la ansiedad en las relaciones sociales.'),
('Andrés Molina', 'andres.molina@ejemplo.com', '+34 621 222 333', 'Estrés y burnout',
 'Trabajo con profesionales que sienten agotamiento y quieren recuperar el equilibrio.'),
('Cristina Ortega', 'cristina.ortega@ejemplo.com', '+34 632 333 444', 'Depresión,Duelo',
 'Acompaño con empatía procesos de tristeza profunda y pérdida hacia una vida con sentido.'),
('Miguel Ángel Torres', 'miguelangel.torres@ejemplo.com', '+34 643 444 555', 'Terapia de pareja,Sexualidad',
 'Especialista en terapia de pareja y sexualidad, con un enfoque respetuoso y directo.'),
('Paula Cabrera', 'paula.cabrera@ejemplo.com', '+34 654 555 666', 'Ansiedad,TOC',
 'Trabajo con TOC y ansiedad usando terapia cognitivo-conductual basada en evidencia.'),
('Natalia Reyes', 'natalia.reyes@ejemplo.com', '+34 676 777 888', 'Terapia infantil,Ansiedad',
 'Especialista en psicología infantil, ayudo a niños a gestionar sus emociones de forma sana.'),
('Beatriz Serrano', 'beatriz.serrano@ejemplo.com', '+34 698 999 000', 'Duelo,Acompañamiento en enfermedad',
 'Ofrezco un espacio seguro para procesar pérdidas y enfermedades con calma y respeto.');
