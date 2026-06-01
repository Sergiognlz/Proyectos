# Importa la librería 'requests' que permite hacer llamadas HTTP a la API de NetBox
import requests

# Lee el token de API del fichero token.txt y elimina espacios o saltos de línea al final
TOKEN = open('token.txt').read().strip()

# Define las cabeceras que se enviarán en cada petición HTTP:
# - Authorization: identifica quién hace la petición (el token actúa como contraseña)
# - Accept: indica que queremos recibir la respuesta en formato JSON
H = {'Authorization': f'Token {TOKEN}', 'Accept': 'application/json'}

# Lista de categorías de objetos de NetBox que queremos borrar, en orden
# (el orden importa: hay que borrar las VMs antes que los clusters, por ejemplo)
endpoints = [
    'virtualization/virtual-machines/',  # Máquinas virtuales (los registros migrados)
    'virtualization/clusters/',           # Clusters (Sandetel-Servicios, Sandetel-Aplicaciones)
    'virtualization/cluster-types/',      # Tipos de cluster (Sandetel)
    'dcim/platforms/',                    # Sistemas operativos
    'tenancy/tenants/',                   # Encargos/propietarios (SDT_ALM, SDT_TI, etc.)
    'dcim/sites/',                        # Entornos (PRODUCCION, DESARROLLO, PREPRODUCCION)
    'extras/tags/',                       # Etiquetas (servicio-ti, aplicacion)
    'extras/custom-fields/',              # Campos personalizados creados para la migración
]

# Recorre cada categoría de la lista anterior
for endpoint in endpoints:

    # Hace una petición GET para obtener todos los objetos de esa categoría
    # limit=500 indica que queremos hasta 500 resultados de una vez
    r = requests.get(f'http://localhost:8000/api/{endpoint}?limit=500', headers=H)

    # Extrae la lista de objetos del JSON de respuesta
    # .get('results', []) devuelve [] si no existe el campo 'results', evitando errores
    objetos = r.json().get('results', [])

    # Recorre cada objeto obtenido y lo borra uno a uno usando su ID único
    for obj in objetos:
        requests.delete(f'http://localhost:8000/api/{endpoint}{obj["id"]}/', headers=H)

    # Muestra por pantalla cuántos objetos se han borrado de esta categoría
    print(f'Limpiado: {endpoint} ({len(objetos)} objetos)')