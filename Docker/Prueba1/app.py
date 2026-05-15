# Importamos Flask y las funciones para manejar peticiones y respuestas JSON
from flask import Flask, jsonify, request

# Importamos SQLAlchemy, que es el ORM para interactuar con la base de datos
from flask_sqlalchemy import SQLAlchemy

# Importamos os para leer variables de entorno del sistema
import os

# Creamos la aplicación Flask
app = Flask(__name__)

# Configuramos la cadena de conexión a la base de datos
# os.getenv lee la variable DATABASE_URL del .env
# Si no existe, usa el segundo valor como fallback (solo para desarrollo local)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@db:5432/mensajes"
)

# Inicializamos SQLAlchemy con nuestra app
# A partir de aquí usamos db para interactuar con la base de datos
db = SQLAlchemy(app)

# Definimos el modelo Mensaje, que representa una tabla en la base de datos
class Mensaje(db.Model):
    # Columna id: número entero, clave primaria, se autoincrementa
    id = db.Column(db.Integer, primary_key=True)
    # Columna texto: cadena de hasta 200 caracteres, no puede estar vacía
    texto = db.Column(db.String(200), nullable=False)

# Ruta raíz GET — devuelve un saludo básico para comprobar que la API funciona
@app.route("/")
def inicio():
    return jsonify({"mensaje": "Hola desde Docker"})

# Ruta GET /mensajes — devuelve todos los mensajes guardados en la base de datos
@app.route("/mensajes", methods=["GET"])
def get_mensajes():
    # Consulta todos los registros de la tabla Mensaje
    mensajes = Mensaje.query.all()
    # Devuelve la lista como JSON, convirtiendo cada objeto a diccionario
    return jsonify([{"id": m.id, "texto": m.texto} for m in mensajes])

# Ruta POST /mensajes — crea un nuevo mensaje en la base de datos
@app.route("/mensajes", methods=["POST"])
def crear_mensaje():
    # Leemos el JSON que viene en el cuerpo de la petición
    datos = request.get_json()
    # Creamos un nuevo objeto Mensaje con el texto recibido
    nuevo = Mensaje(texto=datos["texto"])
    # Añadimos el objeto a la sesión (preparamos la operación)
    db.session.add(nuevo)
    # Confirmamos la operación y guardamos en la base de datos
    db.session.commit()
    # Devolvemos el mensaje creado con código 201 (Created)
    return jsonify({"id": nuevo.id, "texto": nuevo.texto}), 201

# Punto de entrada cuando se ejecuta el archivo directamente
if __name__ == "__main__":
    # Creamos las tablas en la base de datos si no existen
    with app.app_context():
        db.create_all()
    # Arrancamos el servidor en todas las interfaces (0.0.0.0) y puerto 5000
    # 0.0.0.0 es necesario para que sea accesible desde fuera del contenedor
    app.run(host="0.0.0.0", port=5000)