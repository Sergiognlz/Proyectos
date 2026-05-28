import requests

TOKEN = open('token.txt').read().strip()
H = {'Authorization': f'Token {TOKEN}', 'Accept': 'application/json'}

endpoints = [
    'virtualization/virtual-machines/',
    'virtualization/clusters/',
    'virtualization/cluster-types/',
    'dcim/platforms/',
    'tenancy/tenants/',
    'dcim/sites/',
    'extras/tags/',
    'extras/custom-fields/',
]

for endpoint in endpoints:
    r = requests.get(f'http://localhost:8000/api/{endpoint}?limit=500', headers=H)
    objetos = r.json().get('results', [])
    for obj in objetos:
        requests.delete(f'http://localhost:8000/api/{endpoint}{obj["id"]}/', headers=H)
    print(f'Limpiado: {endpoint} ({len(objetos)} objetos)')