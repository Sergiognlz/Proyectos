from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@db:5432/mensajes"
)

db = SQLAlchemy(app)

class Mensaje(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.String(200), nullable=False)

@app.route("/")
def inicio():
    return jsonify({"mensaje": "Hola desde Docker"})

@app.route("/mensajes", methods=["GET"])
def get_mensajes():
    mensajes = Mensaje.query.all()
    return jsonify([{"id": m.id, "texto": m.texto} for m in mensajes])

@app.route("/mensajes", methods=["POST"])
def crear_mensaje():
    datos = request.get_json()
    nuevo = Mensaje(texto=datos["texto"])
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({"id": nuevo.id, "texto": nuevo.texto}), 201

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000)