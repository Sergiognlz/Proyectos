#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Esta primera línea le dice al sistema que este fichero es un programa Python 3.
# La segunda indica que el fichero usa caracteres especiales como tildes y ñ.

"""
wekan_to_deck.py — Script de migración de Wekan a Nextcloud Deck
Versión 2.1

QUÉ HACE ESTE SCRIPT:
  Lee un fichero JSON exportado desde Wekan y crea el mismo tablero
  en Nextcloud Deck, incluyendo columnas, tarjetas y permisos de usuarios.

POR QUÉ NO SE CONECTA A WEKAN DIRECTAMENTE:
  Wekan solo permite usar su API con usuarios locales (no LDAP).
  En Sandetel todos los usuarios son LDAP, así que hay que exportar
  el tablero manualmente desde la web de Wekan y pasarle el fichero al script.

CÓMO USARLO:
  1. Primero siempre en modo simulación (no crea nada en Deck):
     python3 wekan_to_deck.py --json export-board-XXX.json --dry-run

  2. Migración real:
     python3 wekan_to_deck.py --json export-board-XXX.json

FICHEROS NECESARIOS EN LA MISMA CARPETA:
  - wekan_to_deck.py                        (este script)
  - export-board-YLmz8RJ4ikxxKejK7.json    (exportado desde Wekan)
  - user_mapping.json                        (relaciona usuarios Wekan con Nextcloud)

REQUISITO PREVIO:
  pip install requests
"""

# ── Importaciones ──
# Estas líneas cargan herramientas que el script necesita para funcionar.

import json      # Para leer y escribir ficheros JSON (el formato del export de Wekan)
import sys       # Para poder detener el script con un mensaje de error si algo falla
import time      # Para hacer pequeñas pausas entre llamadas a la API (evitar sobrecargar el servidor)
import argparse  # Para leer los argumentos que escribes en la terminal (--json, --dry-run, etc.)
import logging   # Para mostrar mensajes informativos en pantalla y guardarlos en migration.log
from pathlib import Path  # Para trabajar con rutas de ficheros de forma sencilla

# Intentamos importar la librería 'requests', que es la que hace las llamadas HTTP a Nextcloud.
# Si no está instalada, avisamos y paramos.
try:
    import requests
    from requests.auth import HTTPBasicAuth  # Para enviar usuario y contraseña en las llamadas
except ImportError:
    print("ERROR: Instala requests primero: pip install requests")
    sys.exit(1)  # Detiene el script con código de error 1


# ════════════════════════════════════════════
#  CONFIGURACIÓN — LAS ÚNICAS LÍNEAS QUE HAY
#  QUE EDITAR ANTES DE EJECUTAR EL SCRIPT
# ════════════════════════════════════════════

DECK_URL      = "https://at-t1.sandetel.es"   # URL de Nextcloud donde está Deck
DECK_USER     = "sergio.gonzalez.chacon"       # Tu usuario de Nextcloud
DECK_PASSWORD = "Nuevacuenta13*"               # ← PON AQUÍ TU CONTRASEÑA DE NEXTCLOUD

# Nombre del fichero que relaciona los IDs de usuario de Wekan con los de Nextcloud.
# Este fichero ya está creado y listo en la carpeta del proyecto.
USER_MAPPING_FILE = "user_mapping.json"

# Tipos de tableros de Wekan que NO queremos migrar.
# Son plantillas internas de Wekan que no contienen trabajo real.
SKIP_BOARD_TYPES = {"template-board", "template-container"}

# Tipos de tarjetas de Wekan que NO queremos migrar.
# Son tarjetas especiales (plantillas, enlaces) que no tienen equivalente en Deck.
SKIP_CARD_TYPES = {"template-card", "template-list",
                   "cardType-linkedCard", "cardType-linkedBoard"}

# Diccionario que convierte los nombres de colores de Wekan a códigos de color hex.
# Wekan usa nombres como "sky" o "green"; Deck usa códigos como "87CEEB" o "2ECC71".
WEKAN_COLOR_MAP = {
    "white": "FFFFFF",    "green": "2ECC71",    "yellow": "F1C40F",
    "orange": "E67E22",   "red": "E74C3C",      "purple": "9B59B6",
    "blue": "3498DB",     "sky": "87CEEB",      "lime": "A9D400",
    "pink": "FF69B4",     "black": "2C3E50",    "silver": "BDC3C7",
    "peachpuff": "FFDAB9","crimson": "DC143C",  "plum": "DDA0DD",
    "darkgreen": "006400","slateblue": "6A5ACD","magenta": "FF00FF",
    "gold": "FFD700",     "navy": "001F5B",     "gray": "808080",
    "saddlebrown": "8B4513","paleturquoise": "AFEEEE",
    "mistyrose": "FFE4E1","indigo": "4B0082",
}

# Lo mismo pero para los colores de los tableros completos (tienen nombres diferentes).
WEKAN_BOARD_COLOR_MAP = {
    "belize": "2980B9",     "nephritis": "27AE60",  "pomegranate": "C0392B",
    "pumpkin": "D35400",    "wisteria": "8E44AD",   "moderatepink": "E91E8C",
    "strongcyan": "00BCD4", "limegreen": "8BC34A",  "midnight": "1A237E",
    "dark": "2C3E50",       "relax": "16A085",      "corteza": "795548",
    "clearblue": "1976D2",  "natural": "558B2F",    "modern": "00ACC1",
    "moderndark": "006064", "exodark": "212121",    "cleandark": "37474F",
    "cleanlight": "90A4AE",
}


def wekan_member_to_deck_permission(member: dict) -> int:
    """
    Convierte el nivel de permiso de un miembro en Wekan al equivalente en Deck.

    En Wekan los permisos son campos true/false dentro del objeto del miembro.
    En Deck son números: 0=solo leer, 1=editar, 2=administrar, 3=compartir.

    Ejemplos:
      - Si el miembro es admin en Wekan → devuelve 2 (administrar en Deck)
      - Si solo puede leer en Wekan    → devuelve 0 (solo leer en Deck)
      - Cualquier otro caso            → devuelve 1 (editar en Deck)
    """
    if member.get("isAdmin"):        # ¿Es administrador del tablero en Wekan?
        return 2                     # → Permiso "manage" en Deck
    if member.get("isReadOnly") or member.get("isCommentOnly") or \
       member.get("isReadAssignedOnly"):  # ¿Solo puede leer o comentar?
        return 0                     # → Permiso "read" en Deck
    return 1                         # → Permiso "edit" en Deck (caso por defecto)


# ════════════════════════════════════════════
#  SISTEMA DE LOG (REGISTRO DE MENSAJES)
# ════════════════════════════════════════════

# Configuramos el sistema de mensajes para que:
#   - Muestre los mensajes en la pantalla (StreamHandler)
#   - Los guarde también en el fichero migration.log (FileHandler)
# El formato incluye fecha/hora, nivel del mensaje (INFO/WARNING/ERROR) y el texto.
logging.basicConfig(
    level=logging.INFO,  # Mostrar mensajes de nivel INFO o superior
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),                          # → Pantalla
        logging.FileHandler("migration.log", encoding="utf-8"),     # → Fichero
    ]
)
log = logging.getLogger(__name__)  # Creamos el "canal" de log para este script


# ════════════════════════════════════════════
#  CLIENTE DE NEXTCLOUD DECK
#  Todo lo que tiene que ver con hablar con
#  la API de Nextcloud Deck está aquí.
# ════════════════════════════════════════════

class DeckClient:
    """
    Esta clase es el "intérprete" que sabe cómo hablar con Nextcloud Deck.
    Contiene un método para cada acción que queremos hacer en Deck:
    crear tableros, columnas, tarjetas, asignar usuarios, etc.
    """

    def __init__(self, base_url: str, username: str, password: str,
                 dry_run: bool = False):
        """
        Inicializa el cliente. Se ejecuta cuando hacemos DeckClient(...).

        - base_url: la URL de Nextcloud (ej: https://at-t1.sandetel.es)
        - username/password: credenciales para autenticarse
        - dry_run: si es True, el cliente solo simula las acciones sin ejecutarlas
        """
        self.base_url = base_url.rstrip("/")  # Quitamos la / del final si la hay
        self.auth     = HTTPBasicAuth(username, password)  # Prepara las credenciales
        self.dry_run  = dry_run  # Guardamos si estamos en modo simulación
        # La URL base de la API de Deck en este servidor Nextcloud.
        # Verificado que en esta instalación funciona con index.php (no con ocs/v2.php).
        self._ocs = f"{self.base_url}/index.php/apps/deck/api/v1.0"

    def _headers(self) -> dict:
        """
        Devuelve las cabeceras HTTP que hay que incluir en todas las llamadas.
        'OCS-APIRequest: true' le dice a Nextcloud que es una llamada de API.
        'Accept: application/json' le pedimos que nos responda en formato JSON.
        """
        return {
            "OCS-APIRequest": "true",
            "Accept":         "application/json",
            "Content-Type":   "application/json",
        }

    def _get(self, path: str):
        """
        Hace una llamada GET a la API (para obtener datos, no para crearlos).
        Maneja dos formatos de respuesta posibles de Deck:
          - Una lista directa: [...] → la devuelve tal cual
          - Un objeto anidado: {"ocs": {"data": ...}} → extrae el dato útil
        """
        resp = requests.get(
            f"{self._ocs}{path}", auth=self.auth,
            headers=self._headers(), timeout=30  # Si no responde en 30s, error
        )
        resp.raise_for_status()  # Si la respuesta es un error HTTP (4xx/5xx), lanza excepción
        data = resp.json()       # Convierte la respuesta de texto JSON a objeto Python
        if isinstance(data, list):  # ¿La respuesta es una lista?
            return data             # → La devolvemos directamente
        return data.get("ocs", {}).get("data", data)  # → Extraemos el dato útil

    def _post(self, path: str, payload: dict) -> dict:
        """
        Hace una llamada POST a la API (para crear cosas nuevas en Deck).
        Si estamos en modo dry_run, solo muestra lo que haría sin hacerlo.
        """
        if self.dry_run:
            # En modo simulación, solo mostramos el mensaje y devolvemos un ID falso
            log.info(f"  [DRY-RUN] POST {path} → {json.dumps(payload)[:120]}")
            return {"id": abs(hash(str(payload))) % 99999,
                    "title": payload.get("title", "?")}
        resp = requests.post(
            f"{self._ocs}{path}", auth=self.auth,
            headers=self._headers(), json=payload, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):  # Si la respuesta es un diccionario...
            return data.get("ocs", {}).get("data", data)  # ...extraemos el dato útil
        return data  # Si no, la devolvemos tal cual

    def _put(self, path: str, payload: dict) -> dict:
        """
        Hace una llamada PUT a la API (para actualizar o asignar cosas en Deck).
        Funciona igual que _post pero con el método HTTP PUT.
        """
        if self.dry_run:
            log.info(f"  [DRY-RUN] PUT {path}")
            return {}
        resp = requests.put(
            f"{self._ocs}{path}", auth=self.auth,
            headers=self._headers(), json=payload, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data.get("ocs", {}).get("data", data)
        return data

    def test_connection(self):
        """
        Comprueba que podemos conectarnos a Nextcloud Deck antes de empezar.
        Hace una llamada sencilla para obtener la lista de tableros.
        Si funciona, devuelve True. Si falla, muestra el error y devuelve False.
        """
        try:
            self._get("/boards")  # Intentamos obtener la lista de boards
            log.info("Conexión con Nextcloud Deck: ✅ OK")
            return True
        except requests.HTTPError as e:
            log.error(f"Conexión con Nextcloud Deck: ❌ FALLO — {e}")
            return False

    # ── Métodos para crear cosas en Deck ──

    def create_board(self, title: str, color: str = "0087C1") -> dict:
        """Crea un tablero nuevo en Deck con el título y color indicados."""
        return self._post("/boards", {"title": title, "color": color})

    def create_stack(self, board_id: int, title: str, order: int = 1) -> dict:
        """
        Crea una columna (stack) dentro de un tablero.
        'order' indica la posición de la columna de izquierda a derecha.
        """
        return self._post(f"/boards/{board_id}/stacks",
                          {"title": title, "order": order})

    def create_card(self, board_id: int, stack_id: int, title: str,
                    description: str = "", due_date: str = "",
                    order: int = 1) -> dict:
        """
        Crea una tarjeta dentro de una columna.
        - board_id: ID del tablero donde está la columna
        - stack_id: ID de la columna donde va la tarjeta
        - title: título de la tarjeta (máximo 255 caracteres)
        - description: texto de descripción (puede incluir Markdown)
        - due_date: fecha de vencimiento en formato ISO-8601
        - order: posición vertical de la tarjeta en la columna
        """
        payload = {"title": title[:255], "type": "plain", "order": order}
        if description:            # Solo incluimos description si tiene contenido
            payload["description"] = description
        if due_date:               # Solo incluimos duedate si existe
            payload["duedate"] = due_date
        return self._post(f"/boards/{board_id}/stacks/{stack_id}/cards", payload)

    def assign_label_to_card(self, board_id: int, stack_id: int,
                              card_id: int, label_id: int):
        """Asigna una etiqueta de color a una tarjeta."""
        return self._post(
            f"/boards/{board_id}/stacks/{stack_id}/cards/{card_id}/assignLabel",
            {"labelId": label_id}
        )

    def assign_user_to_card(self, board_id: int, stack_id: int,
                             card_id: int, nc_user_id: str):
        """
        Asigna un usuario responsable a una tarjeta.
        IMPORTANTE: Usa PUT (verificado en Deck 1.17, no POST).
        REQUISITO: El usuario debe estar ya en el ACL del tablero.
                   Si no está, Deck devuelve error 400.
        """
        return self._put(
            f"/boards/{board_id}/stacks/{stack_id}/cards/{card_id}/assignUser",
            {"userId": nc_user_id}
        )

    def create_comment(self, card_id: int, message: str) -> dict:
        """Añade un comentario a una tarjeta."""
        return self._post(f"/cards/{card_id}/comments",
                          {"message": message[:1000]})  # Máximo 1000 caracteres

    def create_label(self, board_id: int, title: str, color: str) -> dict:
        """Crea una etiqueta de color en un tablero."""
        return self._post(f"/boards/{board_id}/labels",
                          {"title": title, "color": color[:6]})  # Color hex sin #

    def add_acl(self, board_id: int, nc_user: str,
                permission: int, is_group: bool = False):
        """
        Añade un usuario al tablero con un nivel de permiso determinado.
        IMPORTANTE: Usa POST (verificado en Deck 1.17, no PUT).
        IMPORTANTE: Debe llamarse ANTES de asignar usuarios a tarjetas.
                    Deck no permite asignar un usuario a una tarjeta si
                    ese usuario no es miembro del tablero.

        - type 0 = usuario individual
        - type 1 = grupo
        - permissionEdit: puede editar tarjetas
        - permissionManage: puede cambiar configuración del tablero
        - permissionShare: puede compartir el tablero
        """
        payload = {
            "type":             1 if is_group else 0,   # 0=usuario, 1=grupo
            "participant":      nc_user,                 # UUID del usuario en Nextcloud
            "permissionEdit":   permission >= 1,         # True si permiso es edit o manage
            "permissionShare":  permission >= 3,         # True solo si permiso es share
            "permissionManage": permission >= 2,         # True si permiso es manage
        }
        return self._post(f"/boards/{board_id}/acl", payload)


# ════════════════════════════════════════════
#  FUNCIONES DE TRANSFORMACIÓN
#  Convierten datos del formato Wekan
#  al formato que espera Deck.
# ════════════════════════════════════════════

def build_description(card, checklists_by_card, checklist_items_by_checklist,
                       custom_fields_meta) -> str:
    """
    Construye el texto de descripción de una tarjeta en formato Markdown.
    Deck no tiene checklists ni campos personalizados, así que los convertimos
    a texto Markdown para no perder esa información.

    El resultado tiene tres partes (si existen):
      1. La descripción original de la tarjeta
      2. Los checklists convertidos a listas Markdown (- [x] o - [ ])
      3. Los campos personalizados convertidos a una tabla Markdown
    """
    parts = []  # Lista donde iremos acumulando el texto

    # 1. Descripción original
    desc = (card.get("description") or "").strip()  # Obtenemos la descripción y quitamos espacios
    if desc:
        parts.append(desc)  # Solo la añadimos si no está vacía

    # 2. Checklists → listas Markdown
    card_id = card.get("_id", "")
    # Obtenemos los checklists de esta tarjeta, ordenados por su posición (sort)
    for cl in sorted(checklists_by_card.get(card_id, []),
                     key=lambda x: x.get("sort", 0)):
        cl_id    = cl.get("_id", "")
        cl_title = cl.get("title", "Checklist")
        # Obtenemos los items de este checklist, también ordenados
        items = sorted(checklist_items_by_checklist.get(cl_id, []),
                       key=lambda x: x.get("sort", 0))
        parts.append(f"\n**✅ {cl_title}**")  # Título del checklist en negrita
        for item in items:
            # isFinished es True/False en Wekan → lo convertimos a [x] o [ ] en Markdown
            mark = "- [x]" if item.get("isFinished") else "- [ ]"
            parts.append(f"{mark} {item.get('title', '')}")

    # 3. Campos personalizados → tabla Markdown
    card_cfs = card.get("customFields", [])
    if card_cfs:
        # Solo incluimos los campos que tienen valor (no vacíos)
        filled = [(cf, custom_fields_meta.get(cf.get("_id", "")))
                  for cf in card_cfs
                  if cf.get("value") not in (None, "", [])]
        if filled:
            parts.append("\n**Campos adicionales**")
            parts.append("| Campo | Valor |")
            parts.append("| --- | --- |")
            for cf_val, cf_meta in filled:
                # cf_meta contiene el nombre del campo; cf_val contiene el valor
                name  = cf_meta.get("name", "?") if cf_meta else "?"
                value = str(cf_val.get("value", ""))
                parts.append(f"| {name} | {value} |")

    return "\n".join(parts)  # Unimos todas las partes con saltos de línea


def build_stack_title(swimlane_title, list_title, is_default) -> str:
    """
    Construye el título de una columna en Deck teniendo en cuenta las swimlanes.

    Wekan permite dividir un tablero en filas (swimlanes). Deck no tiene esa función.
    La solución es "aplanar" las swimlanes: en lugar de filas, creamos más columnas
    con el nombre de la swimlane como prefijo.

    Ejemplo:
      - Swimlane "Equipo A" + Columna "En curso" → "Equipo A — En curso"
      - Swimlane "Default" (la que crea Wekan por defecto) → solo "En curso"
    """
    if is_default:
        return list_title  # Swimlane por defecto: ignoramos su nombre
    return f"{swimlane_title} — {list_title}"  # Swimlane real: añadimos como prefijo


# ════════════════════════════════════════════
#  FUNCIONES DE CARGA DE FICHEROS
# ════════════════════════════════════════════

def load_json(json_path: str) -> dict:
    """
    Carga el fichero JSON exportado desde Wekan y lo valida.
    El fichero debe tener el campo _format = "wekan-board-1.0.0".
    Si el fichero no existe, detiene el script con un mensaje de error.
    """
    p = Path(json_path)
    if not p.exists():
        log.error(f"Fichero JSON no encontrado: {json_path}")
        sys.exit(1)  # Detenemos el script
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)  # Leemos el JSON y lo convertimos a objeto Python
    fmt = data.get("_format", "")
    if fmt != "wekan-board-1.0.0":
        log.warning(f"Formato inesperado: '{fmt}' (esperado: wekan-board-1.0.0)")
    else:
        log.info(f"JSON cargado: '{data.get('title')}' — formato {fmt} ✅")
    return data


def load_user_mapping(path: str) -> dict:
    """
    Carga el fichero user_mapping.json que relaciona:
      - userId interno de Wekan (ej: "Jn9hYg8bJAztx6QYs")
      - con el UUID del usuario en Nextcloud (ej: "80cd52dc-0141-1040-...")

    Si el fichero no existe, el script funciona con mapeo 1:1
    (asume que el identificador es el mismo en ambas plataformas).
    """
    p = Path(path)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        log.info(f"User mapping cargado: {len(mapping)} entradas ✅")
        return mapping
    log.warning(f"Fichero '{path}' no encontrado — se usará mapeo 1:1")
    return {}  # Diccionario vacío → el script usará el mismo ID en ambos lados


# ════════════════════════════════════════════
#  FUNCIÓN PRINCIPAL DE MIGRACIÓN
#  Aquí está la lógica del proceso completo.
# ════════════════════════════════════════════

def migrate_board(wekan_data: dict, deck: DeckClient,
                  user_mapping: dict, skip_comments: bool = False) -> dict:
    """
    Migra un tablero completo de Wekan a Nextcloud Deck.
    Recibe los datos del JSON de Wekan y los crea en Deck en este orden:
      1. Crear el tablero
      2. Crear las etiquetas del tablero
      3. Configurar los permisos de usuarios (ACL) ← DEBE IR ANTES QUE LAS TARJETAS
      4. Crear las columnas (stacks)
      5. Crear las tarjetas con sus usuarios asignados
      6. Migrar los comentarios
    """

    board_title = wekan_data.get("title", "Sin título")
    board_type  = wekan_data.get("type", "board")

    # Si el tablero es una plantilla interna de Wekan, lo saltamos
    if board_type in SKIP_BOARD_TYPES:
        log.info(f"SKIP: '{board_title}' es tipo '{board_type}' (plantilla interna)")
        return {"skipped": True, "reason": "template"}

    log.info(f"\n{'='*60}")
    log.info(f"Migrando: '{board_title}'")
    log.info(f"{'='*60}")

    # ── Preparar índices de datos auxiliares ──
    # Construimos un diccionario listId → nombre actual de la lista.
    # Los nombres de las listas pueden cambiar con el tiempo en Wekan.
    # Para obtener el nombre ACTUAL (no el original), ordenamos las actividades
    # por fecha y nos quedamos con el último nombre que tuvo cada lista.
    list_names_from_activities = {}
    for a in sorted(wekan_data.get("activities", []),
                    key=lambda x: x.get("createdAt", "")):  # Ordenamos por fecha
        if a.get("listId") and a.get("listName"):
            # Al sobreescribir, al final del bucle tenemos el nombre más reciente
            list_names_from_activities[a["listId"]] = a["listName"]

    # Construimos la lista de columnas únicas a partir de las tarjetas.
    # (Las tarjetas saben en qué columna están gracias al campo listId)
    all_list_ids = {}
    for card in wekan_data.get("cards", []):
        lid = card.get("listId")
        if lid and lid not in all_list_ids:
            name = list_names_from_activities.get(lid, lid)  # Usamos el nombre más reciente
            all_list_ids[lid] = {"_id": lid, "title": name}

    # Obtenemos las swimlanes (filas horizontales del tablero).
    # Si el JSON no tiene colección swimlanes, las derivamos de las tarjetas.
    swimlanes_raw = wekan_data.get("swimlanes", [])
    if not swimlanes_raw:
        sw_ids = set(c.get("swimlaneId") for c in wekan_data.get("cards", []))
        swimlanes_raw = [{"_id": sid, "title": "Default"} for sid in sw_ids if sid]

    # Determinamos si hay swimlanes "reales" (distintas de la Default que Wekan crea siempre).
    # Si todas son Default, no hay que aplanar nada.
    non_default_sw = [s for s in swimlanes_raw
                      if s.get("title", "").lower() not in ("default", "defecto", "")]
    has_real_sw = len(non_default_sw) > 0  # True si hay swimlanes adicionales

    # Preparamos índices para acceder rápidamente a checklists e items por tarjeta
    checklists_by_card      = {}  # cardId → lista de checklists
    checklist_items_by_list = {}  # checklistId → lista de items
    for cl in wekan_data.get("checklists", []):
        checklists_by_card.setdefault(cl.get("cardId"), []).append(cl)
    for item in wekan_data.get("checklistItems", []):
        checklist_items_by_list.setdefault(item.get("checklistId"), []).append(item)

    # Índice de custom fields por su ID (para obtener el nombre del campo)
    custom_fields_meta = {cf["_id"]: cf for cf in wekan_data.get("customFields", [])}

    # Índice de comentarios por tarjeta
    comments_by_card = {}
    for comment in wekan_data.get("comments", []):
        comments_by_card.setdefault(comment.get("cardId"), []).append(comment)

    # Índice de etiquetas del tablero por su ID
    wekan_labels = {lbl["_id"]: lbl for lbl in wekan_data.get("labels", [])}


    # ════════════════════════════
    #  PASO 1 — Crear el tablero
    # ════════════════════════════
    # Convertimos el color del tablero de nombre Wekan a código hex para Deck
    deck_color    = WEKAN_BOARD_COLOR_MAP.get(wekan_data.get("color", "belize"), "2980B9")
    deck_board    = deck.create_board(board_title, deck_color)
    deck_board_id = deck_board.get("id")  # Guardamos el ID que Deck le ha asignado al tablero
    log.info(f"  Board creado en Deck: id={deck_board_id}")


    # ═══════════════════════════════
    #  PASO 2 — Crear las etiquetas
    # ═══════════════════════════════
    # Recreamos las etiquetas del tablero en Deck.
    # Guardamos el mapa wekan_labelId → deck_labelId para usarlo al asignar etiquetas a tarjetas.
    deck_label_map = {}
    for lbl_id, lbl in wekan_labels.items():
        color   = WEKAN_COLOR_MAP.get(lbl.get("color", "blue"), "3498DB")
        new_lbl = deck.create_label(deck_board_id, lbl.get("name", "Label"), color)
        deck_label_map[lbl_id] = new_lbl.get("id")  # Guardamos el nuevo ID de la etiqueta en Deck
    log.info(f"  Labels creadas: {len(deck_label_map)}")


    # ══════════════════════════════════════════════════════════
    #  PASO 3 — ACL (permisos de usuarios) ← VA PRIMERO
    #
    #  MUY IMPORTANTE: En Deck 1.17, un usuario DEBE estar en
    #  el ACL del tablero ANTES de poder ser asignado a una
    #  tarjeta. Si intentamos asignar un usuario que no está
    #  en el ACL, la API devuelve error 400.
    #  Por eso este paso va aquí, antes de crear las tarjetas.
    # ══════════════════════════════════════════════════════════
    acl_users = {}  # Guardamos qué usuarios están en el ACL para verificarlo después
    for member in wekan_data.get("members", []):
        if not member.get("isActive"):
            continue  # Saltamos usuarios inactivos en Wekan
        wekan_uid  = member.get("userId", "")
        permission = wekan_member_to_deck_permission(member)  # Convertimos el permiso
        nc_user    = user_mapping.get(wekan_uid, wekan_uid)   # Traducimos el ID de usuario
        if nc_user:
            acl_users[nc_user] = permission  # Registramos que este usuario está en el ACL
            try:
                deck.add_acl(deck_board_id, nc_user, permission)
            except Exception as e:
                log.warning(f"  No se pudo añadir ACL para '{nc_user}': {e}")

    activos = sum(1 for m in wekan_data.get("members", []) if m.get("isActive"))
    log.info(f"  ACL configurado para {activos} miembros activos")


    # ════════════════════════════════
    #  PASO 4 — Crear las columnas
    # ════════════════════════════════
    deck_stack_map = {}  # Mapa (swimlane_id, list_id) → deck_stack_id
    stack_order    = 1   # Contador para la posición de cada columna
    ordered_lists  = list(all_list_ids.values())  # Lista de columnas a crear

    if has_real_sw:
        # Si hay swimlanes reales, creamos una columna por cada combinación
        # swimlane × lista original (aplanado)
        log.info("  Swimlanes detectadas: modo aplanado")
        for sw in swimlanes_raw:
            for lst in ordered_lists:
                sw_title = sw.get("title", "Default")
                is_def   = sw_title.lower() in ("default", "defecto", "")
                title    = build_stack_title(sw_title, lst["title"], is_def)
                stack    = deck.create_stack(deck_board_id, title, stack_order)
                deck_stack_map[(sw["_id"], lst["_id"])] = stack.get("id")
                stack_order += 1
    else:
        # Sin swimlanes reales: creamos una columna por cada lista, directo
        log.info("  Sin swimlanes adicionales — stacks directos")
        sw_default_id = swimlanes_raw[0]["_id"] if swimlanes_raw else None
        for lst in ordered_lists:
            stack = deck.create_stack(deck_board_id, lst["title"], stack_order)
            # Registramos el stack con dos claves posibles para buscarlo después
            deck_stack_map[(sw_default_id, lst["_id"])] = stack.get("id")
            deck_stack_map[(None, lst["_id"])]           = stack.get("id")
            stack_order += 1

    log.info(f"  Stacks creados: {len(set(deck_stack_map.values()))}")


    # ═══════════════════════════════
    #  PASO 5 — Crear las tarjetas
    # ═══════════════════════════════
    cards          = wekan_data.get("cards", [])
    migrated_cards = 0  # Contador de tarjetas migradas con éxito
    skipped_cards  = 0  # Contador de tarjetas saltadas
    deck_card_map  = {}  # Mapa wekan_card_id → deck_card_id (para los comentarios)

    # Procesamos las tarjetas ordenadas por su posición (sort) en el tablero original
    for card in sorted(cards, key=lambda x: x.get("sort", 0)):

        # Saltamos tarjetas de tipos especiales o archivadas
        if card.get("type") in SKIP_CARD_TYPES or card.get("archived"):
            skipped_cards += 1
            continue

        card_id     = card.get("_id")
        list_id     = card.get("listId")     # En qué columna estaba la tarjeta
        swimlane_id = card.get("swimlaneId") # En qué swimlane estaba
        title       = (card.get("title") or "Sin título").strip()

        # Buscamos el ID del stack en Deck que corresponde a esta columna/swimlane
        stack_id = (deck_stack_map.get((swimlane_id, list_id))
                    or deck_stack_map.get((None, list_id)))  # Fallback sin swimlane
        if not stack_id:
            # Si no encontramos la columna, la tarjeta está huérfana (su columna fue borrada)
            log.warning(f"  SKIP card '{title}': sin stack para "
                        f"swimlane={swimlane_id} list={list_id}")
            skipped_cards += 1
            continue

        # Construimos la descripción enriquecida (original + checklists + custom fields)
        description = build_description(card, checklists_by_card,
                                        checklist_items_by_list, custom_fields_meta)

        # Procesamos la fecha de vencimiento si existe
        due_date = ""
        if card.get("dueAt"):
            try:
                raw = card["dueAt"]
                # Convertimos el formato de fecha de Wekan (UTC con Z) al estándar ISO-8601
                due_date = raw.replace("Z", "+00:00") if isinstance(raw, str) else ""
            except Exception:
                due_date = ""

        # Creamos la tarjeta en Deck
        new_card    = deck.create_card(deck_board_id, stack_id, title,
                                       description=description, due_date=due_date,
                                       order=card.get("sort", 1))
        new_card_id = new_card.get("id")
        deck_card_map[card_id] = new_card_id  # Guardamos el ID para los comentarios

        # Asignamos las etiquetas a la tarjeta.
        # IMPORTANTE: en el JSON de Wekan las tarjetas usan el campo 'labelIds' (no 'labels').
        # 'labels' pertenece al tablero (definición); 'labelIds' pertenece a la tarjeta (referencia).
        for lbl_id in (card.get("labelIds") or []):
            if lbl_id in deck_label_map:  # Solo si tenemos esa etiqueta en Deck
                try:
                    deck.assign_label_to_card(deck_board_id, stack_id,
                                               new_card_id, deck_label_map[lbl_id])
                except Exception as e:
                    log.warning(f"    No se pudo asignar label: {e}")

        # Asignamos los usuarios responsables de la tarjeta.
        # Combinamos 'members' y 'assignees' (dos campos distintos en Wekan) y eliminamos duplicados.
        card_users = list(set((card.get("members") or []) + (card.get("assignees") or [])))
        for wekan_uid in card_users:
            nc_user = user_mapping.get(wekan_uid, wekan_uid)  # Traducimos el ID
            # Solo intentamos asignar si el usuario está en el ACL del tablero.
            # Si no está, Deck devolvería error 400 y ralentizaría la migración.
            if nc_user not in acl_users:
                log.warning(f"    SKIP assignUser '{nc_user}': no está en el ACL del board")
                continue
            try:
                deck.assign_user_to_card(deck_board_id, stack_id, new_card_id, nc_user)
            except Exception as e:
                log.warning(f"    No se pudo asignar usuario '{nc_user}': {e}")

        migrated_cards += 1
        time.sleep(0.1)  # Pequeña pausa para no sobrecargar la API de Nextcloud

    log.info(f"  Cards migradas: {migrated_cards} | Saltadas: {skipped_cards}")


    # ══════════════════════════════════
    #  PASO 6 — Migrar los comentarios
    # ══════════════════════════════════
    migrated_comments = 0
    if not skip_comments:  # Saltamos si se usó --skip-comments
        for wekan_card_id, deck_card_id in deck_card_map.items():
            # Ordenamos los comentarios por fecha para mantener el orden cronológico
            for comment in sorted(comments_by_card.get(wekan_card_id, []),
                                  key=lambda x: x.get("createdAt", "")):
                text = comment.get("text", "").strip()
                if not text:
                    continue  # Saltamos comentarios vacíos
                # Obtenemos el autor y la fecha del comentario original
                author_id  = comment.get("userId", "?")
                nc_author  = user_mapping.get(author_id, author_id)
                created_at = str(comment.get("createdAt", ""))[:10]  # Solo la fecha (YYYY-MM-DD)
                # Añadimos un prefijo para indicar que el comentario viene de Wekan
                message = f"*[Migrado de Wekan — {nc_author}, {created_at}]*\n\n{text}"
                try:
                    deck.create_comment(deck_card_id, message)
                    migrated_comments += 1
                except Exception as e:
                    log.warning(f"  No se pudo crear comentario: {e}")
                time.sleep(0.05)  # Pausa entre comentarios

    log.info(f"  Comentarios migrados: {migrated_comments}")

    # Devolvemos un resumen de lo que se ha migrado
    return {
        "board_title":    board_title,
        "deck_board_id":  deck_board_id,
        "stacks":         len(set(deck_stack_map.values())),
        "cards_migrated": migrated_cards,
        "cards_skipped":  skipped_cards,
        "comments":       migrated_comments,
        "labels":         len(deck_label_map),
    }


# ════════════════════════════════════════════
#  PUNTO DE ENTRADA DEL SCRIPT
#  Esto es lo primero que se ejecuta cuando
#  lanzamos el script desde la terminal.
# ════════════════════════════════════════════

def main():
    # Configuramos los argumentos que acepta el script desde la terminal
    parser = argparse.ArgumentParser(
        description="Migración Wekan → Nextcloud Deck v2.1"
    )
    parser.add_argument(
        "--json", type=str, required=True,     # Obligatorio: ruta al fichero JSON
        help="Ruta al fichero JSON exportado desde Wekan"
    )
    parser.add_argument(
        "--dry-run", action="store_true",       # Opcional: modo simulación
        help="Simular sin crear nada en Deck"
    )
    parser.add_argument(
        "--skip-comments", action="store_true", # Opcional: saltar comentarios
        help="No migrar comentarios (más rápido)"
    )
    args = parser.parse_args()  # Leemos los argumentos que escribió el usuario

    if args.dry_run:
        log.info("*** MODO DRY-RUN: no se creará nada en Nextcloud Deck ***")

    # Cargamos los ficheros de datos
    wekan_data   = load_json(args.json)        # El export de Wekan
    user_mapping = load_user_mapping(USER_MAPPING_FILE)  # El mapeo de usuarios

    # Creamos el cliente de Deck con las credenciales configuradas arriba
    log.info(f"Conectando a Nextcloud Deck: {DECK_URL}")
    deck = DeckClient(DECK_URL, DECK_USER, DECK_PASSWORD, dry_run=args.dry_run)

    # Verificamos la conexión (solo en migración real, no en dry-run)
    if not args.dry_run:
        if not deck.test_connection():
            log.error("No se puede conectar a Nextcloud Deck. Verifica URL y credenciales.")
            sys.exit(1)

    # Ejecutamos la migración
    try:
        result = migrate_board(wekan_data, deck, user_mapping,
                               skip_comments=args.skip_comments)
    except Exception as e:
        log.error(f"Error durante la migración: {e}", exc_info=True)
        sys.exit(1)

    # Mostramos el resumen final
    log.info("\n" + "="*60)
    log.info("RESUMEN DE MIGRACIÓN")
    log.info("="*60)
    if result.get("skipped"):
        log.info(f"SALTADO: {result.get('reason')}")
    else:
        log.info(f"✅ '{result.get('board_title')}'")
        log.info(f"   Stacks (columnas): {result.get('stacks')}")
        log.info(f"   Cards migradas:    {result.get('cards_migrated')}")
        log.info(f"   Cards saltadas:    {result.get('cards_skipped')}")
        log.info(f"   Comentarios:       {result.get('comments')}")
        log.info(f"   Labels:            {result.get('labels')}")
    log.info(f"\nLog completo guardado en: migration.log")


# Esta línea asegura que main() solo se ejecuta cuando lanzamos el script
# directamente (no cuando lo importamos desde otro script).
if __name__ == "__main__":
    main()