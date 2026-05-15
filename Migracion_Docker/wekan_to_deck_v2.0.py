#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wekan_to_deck.py — Script de migración de Wekan a Nextcloud Deck
================================================================
Versión 2.0 — Cambio de enfoque: lectura desde fichero JSON local

  CAMBIO PRINCIPAL respecto a v1.1:
    El script ya NO se conecta a la API de Wekan para extraer los datos.
    En su lugar, lee directamente el fichero JSON exportado manualmente
    desde la interfaz web de Wekan (menú del tablero → Exportar).

    Motivo: Wekan usa autenticación LDAP para todos sus usuarios.
    La API REST de Wekan no funciona con usuarios LDAP, requiere un
    usuario admin local que no existe en esta instalación.

    Flujo nuevo:
      1. Exportar el tablero desde Wekan (interfaz web) → fichero JSON
      2. Colocar el JSON en la misma carpeta que este script
      3. Ejecutar: python3 wekan_to_deck.py --json fichero.json
      4. El script lee el JSON y crea el tablero en Nextcloud Deck

  HISTORIAL DE VERSIONES:
    v1.0 — Script inicial con conexión a API de Wekan
    v1.1 — Correcciones: campo labelIds (no labels), endpoint boards correcto
    v2.0 — Nuevo enfoque: lectura desde JSON local, sin conexión a Wekan

Uso:
    # Simular sin crear nada (recomendado siempre primero):
    python3 wekan_to_deck.py --json export-board-XXX.json --dry-run

    # Migración real:
    python3 wekan_to_deck.py --json export-board-XXX.json

    # Sin migrar comentarios (más rápido):
    python3 wekan_to_deck.py --json export-board-XXX.json --skip-comments

Requisitos:
    pip install requests

Ficheros necesarios en la misma carpeta:
    - wekan_to_deck.py         (este script)
    - export-board-XXX.json    (exportado desde Wekan)
    - user_mapping.json        (mapeo wekan_userId → nextcloud_UUID)
"""

import json
import sys
import time
import argparse
import logging
from pathlib import Path

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    print("ERROR: Instala requests primero: pip install requests")
    sys.exit(1)

# ─────────────────────────────────────────────
#  CONFIGURACIÓN — EDITAR ANTES DE EJECUTAR
# ─────────────────────────────────────────────

# Nextcloud Deck
DECK_URL      = "https://at-t1.sandetel.es"   # URL de tu Nextcloud
DECK_USER     = "admin"                         # Tu usuario admin de Nextcloud
DECK_PASSWORD = "tu_password_nc"               # Tu contraseña de Nextcloud

# Fichero de mapeo wekan_userId → nextcloud_UUID
# Generado automáticamente: user_mapping.json
USER_MAPPING_FILE = "user_mapping.json"

# Tipos de boards/cards que NO se deben migrar (de config/const.js de Wekan)
SKIP_BOARD_TYPES = {"template-board", "template-container"}
SKIP_CARD_TYPES  = {"template-card", "template-list",
                    "cardType-linkedCard", "cardType-linkedBoard"}

# Mapeo de colores de Wekan (nombres) a hexadecimal para Deck
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

# Mapeo de colores de board de Wekan a hexadecimal para Deck
WEKAN_BOARD_COLOR_MAP = {
    "belize": "2980B9",     "nephritis": "27AE60",  "pomegranate": "C0392B",
    "pumpkin": "D35400",    "wisteria": "8E44AD",   "moderatepink": "E91E8C",
    "strongcyan": "00BCD4", "limegreen": "8BC34A",  "midnight": "1A237E",
    "dark": "2C3E50",       "relax": "16A085",      "corteza": "795548",
    "clearblue": "1976D2",  "natural": "558B2F",    "modern": "00ACC1",
    "moderndark": "006064", "exodark": "212121",    "cleandark": "37474F",
    "cleanlight": "90A4AE",
}

# Mapeo de permisos Wekan → Deck
# Deck: 0=READ, 1=EDIT, 2=MANAGE, 3=SHARE
def wekan_member_to_deck_permission(member: dict) -> int:
    if member.get("isAdmin"):
        return 2  # MANAGE
    if member.get("isReadOnly") or member.get("isCommentOnly") or \
       member.get("isReadAssignedOnly"):
        return 0  # READ
    return 1      # EDIT

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("migration.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  CLIENTE NEXTCLOUD DECK
# ─────────────────────────────────────────────

class DeckClient:
    """
    Cliente para la API OCS de Nextcloud Deck.
    Documentación: https://deck.readthedocs.io/en/latest/API/
    Endpoint base: /ocs/v2.php/apps/deck/api/v1.0/
    """

    def __init__(self, base_url: str, username: str, password: str,
                 dry_run: bool = False):
        self.base_url = base_url.rstrip("/")
        self.auth     = HTTPBasicAuth(username, password)
        self.dry_run  = dry_run
        self._ocs     = f"{self.base_url}/ocs/v2.php/apps/deck/api/v1.0"

    def _headers(self) -> dict:
        return {
            "OCS-APIRequest": "true",
            "Accept":         "application/json",
            "Content-Type":   "application/json",
        }

    def _get(self, path: str) -> dict:
        resp = requests.get(
            f"{self._ocs}{path}", auth=self.auth,
            headers=self._headers(), timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("ocs", {}).get("data", data)

    def _post(self, path: str, payload: dict) -> dict:
        if self.dry_run:
            log.info(f"  [DRY-RUN] POST {path} → {json.dumps(payload)[:120]}")
            return {"id": abs(hash(str(payload))) % 99999,
                    "title": payload.get("title", "?")}
        resp = requests.post(
            f"{self._ocs}{path}", auth=self.auth,
            headers=self._headers(), json=payload, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("ocs", {}).get("data", data)

    def _put(self, path: str, payload: dict) -> dict:
        if self.dry_run:
            log.info(f"  [DRY-RUN] PUT {path}")
            return {}
        resp = requests.put(
            f"{self._ocs}{path}", auth=self.auth,
            headers=self._headers(), json=payload, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("ocs", {}).get("data", data)

    def test_connection(self):
        """Verifica que la conexión con Nextcloud Deck funciona."""
        try:
            self._get("/boards")
            log.info("Conexión con Nextcloud Deck: ✅ OK")
            return True
        except requests.HTTPError as e:
            log.error(f"Conexión con Nextcloud Deck: ❌ FALLO — {e}")
            return False

    # ── Boards ──
    def create_board(self, title: str, color: str = "0087C1") -> dict:
        """POST /boards — crea un board. Color en hex sin #."""
        return self._post("/boards", {"title": title, "color": color})

    # ── Stacks (= columnas) ──
    def create_stack(self, board_id: int, title: str, order: int = 1) -> dict:
        """POST /boards/:id/stacks — crea una columna."""
        return self._post(
            f"/boards/{board_id}/stacks",
            {"title": title, "order": order}
        )

    # ── Cards ──
    def create_card(self, board_id: int, stack_id: int, title: str,
                    description: str = "", due_date: str = "",
                    order: int = 1) -> dict:
        """POST /boards/:id/stacks/:sid/cards — crea una tarjeta."""
        payload = {"title": title[:255], "type": "plain", "order": order}
        if description:
            payload["description"] = description
        if due_date:
            payload["duedate"] = due_date
        return self._post(
            f"/boards/{board_id}/stacks/{stack_id}/cards", payload
        )

    def assign_label_to_card(self, board_id: int, stack_id: int,
                              card_id: int, label_id: int):
        """POST .../assignLabel — asigna etiqueta a una card."""
        return self._post(
            f"/boards/{board_id}/stacks/{stack_id}/cards/{card_id}/assignLabel",
            {"labelId": label_id}
        )

    def assign_user_to_card(self, board_id: int, stack_id: int,
                             card_id: int, nc_user_id: str):
        """POST .../assignUser — asigna usuario a una card."""
        return self._post(
            f"/boards/{board_id}/stacks/{stack_id}/cards/{card_id}/assignUser",
            {"userId": nc_user_id}
        )

    # ── Comentarios ──
    def create_comment(self, card_id: int, message: str) -> dict:
        """POST /cards/:id/comments — añade comentario."""
        return self._post(
            f"/cards/{card_id}/comments",
            {"message": message[:1000]}
        )

    # ── Labels del board ──
    def create_label(self, board_id: int, title: str, color: str) -> dict:
        """POST /boards/:id/labels — crea etiqueta. Color en hex sin #."""
        return self._post(
            f"/boards/{board_id}/labels",
            {"title": title, "color": color[:6]}
        )

    # ── ACL (permisos) ──
    def add_acl(self, board_id: int, nc_user: str,
                permission: int, is_group: bool = False):
        """PUT /boards/:id/acl — añade usuario al board con permisos."""
        payload = {
            "type":             1 if is_group else 0,
            "participant":      nc_user,
            "permissionEdit":   permission >= 1,
            "permissionShare":  permission >= 3,
            "permissionManage": permission >= 2,
        }
        return self._put(f"/boards/{board_id}/acl", payload)


# ─────────────────────────────────────────────
#  TRANSFORMADORES
# ─────────────────────────────────────────────

def build_description(card: dict,
                       checklists_by_card: dict,
                       checklist_items_by_checklist: dict,
                       custom_fields_meta: dict) -> str:
    """
    Construye la descripción Markdown de la card incorporando:
      1. Descripción original
      2. Checklists → - [x] / - [ ]
      3. Custom fields → tabla Markdown
    """
    parts = []

    # 1. Descripción original
    desc = (card.get("description") or "").strip()
    if desc:
        parts.append(desc)

    # 2. Checklists
    card_id = card.get("_id", "")
    for cl in sorted(checklists_by_card.get(card_id, []),
                     key=lambda x: x.get("sort", 0)):
        cl_id    = cl.get("_id", "")
        cl_title = cl.get("title", "Checklist")
        items    = sorted(
            checklist_items_by_checklist.get(cl_id, []),
            key=lambda x: x.get("sort", 0)
        )
        parts.append(f"\n**✅ {cl_title}**")
        for item in items:
            mark = "- [x]" if item.get("isFinished") else "- [ ]"
            parts.append(f"{mark} {item.get('title', '')}")

    # 3. Custom fields
    card_cfs = card.get("customFields", [])
    if card_cfs:
        filled = [
            (cf, custom_fields_meta.get(cf.get("_id", "")))
            for cf in card_cfs
            if cf.get("value") not in (None, "", [])
        ]
        if filled:
            parts.append("\n**Campos adicionales**")
            parts.append("| Campo | Valor |")
            parts.append("| --- | --- |")
            for cf_val, cf_meta in filled:
                name  = cf_meta.get("name", "?") if cf_meta else "?"
                value = str(cf_val.get("value", ""))
                parts.append(f"| {name} | {value} |")

    return "\n".join(parts)


def build_stack_title(swimlane_title: str, list_title: str,
                       is_default: bool) -> str:
    """Construye el título del stack con aplanado de swimlanes."""
    if is_default:
        return list_title
    return f"{swimlane_title} — {list_title}"


# ─────────────────────────────────────────────
#  CARGA DEL JSON
# ─────────────────────────────────────────────

def load_json(json_path: str) -> dict:
    """Carga y valida el fichero JSON exportado desde Wekan."""
    p = Path(json_path)
    if not p.exists():
        log.error(f"Fichero JSON no encontrado: {json_path}")
        sys.exit(1)

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    fmt = data.get("_format", "")
    if fmt != "wekan-board-1.0.0":
        log.warning(f"Formato inesperado: '{fmt}' (esperado: wekan-board-1.0.0)")
    else:
        log.info(f"JSON cargado: '{data.get('title')}' — formato {fmt} ✅")

    return data


def load_user_mapping(path: str) -> dict:
    """Carga el fichero de mapeo wekan_userId → nextcloud_UUID."""
    p = Path(path)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        log.info(f"User mapping cargado: {len(mapping)} entradas ✅")
        return mapping
    log.warning(f"Fichero '{path}' no encontrado — se usará mapeo 1:1")
    return {}


# ─────────────────────────────────────────────
#  MIGRACIÓN DE UN BOARD
# ─────────────────────────────────────────────

def migrate_board(wekan_data: dict, deck: DeckClient,
                  user_mapping: dict, skip_comments: bool = False) -> dict:
    """Migra el board del JSON a Nextcloud Deck."""

    board_title = wekan_data.get("title", "Sin título")
    board_type  = wekan_data.get("type", "board")

    if board_type in SKIP_BOARD_TYPES:
        log.info(f"SKIP: '{board_title}' es tipo '{board_type}' (template)")
        return {"skipped": True, "reason": "template"}

    log.info(f"\n{'='*60}")
    log.info(f"Migrando: '{board_title}'")
    log.info(f"{'='*60}")

    # ── Índices auxiliares ──
    # Construir mapa listId → nombre MÁS RECIENTE ordenando activities por fecha.
    # Necesario porque los nombres de las listas pueden cambiar (ej: "PROD" → "PRODUCCIÓN (Revisar)").
    # Al ordenar por createdAt ascendente y sobreescribir, el último valor es el más reciente.
    list_names_from_activities = {}
    for a in sorted(wekan_data.get("activities", []), key=lambda x: x.get("createdAt", "")):
        if a.get("listId") and a.get("listName"):
            list_names_from_activities[a["listId"]] = a["listName"]

    # Construir lista completa de listas desde las cards
    all_list_ids = {}
    for card in wekan_data.get("cards", []):
        lid = card.get("listId")
        if lid and lid not in all_list_ids:
            name = list_names_from_activities.get(lid, lid)
            all_list_ids[lid] = {"_id": lid, "title": name}

    swimlanes_raw = wekan_data.get("swimlanes", [])
    # Si no hay colección swimlanes, derivar de las cards
    if not swimlanes_raw:
        sw_ids = set(c.get("swimlaneId") for c in wekan_data.get("cards", []))
        swimlanes_raw = [{"_id": sid, "title": "Default"} for sid in sw_ids if sid]

    non_default_sw = [
        s for s in swimlanes_raw
        if s.get("title", "").lower() not in ("default", "defecto", "")
    ]
    has_real_sw = len(non_default_sw) > 0

    checklists_by_card      = {}
    checklist_items_by_list = {}
    for cl in wekan_data.get("checklists", []):
        checklists_by_card.setdefault(cl.get("cardId"), []).append(cl)
    for item in wekan_data.get("checklistItems", []):
        checklist_items_by_list.setdefault(
            item.get("checklistId"), []
        ).append(item)

    custom_fields_meta = {
        cf["_id"]: cf for cf in wekan_data.get("customFields", [])
    }
    comments_by_card = {}
    for comment in wekan_data.get("comments", []):
        comments_by_card.setdefault(comment.get("cardId"), []).append(comment)

    wekan_labels = {
        lbl["_id"]: lbl for lbl in wekan_data.get("labels", [])
    }

    # ── 1. Crear board en Deck ──
    deck_color = WEKAN_BOARD_COLOR_MAP.get(
        wekan_data.get("color", "belize"), "2980B9"
    )
    deck_board    = deck.create_board(board_title, deck_color)
    deck_board_id = deck_board.get("id")
    log.info(f"  Board creado en Deck: id={deck_board_id}")

    # ── 2. Crear labels ──
    deck_label_map = {}
    for lbl_id, lbl in wekan_labels.items():
        color   = WEKAN_COLOR_MAP.get(lbl.get("color", "blue"), "3498DB")
        new_lbl = deck.create_label(deck_board_id, lbl.get("name", "Label"), color)
        deck_label_map[lbl_id] = new_lbl.get("id")
    log.info(f"  Labels creadas: {len(deck_label_map)}")

    # ── 3. Crear stacks ──
    deck_stack_map = {}
    stack_order    = 1

    # Ordenar listas por orden de aparición en el tablero original
    ordered_lists = list(all_list_ids.values())

    if has_real_sw:
        log.info(f"  Swimlanes detectadas: modo aplanado")
        for sw in swimlanes_raw:
            for lst in ordered_lists:
                sw_title = sw.get("title", "Default")
                is_def   = sw_title.lower() in ("default", "defecto", "")
                title    = build_stack_title(sw_title, lst["title"], is_def)
                stack    = deck.create_stack(deck_board_id, title, stack_order)
                deck_stack_map[(sw["_id"], lst["_id"])] = stack.get("id")
                stack_order += 1
    else:
        log.info(f"  Sin swimlanes adicionales — stacks directos")
        sw_default_id = swimlanes_raw[0]["_id"] if swimlanes_raw else None
        for lst in ordered_lists:
            stack = deck.create_stack(deck_board_id, lst["title"], stack_order)
            deck_stack_map[(sw_default_id, lst["_id"])] = stack.get("id")
            deck_stack_map[(None, lst["_id"])]           = stack.get("id")
            stack_order += 1

    log.info(f"  Stacks creados: {len(set(deck_stack_map.values()))}")

    # ── 4. Crear cards ──
    cards          = wekan_data.get("cards", [])
    migrated_cards = 0
    skipped_cards  = 0
    deck_card_map  = {}

    for card in sorted(cards, key=lambda x: x.get("sort", 0)):
        if card.get("type") in SKIP_CARD_TYPES or card.get("archived"):
            skipped_cards += 1
            continue

        card_id     = card.get("_id")
        list_id     = card.get("listId")
        swimlane_id = card.get("swimlaneId")
        title       = (card.get("title") or "Sin título").strip()

        stack_id = (deck_stack_map.get((swimlane_id, list_id))
                    or deck_stack_map.get((None, list_id)))

        if not stack_id:
            log.warning(f"  SKIP card '{title}': sin stack para "
                        f"swimlane={swimlane_id} list={list_id}")
            skipped_cards += 1
            continue

        description = build_description(
            card, checklists_by_card,
            checklist_items_by_list, custom_fields_meta
        )

        due_date = ""
        if card.get("dueAt"):
            try:
                raw = card["dueAt"]
                due_date = raw.replace("Z", "+00:00") if isinstance(raw, str) else ""
            except Exception:
                due_date = ""

        new_card    = deck.create_card(
            deck_board_id, stack_id, title,
            description=description,
            due_date=due_date,
            order=card.get("sort", 1)
        )
        new_card_id = new_card.get("id")
        deck_card_map[card_id] = new_card_id

        # Asignar etiquetas (campo labelIds en las cards, confirmado en código fuente)
        for lbl_id in (card.get("labelIds") or []):
            if lbl_id in deck_label_map:
                try:
                    deck.assign_label_to_card(
                        deck_board_id, stack_id,
                        new_card_id, deck_label_map[lbl_id]
                    )
                except Exception as e:
                    log.warning(f"    No se pudo asignar label: {e}")

        # Asignar usuarios
        card_users = list(set(
            (card.get("members") or []) + (card.get("assignees") or [])
        ))
        for wekan_uid in card_users:
            nc_user = user_mapping.get(wekan_uid, wekan_uid)
            try:
                deck.assign_user_to_card(
                    deck_board_id, stack_id, new_card_id, nc_user
                )
            except Exception as e:
                log.warning(f"    No se pudo asignar usuario '{nc_user}': {e}")

        migrated_cards += 1
        time.sleep(0.1)

    log.info(f"  Cards migradas: {migrated_cards} | Saltadas: {skipped_cards}")

    # ── 5. Comentarios ──
    migrated_comments = 0
    if not skip_comments:
        for wekan_card_id, deck_card_id in deck_card_map.items():
            for comment in sorted(
                comments_by_card.get(wekan_card_id, []),
                key=lambda x: x.get("createdAt", "")
            ):
                text = comment.get("text", "").strip()
                if not text:
                    continue
                author_id  = comment.get("userId", "?")
                nc_author  = user_mapping.get(author_id, author_id)
                created_at = str(comment.get("createdAt", ""))[:10]
                message    = (f"*[Migrado de Wekan — {nc_author}, "
                              f"{created_at}]*\n\n{text}")
                try:
                    deck.create_comment(deck_card_id, message)
                    migrated_comments += 1
                except Exception as e:
                    log.warning(f"  No se pudo crear comentario: {e}")
                time.sleep(0.05)

    log.info(f"  Comentarios migrados: {migrated_comments}")

    # ── 6. ACL (permisos del board) ──
    for member in wekan_data.get("members", []):
        if not member.get("isActive"):
            continue  # Ignorar miembros inactivos
        wekan_uid  = member.get("userId", "")
        permission = wekan_member_to_deck_permission(member)
        nc_user    = user_mapping.get(wekan_uid, wekan_uid)
        if nc_user:
            try:
                deck.add_acl(deck_board_id, nc_user, permission)
            except Exception as e:
                log.warning(f"  No se pudo añadir ACL para '{nc_user}': {e}")

    activos = sum(1 for m in wekan_data.get("members", []) if m.get("isActive"))
    log.info(f"  ACL configurado para {activos} miembros activos")

    return {
        "board_title":    board_title,
        "deck_board_id":  deck_board_id,
        "stacks":         len(set(deck_stack_map.values())),
        "cards_migrated": migrated_cards,
        "cards_skipped":  skipped_cards,
        "comments":       migrated_comments,
        "labels":         len(deck_label_map),
    }


# ─────────────────────────────────────────────
#  ENTRYPOINT
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Migración Wekan → Nextcloud Deck v2.0 (desde JSON local)"
    )
    parser.add_argument(
        "--json", type=str, required=True,
        help="Ruta al fichero JSON exportado desde Wekan"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simular sin crear nada en Deck (recomendado siempre primero)"
    )
    parser.add_argument(
        "--skip-comments", action="store_true",
        help="No migrar comentarios"
    )
    args = parser.parse_args()

    if args.dry_run:
        log.info("*** MODO DRY-RUN: no se creará nada en Nextcloud Deck ***")

    # Cargar datos
    wekan_data   = load_json(args.json)
    user_mapping = load_user_mapping(USER_MAPPING_FILE)

    # Conectar a Deck
    log.info(f"Conectando a Nextcloud Deck: {DECK_URL}")
    deck = DeckClient(DECK_URL, DECK_USER, DECK_PASSWORD, dry_run=args.dry_run)

    if not args.dry_run:
        if not deck.test_connection():
            log.error("No se puede conectar a Nextcloud Deck. Verifica URL y credenciales.")
            sys.exit(1)

    # Migrar
    try:
        result = migrate_board(
            wekan_data, deck, user_mapping,
            skip_comments=args.skip_comments
        )
    except Exception as e:
        log.error(f"Error durante la migración: {e}", exc_info=True)
        sys.exit(1)

    # Resumen
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


if __name__ == "__main__":
    main()
