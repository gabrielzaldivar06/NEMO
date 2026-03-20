#!/usr/bin/env python3
"""
NEMO V1.0 — Neural Engine Memory Observer
==========================================
Icono premium en la bandeja del sistema que monitoriza en tiempo real:
  • Embeddings (LM Studio)
  • Reranker (llama-server)
  • Base de datos SQLite

Uso:
    python status_monitor.py

Requisitos:
    pip install pystray pillow customtkinter
"""

import math
import time
import json
import sqlite3
import threading
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

import pystray
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── Branding ──────────────────────────────────────────────────────────────────
APP_NAME    = "NEMO"
APP_VERSION = "V1.0"
APP_FULL    = f"{APP_NAME} {APP_VERSION}"
APP_SUB     = "Neural Engine Memory Observer"

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "embedding_config.json"
DATA_DIR    = Path.home() / ".ai_memory"
MEM_DB      = DATA_DIR / "ai_memories.db"
CONV_DB     = DATA_DIR / "conversations.db"

# ── Intervalos ────────────────────────────────────────────────────────────────
POLL_SECONDS = 30
HTTP_TIMEOUT = 3

# ── Paleta premium (Catppuccin Mocha + accents) ───────────────────────────────
C = {
    "base":    "#1e1e2e",
    "mantle":  "#181825",
    "crust":   "#11111b",
    "surface0": "#313244",
    "surface1": "#45475a",
    "surface2": "#585b70",
    "overlay0": "#6c7086",
    "text":    "#cdd6f4",
    "subtext": "#a6adc8",
    "blue":    "#89b4fa",
    "sapphire": "#74c7ec",
    "sky":     "#89dceb",
    "green":   "#a6e3a1",
    "yellow":  "#f9e2af",
    "peach":   "#fab387",
    "red":     "#f38ba8",
    "mauve":   "#cba6f7",
    "pink":    "#f5c2e7",
    # accent gradients for icon
    "grad_a":  "#7c3aed",    # violeta (from)
    "grad_b":  "#2563eb",    # azul (to)
    "ok_glow":    "#a6e3a1",
    "warn_glow":  "#f9e2af",
    "error_glow": "#f38ba8",
}

STATUS_COLOR = {
    "ok":      C["green"],
    "warn":    C["yellow"],
    "error":   C["red"],
    "unknown": C["overlay0"],
}
STATUS_LABEL = {
    "ok":      "Todos los servicios activos",
    "warn":    "Servicio parcial o degradado",
    "error":   "Fallo crítico detectado",
    "unknown": "Comprobando servicios…",
}
STATUS_SYMBOL = {
    "ok":      "✦",
    "warn":    "◈",
    "error":   "✖",
    "unknown": "◌",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Generador de icono premium (PIL)
# ═══════════════════════════════════════════════════════════════════════════════

def _make_icon(status: str) -> Image.Image:
    """Icono 128×128 con fondo oscuro, hexágono degradado vibrante y letra N."""
    SIZE   = 128
    MARGIN = 8
    img    = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)

    glow_colors = {
        "ok":      (166, 227, 161),
        "warn":    (249, 226, 175),
        "error":   (243, 139, 168),
        "unknown": (108, 112, 134),
    }
    main_colors = {
        "ok":      [(124, 58, 237), (34, 197, 94)],
        "warn":    [(234, 88,  12), (250, 204, 21)],
        "error":   [(220, 38,  38), (244, 63, 94)],
        "unknown": [(75,  85,  99), (107, 114, 128)],
    }

    # ── Sombra exterior ────────────────────────────────────────────────────────
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sd     = ImageDraw.Draw(shadow)
    glow   = glow_colors.get(status, (108, 112, 134))
    for r in range(4, 0, -1):
        alpha = 40 * r
        sd.ellipse((MARGIN - r * 3, MARGIN - r * 3,
                    SIZE - MARGIN + r * 3, SIZE - MARGIN + r * 3),
                   fill=(*glow, alpha))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)

    # ── Hexágono de fondo ──────────────────────────────────────────────────────
    cx, cy = SIZE // 2, SIZE // 2
    R = SIZE // 2 - MARGIN
    hex_pts = [
        (int(cx + R * math.cos(math.radians(60 * i - 30))),
         int(cy + R * math.sin(math.radians(60 * i - 30))))
        for i in range(6)
    ]
    draw.polygon(hex_pts, fill=(*[int(x * 0.9) for x in [30, 30, 46]], 255))

    # ── Degradado radial sobre el hexágono ────────────────────────────────────
    grad_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad_layer)
    c1, c2 = main_colors.get(status, main_colors["unknown"])
    steps = 40
    for i in range(steps, 0, -1):
        t     = i / steps
        alpha = int(220 * (1 - t * 0.6))
        r_col = int(c1[0] * (1 - t) + c2[0] * t)
        g_col = int(c1[1] * (1 - t) + c2[1] * t)
        b_col = int(c1[2] * (1 - t) + c2[2] * t)
        rad   = int(R * t)
        gd.ellipse((cx - rad, cy - rad, cx + rad, cy + rad),
                   fill=(r_col, g_col, b_col, alpha))

    # Aplicar clip hexagonal al gradiente
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).polygon(hex_pts, fill=255)
    grad_layer.putalpha(mask)
    img = Image.alpha_composite(img, grad_layer)
    draw = ImageDraw.Draw(img)

    # ── Borde hexagonal brillante ──────────────────────────────────────────────
    draw.polygon(hex_pts, outline=(255, 255, 255, 60), width=2)

    # ── Letra "N" central ─────────────────────────────────────────────────────
    try:
        font = ImageFont.truetype("arialbd.ttf", 58)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", 58)
        except Exception:
            font = ImageFont.load_default()

    letter = "N"
    bbox   = draw.textbbox((0, 0), letter, font=font)
    lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = cx - lw // 2 - bbox[0]
    ty = cy - lh // 2 - bbox[1] - 2

    # Sombra de texto
    draw.text((tx + 2, ty + 2), letter, font=font, fill=(0, 0, 0, 120))
    # Texto blanco
    draw.text((tx, ty), letter, font=font, fill=(255, 255, 255, 240))

    # ── Brillo top-left ────────────────────────────────────────────────────────
    draw.ellipse((MARGIN + 12, MARGIN + 10, MARGIN + 38, MARGIN + 30),
                 fill=(255, 255, 255, 35))

    # ── Dot de estado (esquina inferior derecha) ───────────────────────────────
    dot_color = glow_colors.get(status, (108, 112, 134))
    dot_x, dot_y = SIZE - MARGIN - 14, SIZE - MARGIN - 14
    draw.ellipse((dot_x - 9, dot_y - 9, dot_x + 9, dot_y + 9),
                 fill=(20, 20, 30, 200))
    draw.ellipse((dot_x - 7, dot_y - 7, dot_x + 7, dot_y + 7),
                 fill=(*dot_color, 255))

    return img.resize((64, 64), Image.LANCZOS)


# ═══════════════════════════════════════════════════════════════════════════════
# Comprobaciones de servicios
# ═══════════════════════════════════════════════════════════════════════════════

def _load_embed_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def check_lmstudio(cfg: dict) -> dict:
    try:
        url = (cfg.get("lm_studio", {}).get("base_url", "http://localhost:1234")
               + "/v1/models")
        req = urllib.request.Request(url, headers={"User-Agent": "NEMO/1.0"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            data   = json.loads(r.read())
            models = [m["id"] for m in data.get("data", [])]
            label  = models[0][:32] + "…" if models and len(models[0]) > 32 else (models[0] if models else "sin modelos")
            return {"status": "ok", "msg": label, "detail": f"{len(models)} modelo(s) cargado(s)"}
    except urllib.error.URLError:
        return {"status": "error", "msg": "Sin conexión", "detail": "LM Studio no responde en puerto 1234"}
    except Exception as e:
        return {"status": "warn", "msg": str(e)[:40], "detail": "Respuesta inesperada"}


def check_reranker(cfg: dict) -> dict:
    """Check if BGE-reranker is loaded in LM Studio (port 1234)."""
    try:
        url = "http://localhost:1234/v1/models"
        req = urllib.request.Request(url, headers={"User-Agent": "NEMO/1.0"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            models = [m.get("id", "") for m in data.get("data", [])]
            loaded = any("rerank" in m.lower() or "bge" in m.lower() for m in models)
            if loaded:
                return {"status": "ok", "msg": "BGE-reranker activo · :1234", "detail": str(models)}
            return {"status": "warn", "msg": "No cargado (run start_reranker.bat)", "detail": "Ejecuta: lms load text-embedding-bge-reranker-v2-m3 -y"}
    except urllib.error.URLError:
        return {"status": "warn", "msg": "LM Studio offline", "detail": "Puerto 1234 no responde"}
    except Exception as e:
        return {"status": "warn", "msg": str(e)[:40], "detail": ""}


def check_database() -> dict:
    rows = []
    for db, name in ((MEM_DB, "ai_memories"), (CONV_DB, "conversations")):
        if not db.exists():
            rows.append(f"{name}: no inicializada")
            continue
        try:
            con    = sqlite3.connect(str(db), timeout=2)
            tables = con.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
            con.close()
            rows.append(f"{name}: {tables} tabla(s)")
        except Exception as e:
            return {"status": "error", "msg": f"{name} corrupta", "detail": str(e)}
    status = "ok" if all("no inicializada" not in r for r in rows) else "warn"
    return {"status": status, "msg": "; ".join(rows), "detail": str(DATA_DIR)}


def _db_stats() -> list[tuple[str, str]]:
    """Devuelve lista de (nombre_tabla, conteo) para todas las tablas."""
    rows = []
    for db in (MEM_DB, CONV_DB):
        if not db.exists():
            continue
        try:
            con    = sqlite3.connect(str(db), timeout=2)
            tables = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            for tbl in tables:
                try:
                    c = con.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]
                    rows.append((tbl, str(c)))
                except Exception:
                    pass
            con.close()
        except Exception:
            pass
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# Estado global
# ═══════════════════════════════════════════════════════════════════════════════

class MonitorState:
    def __init__(self):
        self.embed   = {"status": "unknown", "msg": "Sin comprobar", "detail": ""}
        self.rerank  = {"status": "unknown", "msg": "Sin comprobar", "detail": ""}
        self.db      = {"status": "unknown", "msg": "Sin comprobar", "detail": ""}
        self.last_ok = None
        self.lock    = threading.Lock()

    def overall(self) -> str:
        statuses = [self.embed["status"], self.rerank["status"], self.db["status"]]
        if "error"   in statuses: return "error"
        if "warn"    in statuses: return "warn"
        if "unknown" in statuses: return "warn"
        return "ok"

    def update(self, embed, rerank, db):
        with self.lock:
            self.embed  = embed
            self.rerank = rerank
            self.db     = db
            if self.overall() == "ok":
                self.last_ok = datetime.now()

    def tooltip(self) -> str:
        lbl = STATUS_LABEL.get(self.overall(), "")
        ts  = self.last_ok.strftime("%H:%M:%S") if self.last_ok else "—"
        return f"{APP_FULL} · {lbl}\nÚltimo OK: {ts}"


STATE = MonitorState()


# ═══════════════════════════════════════════════════════════════════════════════
# Hilo de polling
# ═══════════════════════════════════════════════════════════════════════════════

def _poll(icon: pystray.Icon):
    while True:
        cfg = _load_embed_config()
        STATE.update(check_lmstudio(cfg), check_reranker(cfg), check_database())
        icon.icon  = _make_icon(STATE.overall())
        icon.title = STATE.tooltip()
        icon.menu  = _build_menu(icon)
        time.sleep(POLL_SECONDS)


# ═══════════════════════════════════════════════════════════════════════════════
# Ventana premium (CustomTkinter)
# ═══════════════════════════════════════════════════════════════════════════════

# Referencia global a la ventana activa (evita múltiples instancias)
_win_ref: "ctk.CTk | None" = None
_win_lock = threading.Lock()


def _build_window() -> "ctk.CTk":
    """Construye y devuelve la ventana CTk. Debe llamarse desde hilo propio."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    win = ctk.CTk()
    win.title(f"{APP_FULL} — Estado del sistema")
    win.geometry("520x580")
    win.resizable(False, False)
    win.configure(fg_color=C["base"])

    # Icono de la ventana
    try:
        from PIL import ImageTk
        _ik = ImageTk.PhotoImage(_make_icon(STATE.overall()), master=win)
        win.iconphoto(True, _ik)
        win._nemo_icon_ref = _ik          # evita que GC lo elimine
    except Exception:
        pass

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(win, fg_color=C["mantle"], corner_radius=0, height=90)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)

    hdr_inner = ctk.CTkFrame(hdr, fg_color="transparent")
    hdr_inner.place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(hdr_inner, text=APP_NAME,
                 font=ctk.CTkFont("Segoe UI", 32, "bold"),
                 text_color=C["blue"]).pack(side="left", padx=(0, 8))
    ctk.CTkLabel(hdr_inner, text=APP_VERSION,
                 font=ctk.CTkFont("Segoe UI", 16),
                 text_color=C["subtext"]).pack(side="left", pady=(10, 0))

    ctk.CTkLabel(hdr, text=APP_SUB,
                 font=ctk.CTkFont("Segoe UI", 10),
                 text_color=C["overlay0"]).place(relx=0.5, rely=0.85, anchor="center")

    # ── Estado global ─────────────────────────────────────────────────────────
    overall = STATE.overall()
    glbl = ctk.CTkFrame(win, fg_color=C["surface0"], corner_radius=12, height=52)
    glbl.pack(fill="x", padx=20, pady=(14, 6))
    glbl.pack_propagate(False)

    sym_color = STATUS_COLOR.get(overall, C["overlay0"])
    sym_label = STATUS_SYMBOL.get(overall, "?")
    ctk.CTkLabel(glbl, text=sym_label,
                 font=ctk.CTkFont("Segoe UI", 20),
                 text_color=sym_color).place(relx=0.04, rely=0.5, anchor="w")

    msg = STATUS_LABEL.get(overall, "")
    ctk.CTkLabel(glbl, text=msg,
                 font=ctk.CTkFont("Segoe UI", 12, "bold"),
                 text_color=sym_color).place(relx=0.12, rely=0.5, anchor="w")

    ts_str = STATE.last_ok.strftime("%d/%m/%Y  %H:%M:%S") if STATE.last_ok else "—"
    ctk.CTkLabel(glbl, text=f"Último OK: {ts_str}",
                 font=ctk.CTkFont("Segoe UI", 10),
                 text_color=C["overlay0"]).place(relx=0.98, rely=0.5, anchor="e")

    # ── Cards de servicio ─────────────────────────────────────────────────────
    services = [
        ("⬡  Embeddings",  "LM Studio · localhost:1234",   STATE.embed),
        ("⬡  Reranker",    "llama-server · localhost:8080", STATE.rerank),
        ("⬡  Base datos",  str(DATA_DIR),                   STATE.db),
    ]

    for title, _subtitle, svc in services:
        card = ctk.CTkFrame(win, fg_color=C["mantle"], corner_radius=12, height=72)
        card.pack(fill="x", padx=20, pady=4)
        card.pack_propagate(False)

        sc  = STATUS_COLOR.get(svc["status"], C["overlay0"])
        bar = ctk.CTkFrame(card, fg_color=sc, corner_radius=4, width=4)
        bar.place(relx=0, rely=0.1, relheight=0.8)
        led = ctk.CTkFrame(card, fg_color=sc, corner_radius=100, width=10, height=10)
        led.place(relx=0.04, rely=0.5, anchor="center")

        ctk.CTkLabel(card, text=title,
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=C["text"]).place(relx=0.09, rely=0.28, anchor="w")
        ctk.CTkLabel(card, text=svc["msg"],
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C["subtext"]).place(relx=0.09, rely=0.60, anchor="w")
        ctk.CTkLabel(card, text=svc["detail"][:48],
                     font=ctk.CTkFont("Consolas", 9),
                     text_color=C["overlay0"]).place(relx=0.99, rely=0.5, anchor="e")

    # ── Tabla de base de datos ────────────────────────────────────────────────
    ctk.CTkLabel(win, text="  Registros almacenados",
                 font=ctk.CTkFont("Segoe UI", 11, "bold"),
                 text_color=C["subtext"],
                 anchor="w").pack(fill="x", padx=20, pady=(12, 2))

    db_frame = ctk.CTkScrollableFrame(win, fg_color=C["crust"],
                                      corner_radius=12, height=120)
    db_frame.pack(fill="x", padx=20, pady=(0, 10))

    stats = _db_stats()
    if stats:
        for i, (tbl, cnt) in enumerate(stats):
            row_color = C["surface0"] if i % 2 == 0 else "transparent"
            row = ctk.CTkFrame(db_frame, fg_color=row_color, corner_radius=6, height=28)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=f"  {tbl}",
                         font=ctk.CTkFont("Consolas", 10),
                         text_color=C["text"],
                         anchor="w").place(relx=0, rely=0.5, anchor="w")
            ctk.CTkLabel(row, text=f"{cnt}  ",
                         font=ctk.CTkFont("Consolas", 10, "bold"),
                         text_color=C["sapphire"],
                         anchor="e").place(relx=1, rely=0.5, anchor="e")
    else:
        ctk.CTkLabel(db_frame, text="  Sin registros o base de datos no inicializada",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C["overlay0"]).pack(anchor="w", pady=8, padx=8)

    # ── Footer / botones ──────────────────────────────────────────────────────
    btn_row = ctk.CTkFrame(win, fg_color="transparent")
    btn_row.pack(pady=8)

    # Flag para distinguir refresh de cierre normal
    win._nemo_refresh = False

    def _on_refresh():
        win._nemo_refresh = True
        win.destroy()

    def _on_close():
        win._nemo_refresh = False
        win.destroy()

    # X del SO y botón Cerrar hacen lo mismo
    win.protocol("WM_DELETE_WINDOW", _on_close)

    ctk.CTkButton(btn_row, text="↻  Actualizar", command=_on_refresh,
                  fg_color=C["surface0"], hover_color=C["surface1"],
                  text_color=C["text"],
                  font=ctk.CTkFont("Segoe UI", 11),
                  corner_radius=8, width=130, height=34).pack(side="left", padx=6)

    ctk.CTkButton(btn_row, text="—  Minimizar", command=win.iconify,
                  fg_color=C["surface0"], hover_color=C["surface1"],
                  text_color=C["text"],
                  font=ctk.CTkFont("Segoe UI", 11),
                  corner_radius=8, width=130, height=34).pack(side="left", padx=6)

    ctk.CTkButton(btn_row, text="✕  Cerrar", command=_on_close,
                  fg_color=C["surface0"], hover_color=C["surface1"],
                  text_color=C["text"],
                  font=ctk.CTkFont("Segoe UI", 11),
                  corner_radius=8, width=130, height=34).pack(side="left", padx=6)

    ctk.CTkLabel(win, text=f"{APP_FULL}  ·  Neural Engine Memory Observer",
                 font=ctk.CTkFont("Segoe UI", 8),
                 text_color=C["overlay0"]).pack(pady=(0, 6))

    return win


def _run_window_thread():
    """Corre en su propio hilo daemon. Gestiona el ciclo build → mainloop → refresh."""
    global _win_ref
    while True:
        win = _build_window()
        with _win_lock:
            _win_ref = win
        win.mainloop()
        should_refresh = getattr(win, "_nemo_refresh", False)
        with _win_lock:
            _win_ref = None
        if not should_refresh:
            break   # cierre normal: terminar el hilo
        # refresh: volver a construir la ventana


def _open_details(icon=None, item=None):
    """Llamado desde el menú de bandeja. Siempre en su propio daemon-thread."""
    global _win_ref
    with _win_lock:
        existing = _win_ref

    if existing is not None:
        # Ya hay una ventana abierta: restaurar y traer al frente
        try:
            existing.after(0, lambda: (existing.deiconify(), existing.lift(),
                                       existing.focus_force()))
        except Exception:
            pass
        return

    t = threading.Thread(target=_run_window_thread, daemon=True, name="nemo-window")
    t.start()


def _pil_to_tk(root, img: Image.Image):
    """Convierte PIL Image a PhotoImage para iconphoto."""
    from PIL import ImageTk
    return ImageTk.PhotoImage(img, master=root)


# ═══════════════════════════════════════════════════════════════════════════════
# Menú de bandeja
# ═══════════════════════════════════════════════════════════════════════════════

def _build_menu(icon) -> pystray.Menu:
    with STATE.lock:
        overall    = STATE.overall()
        embed_msg  = STATE.embed["msg"]
        rerank_msg = STATE.rerank["msg"]
        db_msg     = STATE.db["msg"]

    sym   = STATUS_SYMBOL.get(overall, "?")
    label = STATUS_LABEL.get(overall, "")
    ts    = STATE.last_ok.strftime("%H:%M:%S") if STATE.last_ok else "—"

    def _force_check(icon, item):
        cfg = _load_embed_config()
        STATE.update(check_lmstudio(cfg), check_reranker(cfg), check_database())
        icon.icon  = _make_icon(STATE.overall())
        icon.title = STATE.tooltip()
        icon.menu  = _build_menu(icon)

    return pystray.Menu(
        pystray.MenuItem(f"{APP_FULL}  —  {sym} {label}", None, enabled=False),
        pystray.MenuItem(f"   Último OK: {ts}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"   Embed:   {embed_msg[:48]}",  None, enabled=False),
        pystray.MenuItem(f"   Rerank:  {rerank_msg[:48]}", None, enabled=False),
        pystray.MenuItem(f"   BD:      {db_msg[:48]}",     None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("↻  Verificar ahora",  _force_check),
        pystray.MenuItem("ℹ  Ver panel…",        _open_details),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("✕  Salir",             lambda i, it: i.stop()),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Punto de entrada
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    icon = pystray.Icon(
        name=APP_NAME.lower(),
        icon=_make_icon("unknown"),
        title=f"{APP_FULL} — Iniciando…",
    )

    cfg = _load_embed_config()
    STATE.update(check_lmstudio(cfg), check_reranker(cfg), check_database())
    icon.icon  = _make_icon(STATE.overall())
    icon.title = STATE.tooltip()
    icon.menu  = _build_menu(icon)

    t = threading.Thread(target=_poll, args=(icon,), daemon=True)
    t.start()

    print(f"[{APP_FULL}] Iniciado — icono en la bandeja del sistema.")
    icon.run()


if __name__ == "__main__":
    main()
