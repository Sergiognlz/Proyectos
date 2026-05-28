"""
migrate.py — Migración CMDBuild → NetBox (script unificado)
Sandetel / Junta de Andalucía

Ejecuta todo el proceso de migración desde cero:
  1. Crea Custom Fields
  2. Crea clusters, sites, tenants, tags y plataformas
  3. Importa Servicios TI (cluster: Sandetel-Servicios)
  4. Importa Aplicaciones (cluster: Sandetel-Aplicaciones)
  5. Vincula aplicaciones con su servicio TI relacionado

Requisitos:
    pip install requests pandas tqdm

Estructura esperada (misma carpeta que este script):
    aplicaciones.csv
    servicios_ti.csv
    token.txt

Uso:
    python migrate.py
"""

import requests
import pandas as pd
from tqdm import tqdm
import logging
import os
import re
from datetime import datetime

# ─── Configuración ────────────────────────────────────────────────────────────
NETBOX_URL = "http://localhost:8000"
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "token.txt")
CSV_APP    = os.path.join(BASE_DIR, "aplicaciones.csv")
CSV_SVC    = os.path.join(BASE_DIR, "servicios_ti.csv")
LOG_FILE   = os.path.join(BASE_DIR, f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ─── Token ────────────────────────────────────────────────────────────────────
with open(TOKEN_FILE, "r", encoding="utf-8") as f:
    TOKEN = f.read().strip()

HEADERS = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type":  "application/json",
    "Accept":        "application/json",
}

# ─── Contadores ───────────────────────────────────────────────────────────────
stats = {"creados": 0, "omitidos": 0, "errores": 0}

# ─── Caché ────────────────────────────────────────────────────────────────────
_cache = {
    "sites":     {},
    "tenants":   {},
    "tags":      {},
    "clusters":  {},
    "platforms": {},
}

# ─── Helpers generales ────────────────────────────────────────────────────────
def api_get(endpoint, params=None):
    r = requests.get(f"{NETBOX_URL}/api/{endpoint}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()

def api_post(endpoint, payload):
    return requests.post(f"{NETBOX_URL}/api/{endpoint}", headers=HEADERS, json=payload)

def clean(val):
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return ""
    return str(val).strip()

def clean_number(val):
    v = clean(val)
    if not v:
        return None
    try:
        return int(float(re.sub(r"[^\d.]", "", v)))
    except Exception:
        return None

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:100]

# ─── Creación de objetos base ─────────────────────────────────────────────────
def get_or_create_site(nombre):
    if not nombre:
        nombre = "Sin entorno"
    if nombre in _cache["sites"]:
        return _cache["sites"][nombre]
    slug = slugify(nombre)
    data = api_get("dcim/sites/", {"slug": slug})
    if data["count"] > 0:
        _cache["sites"][nombre] = data["results"][0]["id"]
        return _cache["sites"][nombre]
    r = api_post("dcim/sites/", {"name": nombre, "slug": slug})
    if r.status_code in (200, 201):
        _cache["sites"][nombre] = r.json()["id"]
        log.info(f"  Site creado: {nombre}")
        return _cache["sites"][nombre]
    log.warning(f"  No se pudo crear site '{nombre}': {r.text[:120]}")
    return None

def get_or_create_tenant(nombre):
    if not nombre:
        return None
    if nombre in _cache["tenants"]:
        return _cache["tenants"][nombre]
    slug = slugify(nombre)
    data = api_get("tenancy/tenants/", {"slug": slug})
    if data["count"] > 0:
        _cache["tenants"][nombre] = data["results"][0]["id"]
        return _cache["tenants"][nombre]
    r = api_post("tenancy/tenants/", {"name": nombre, "slug": slug})
    if r.status_code in (200, 201):
        _cache["tenants"][nombre] = r.json()["id"]
        log.info(f"  Tenant creado: {nombre}")
        return _cache["tenants"][nombre]
    log.warning(f"  No se pudo crear tenant '{nombre}': {r.text[:120]}")
    return None

def get_or_create_tag(nombre, color):
    if nombre in _cache["tags"]:
        return _cache["tags"][nombre]
    slug = slugify(nombre)
    data = api_get("extras/tags/", {"slug": slug})
    if data["count"] > 0:
        t = data["results"][0]
        _cache["tags"][nombre] = {"id": t["id"], "name": t["name"], "slug": t["slug"]}
        return _cache["tags"][nombre]
    r = api_post("extras/tags/", {"name": nombre, "slug": slug, "color": color})
    if r.status_code in (200, 201):
        t = r.json()
        _cache["tags"][nombre] = {"id": t["id"], "name": t["name"], "slug": t["slug"]}
        log.info(f"  Tag creado: {nombre}")
        return _cache["tags"][nombre]
    log.warning(f"  No se pudo crear tag '{nombre}': {r.text[:120]}")
    return None

def get_or_create_cluster_type(nombre):
    slug = slugify(nombre)
    data = api_get("virtualization/cluster-types/", {"slug": slug})
    if data["count"] > 0:
        return data["results"][0]["id"]
    r = api_post("virtualization/cluster-types/", {"name": nombre, "slug": slug})
    if r.status_code in (200, 201):
        return r.json()["id"]
    return None

def get_or_create_cluster(nombre):
    if nombre in _cache["clusters"]:
        return _cache["clusters"][nombre]
    data = api_get("virtualization/clusters/", {"name": nombre})
    if data["count"] > 0:
        _cache["clusters"][nombre] = data["results"][0]["id"]
        return _cache["clusters"][nombre]
    ct_id = get_or_create_cluster_type("Sandetel")
    if not ct_id:
        return None
    r = api_post("virtualization/clusters/", {"name": nombre, "type": ct_id})
    if r.status_code in (200, 201):
        _cache["clusters"][nombre] = r.json()["id"]
        log.info(f"  Cluster creado: {nombre}")
        return _cache["clusters"][nombre]
    log.warning(f"  No se pudo crear cluster '{nombre}': {r.text[:120]}")
    return None

def get_or_create_platform(nombre):
    if not nombre:
        return None
    if nombre in _cache["platforms"]:
        return _cache["platforms"][nombre]
    slug = slugify(nombre)
    data = api_get("dcim/platforms/", {"slug": slug})
    if data["count"] > 0:
        _cache["platforms"][nombre] = data["results"][0]["id"]
        return _cache["platforms"][nombre]
    r = api_post("dcim/platforms/", {"name": nombre[:100], "slug": slug})
    if r.status_code in (200, 201):
        _cache["platforms"][nombre] = r.json()["id"]
        return _cache["platforms"][nombre]
    return None

def vm_existe(nombre, cluster_id):
    data = api_get("virtualization/virtual-machines/",
                   {"name": nombre, "cluster_id": cluster_id})
    if data["count"] == 0:
        return None
    return data["results"][0]["id"]

# ─── Custom Fields ────────────────────────────────────────────────────────────
def crear_custom_fields():
    log.info("Creando Custom Fields...")
    vm_type = "virtualization.virtualmachine"
    campos = [
        {"name": "cf_servicio_gniv",           "label": "Servicio GNIV",               "type": "text"},
        {"name": "cf_proyecto_cs",             "label": "Proyecto/Servicio CS",         "type": "text"},
        {"name": "cf_tamano_u",                "label": "Tamaño U",                     "type": "text"},
        {"name": "cf_espacio_alm_bck",         "label": "Espacio ALM/BCK (GB)",         "type": "text"},
        {"name": "cf_apagado_baja",            "label": "Apagado/Baja",                 "type": "text"},
        {"name": "cf_horario",                 "label": "Horario",                      "type": "text"},
        {"name": "cf_tipo_dispositivo",        "label": "Tipo Dispositivo",             "type": "text"},
        {"name": "cf_tipo_equipo",             "label": "Tipo Equipo",                  "type": "text"},
        {"name": "cf_contactos",               "label": "Contactos",                    "type": "text"},
        {"name": "cf_administracion",          "label": "Administración",               "type": "text"},
        {"name": "cf_fecha_alta",              "label": "Fecha Alta",                   "type": "text"},
        {"name": "cf_fecha_baja",              "label": "Fecha Baja",                   "type": "text"},
        {"name": "cf_tipo_alojamiento",        "label": "Tipo Alojamiento",             "type": "text"},
        {"name": "cf_servicio",                "label": "Servicio",                     "type": "text"},
        {"name": "cf_aplicacion_software",     "label": "Aplicación Software",          "type": "text"},
        {"name": "cf_docker",                  "label": "Docker",                       "type": "boolean"},
        {"name": "cf_version",                 "label": "Versión",                      "type": "text"},
        {"name": "cf_url",                     "label": "URL",                          "type": "url"},
        {"name": "cf_ruta_documentacion",      "label": "Ruta Documentación",           "type": "text"},
        {"name": "cf_uso",                     "label": "Uso Interno/Externo",          "type": "text"},
        {"name": "cf_bbdd",                    "label": "BBDD",                         "type": "text"},
        {"name": "cf_servicio_ti_relacionado", "label": "Servicio TI relacionado",      "type": "text"},
    ]
    existing = {cf["name"] for cf in api_get("extras/custom-fields/", {"limit": 200})["results"]}
    for campo in campos:
        if campo["name"] in existing:
            continue
        payload = {
            "name":         campo["name"],
            "label":        campo["label"],
            "type":         campo["type"],
            "object_types": [vm_type],
            "ui_visible":   "always",
            "ui_editable":  "yes",
        }
        r = api_post("extras/custom-fields/", payload)
        if r.status_code in (200, 201):
            log.info(f"  Custom Field creado: {campo['name']}")
        else:
            log.warning(f"  Error CF {campo['name']}: {r.text[:120]}")

# ─── Conversión de estado ─────────────────────────────────────────────────────
def mapear_estado_app(estado):
    return {
        "ALTA":          "active",
        "DESARROLLO":    "staged",
        "BAJA":          "decommissioning",
        "PREPRODUCCION": "staged",
        "PREPRODUCCIÓN": "staged",
    }.get(str(estado).strip().upper(), "active")

def mapear_estado_svc(estado):
    return {
        "OPERATIVO":         "active",
        "APAGADO":           "offline",
        "BAJA":              "decommissioning",
        "FUERA DE SERVICIO": "decommissioning",
    }.get(str(estado).strip().upper(), "active")

# ─── PASO 3: Importar Servicios TI ───────────────────────────────────────────
def importar_servicios_ti(cluster_id, tag_svc):
    log.info("=" * 60)
    log.info("IMPORTANDO SERVICIOS TI")
    log.info("=" * 60)

    df = pd.read_csv(CSV_SVC, sep=";", encoding="utf-8-sig", dtype=str)

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Servicios TI"):
        nombre = clean(row.get("DISPOSITIVO (BDI)", ""))
        if not nombre:
            stats["omitidos"] += 1
            continue

        site_id     = get_or_create_site(clean(row.get("ENTORNO", "")) or "Sin entorno")
        tenant_id   = get_or_create_tenant(clean(row.get("ENCARGO", "")))
        platform_id = get_or_create_platform(clean(row.get("SISTEMA OPERATIVO", "")))

        if vm_existe(nombre, cluster_id):
            log.info(f"  OMITIDO (ya existe): {nombre}")
            stats["omitidos"] += 1
            continue

        vcpus  = clean_number(row.get("CPU", ""))
        ram_gb = clean_number(row.get("RAM (GB)", ""))
        memory = ram_gb * 1024 if ram_gb else None
        disk   = clean_number(row.get("DISK (GB)", ""))

        detalle  = clean(row.get("DETALLE SERVICIO", ""))
        coment   = clean(row.get("COMENTARIOS", ""))
        comments = "\n\n".join(filter(None, [detalle, coment]))

        custom_fields = {k: v for k, v in {
            "cf_servicio_gniv":    clean(row.get("SERVICIO GNIV", "")),
            "cf_proyecto_cs":      clean(row.get("PROYECTO_SERVICIO_CS", "")),
            "cf_tamano_u":         clean(row.get("TAMAÑO U", "")),
            "cf_espacio_alm_bck":  clean(row.get("ESPACIO ALM/BCK (GB)", "")),
            "cf_apagado_baja":     clean(row.get("APAGADO/BAJA", "")),
            "cf_horario":          clean(row.get("HORARIO", "")),
            "cf_tipo_dispositivo": clean(row.get("TIPO DISPOSITIVO", "")),
            "cf_tipo_equipo":      clean(row.get("TIPO EQUIPO", "")),
            "cf_contactos":        clean(row.get("CONTACTOS", "")),
            "cf_administracion":   clean(row.get("ADMINISTRACIÓN", "")),
            "cf_fecha_alta":       clean(row.get("FECHA ALTA", "")),
            "cf_fecha_baja":       clean(row.get("FECHA BAJA", "")),
            "cf_tipo_alojamiento": clean(row.get("TIPO ALOJAMIENTO", "")),
        }.items() if v != ""}

        payload = {
            "name":          nombre[:64],
            "status":        mapear_estado_svc(clean(row.get("ESTADO", ""))),
            "site":          site_id,
            "cluster":       cluster_id,
            "comments":      comments,
            "tags":          [tag_svc],
            "custom_fields": custom_fields,
        }
        if tenant_id:   payload["tenant"]   = tenant_id
        if platform_id: payload["platform"] = platform_id
        if vcpus:       payload["vcpus"]    = vcpus
        if memory:      payload["memory"]   = memory
        if disk:        payload["disk"]     = disk

        r = api_post("virtualization/virtual-machines/", payload)
        if r.status_code in (200, 201):
            log.info(f"  OK: {nombre}")
            stats["creados"] += 1
        else:
            log.error(f"  ERROR: {nombre} → {r.text[:200]}")
            stats["errores"] += 1

# ─── PASO 4: Importar Aplicaciones ───────────────────────────────────────────
def importar_aplicaciones(cluster_id, tag_app, nombres_svc):
    log.info("=" * 60)
    log.info("IMPORTANDO APLICACIONES")
    log.info("=" * 60)

    df = pd.read_csv(CSV_APP, sep=";", encoding="utf-8-sig", dtype=str)

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Aplicaciones"):
        nombre = clean(row.get("Dispositivo BDI", ""))
        if not nombre:
            stats["omitidos"] += 1
            continue

        site_id = get_or_create_site(clean(row.get("ENTORNO", "")) or "Sin entorno")

        if vm_existe(nombre, cluster_id):
            log.info(f"  OMITIDO (ya existe): {nombre}")
            stats["omitidos"] += 1
            continue

        docker   = clean(row.get("DOCKER", "")).lower() == "true"
        comments = clean(row.get("OBSERVACION", ""))

        custom_fields = {
            "cf_servicio":            clean(row.get("SERVICIO", "")),
            "cf_aplicacion_software": clean(row.get("APLICACION SOFTWARE", "")),
            "cf_docker":              docker,
            "cf_version":             clean(row.get("VERSION", "")),
            "cf_url":                 clean(row.get("URL", "")),
            "cf_ruta_documentacion":  clean(row.get("Ruta Documentación", "")),
            "cf_uso":                 clean(row.get("USO INTERNO/EXTERNO", "")),
            "cf_bbdd":                clean(row.get("BBDD", "")),
        }

        # Si este dispositivo también existe en Servicios TI, añadir el vínculo
        if nombre in nombres_svc:
            custom_fields["cf_servicio_ti_relacionado"] = nombre

        custom_fields = {k: v for k, v in custom_fields.items()
                         if v != "" and v is not None}

        payload = {
            "name":          nombre[:64],
            "status":        mapear_estado_app(clean(row.get("ESTADO APLICACIÓN", ""))),
            "site":          site_id,
            "cluster":       cluster_id,
            "comments":      comments,
            "tags":          [tag_app],
            "custom_fields": custom_fields,
        }

        r = api_post("virtualization/virtual-machines/", payload)
        if r.status_code in (200, 201):
            log.info(f"  OK: {nombre}")
            stats["creados"] += 1
        else:
            log.error(f"  ERROR: {nombre} → {r.text[:200]}")
            stats["errores"] += 1

# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Iniciando migración CMDBuild → NetBox")
    log.info(f"Log: {LOG_FILE}")

    # Verificar conexión
    try:
        r = requests.get(f"{NETBOX_URL}/api/", headers=HEADERS)
        r.raise_for_status()
        log.info("Conexión con NetBox: OK")
    except Exception as e:
        log.error(f"No se puede conectar con NetBox: {e}")
        exit(1)

    # PASO 1: Custom Fields
    crear_custom_fields()

    # PASO 2: Objetos base
    log.info("Creando objetos base...")
    cluster_svc = get_or_create_cluster("Sandetel-Servicios")
    cluster_app = get_or_create_cluster("Sandetel-Aplicaciones")
    tag_svc     = get_or_create_tag("servicio-ti", "e74c3c")
    tag_app     = get_or_create_tag("aplicacion",  "2ecc71")

    if not cluster_svc or not cluster_app:
        log.error("No se pudieron crear los clusters. Abortando.")
        exit(1)

    # Nombres de Servicios TI para identificar duplicados
    df_svc      = pd.read_csv(CSV_SVC, sep=";", encoding="utf-8-sig", dtype=str)
    nombres_svc = set(df_svc["DISPOSITIVO (BDI)"].str.strip())

    # PASO 3: Servicios TI
    importar_servicios_ti(cluster_svc, tag_svc)

    # PASO 4: Aplicaciones
    importar_aplicaciones(cluster_app, tag_app, nombres_svc)

    # Resumen final
    log.info("=" * 60)
    log.info("RESUMEN DE MIGRACIÓN")
    log.info(f"  Creados:  {stats['creados']}")
    log.info(f"  Omitidos: {stats['omitidos']}")
    log.info(f"  Errores:  {stats['errores']}")
    log.info(f"  Log:      {LOG_FILE}")
    log.info("=" * 60)