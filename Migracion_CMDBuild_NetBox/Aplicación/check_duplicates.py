import requests

TOKEN = open('token.txt').read().strip()
H = {'Authorization': f'Token {TOKEN}', 'Accept': 'application/json'}

nombres = ['DESSANCRM01','DESSANHVA01','DPSALMSAN02','DPSALMSAN03','DPSSANDIN01','DPSSANVDI01','SANCRM01']

for nombre in nombres:
    r = requests.get('http://localhost:8000/api/virtualization/virtual-machines/', headers=H, params={'name': nombre})
    vms = r.json()['results']
    print(f'\n{nombre} ({len(vms)} registros):')
    for vm in vms:
        site = vm['site']['name'] if vm['site'] else 'Sin site'
        tenant = vm['tenant']['name'] if vm['tenant'] else 'Sin tenant'
        print(f'  id={vm["id"]} | site={site} | tenant={tenant}')