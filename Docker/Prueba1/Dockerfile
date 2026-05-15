# Etapa 1: construcción
FROM python:3.14 AS builder
# Usamos la imagen completa de Python (con todas las herramientas de compilación)
# AS builder le da nombre a esta etapa para referenciarla después

WORKDIR /app
# Creamos y establecemos /app como directorio de trabajo

COPY requirements.txt .
# Copiamos solo el archivo de dependencias (antes que el código, para aprovechar la caché)

RUN pip install --prefix=/install -r requirements.txt
# Instalamos las dependencias en la carpeta /install en lugar del sistema
# Así podemos copiarlas limpiamente a la siguiente etapa


# Etapa 2: imagen final
FROM python:3.14-slim
# Partimos de la imagen ligera de Python, sin herramientas de compilación

RUN groupadd -r appuser && useradd -r -g appuser appuser
# Creamos un grupo llamado appuser (-r significa que es un grupo del sistema)
# Y creamos un usuario llamado appuser dentro de ese grupo
# Este usuario no tiene contraseña ni directorio home, solo puede ejecutar la app

WORKDIR /app
# Establecemos /app como directorio de trabajo en esta etapa también

COPY --from=builder /install /usr/local
# Copiamos las dependencias instaladas en la etapa builder al sistema de esta imagen

COPY . .
# Copiamos el código de la aplicación al contenedor

RUN chown -R appuser:appuser /app
# Damos al usuario appuser la propiedad de toda la carpeta /app
# Sin esto, appuser no podría leer ni ejecutar los archivos

USER appuser
# A partir de aquí todo se ejecuta como appuser, no como root

EXPOSE 5000
# Documentamos que la app usa el puerto 5000

CMD ["python", "app.py"]
# Comando que se ejecuta al arrancar el contenedor, ahora como appuser