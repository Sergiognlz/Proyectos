"""
migrate.py — Migración CMDBuild → NetBox
Sandetel / Junta de Andalucía

Uso:
    python migrate.py

Requisitos:
    pip install requests pandas tqdm

Estructura esperada de ficheros (misma carpeta que este script):
    aplicaciones.csv
    servicios_ti.csv
    token.txt
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

# ─── Leer token ───────────────────────────────────────────────────────────────
with open(TOKEN_FILE, "r", encoding="utf-8") as f:
    TOKEN = f.read().strip()

HEADERS = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type":  "application/json",
    "Accept":        "application/json",
}

# ─── Contadores globales ──────────────────────────────────────────────────────
stats = {"creados": 0, "omitidos": 0, "errores": 0}

# ─── Helpers de API ───────────────────────────────────────────────────────────
def api_get(endpoint, params=None):
    r = requests.get(f"{NETBOX_URL}/api/{endpoint}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()

def api_post(endpoint, payload):
    r = requests.post(f"{NETBOX_URL}/api/{endpoint}", headers=HEADERS, json=payload)
    return r

def clean(val):
    """Limpia valores nulos y espacios."""
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return ""
    return str(val).strip()

def clean_number(val):
    """Limpia números con espacios o decimales innecesarios (ej: '5000.000 ' → '5000')."""
    v = clean(val)
    if not v:
        return None
    try:
        return int(float(re.sub(r"[^\d.]", "", v)))
    except Exception:
        return None

# ─── Caché de objetos ya creados ─────────────────────────────────────────────
_cache_sites    = {}
_cache_tenants  = {}
_cache_tags     = {}
_cache_clusters = {}
_cache_platforms = {}

# ─── Funciones de creación de objetos base ────────────────────────────────────

def get_or_create_site(nombre):
    if not nombre:
        nombre = "Sin entorno"
    if nombre in _cache_sites:
        return _cache_sites[nombre]
    slug = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")
    # Buscar
    data = api_get("dcim/sites/", {"slug": slug})
    if data["count"] > 0:
        _cache_sites[nombre] = data["results"][0]["id"]
        return _cache_sites[nombre]
    # Crear
    r = api_post("dcim/sites/", {"name": nombre, "slug": slug})
    if r.status_code in (200, 201):
        _cache_sites[nombre] = r.json()["id"]
        log.info(f"  Site creado: {nombre}")
        return _cache_sites[nombre]
    log.warning(f"  No se pudo crear site '{nombre}': {r.text[:120]}")
    return None

def get_or_create_tenant(nombre):
    if not nombre:
        return None
    if nombre in _cache_tenants:
        return _cache_tenants[nombre]
    slug = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")
    data = api_get("tenancy/tenants/", {"slug": slug})
    if data["count"] > 0:
        _cache_tenants[nombre] = data["results"][0]["id"]
        return _cache_tenants[nombre]
    r = api_post("tenancy/tenants/", {"name": nombre, "slug": slug})
    if r.status_code in (200, 201):
        _cache_tenants[nombre] = r.json()["id"]
        log.info(f"  Tenant creado: {nombre}")
        return _cache_tenants[nombre]
    log.warning(f"  No se pudo crear tenant '{nombre}': {r.text[:120]}")
    return None

def get_or_create_tag(nombre, color="3498db"):
    if not nombre:
        return None
    if nombre in _cache_tags:
        return _cache_tags[nombre]
    slug = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")
    data = api_get("extras/tags/", {"slug": slug})
    if data["count"] > 0:
        _cache_tags[nombre] = {"id": data["results"][0]["id"], "name": nombre, "slug": slug}
        return _cache_tags[nombre]
    r = api_post("extras/tags/", {"name": nombre, "slug": slug, "color": color})
    if r.status_code in (200, 201):
        _cache_tags[nombre] = {"id": r.json()["id"], "name": nombre, "slug": slug}
        log.info(f"  Tag creado: {nombre}")
        return _cache_tags[nombre]
    log.warning(f"  No se pudo crear tag '{nombre}': {r.text[:120]}")
    return None

def get_or_create_cluster():
    """NetBox requiere un cluster para las VMs. Usamos uno genérico."""
    nombre = "Sandetel"
    if nombre in _cache_clusters:
        return _cache_clusters[nombre]
    # Necesitamos un cluster type primero
    ct_data = api_get("virtualization/cluster-types/", {"slug": "sandetel"})
    if ct_data["count"] > 0:
        ct_id = ct_data["results"][0]["id"]
    else:
        r = api_post("virtualization/cluster-types/", {"name": "Sandetel", "slug": "sandetel"})
        ct_id = r.json()["id"] if r.status_code in (200, 201) else None
    if not ct_id:
        return None
    # Crear cluster
    data = api_get("virtualization/clusters/", {"name": nombre})
    if data["count"] > 0:
        _cache_clusters[nombre] = data["results"][0]["id"]
        return _cache_clusters[nombre]
    r = api_post("virtualization/clusters/", {"name": nombre, "type": ct_id})
    if r.status_code in (200, 201):
        _cache_clusters[nombre] = r.json()["id"]
        log.info(f"  Cluster creado: {nombre}")
        return _cache_clusters[nombre]
    return None

def get_or_create_platform(nombre):
    if not nombre:
        return None
    if nombre in _cache_platforms:
        return _cache_platforms[nombre]
    slug = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")[:100]
    data = api_get("dcim/platforms/", {"slug": slug})
    if data["count"] > 0:
        _cache_platforms[nombre] = data["results"][0]["id"]
        return _cache_platforms[nombre]
    r = api_post("dcim/platforms/", {"name": nombre[:100], "slug": slug})
    if r.status_code in (200, 201):
        _cache_platforms[nombre] = r.json()["id"]
        log.info(f"  Platform creado: {nombre}")
        return _cache_platforms[nombre]
    return None

# ─── Custom Fields ────────────────────────────────────────────────────────────

def crear_custom_fields():
    """Crea todos los Custom Fields necesarios en NetBox antes de importar."""
    log.info("Creando Custom Fields...")

    # content_types para Virtual Machine
    vm_type = "virtualization.virtualmachine"

    campos = [
        # Aplicaciones
        {"name": "cf_servicio",            "label": "Servicio",              "type": "text"},
        {"name": "cf_aplicacion_software", "label": "Aplicación Software",   "type": "text"},
        {"name": "cf_docker",              "label": "Docker",                "type": "boolean"},
        {"name": "cf_version",             "label": "Versión",               "type": "text"},
        {"name": "cf_url",                 "label": "URL",                   "type": "url"},
        {"name": "cf_ruta_documentacion",  "label": "Ruta Documentación",    "type": "text"},
        {"name": "cf_uso",                 "label": "Uso Interno/Externo",   "type": "text"},
        {"name": "cf_bbdd",                "label": "BBDD",                  "type": "text"},
        # Servicios TI
        {"name": "cf_servicio_gniv",       "label": "Servicio GNIV",         "type": "text"},
        {"name": "cf_proyecto_cs",         "label": "Proyecto/Servicio CS",  "type": "text"},
        {"name": "cf_tamano_u",            "label": "Tamaño U",              "type": "text"},
        {"name": "cf_espacio_alm_bck",     "label": "Espacio ALM/BCK (GB)",  "type": "text"},
        {"name": "cf_apagado_baja",        "label": "Apagado/Baja",          "type": "text"},
        {"name": "cf_horario",             "label": "Horario",               "type": "text"},
        {"name": "cf_tipo_dispositivo",    "label": "Tipo Dispositivo",      "type": "text"},
        {"name": "cf_tipo_equipo",         "label": "Tipo Equipo",           "type": "text"},
        {"name": "cf_contactos",           "label": "Contactos",             "type": "text"},
        {"name": "cf_administracion",      "label": "Administración",        "type": "text"},
        {"name": "cf_fecha_alta",          "label": "Fecha Alta",            "type": "text"},
        {"name": "cf_fecha_baja",          "label": "Fecha Baja",            "type": "text"},
        {"name": "cf_tipo_alojamiento",    "label": "Tipo Alojamiento",      "type": "text"},
    ]

    existing = {cf["name"] for cf in api_get("extras/custom-fields/", {"limit": 200})["results"]}

    for campo in campos:
        if campo["name"] in existing:
            continue
        payload = {
            "name":          campo["name"],
            "label":         campo["label"],
            "type":          campo["type"],
            "object_types":  [vm_type],
            "ui_visible":    "always",
            "ui_editable":   "yes",
        }
        r = api_post("extras/custom-fields/", payload)
        if r.status_code in (200, 201):
            log.info(f"  Custom Field creado: {campo['name']}")
        else:
            log.warning(f"  Error creando CF {campo['name']}: {r.text[:120]}")

# ─── Conversión de estado ─────────────────────────────────────────────────────

def mapear_estado_app(estado):
    mapa = {
        "ALTA":         "active",
        "DESARROLLO":   "staged",
        "BAJA":         "decommissioning",
        "PREPRODUCCION":"staged",
        "PREPRODUCCIÓN":"staged",
    }
    return mapa.get(str(estado).strip().upper(), "active")

def mapear_estado_svc(estado):
    mapa = {
        "OPERATIVO":    "active",
        "APAGADO":      "offline",
        "BAJA":         "decommissioning",
    }
    return mapa.get(str(estado).strip().upper(), "active")

# ─── Comprobar duplicado ──────────────────────────────────────────────────────

def vm_existe(nombre, site_id):
    data = api_get("virtualization/virtual-machines/", {"name": nombre, "site_id": site_id})
    return data["count"] > 0

# ─── IMPORTAR APLICACIONES ────────────────────────────────────────────────────

def importar_aplicaciones(cluster_id):
    log.info("=" * 60)
    log.info("IMPORTANDO APLICACIONES")
    log.info("=" * 60)

    df = pd.read_csv(CSV_APP, sep=";", encoding="utf-8-sig", dtype=str)
    tag_app = get_or_create_tag("aplicacion", "2ecc71")

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Aplicaciones"):
        nombre = clean(row.get("Dispositivo BDI", ""))
        if not nombre:
            log.warning("  Fila sin nombre, omitida.")
            stats["omitidos"] += 1
            continue

        entorno  = clean(row.get("ENTORNO", "")) or "Sin entorno"
        site_id  = get_or_create_site(entorno)

        if vm_existe(nombre, site_id):
            log.info(f"  OMITIDO (ya existe): {nombre}")
            stats["omitidos"] += 1
            continue

        estado   = mapear_estado_app(clean(row.get("ESTADO APLICACIÓN", "")))
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
        # Eliminar campos vacíos para no sobreescribir con null
        custom_fields = {k: v for k, v in custom_fields.items() if v != "" and v is not None}

        payload = {
            "name":          nombre[:64],
            "status":        estado,
            "site":          site_id,
            "cluster":       cluster_id,
            "comments":      comments,
            "tags":          [tag_app] if tag_app else [],
            "custom_fields": custom_fields,
        }

        r = api_post("virtualization/virtual-machines/", payload)
        if r.status_code in (200, 201):
            log.info(f"  OK: {nombre}")
            stats["creados"] += 1
        else:
            log.error(f"  ERROR: {nombre} → {r.text[:200]}")
            stats["errores"] += 1

# ─── IMPORTAR SERVICIOS TI ────────────────────────────────────────────────────

def importar_servicios_ti(cluster_id):
    log.info("=" * 60)
    log.info("IMPORTANDO SERVICIOS TI")
    log.info("=" * 60)

    df = pd.read_csv(CSV_SVC, sep=";", encoding="utf-8-sig", dtype=str)
    tag_svc = get_or_create_tag("servicio-ti", "e74c3c")

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Servicios TI"):
        nombre = clean(row.get("DISPOSITIVO (BDI)", ""))
        if not nombre:
            log.warning("  Fila sin nombre, omitida.")
            stats["omitidos"] += 1
            continue

        entorno  = clean(row.get("ENTORNO", "")) or "Sin entorno"
        site_id  = get_or_create_site(entorno)

        if vm_existe(nombre, site_id):
            log.info(f"  OMITIDO (ya existe): {nombre}")
            stats["omitidos"] += 1
            continue

        estado   = mapear_estado_svc(clean(row.get("ESTADO", "")))
        tenant_id = get_or_create_tenant(clean(row.get("ENCARGO", "")))
        platform_id = get_or_create_platform(clean(row.get("SISTEMA OPERATIVO", "")))

        # CPU, RAM, Disco
        vcpus  = clean_number(row.get("CPU", ""))
        ram_gb = clean_number(row.get("RAM (GB)", ""))
        memory = ram_gb * 1024 if ram_gb else None   # NetBox usa MB
        disk   = clean_number(row.get("DISK (GB)", ""))

        # Comments: DETALLE SERVICIO + COMENTARIOS
        detalle  = clean(row.get("DETALLE SERVICIO", ""))
        coment   = clean(row.get("COMENTARIOS", ""))
        comments = "\n\n".join(filter(None, [detalle, coment]))

        custom_fields = {
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
        }
        custom_fields = {k: v for k, v in custom_fields.items() if v != "" and v is not None}

        payload = {
            "name":          nombre[:64],
            "status":        estado,
            "site":          site_id,
            "cluster":       cluster_id,
            "comments":      comments,
            "tags":          [tag_svc] if tag_svc else [],
            "custom_fields": custom_fields,
        }
        if tenant_id:
            payload["tenant"] = tenant_id
        if platform_id:
            payload["platform"] = platform_id
        if vcpus:
            payload["vcpus"] = vcpus
        if memory:
            payload["memory"] = memory
        if disk:
            payload["disk"] = disk

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
    log.info(f"NetBox URL: {NETBOX_URL}")
    log.info(f"Log: {LOG_FILE}")

    # Verificar conexión
    try:
        r = requests.get(f"{NETBOX_URL}/api/", headers=HEADERS)
        r.raise_for_status()
        log.info("Conexión con NetBox: OK")
    except Exception as e:
        log.error(f"No se puede conectar con NetBox: {e}")
        exit(1)

    # Crear custom fields
    crear_custom_fields()

    # Crear cluster base (requerido por NetBox para VMs)
    cluster_id = get_or_create_cluster()
    if not cluster_id:
        log.error("No se pudo crear el cluster. Abortando.")
        exit(1)

    # Importar
    importar_aplicaciones(cluster_id)
    importar_servicios_ti(cluster_id)

    # Resumen
    log.info("=" * 60)
    log.info("RESUMEN DE MIGRACIÓN")
    log.info(f"  Creados:  {stats['creados']}")
    log.info(f"  Omitidos: {stats['omitidos']}")
    log.info(f"  Errores:  {stats['errores']}")
    log.info(f"  Log guardado en: {LOG_FILE}")
    log.info("=" * 60)