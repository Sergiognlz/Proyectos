# =============================================================================
# gestor_prestamos.py
# =============================================================================
# Aplicación de escritorio para gestionar documentos de préstamo de
# equipamiento. Usa tkinter (incluido en Python, sin instalar nada extra).
#
# FASE 1 — Copiar:
#   Detecta PDFs con cualquier variante de "Préstamo" en el nombre y los
#   COPIA a la carpeta Préstamos. El original se mantiene intacto.
#
# FASE 2 — Archivar:
#   Permite filtrar por nombre y seleccionar individualmente qué documentos
#   mover a Archivado! cuando el préstamo se cierra.
#
# Para generar el .exe distribuible (sin necesidad de Python instalado):
#   pip install pyinstaller
#   pyinstaller --onefile --windowed gestor_prestamos.py
#   El ejecutable aparecerá en la carpeta dist/
# =============================================================================

# -- Librerías estándar de Python (no requieren instalación) ------------------
import hashlib      # Para calcular el hash MD5 y verificar integridad de archivos
import json         # Para leer y escribir el archivo de progreso (progreso.json)
import shutil       # Para copiar y mover archivos entre carpetas
import threading    # Para ejecutar tareas pesadas sin bloquear la interfaz gráfica
import tkinter as tk                    # Librería de interfaz gráfica de escritorio
from datetime import datetime           # Para registrar la fecha y hora de cada operación
from pathlib import Path                # Para manejar rutas de archivos de forma segura
from tkinter import messagebox, ttk     # Componentes adicionales de tkinter: diálogos y widgets mejorados


# =============================================================================
# RUTAS DE CARPETAS
# =============================================================================

# Carpeta de origen: donde están los documentos originales de entrega/recogida
ORIGEN    = Path(r"\\archivo.intcdm.sandetel.int\1.CEO\3.TECNOLOGIA_INFORMACION\JATII\GPT\06.SALVAGUARDA\03.Documentos Equipamiento\Entrega, recogida o cesión")

# Carpeta destino principal: donde se copian los documentos de préstamo activos
PRESTAMOS = Path(r"\\archivo.intcdm.sandetel.int\1.CEO\3.TECNOLOGIA_INFORMACION\JATII\GPT\06.SALVAGUARDA\03.Documentos Equipamiento\Préstamos")

# Subcarpeta dentro de Préstamos para documentos ya devueltos o cerrados
ARCHIVADO = Path(r"\\archivo.intcdm.sandetel.int\1.CEO\3.TECNOLOGIA_INFORMACION\JATII\GPT\06.SALVAGUARDA\03.Documentos Equipamiento\Préstamos\Archivado!")


# =============================================================================
# FILTRO DE NOMBRES
# Lista de cadenas que deben aparecer en el nombre del PDF para ser procesado.
# La búsqueda no distingue mayúsculas, minúsculas ni tildes.
# Añadir aquí nuevas variantes si aparecen con el tiempo.
# =============================================================================
PALABRAS_CLAVE = [
    "prestamo",           # Variante sin tilde
    "préstamo",           # Variante con tilde
    "entrega_prestamo",   # Nombre compuesto con guión bajo
    "recogida_prestamo",  # Nombre compuesto con guión bajo
    "entrega prestamo",   # Nombre compuesto con espacio
    "recogida prestamo",  # Nombre compuesto con espacio
]


# =============================================================================
# ARCHIVO DE PROGRESO
# El script guarda el estado de cada archivo en progreso.json, en la misma
# carpeta que el ejecutable, para que no se pierda si se mueve el .exe.
# =============================================================================
ARCHIVO_PROGRESO = Path(__file__).parent / "progreso.json"


# =============================================================================
# ESTADOS POSIBLES DE CADA ARCHIVO
# =============================================================================
PENDIENTE        = "pendiente"
COPIADO          = "copiado"
COMPLETADO       = "completado"
ARCHIVADO_ESTADO = "archivado"
ERROR            = "error"


# =============================================================================
# PALETA DE COLORES DE LA INTERFAZ
# =============================================================================
COLOR_FONDO        = "#F7F6F3"
COLOR_PANEL        = "#FFFFFF"
COLOR_BORDE        = "#E0DED8"
COLOR_TEXTO        = "#1A1A18"
COLOR_TEXTO_MUTED  = "#6B6A65"
COLOR_ACENTO       = "#185FA5"
COLOR_ACENTO_BG    = "#E6F1FB"
COLOR_OK           = "#3B6D11"
COLOR_ERROR        = "#A32D2D"
COLOR_WARN         = "#854F0B"
COLOR_ARCHIVO      = "#534AB7"
COLOR_ARCHIVO_BG   = "#EEEDFE"
COLOR_SELECCION    = "#B5D4F4"   # Azul claro para filas seleccionadas en Fase 2
COLOR_FILA_ALT     = "#F7F6F3"


# =============================================================================
# FUNCIONES DE LÓGICA DE NEGOCIO
# =============================================================================

def coincide_filtro(nombre: str) -> bool:
    """
    Comprueba si el nombre contiene alguna de las palabras clave de préstamo.
    Convierte a minúsculas para comparar sin distinción de mayúsculas ni tildes.
    """
    nombre_lower = nombre.lower()
    encontrado   = False

    for palabra in PALABRAS_CLAVE:
        if palabra in nombre_lower:
            encontrado = True

    return encontrado


def sanear_nombre(nombre: str) -> str:
    """
    Elimina caracteres no permitidos en rutas de Windows sustituyéndolos por _.
    """
    caracteres_invalidos = r'/:*?"<>|'
    nombre_saneado       = nombre

    for caracter in caracteres_invalidos:
        nombre_saneado = nombre_saneado.replace(caracter, "_")

    nombre_saneado = nombre_saneado.strip()

    return nombre_saneado


def destino_unico(carpeta: Path, nombre: str, extension: str) -> Path:
    """
    Genera una ruta destino que no colisione con archivos ya existentes.
    Si 'informe.pdf' existe, prueba 'informe_1.pdf', 'informe_2.pdf', etc.
    """
    candidato = carpeta / f"{nombre}{extension}"
    contador  = 1

    while candidato.exists():
        candidato = carpeta / f"{nombre}_{contador}{extension}"
        contador  = contador + 1

    return candidato


def hash_md5(ruta: Path) -> str:
    """
    Calcula el hash MD5 de un archivo leyéndolo en bloques de 64KB.
    El hash es una huella digital: dos archivos idénticos tienen el mismo hash.
    """
    calculador   = hashlib.md5()
    bloque_bytes = 65536

    with open(ruta, "rb") as archivo:
        bloque = archivo.read(bloque_bytes)

        while bloque != b"":
            calculador.update(bloque)
            bloque = archivo.read(bloque_bytes)

    return calculador.hexdigest()


def cargar_progreso() -> dict:
    """
    Lee progreso.json y devuelve su contenido.
    Si no existe o está dañado, devuelve un diccionario vacío.
    """
    progreso = {}

    if ARCHIVO_PROGRESO.exists():
        try:
            with open(ARCHIVO_PROGRESO, encoding="utf-8") as archivo:
                progreso = json.load(archivo)
        except Exception:
            progreso = {}

    return progreso


def guardar_progreso(progreso: dict) -> None:
    """Guarda el diccionario de progreso en progreso.json."""
    with open(ARCHIVO_PROGRESO, "w", encoding="utf-8") as archivo:
        json.dump(progreso, archivo, ensure_ascii=False, indent=2)


def buscar_pdfs_para_copiar() -> list:
    """
    Busca en ORIGEN (y subcarpetas) los PDFs que coinciden con el filtro
    y que todavía no existen en la carpeta destino.
    La fuente de verdad es la existencia física del archivo en destino,
    no el progreso.json (que solo se usa para reanudar copias interrumpidas).
    Devuelve lista de tuplas (ruta_origen, ruta_destino).
    """
    if not ORIGEN.exists():
        raise FileNotFoundError(f"No se puede acceder a la carpeta origen:\n{ORIGEN}")

    todos_los_pdfs = list(ORIGEN.glob("**/*.pdf"))
    plan           = []

    for pdf in todos_los_pdfs:
        pasa_filtro = coincide_filtro(pdf.stem)

        if pasa_filtro:
            titulo = sanear_nombre(pdf.stem)

            if titulo != "":
                # Comprobamos si el archivo ya existe físicamente en destino
                # Si existe, lo saltamos — si no existe, lo añadimos al plan
                ruta_en_destino = PRESTAMOS / f"{titulo}{pdf.suffix}"

                if not ruta_en_destino.exists():
                    # Limpiamos el estado del JSON para que copiar_con_verificacion
                    # no lo salte por estar marcado como completado anteriormente
                    progreso = cargar_progreso()
                    clave    = str(pdf)
                    if clave in progreso:
                        del progreso[clave]
                        guardar_progreso(progreso)

                    ruta_final = destino_unico(PRESTAMOS, titulo, pdf.suffix)
                    plan.append((pdf, ruta_final))

    return plan


def buscar_pdfs_para_archivar() -> list:
    """
    Lista todos los PDFs en la raíz de PRESTAMOS (sin subcarpetas).
    Devuelve lista de tuplas (ruta_en_prestamos, ruta_en_archivado).
    """
    if not PRESTAMOS.exists():
        raise FileNotFoundError(f"No se puede acceder a la carpeta Préstamos:\n{PRESTAMOS}")

    plan = []

    for pdf in PRESTAMOS.glob("*.pdf"):
        nombre_saneado = sanear_nombre(pdf.stem)
        destino        = destino_unico(ARCHIVADO, nombre_saneado, pdf.suffix)
        plan.append((pdf, destino))

    return plan


def copiar_con_verificacion(origen_pdf: Path, ruta_final: Path,
                             progreso: dict, log_cb) -> bool:
    """
    Copia un archivo de forma segura:
      Paso 1: Copia al destino y guarda el hash del original
      Paso 2: Verifica que el hash de la copia coincide
    Si algo falla hace rollback (borra la copia, el original queda intacto).
    """
    clave  = str(origen_pdf)
    estado = progreso.get(clave, {}).get("estado", PENDIENTE)
    exito  = True

    # Paso 1: Copiar
    if estado == PENDIENTE and exito:
        try:
            hash_origen = hash_md5(origen_pdf)
            shutil.copy2(str(origen_pdf), ruta_final)

            progreso[clave] = {
                "estado":      COPIADO,
                "origen":      str(origen_pdf),
                "destino":     str(ruta_final),
                "hash_origen": hash_origen,
                "timestamp":   datetime.now().isoformat(),
            }
            guardar_progreso(progreso)

        except Exception as excepcion:
            if ruta_final.exists():
                ruta_final.unlink()

            log_cb(f"✗ Error al copiar {origen_pdf.name}: {excepcion}", "error")
            progreso[clave] = {"estado": ERROR, "error": str(excepcion)}
            guardar_progreso(progreso)
            exito = False

        if exito:
            estado = COPIADO

    # Paso 2: Verificar hash
    if estado == COPIADO and exito:
        try:
            hash_original = progreso[clave]["hash_origen"]
            hash_copia    = hash_md5(ruta_final)

            if hash_original != hash_copia:
                raise ValueError("El hash no coincide — la copia puede estar corrupta")

            progreso[clave]["estado"] = COMPLETADO
            guardar_progreso(progreso)
            log_cb(f"✓ Copiado y verificado: {origen_pdf.name}", "ok")

        except Exception as excepcion:
            if ruta_final.exists():
                ruta_final.unlink()
                log_cb("  Rollback: copia eliminada, original intacto.", "warn")

            log_cb(f"✗ Verificación fallida {origen_pdf.name}: {excepcion}", "error")
            progreso[clave]["estado"] = ERROR
            progreso[clave]["error"]  = str(excepcion)
            guardar_progreso(progreso)
            exito = False

    return exito


def archivar_archivo(pdf: Path, destino: Path, log_cb) -> bool:
    """
    Mueve un PDF de Préstamos a Archivado!
    Devuelve True si fue correcto, False si hubo error.
    """
    exito = True

    try:
        ARCHIVADO.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pdf), destino)
        log_cb(f"✓ Archivado: {pdf.name}", "archivo")

    except Exception as excepcion:
        log_cb(f"✗ Error archivando {pdf.name}: {excepcion}", "error")
        exito = False

    return exito


# =============================================================================
# CLASE PRINCIPAL DE LA INTERFAZ GRÁFICA
# =============================================================================

class App(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("Gestor de Documentos — Equipamiento en Préstamo")
        self.resizable(True, True)   # Ventana redimensionable
        self.configure(bg=COLOR_FONDO)

        self.plan_copia   = []       # Lista de archivos pendientes de copiar
        self.plan_archivo = []       # Lista COMPLETA de archivos en Préstamos
        self.en_proceso   = False
        self.modo         = "copia"

        self._construir_ui()
        self._centrar_ventana(860, 1100)

    # =========================================================================
    # CONSTRUCCIÓN DE LA INTERFAZ
    # =========================================================================

    def _construir_ui(self):
        """Construye todos los elementos visuales de la ventana."""

        # Cabecera azul
        header = tk.Frame(self, bg=COLOR_ACENTO, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Gestor de Documentos — Equipamiento en Préstamo",
            bg=COLOR_ACENTO, fg="white",
            font=("Georgia", 12, "bold"), anchor="w"
        ).pack(side="left", padx=16, pady=12)

        # Pestañas de fase
        self.tab_frame = tk.Frame(self, bg=COLOR_FONDO)
        self.tab_frame.pack(fill="x", padx=16, pady=(10, 0))

        self.btn_tab_copia = self._tab_btn(
            self.tab_frame, "① Copiar a Préstamos",
            lambda: self._cambiar_modo("copia"), activo=True
        )
        self.btn_tab_copia.pack(side="left", padx=(0, 4))

        self.btn_tab_arch = self._tab_btn(
            self.tab_frame, "② Archivar devueltos",
            lambda: self._cambiar_modo("archivar"), activo=False
        )
        self.btn_tab_arch.pack(side="left")

        # ── Frame inferior fijo — siempre visible independientemente del tamaño
        # Se empaqueta ANTES que el contenido para que tkinter lo reserve primero
        frame_inferior = tk.Frame(self, bg=COLOR_FONDO)
        frame_inferior.pack(side="bottom", fill="x", padx=16, pady=(0, 10))

        # Barra de progreso en el frame inferior
        self.progress = ttk.Progressbar(frame_inferior, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 8))

        # Botones de acción en el frame inferior
        frame_btns = tk.Frame(frame_inferior, bg=COLOR_FONDO)
        frame_btns.pack(fill="x")

        self.btn_cancelar = self._boton(
            frame_btns, "Cerrar", self._cerrar,
            COLOR_FONDO, COLOR_TEXTO_MUTED, borde=COLOR_BORDE
        )
        self.btn_cancelar.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_accion = self._boton(
            frame_btns, "Copiar archivos →", self._ejecutar,
            COLOR_ACENTO_BG, COLOR_ACENTO, borde=COLOR_ACENTO
        )
        self.btn_accion.pack(side="left", fill="x", expand=True)
        self.btn_accion.config(state="disabled")

        # ── Área de contenido scrollable — ocupa el espacio restante
        contenido = tk.Frame(self, bg=COLOR_FONDO)
        contenido.pack(fill="both", expand=True, padx=16, pady=(10, 0))

        # Panel de rutas
        self.frame_rutas = self._panel(contenido, "Rutas")
        self.frame_rutas.pack(fill="x", pady=(0, 8))
        self._refrescar_rutas()

        # Buscador (solo visible en Fase 2)
        self.frame_buscador = tk.Frame(contenido, bg=COLOR_FONDO)
        self.frame_buscador.pack(fill="x", pady=(0, 8))
        self._construir_buscador(self.frame_buscador)
        self.frame_buscador.pack_forget()   # Ocultamos hasta que se active Fase 2

        # Botón buscar archivos
        self.btn_buscar = self._boton(
            contenido, "🔍  Buscar archivos", self._buscar,
            COLOR_ACENTO, "white"
        )
        self.btn_buscar.pack(fill="x", pady=(0, 8))

        # Tabla de resultados
        frame_tabla = self._panel(contenido, "Archivos encontrados")
        frame_tabla.pack(fill="both", expand=True, pady=(0, 8))
        self._construir_tabla(frame_tabla)

        # Panel de selección (solo visible en Fase 2)
        self.frame_seleccion = tk.Frame(contenido, bg=COLOR_FONDO)
        self.frame_seleccion.pack(fill="x", pady=(0, 4))
        self._construir_controles_seleccion(self.frame_seleccion)
        self.frame_seleccion.pack_forget()   # Ocultamos hasta Fase 2

        # Log de actividad
        frame_log = self._panel(contenido, "Registro de actividad")
        frame_log.pack(fill="x", pady=(0, 8))

        self.txt_log = tk.Text(
            frame_log, height=4,
            bg=COLOR_FONDO, fg=COLOR_TEXTO_MUTED,
            relief="flat", font=("Courier New", 9),
            state="disabled", wrap="word", bd=0
        )
        self.txt_log.pack(fill="x", padx=8, pady=6)
        self.txt_log.tag_config("ok",      foreground=COLOR_OK)
        self.txt_log.tag_config("error",   foreground=COLOR_ERROR)
        self.txt_log.tag_config("warn",    foreground=COLOR_WARN)
        self.txt_log.tag_config("info",    foreground=COLOR_ACENTO)
        self.txt_log.tag_config("archivo", foreground=COLOR_ARCHIVO)

    def _construir_buscador(self, parent):
        """
        Construye el campo de búsqueda por nombre para la Fase 2.
        Filtra la tabla en tiempo real mientras el usuario escribe.
        """
        panel = self._panel(parent, "Filtrar por nombre")
        panel.pack(fill="x")

        fila = tk.Frame(panel, bg=COLOR_PANEL)
        fila.pack(fill="x", padx=10, pady=6)

        tk.Label(
            fila, text="Buscar:",
            bg=COLOR_PANEL, fg=COLOR_TEXTO_MUTED,
            font=("Courier New", 9)
        ).pack(side="left", padx=(0, 8))

        # Variable de tkinter vinculada al campo de texto
        # trace_add llama a _filtrar_tabla cada vez que cambia el valor
        self.var_busqueda = tk.StringVar()
        self.var_busqueda.trace_add("write", self._filtrar_tabla)

        self.entry_busqueda = tk.Entry(
            fila,
            textvariable=self.var_busqueda,
            font=("Courier New", 10),
            bg=COLOR_PANEL, fg=COLOR_TEXTO,
            relief="flat",
            highlightbackground=COLOR_BORDE,
            highlightthickness=1,
            width=40
        )
        self.entry_busqueda.pack(side="left", ipady=4)

        # Botón para limpiar el campo de búsqueda
        self.btn_limpiar_busqueda = self._boton(
            fila, "✕ Limpiar", self._limpiar_busqueda,
            COLOR_FONDO, COLOR_TEXTO_MUTED, borde=COLOR_BORDE
        )
        self.btn_limpiar_busqueda.pack(side="left", padx=(8, 0))

    def _construir_controles_seleccion(self, parent):
        """
        Construye los botones de selección masiva para la Fase 2:
        'Seleccionar todo' y 'Deseleccionar todo'.
        """
        # Contador de seleccionados (se actualiza al seleccionar/deseleccionar)
        self.lbl_seleccion = tk.Label(
            parent,
            text="0 archivo(s) seleccionado(s)",
            bg=COLOR_FONDO, fg=COLOR_TEXTO_MUTED,
            font=("Courier New", 9)
        )
        self.lbl_seleccion.pack(side="left")

        self.btn_sel_todo = self._boton(
            parent, "Seleccionar todo", self._seleccionar_todo,
            COLOR_FONDO, COLOR_ARCHIVO, borde=COLOR_ARCHIVO
        )
        self.btn_sel_todo.pack(side="right", padx=(6, 0))

        self.btn_desel_todo = self._boton(
            parent, "Deseleccionar todo", self._deseleccionar_todo,
            COLOR_FONDO, COLOR_TEXTO_MUTED, borde=COLOR_BORDE
        )
        self.btn_desel_todo.pack(side="right")

    def _tab_btn(self, parent, texto, cmd, activo=False):
        """Crea un botón de pestaña con estilo activo o inactivo."""
        bg_color = COLOR_ACENTO if activo else COLOR_FONDO
        fg_color = "white"      if activo else COLOR_TEXTO_MUTED

        boton = tk.Button(
            parent, text=texto, command=cmd,
            bg=bg_color, fg=fg_color,
            activebackground=COLOR_ACENTO, activeforeground="white",
            relief="flat", font=("Georgia", 9),
            padx=12, pady=6, cursor="hand2",
            highlightbackground=COLOR_BORDE, highlightthickness=1
        )
        return boton

    def _panel(self, parent, titulo: str) -> tk.Frame:
        """Crea un panel con borde, fondo blanco y título."""
        outer = tk.Frame(
            parent, bg=COLOR_PANEL,
            highlightbackground=COLOR_BORDE,
            highlightthickness=1
        )
        tk.Label(
            outer, text=titulo.upper(),
            bg=COLOR_PANEL, fg=COLOR_TEXTO_MUTED,
            font=("Courier New", 8, "bold"), anchor="w"
        ).pack(fill="x", padx=10, pady=(6, 2))

        tk.Frame(outer, bg=COLOR_BORDE, height=1).pack(fill="x")

        return outer

    def _etiqueta_ruta(self, parent, label: str, valor: str):
        """Añade una fila etiqueta + valor dentro de un panel."""
        fila = tk.Frame(parent, bg=COLOR_PANEL)
        fila.pack(fill="x", padx=10, pady=3)

        tk.Label(
            fila, text=label,
            bg=COLOR_PANEL, fg=COLOR_TEXTO_MUTED,
            font=("Courier New", 9), width=9, anchor="w"
        ).pack(side="left")

        tk.Label(
            fila, text=valor,
            bg=COLOR_PANEL, fg=COLOR_TEXTO,
            font=("Courier New", 9), anchor="w",
            wraplength=680, justify="left"
        ).pack(side="left")

    def _boton(self, parent, texto, cmd, bg, fg, borde=None):
        """Crea un botón con el estilo visual de la aplicación."""
        boton = tk.Button(
            parent, text=texto, command=cmd,
            bg=bg, fg=fg,
            activebackground=bg, activeforeground=fg,
            relief="flat", font=("Georgia", 10),
            padx=12, pady=8, cursor="hand2",
            highlightbackground=borde or bg,
            highlightthickness=1 if borde else 0,
        )
        return boton

    def _construir_tabla(self, parent):
        """
        Construye la tabla de resultados con tres columnas.
        En Fase 2 permite selección múltiple (selectmode="extended").
        En Fase 1 solo muestra información (selectmode="none").
        """
        frame = tk.Frame(parent, bg=COLOR_PANEL)
        frame.pack(fill="both", expand=True, padx=8, pady=6)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        estilo.configure(
            "Tabla.Treeview",
            background=COLOR_PANEL,
            fieldbackground=COLOR_PANEL,
            foreground=COLOR_TEXTO,
            font=("Courier New", 9),
            rowheight=24, borderwidth=0
        )
        estilo.configure(
            "Tabla.Treeview.Heading",
            background=COLOR_FONDO,
            foreground=COLOR_TEXTO_MUTED,
            font=("Courier New", 8, "bold"), relief="flat"
        )
        estilo.map(
            "Tabla.Treeview",
            background=[("selected", COLOR_SELECCION)]
        )

        columnas = ("origen", "destino", "estado")
        self.tabla = ttk.Treeview(
            frame, columns=columnas,
            show="headings", height=8,
            style="Tabla.Treeview",
            selectmode="none"   # Empezamos en modo sin selección (Fase 1)
        )

        self.tabla.heading("origen",  text="ARCHIVO ORIGEN")
        self.tabla.heading("destino", text="ARCHIVO DESTINO")
        self.tabla.heading("estado",  text="ESTADO")
        self.tabla.column("origen",  width=310, anchor="w")
        self.tabla.column("destino", width=310, anchor="w")
        self.tabla.column("estado",  width=100, anchor="center")

        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Vinculamos el clic en una fila al método de selección (activo en Fase 2)
        self.tabla.bind("<<TreeviewSelect>>", self._actualizar_contador_seleccion)

        self.tabla.tag_configure("alt",        background=COLOR_FILA_ALT)
        self.tabla.tag_configure("completado", foreground=COLOR_OK)
        self.tabla.tag_configure("error",      foreground=COLOR_ERROR)
        self.tabla.tag_configure("warn",       foreground=COLOR_WARN)
        self.tabla.tag_configure("archivo",    foreground=COLOR_ARCHIVO)

    # =========================================================================
    # MÉTODOS DE COMPORTAMIENTO
    # =========================================================================

    def _cambiar_modo(self, modo: str):
        """
        Cambia entre Fase 1 (copia) y Fase 2 (archivar).
        Muestra u oculta el buscador y los controles de selección según el modo.
        """
        if not self.en_proceso:
            self.modo = modo
            es_copia  = (modo == "copia")

            # Actualizamos el aspecto de las pestañas
            self.btn_tab_copia.config(
                bg=COLOR_ACENTO if es_copia     else COLOR_FONDO,
                fg="white"      if es_copia     else COLOR_TEXTO_MUTED
            )
            self.btn_tab_arch.config(
                bg=COLOR_ACENTO if not es_copia else COLOR_FONDO,
                fg="white"      if not es_copia else COLOR_TEXTO_MUTED
            )

            # Actualizamos el botón de acción
            self.btn_accion.config(
                text="Copiar archivos →"         if es_copia else "Archivar seleccionados →",
                bg=COLOR_ACENTO_BG               if es_copia else COLOR_ARCHIVO_BG,
                fg=COLOR_ACENTO                  if es_copia else COLOR_ARCHIVO,
                highlightbackground=COLOR_ACENTO if es_copia else COLOR_ARCHIVO
            )
            self.btn_accion.config(state="disabled")

            # Mostramos u ocultamos el buscador y controles de selección
            if es_copia:
                self.frame_buscador.pack_forget()
                self.frame_seleccion.pack_forget()
                # En Fase 1 la tabla no permite selección
                self.tabla.configure(selectmode="none")
            else:
                # En Fase 2 mostramos buscador y controles de selección
                self.frame_buscador.pack(fill="x", pady=(0, 8),
                                         before=self.btn_buscar)
                self.frame_seleccion.pack(fill="x", pady=(0, 4))
                # En Fase 2 permitimos selección múltiple con Ctrl+clic
                self.tabla.configure(selectmode="extended")
                self.var_busqueda.set("")   # Limpiamos el buscador al entrar

            self._limpiar_tabla()
            self._refrescar_rutas()

    def _refrescar_rutas(self):
        """Actualiza el panel de rutas según el modo activo."""
        for widget in self.frame_rutas.winfo_children():
            if isinstance(widget, tk.Frame):
                widget.destroy()

        if self.modo == "copia":
            self._etiqueta_ruta(self.frame_rutas, "Origen:",  str(ORIGEN))
            self._etiqueta_ruta(self.frame_rutas, "Destino:", str(PRESTAMOS))
        else:
            self._etiqueta_ruta(self.frame_rutas, "Origen:",  str(PRESTAMOS))
            self._etiqueta_ruta(self.frame_rutas, "Destino:", str(ARCHIVADO))

    def _filtrar_tabla(self, *args):
        """
        Filtra las filas visibles de la tabla según el texto del buscador.
        Se llama automáticamente cada vez que el usuario escribe en el campo.
        Muestra solo los archivos cuyo nombre contiene el texto buscado.
        Solo activo en Fase 2.
        """
        if self.modo == "archivar":
            texto_busqueda  = self.var_busqueda.get().lower()

            self._limpiar_tabla()

            for indice, (origen, destino) in enumerate(self.plan_archivo):
                nombre_lower    = origen.name.lower()
                texto_vacio     = (texto_busqueda == "")
                nombre_coincide = (texto_busqueda in nombre_lower)

                if texto_vacio or nombre_coincide:
                    tag_fila = "alt" if indice % 2 != 0 else ""
                    tags     = (tag_fila,) if tag_fila != "" else ()
                    self.tabla.insert("", "end",
                                      values=(origen.name, destino.name, "pendiente"),
                                      tags=tags)

            self._actualizar_contador_seleccion()

    def _limpiar_busqueda(self):
        """Limpia el campo de búsqueda, lo que recarga todas las filas."""
        self.var_busqueda.set("")
        self.entry_busqueda.focus()

    def _seleccionar_todo(self):
        """Selecciona todas las filas visibles en la tabla."""
        todas_las_filas = self.tabla.get_children()

        for fila in todas_las_filas:
            self.tabla.selection_add(fila)

        self._actualizar_contador_seleccion()

    def _deseleccionar_todo(self):
        """Quita la selección de todas las filas."""
        self.tabla.selection_remove(self.tabla.get_children())
        self._actualizar_contador_seleccion()

    def _actualizar_contador_seleccion(self, event=None):
        """
        Actualiza la etiqueta que muestra cuántos archivos están seleccionados.
        Se llama al seleccionar/deseleccionar filas o al filtrar la tabla.
        """
        if self.modo == "archivar":
            n_seleccionados = len(self.tabla.selection())
            self.lbl_seleccion.config(
                text=f"{n_seleccionados} archivo(s) seleccionado(s)"
            )

    def _buscar(self):
        """Lanza la búsqueda en un hilo separado para no bloquear la UI."""
        self.btn_buscar.config(state="disabled", text="Buscando…")
        self._log("Buscando archivos…", "info")

        hilo = threading.Thread(target=self._buscar_hilo, daemon=True)
        hilo.start()

    def _buscar_hilo(self):
        """
        Ejecutado en hilo secundario.
        Llama a la función de búsqueda del modo activo y pasa el resultado a la UI.
        """
        try:
            if self.modo == "copia":
                plan = buscar_pdfs_para_copiar()
            else:
                plan = buscar_pdfs_para_archivar()

            self.after(0, lambda p=plan: self._mostrar_plan(p))

        except Exception as excepcion:
            mensaje = str(excepcion)
            self.after(0, lambda m=mensaje: self._log(f"✗ {m}", "error"))

        finally:
            # Siempre reactivamos el botón, haya archivos, no haya, o falle algo
            self.after(0, lambda: self.btn_buscar.config(
                state="normal", text="🔍  Buscar archivos"))

    def _mostrar_plan(self, plan: list):
        """
        Rellena la tabla con el plan de archivos encontrado.
        En Fase 2 también rellena el buscador y activa la selección.
        """
        if self.modo == "copia":
            self.plan_copia   = plan
        else:
            self.plan_archivo = plan

        self._limpiar_tabla()

        if len(plan) == 0:
            mensaje = ("No hay archivos pendientes de copiar."
                       if self.modo == "copia"
                       else "No hay archivos en la carpeta Préstamos.")
            self._log(mensaje, "warn")
            self.btn_accion.config(state="disabled")

        else:
            if self.modo == "copia":
                for indice, (origen, destino) in enumerate(plan):
                    renombrado  = (origen.stem != destino.stem)
                    tag_fila    = "alt"  if indice % 2 != 0 else ""
                    tag_estado  = "warn" if renombrado       else ""
                    tags        = tuple(t for t in (tag_fila, tag_estado) if t != "")
                    estado_txt  = "⚠ renombrado" if renombrado else "pendiente"

                    self.tabla.insert("", "end",
                                      values=(origen.name, destino.name, estado_txt),
                                      tags=tags)

                ya_completados = sum(
                    1 for v in cargar_progreso().values()
                    if v.get("estado") == COMPLETADO
                )
                sufijo = (f"  |  {ya_completados} ya copiados anteriormente."
                          if ya_completados > 0 else "")
                self._log(f"✓ {len(plan)} archivo(s) encontrado(s){sufijo}", "ok")

            else:
                self._filtrar_tabla()
                self._log(
                    f"✓ {len(plan)} archivo(s) en Préstamos. "
                    "Filtra por nombre y selecciona los que quieres archivar.",
                    "ok"
                )

            self.btn_buscar.config(state="normal", text="🔍  Buscar archivos")
            self.btn_accion.config(state="normal")

    def _ejecutar(self):
        """
        Lanza la operación principal.
        En Fase 2 solo procesa los archivos seleccionados en la tabla.
        """
        if self.modo == "copia":
            plan = self.plan_copia

        else:
            filas_seleccionadas = self.tabla.selection()

            if len(filas_seleccionadas) == 0:
                self._log("Selecciona al menos un archivo para archivar.", "warn")
                return

            nombres_seleccionados = set()
            for fila_id in filas_seleccionadas:
                nombre_origen = self.tabla.item(fila_id, "values")[0]
                nombres_seleccionados.add(nombre_origen)

            plan = [
                (origen, destino)
                for origen, destino in self.plan_archivo
                if origen.name in nombres_seleccionados
            ]

        if len(plan) == 0:
            return

        continuar = True
        if self.modo == "archivar":
            continuar = messagebox.askyesno(
                "Confirmar archivo",
                f"Se moverán {len(plan)} archivo(s) a la carpeta Archivado!.\n\n"
                "Esta acción no se puede deshacer desde esta aplicación.\n\n"
                "¿Continuar?"
            )

        if continuar:
            self.btn_accion.config(state="disabled", text="Procesando…")
            self.btn_buscar.config(state="disabled")
            self.en_proceso = True
            self.progress["maximum"] = len(plan)
            self.progress["value"]   = 0

            hilo = threading.Thread(
                target=self._ejecutar_hilo,
                args=(plan,),
                daemon=True
            )
            hilo.start()

    def _ejecutar_hilo(self, plan: list):
        """
        Ejecutado en hilo secundario.
        Procesa cada archivo del plan y actualiza la tabla y la barra de progreso.
        """
        ok     = 0
        fallos = 0

        if self.modo == "copia":
            PRESTAMOS.mkdir(parents=True, exist_ok=True)
            progreso = cargar_progreso()

            for indice, (origen, destino) in enumerate(plan):
                exito         = copiar_con_verificacion(origen, destino, progreso, self._log)
                tag_resultado = "completado" if exito else "error"
                txt_resultado = "✓ copiado"  if exito else "✗ error"

                if exito:
                    ok     = ok + 1
                else:
                    fallos = fallos + 1

                self._actualizar_fila(indice, txt_resultado, tag_resultado, plan)
                valor_progreso = indice + 1
                self.after(0, lambda v=valor_progreso: self.progress.configure(value=v))

        else:
            ARCHIVADO.mkdir(parents=True, exist_ok=True)

            for indice, (origen, destino) in enumerate(plan):
                exito         = archivar_archivo(origen, destino, self._log)
                tag_resultado = "archivo"     if exito else "error"
                txt_resultado = "✓ archivado" if exito else "✗ error"

                if exito:
                    ok     = ok + 1
                else:
                    fallos = fallos + 1

                self._actualizar_fila(indice, txt_resultado, tag_resultado, plan)
                valor_progreso = indice + 1
                self.after(0, lambda v=valor_progreso: self.progress.configure(value=v))

        accion    = "copiados" if self.modo == "copia" else "archivados"
        resumen   = f"Completado — {accion.capitalize()}: {ok}"
        nivel_log = "ok"

        if fallos > 0:
            resumen   = resumen + f"  |  Errores: {fallos} (vuelve a buscar para reintentar)"
            nivel_log = "warn"

        self.after(0, lambda: self._log(resumen, nivel_log))

        texto_btn = ("Copiar archivos →" if self.modo == "copia"
                     else "Archivar seleccionados →")
        self.after(0, lambda: self.btn_buscar.config(
            state="normal", text="🔍  Buscar archivos"))
        self.after(0, lambda: self.btn_accion.config(
            state="disabled", text=texto_btn))

        self.en_proceso = False

    def _cerrar(self):
        """Cierra la aplicación si no hay proceso en curso."""
        if self.en_proceso:
            self._log("El proceso está en curso, espera a que termine.", "warn")
        else:
            self.destroy()

    # =========================================================================
    # MÉTODOS AUXILIARES DE UI
    # =========================================================================

    def _limpiar_tabla(self):
        """Elimina todas las filas de la tabla."""
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)

    def _log(self, mensaje: str, nivel: str = ""):
        """
        Añade una línea al log con marca de tiempo y color según el nivel.
        Siempre se ejecuta en el hilo principal mediante self.after().
        """
        def _escribir():
            marca_tiempo = datetime.now().strftime("%H:%M:%S")
            self.txt_log.config(state="normal")
            self.txt_log.insert("end", f"[{marca_tiempo}] {mensaje}\n", nivel)
            self.txt_log.see("end")
            self.txt_log.config(state="disabled")

        self.after(0, _escribir)

    def _actualizar_fila(self, indice: int, estado_txt: str, tag: str, plan: list):
        """
        Actualiza el estado de una fila en la tabla buscándola por el nombre
        del archivo en el plan concreto que se está ejecutando.
        Recibe el plan como parámetro para no confundir el plan filtrado
        por selección con el plan completo de archivos.
        """
        def _update():
            nombre_plan = plan[indice][0].name

            for fila_id in self.tabla.get_children():
                valores = list(self.tabla.item(fila_id, "values"))

                if valores[0] == nombre_plan:
                    valores[2] = estado_txt
                    self.tabla.item(fila_id, values=valores, tags=(tag,))

        self.after(0, _update)

    def _centrar_ventana(self, ancho: int, alto: int):
        """Centra la ventana en la pantalla."""
        self.update_idletasks()
        pos_x = (self.winfo_screenwidth()  - ancho) // 2
        pos_y = (self.winfo_screenheight() - alto)  // 2
        self.geometry(f"{ancho}x{alto}+{pos_x}+{pos_y}")


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================
if __name__ == "__main__":
    # Corrige el escalado en pantallas de alta resolución (HiDPI) en Windows
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)

    app = App()
    app.mainloop()