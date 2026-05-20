"""
fix_tags.py — Asigna tags correctos a las VMs que les faltan
Sandetel / Junta de Andalucía

Uso:
    python fix_tags.py

Lee los CSV originales y asigna el tag correcto a cada VM en NetBox
según si viene de aplicaciones.csv o servicios_ti.csv.
"""

import requests
import pandas as pd
import logging
import os
import re

# ─── Configuración ────────────────────────────────────────────────────────────
NETBOX_URL = "http://localhost:8000"
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "token.txt")
CSV_APP    = os.path.join(BASE_DIR, "aplicaciones.csv")
CSV_SVC    = os.path.join(BASE_DIR, "servicios_ti.csv")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

with open(TOKEN_FILE, "r", encoding="utf-8") as f:
    TOKEN = f.read().strip()

HEADERS = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type":  "application/json",
    "Accept":        "application/json",
}

stats = {"actualizados": 0, "ya_ok": 0, "errores": 0}

# ─── Helpers ──────────────────────────────────────────────────────────────────
def clean(val):
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return ""
    return str(val).strip()

def get_or_create_tag(nombre, color):
    slug = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")
    r = requests.get(f"{NETBOX_URL}/api/extras/tags/", headers=HEADERS, params={"slug": slug})
    data = r.json()
    if data["count"] > 0:
        t = data["results"][0]
        return {"id": t["id"], "name": t["name"], "slug": t["slug"]}
    r = requests.post(f"{NETBOX_URL}/api/extras/tags/", headers=HEADERS,
                      json={"name": nombre, "slug": slug, "color": color})
    t = r.json()
    return {"id": t["id"], "name": t["name"], "slug": t["slug"]}

def get_vm(nombre):
    """Busca una VM por nombre y devuelve su id y tags actuales."""
    r = requests.get(f"{NETBOX_URL}/api/virtualization/virtual-machines/",
                     headers=HEADERS, params={"name": nombre, "limit": 10})
    data = r.json()
    if data["count"] == 0:
        return None
    # Si hay varias con el mismo nombre, las devolvemos todas
    return data["results"]

def patch_vm_tags(vm_id, tags_actuales, tag_nuevo):
    """Añade tag_nuevo a la VM si no lo tiene ya."""
    slugs_actuales = {t["slug"] for t in tags_actuales}
    if tag_nuevo["slug"] in slugs_actuales:
        return "ya_ok"
    nuevos_tags = tags_actuales + [tag_nuevo]
    r = requests.patch(
        f"{NETBOX_URL}/api/virtualization/virtual-machines/{vm_id}/",
        headers=HEADERS,
        json={"tags": [{"id": t["id"]} for t in nuevos_tags]}
    )
    if r.status_code in (200, 201):
        return "ok"
    else:
        log.error(f"  Error en VM {vm_id}: {r.text[:150]}")
        return "error"

# ─── Procesar un CSV ──────────────────────────────────────────────────────────
def procesar(csv_path, col_nombre, tag):
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig", dtype=str)
    for _, row in df.iterrows():
        nombre = clean(row.get(col_nombre, ""))
        if not nombre:
            continue
        vms = get_vm(nombre)
        if not vms:
            log.warning(f"  No encontrada en NetBox: {nombre}")
            stats["errores"] += 1
            continue
        for vm in vms:
            resultado = patch_vm_tags(vm["id"], vm["tags"], tag)
            if resultado == "ok":
                log.info(f"  Tag añadido: {nombre} (id={vm['id']})")
                stats["actualizados"] += 1
            elif resultado == "ya_ok":
                log.info(f"  Ya tenía el tag: {nombre}")
                stats["ya_ok"] += 1
            else:
                stats["errores"] += 1

# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Corrigiendo tags...")

    tag_app = get_or_create_tag("aplicacion", "2ecc71")
    tag_svc = get_or_create_tag("servicio-ti", "e74c3c")

    log.info("— Aplicaciones —")
    procesar(CSV_APP, "Dispositivo BDI", tag_app)

    log.info("— Servicios TI —")
    procesar(CSV_SVC, "DISPOSITIVO (BDI)", tag_svc)

    log.info("=" * 50)
    log.info(f"  Actualizados: {stats['actualizados']}")
    log.info(f"  Ya correctos: {stats['ya_ok']}")
    log.info(f"  Errores:      {stats['errores']}")
    log.info("=" * 50)
    