#!/usr/bin/env python3
"""
NEMO Installer v1.1.0
Windows bootstrapper — installs NEMO and auto-configures all detected MCP clients.

Build with:
    pip install pyinstaller
    pyinstaller --onefile --windowed --name "NEMO Installer" nemo_installer.py
"""

import base64
import ctypes
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import winreg
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import BooleanVar, Button, Canvas, Checkbutton, DISABLED, DoubleVar, END
from tkinter import Entry, Frame, Label, LEFT, NORMAL, RIGHT, Scrollbar, StringVar
from tkinter import Text, Tk, Toplevel, VERTICAL, WORD, X, Y, FLAT, BOTH, filedialog
from tkinter import messagebox, ttk

# ── Constants ──────────────────────────────────────────────────────────────

APP_VERSION = "1.1.0"
OLLAMA_URL  = "https://ollama.ai/download/OllamaSetup.exe"
EMBED_MODEL = "nomic-embed-text"
DEFAULT_DIR = str(Path.home() / "AppData" / "Local" / "NEMO")

# Only the runtime files needed — no docs, tests, examples, scripts
RAW_BASE = "https://raw.githubusercontent.com/gabrielzaldivar06/persistent-ai-memory/main/"
CORE_FILES = [
    "ai_memory_mcp_server.py",
    "ai_memory_core.py",
    "short_term_memory.py",
    "tag_manager.py",
    "utils.py",
    "settings.py",
    "database_maintenance.py",
    "requirements.txt",
    "memory_config.json",
    "embedding_config.json",
]

WIN_W = 900
WIN_H = 580

# ── Colors ─────────────────────────────────────────────────────

BG          = "#07090f"
SURFACE     = "#0d1120"
SURFACE2    = "#121828"
SURFACE3    = "#17203a"
BORDER      = "#1a2540"
BORDER2     = "#243050"
BLUE        = "#3b7eff"
BLUE_BRIGHT = "#5b9dff"
BLUE_DIM    = "#1d4ed8"
BLUE_GLOW   = "#1a3a80"
PURPLE      = "#8b5cf6"
GREEN       = "#22c55e"
GREEN_DIM   = "#15803d"
RED         = "#ef4444"
YELLOW      = "#eab308"
TEXT        = "#e2e8f0"
DIM         = "#94a3b8"
MUTED       = "#64748b"

# ── Embedded icon (64×64 RGBA PNG wrapped in ICO) ─────────────────────

ICON_B64 = (
    "AAABAAEAQEAAAAEAIACWBAAAFgAAAIlQTkcNChoKAAAADUlIRFIAAABAAAAAQAgGAAAAqmlx3g"
    "AABF1JREFUeNrtWltsTFsYnie9nOm0Mx12263MtFp6ybSj7TQudagjFHHqVklLSFxLSRUVl+"
    "BBThpPSAgenBMiIXF7QZyEByHKg3gQXsQ9JMSL8PrZ32LXbN0ynT06Gv0fVvbstddas/7v/"
    "75//Wvt7RqS6sFgLi4BQAAQAAQAAUAAEAAEAAFAAEhuSXFrcGshePSIuvJ+0ABAo7XKZciv24"
    "lA/T/qynvW//YA0Eh9XAeK555CaPkdhFsfqivvWZ9sEFzJpj09TWOr21/h0DX0lOr2l6qez5"
    "MpB1dSNJvmRWpmAFkFMxGcfhiVax5ZjDcLmUA5cPwBBUBcmv1qbLq/Au68ScgIzEFm8RJ4y9"
    "uQW7cfo5tvorrjvS0AY9seq/GTKQNXYprdjKzgNFtjs8M7MLR2H7S6o8idehp6wxUEFt5DybJ"
    "HGNv+zhaA8LqnCM44AndOeGAAYNXsS8tkazreonTxDYycfhz+qj29jM3/+7a68p71fM52wdln"
    "EFrzDJHOT5bxeM96Ps8sXIBUz4hfDwC1SLrT47aUNTxJj9Kz3xtLBpAJZIRiRlGzqg/Mu4Xi"
    "5m6E1r5GuO25QfsnqFj9AGVL76p6Pmc7tk/zlf5aAEh/apK0twOAWqamqe1oYykHyoKx4A8t"
    "Am/pKmgTDytW8BqY342CxssomPUfAlO7FMj6uO3Qandb2rEf+w9cBmx4jcLGc/CNaVHGMgB+"
    "C4Y+uIfXwxfqQM6UE9Bn/q88m/vXWeP+pAFYKzwj6y2rCj1uMoXt2Y/9OQ7HG1AxINL5EaHW"
    "Vxi1qNuYcJfyfrpWo/pRvx6DCf6qXcibdl4V/tbqjiFvxiX4KjsNz9ba/ueP+rKuP+JC3KsA"
    "NUvtUsNFTdeR33BeUTbnz3+RXbkVnmCjrReHRrpUO14zRjTEyBvs2dMfcSH+PMDQLLVLDVPL"
    "/qrd8NfsVdTWG65i2PiDvXRMj9PzZEBmUQtSMob3aXJ28eNnxwVHmSC1Sw1TyzTcW74e3rK1"
    "yniC0OMxQxZZJSss7dL98WV5/R0XHO8FqOFoz0ZrlnIwZTFs/AHos64rprj1yY7+qz/jQkJ7"
    "AWrZ1Ha0d+j5HlkYxpMZZAi9lpKhO9tbxIgLTvcqjvcC36/b0dGdNCfdzSWPsuBvgkJwfGOa"
    "HJ8H2MUFzoPzcTKeo72AXeZmGkvNM9BFL3lcHUxZcNUobLyAkpZrqFh5z9F5QHRcMDNLzofz"
    "ine8BPIAa+5OjX+h+4FeSx7zA3qe+QLzBuYPkS0frFnlxjcYvfAicms3Ge2rkZZdHrPwf3+0"
    "t+jr+UJCmWC47RlGzb+MnAnM/bf1BDwzMLIuurAd2zOD7Mt4sYo5Hvs5PV9IaC9Qs+Ujyla9"
    "QLDp/hd6xyhsx/bsl4zxOO9Y5wvCAIkBsgpIHiCZoOwFZDco5wFyIiRngnIqLO8F5M2QvBuU"
    "t8PyfYB8ISLfCMlXYvKdoHwpKt8KCwACgAAgAAgAAoAAIAAMgvIZe602p/KgvfoAAAAASUVORK5CYII="
)

# ── Editor definitions ─────────────────────────────────────────────────────

EDITORS = {
    "VS Code": {
        "icon"  : "💻",
        "detect": Path.home() / "AppData/Roaming/Code/User",
        "config": Path.home() / "AppData/Roaming/Code/User/mcp.json",
        "format": "vscode",
        "restart": "code --reuse-window",
    },
    "Cursor": {
        "icon"  : "🎯",
        "detect": Path.home() / ".cursor",
        "config": Path.home() / ".cursor/mcp.json",
        "format": "vscode",
        "restart": "cursor --reuse-window",
    },
    "Windsurf": {
        "icon"  : "🌊",
        "detect": Path.home() / "AppData/Roaming/Windsurf/User",
        "config": Path.home() / "AppData/Roaming/Windsurf/User/mcp.json",
        "format": "vscode",
        "restart": None,
    },
    "Claude Desktop": {
        "icon"  : "🤖",
        "detect": Path.home() / "AppData/Roaming/Claude",
        "config": Path.home() / "AppData/Roaming/Claude/claude_desktop_config.json",
        "format": "claude",
        "restart": None,
    },
    "Continue.dev": {
        "icon"  : "🔁",
        "detect": Path.home() / ".continue",
        "config": Path.home() / ".continue/config.json",
        "format": "continue",
        "restart": None,
    },
    "Zed": {
        "icon"  : "⚡",
        "detect": Path.home() / "AppData/Roaming/Zed",
        "config": Path.home() / "AppData/Roaming/Zed/settings.json",
        "format": "zed",
        "restart": None,
    },
}

INSTALL_STEPS = [
    ("python",    "Verificar Python 3.10+"),
    ("download",  f"Descargar {len(CORE_FILES)} archivos de NEMO"),
    ("venv",      "Crear entorno virtual"),
    ("packages",  "Instalar paquetes Python"),
    ("ollama",    "Verificar / instalar Ollama"),
    ("model",     "Descargar modelo de embeddings"),
    ("editors",   "Configurar editores detectados"),
    ("shortcuts", "Crear accesos directos"),
]

# ── Utility functions ──────────────────────────────────────────────────────

def winget_install_python() -> bool:
    """Attempt silent Python install via winget. Returns True if succeeded."""
    try:
        r = subprocess.run(
            ["winget", "install", "Python.Python.3.12", "-e",
             "--silent", "--accept-package-agreements",
             "--accept-source-agreements"],
            capture_output=True, text=True, timeout=180,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def find_python() -> str | None:
    """Return path to Python 3.10+ on the system, or None."""
    candidates = []

    # 1. Windows py launcher
    for flag in ["-3.12", "-3.11", "-3.10", "-3"]:
        try:
            r = subprocess.run(
                ["py", flag, "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                p = r.stdout.strip()
                if p:
                    candidates.append(p)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # 2. Common command names
    for name in ["python3", "python"]:
        try:
            r = subprocess.run(
                [name, "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                p = r.stdout.strip()
                if p and p not in candidates:
                    candidates.append(p)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # 3. Common install locations
    search_roots = [
        Path.home() / "AppData/Local/Programs/Python",
        Path("C:/Python312"), Path("C:/Python311"), Path("C:/Python310"),
        Path("C:/Program Files/Python312"),
        Path("C:/Program Files/Python311"),
        Path("C:/Program Files/Python310"),
    ]
    for root in search_roots:
        if root.is_file() and root.name == "python.exe":
            candidates.append(str(root))
        elif root.is_dir():
            direct = root / "python.exe"
            if direct.exists():
                candidates.append(str(direct))
            try:
                for sub in sorted(root.iterdir(), reverse=True):
                    if sub.is_dir():
                        py = sub / "python.exe"
                        if py.exists():
                            candidates.append(str(py))
            except PermissionError:
                pass

    # Validate version
    for candidate in candidates:
        try:
            r = subprocess.run(
                [candidate, "-c",
                 "import sys; v=sys.version_info; print(v.major, v.minor)"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                parts = r.stdout.strip().split()
                if len(parts) >= 2 and int(parts[0]) == 3 and int(parts[1]) >= 10:
                    return candidate
        except Exception:
            continue
    return None


def is_ollama_installed() -> bool:
    try:
        r = subprocess.run(
            ["ollama", "--version"], capture_output=True, timeout=5,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def write_mcp_config(
    config_path: Path,
    python_exe: str,
    server_script: str,
    fmt: str,
) -> None:
    """Merge NEMO entry into the editor's MCP config file, preserving existing entries."""
    # Normalize to forward slashes for cross-platform JSON readability
    python_fwd = python_exe.replace("\\", "/")
    script_fwd = server_script.replace("\\", "/")

    existing: dict = {}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    if fmt == "vscode":
        existing.setdefault("servers", {})
        existing["servers"]["nemo"] = {
            "type"   : "stdio",
            "command": python_fwd,
            "args"   : [script_fwd],
            "env"    : {},
        }
    elif fmt == "claude":
        existing.setdefault("mcpServers", {})
        existing["mcpServers"]["nemo"] = {
            "command": python_fwd,
            "args"   : [script_fwd],
        }
    elif fmt == "continue":
        existing.setdefault("mcpServers", [])
        # Remove old nemo entry if present
        existing["mcpServers"] = [
            s for s in existing["mcpServers"]
            if s.get("name") != "nemo"
        ]
        existing["mcpServers"].append({
            "name"   : "nemo",
            "command": python_fwd,
            "args"   : [script_fwd],
            "transport": "stdio",
        })
    elif fmt == "zed":
        existing.setdefault("context_servers", {})
        existing["context_servers"]["nemo"] = {
            "command": {"path": python_fwd, "args": [script_fwd]},
        }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def create_windows_shortcut(target: str, shortcut_path: str, description: str = "") -> None:
    """Create a .lnk shortcut via PowerShell (no extra dependencies)."""
    ps_script = (
        f'$ws = New-Object -ComObject WScript.Shell;'
        f'$s = $ws.CreateShortcut("{shortcut_path}");'
        f'$s.TargetPath = "{target}";'
        f'$s.Description = "{description}";'
        f'$s.Save()'
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        capture_output=True, timeout=15,
    )


# ── Step widget ────────────────────────────────────────────────────────────

class StepItem(Frame):
    _ICONS  = {"pending": "○", "done": "✓", "error": "✗", "skip": "⊘"}
    _SPIN   = ["◐", "◓", "◑", "◒"]
    _COLORS = {
        "pending": MUTED,
        "running": BLUE,
        "done"   : GREEN,
        "error"  : RED,
        "skip"   : MUTED,
    }

    def __init__(self, parent: Frame, label: str) -> None:
        super().__init__(parent, bg=SURFACE, pady=6)
        self._state    = "pending"
        self._spin_idx = 0
        self._icon_var = StringVar(value=self._ICONS["pending"])
        self._icon_lbl = Label(
            self, textvariable=self._icon_var,
            bg=SURFACE, fg=MUTED, font=("Segoe UI", 12), width=2,
        )
        self._icon_lbl.pack(side=LEFT, padx=(4, 8))
        self._text_lbl = Label(
            self, text=label,
            bg=SURFACE, fg=MUTED, font=("Segoe UI", 10), anchor="w",
        )
        self._text_lbl.pack(side=LEFT, fill=X, expand=True)

    def set_state(self, state: str) -> None:
        self._state = state
        if state == "running":
            self._spin_idx = 0
            self._icon_lbl.config(fg=BLUE)
            self._text_lbl.config(fg=TEXT)
            self._tick()
        else:
            self._icon_var.set(self._ICONS.get(state, "○"))
            self._icon_lbl.config(fg=self._COLORS.get(state, MUTED))
            if state == "done":
                fg = GREEN
            elif state == "error":
                fg = RED
            elif state == "skip":
                fg = MUTED
            else:
                fg = DIM
            self._text_lbl.config(fg=fg)

    def _tick(self) -> None:
        if self._state != "running":
            return
        self._spin_idx = (self._spin_idx + 1) % 4
        self._icon_var.set(self._SPIN[self._spin_idx])
        self.after(160, self._tick)


# ── Main application ───────────────────────────────────────────────────────

class NemoInstaller(Tk):

    def __init__(self) -> None:
        super().__init__()
        self.title(f"NEMO  ·  Instalador  v{APP_VERSION}")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - WIN_W) // 2
        y = (self.winfo_screenheight() - WIN_H) // 2
        self.geometry(f"+{x}+{y}")

        # Set window icon from embedded asset
        try:
            ico_data = base64.b64decode(ICON_B64)
            _ico_path = Path(tempfile.gettempdir()) / "nemo_installer.ico"
            _ico_path.write_bytes(ico_data)
            self.iconbitmap(str(_ico_path))
        except Exception:
            pass

        # State
        self.install_dir  = StringVar(value=DEFAULT_DIR)
        self.python_path: str | None = None
        self.editor_vars  = {
            name: BooleanVar(value=info["detect"].exists())
            for name, info in EDITORS.items()
        }
        self.autostart_var    = BooleanVar(value=False)
        self.step_items: dict[str, StepItem] = {}
        self.install_results: dict[str, str] = {}
        self._configured_editors: list[str] = []
        self._full_log        = ""
        self._cancelled       = threading.Event()

        self._build_header()
        self.content = Frame(self, bg=BG)
        self.content.pack(fill=BOTH, expand=True)

        self._show_welcome()

    # ── Header ─────────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        hdr = Frame(self, bg=SURFACE, height=64)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)

        # Canvas neural-network logo
        ico = Canvas(hdr, width=44, height=44, bg=SURFACE, highlightthickness=0)
        ico.pack(side=LEFT, padx=(18, 10), pady=10)
        _nodes = [(9,14),(9,22),(9,30), (22,11),(22,22),(22,33), (36,22)]
        _edges = [(0,3),(0,4),(1,3),(1,4),(1,5),(2,4),(2,5),(3,6),(4,6),(5,6)]
        for e1, e2 in _edges:
            x1,y1 = _nodes[e1]; x2,y2 = _nodes[e2]
            ico.create_line(x1,y1,x2,y2, fill=BLUE_GLOW, width=1)
        for nx, ny in _nodes:
            ico.create_oval(nx-4,ny-4,nx+4,ny+4, fill=BLUE, outline=BLUE_BRIGHT, width=1)
            ico.create_oval(nx-2,ny-2,nx+2,ny+2, fill=BLUE_BRIGHT, outline="")

        # Brand name
        brand = Frame(hdr, bg=SURFACE)
        brand.pack(side=LEFT)
        Label(brand, text="NEMO", bg=SURFACE, fg=TEXT,
              font=("Segoe UI", 19, "bold")).pack(anchor="w")
        Label(brand, text="Memoria Persistente para tu IA", bg=SURFACE, fg=MUTED,
              font=("Segoe UI", 8)).pack(anchor="w")

        # Version badge
        vbadge = Frame(hdr, bg=SURFACE3, padx=8, pady=2)
        vbadge.pack(side=LEFT, padx=12, pady=22)
        Label(vbadge, text=f"v{APP_VERSION}", bg=SURFACE3, fg=DIM,
              font=("Segoe UI", 8, "bold")).pack()

        # Right trust badge
        trust = Frame(hdr, bg=SURFACE2, padx=12, pady=6,
                      highlightbackground=GREEN_DIM, highlightthickness=1)
        trust.pack(side=RIGHT, padx=20, pady=14)
        Label(trust, text="🔒  100% Local · Sin nube · Sin suscripciones",
              bg=SURFACE2, fg=GREEN, font=("Segoe UI", 9, "bold")).pack()

        # Gradient accent line (blue → purple)
        line = Canvas(self, height=3, bg=BG, highlightthickness=0)
        line.pack(fill=X)
        def _draw_line():
            w = line.winfo_width()
            if w < 2:
                line.after(30, _draw_line)
                return
            steps = 40
            for i in range(steps):
                x0 = i * w // steps
                x1 = (i + 1) * w // steps
                r = int(0x3b + (0x8b - 0x3b) * i / steps)
                g = int(0x7e + (0x5c - 0x7e) * i / steps)
                b = int(0xff + (0xf6 - 0xff) * i / steps)
                color = f"#{r:02x}{g:02x}{b:02x}"
                line.create_rectangle(x0, 0, x1, 3, fill=color, outline="")
        line.after(60, _draw_line)

    # ── Page helpers ────────────────────────────────────────────────────────

    def _clear(self) -> None:
        for w in self.content.winfo_children():
            w.destroy()
        self.step_items.clear()

    def _btn(self, parent: Frame, text: str, cmd, primary: bool = False, **kw) -> Button:
        b = Button(
            parent, text=text, command=cmd,
            bg=BLUE if primary else SURFACE2,
            fg="white" if primary else DIM,
            activebackground=BLUE_BRIGHT if primary else SURFACE3,
            activeforeground="white" if primary else TEXT,
            relief=FLAT, cursor="hand2",
            font=("Segoe UI", 10, "bold" if primary else "normal"),
            padx=26 if primary else 18,
            pady=11 if primary else 9,
            **kw,
        )
        if primary:
            b.bind("<Enter>", lambda e: b.config(bg=BLUE_BRIGHT))
            b.bind("<Leave>", lambda e: b.config(bg=BLUE))
        else:
            b.bind("<Enter>", lambda e: b.config(bg=SURFACE3, fg=TEXT))
            b.bind("<Leave>", lambda e: b.config(bg=SURFACE2, fg=DIM))
        return b

    def _bottom_bar(self) -> Frame:
        bar = Frame(self.content, bg=BG)
        bar.pack(fill=X, padx=60, pady=(0, 28), side="bottom")
        return bar

    def _feature_card(
        self, parent: Frame, icon: str, headline: str, detail: str,
        accent: str = BLUE,
    ) -> None:
        card = Frame(parent, bg=SURFACE,
                     highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill=X, pady=5)
        Frame(card, bg=accent, width=4).pack(side=LEFT, fill=Y)
        inner = Frame(card, bg=SURFACE, padx=16, pady=10)
        inner.pack(side=LEFT, fill=X, expand=True)
        top_row = Frame(inner, bg=SURFACE)
        top_row.pack(fill=X)
        Label(top_row, text=icon, bg=SURFACE,
              font=("Segoe UI", 15), width=2).pack(side=LEFT)
        Label(top_row, text=headline, bg=SURFACE, fg=TEXT,
              font=("Segoe UI", 10, "bold"), anchor="w").pack(side=LEFT, padx=(8, 0))
        Label(inner, text=detail, bg=SURFACE, fg=MUTED,
              font=("Segoe UI", 9), anchor="w").pack(anchor="w", padx=(26, 0), pady=(2, 0))

    def _section_label(self, parent: Frame, text: str) -> None:
        row = Frame(parent, bg=BG)
        row.pack(fill=X, pady=(10, 5))
        Frame(row, bg=BLUE, width=3, height=16).pack(side=LEFT)
        Label(row, text=text, bg=BG, fg=DIM,
              font=("Segoe UI", 8, "bold"), padx=10).pack(side=LEFT)

    # ── Page: Welcome ───────────────────────────────────────────────────────

    def _show_welcome(self) -> None:
        self._clear()
        f = Frame(self.content, bg=BG)
        f.pack(fill=BOTH, expand=True, padx=60, pady=28)

        # Hero section
        hero = Frame(f, bg=BG)
        hero.pack(fill=X, pady=(0, 18))
        Label(hero, text="Bienvenido al instalador de",
              bg=BG, fg=MUTED, font=("Segoe UI", 11)).pack(anchor="w")
        Label(hero, text="NEMO  Memory Server",
              bg=BG, fg=TEXT, font=("Segoe UI", 22, "bold")).pack(anchor="w")
        Label(hero, text="Todo queda configurado automáticamente en unos minutos.",
              bg=BG, fg=DIM, font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 0))

        Frame(f, bg=BORDER, height=1).pack(fill=X, pady=(0, 14))

        cards_frame = Frame(f, bg=BG)
        cards_frame.pack(fill=X)
        self._feature_card(cards_frame, "🧠", "Memoria semántica de alta precisión",
                           "Recuperación inteligente — 92% precisión Top-1, MRR 0.9583",
                           accent=BLUE)
        self._feature_card(cards_frame, "🔒", "100% local y privado",
                           "Ningún dato sale de tu máquina. Sin cuentas, sin telemetría.",
                           accent=GREEN)
        self._feature_card(cards_frame, "⚡", "31 herramientas MCP integradas",
                           "Memoria, agenda, correcciones, reflexiones. Un servidor, todo.",
                           accent=PURPLE)
        self._feature_card(cards_frame, "🔄", "Persiste entre sesiones y reinicios",
                           "Sobrevive cambios de editor, actualizaciones y reinicios.",
                           accent=YELLOW)

        bar = self._bottom_bar()
        Label(bar, text="Requisitos: Windows 10/11 · Python 3.10+ · ~800 MB libres",
              bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side=LEFT)

        btn_row = Frame(bar, bg=BG)
        btn_row.pack(side=RIGHT)
        self._btn(btn_row, "Personalizar  →", self._show_configure).pack(side=RIGHT, padx=(8, 0))
        self._btn(btn_row, "⚡  Instalación Express", self._start_install, primary=True).pack(side=RIGHT)

    # ── Page: Configure ─────────────────────────────────────────────────────

    def _show_configure(self) -> None:
        self._clear()
        f = Frame(self.content, bg=BG)
        f.pack(fill=BOTH, expand=True, padx=60, pady=24)

        Label(f, text="Configurar instalación",
              bg=BG, fg=TEXT, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        Label(f, text="Revisa las opciones y pulsa Instalar cuando estés listo.",
              bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 4))
        Frame(f, bg=BORDER, height=1).pack(fill=X, pady=(4, 4))

        # Install directory
        self._section_label(f, "DIRECTORIO DE INSTALACIÓN")
        box = Frame(f, bg=SURFACE, padx=18, pady=14,
                    highlightbackground=BORDER, highlightthickness=1)
        box.pack(fill=X, pady=(0, 4))
        row = Frame(box, bg=SURFACE)
        row.pack(fill=X)
        Entry(row, textvariable=self.install_dir, bg=SURFACE2, fg=TEXT,
              insertbackground=TEXT, relief=FLAT, font=("Segoe UI", 10),
              highlightbackground=BORDER2, highlightthickness=1).pack(
            side=LEFT, fill=X, expand=True, ipady=7, padx=(0, 10))
        self._btn(row, "Examinar…", lambda: self.install_dir.set(
            filedialog.askdirectory(initialdir=self.install_dir.get())
            or self.install_dir.get()
        )).pack(side=LEFT)

        # Editor detection
        self._section_label(f, "EDITORES DETECTADOS")
        ed_box = Frame(f, bg=SURFACE, padx=18, pady=14,
                       highlightbackground=BORDER, highlightthickness=1)
        ed_box.pack(fill=X, pady=(0, 4))
        grid = Frame(ed_box, bg=SURFACE)
        grid.pack(fill=X)
        for i, (name, info) in enumerate(EDITORS.items()):
            detected = info["detect"].exists()
            suffix = "  ✓ detectado" if detected else "  (no instalado)"
            cb = Checkbutton(
                grid, text=f"{info['icon']}  {name}{suffix}",
                variable=self.editor_vars[name],
                bg=SURFACE, fg=TEXT if detected else MUTED,
                selectcolor=SURFACE3, activebackground=SURFACE,
                activeforeground=TEXT, font=("Segoe UI", 10), cursor="hand2",
            )
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 40), pady=4)

        # Options
        self._section_label(f, "OPCIONES")
        opt_box = Frame(f, bg=SURFACE, padx=18, pady=14,
                        highlightbackground=BORDER, highlightthickness=1)
        opt_box.pack(fill=X)
        Checkbutton(
            opt_box, text="⚡  Iniciar NEMO automáticamente con Windows",
            variable=self.autostart_var,
            bg=SURFACE, fg=DIM, selectcolor=SURFACE3,
            activebackground=SURFACE, activeforeground=TEXT,
            font=("Segoe UI", 10), cursor="hand2",
        ).pack(anchor="w")

        bar = self._bottom_bar()
        self._btn(bar, "← Atrás", self._show_welcome).pack(side=LEFT)
        self._btn(bar, "Instalar ahora  →", self._start_install, primary=True).pack(side=RIGHT)

    # ── Page: Installing ────────────────────────────────────────────────────

    def _show_installing(self) -> None:
        self._clear()
        main = Frame(self.content, bg=BG)
        main.pack(fill=BOTH, expand=True)

        # Left panel — step list
        left = Frame(main, bg=SURFACE, width=272)
        left.pack(side=LEFT, fill=Y)
        left.pack_propagate(False)

        left_hdr = Frame(left, bg=SURFACE2, height=44)
        left_hdr.pack(fill=X)
        left_hdr.pack_propagate(False)
        Label(left_hdr, text="PROGRESO", bg=SURFACE2, fg=MUTED,
              font=("Segoe UI", 8, "bold"), padx=20).pack(side=LEFT, pady=14)
        Label(left_hdr, text=f"{len(INSTALL_STEPS)} pasos", bg=SURFACE2, fg=MUTED,
              font=("Segoe UI", 8), padx=10).pack(side=RIGHT, pady=14)
        Frame(left, bg=BORDER, height=1).pack(fill=X)

        for key, label in INSTALL_STEPS:
            item = StepItem(left, label)
            item.pack(fill=X, padx=16, pady=1)
            self.step_items[key] = item

        Frame(main, bg=BORDER, width=1).pack(side=LEFT, fill=Y)

        # Right panel — log
        right = Frame(main, bg=BG)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        log_hdr = Frame(right, bg=SURFACE2, height=44)
        log_hdr.pack(fill=X)
        log_hdr.pack_propagate(False)
        Label(log_hdr, text="▶  Registro en tiempo real", bg=SURFACE2, fg=MUTED,
              font=("Segoe UI", 9), padx=20).pack(side=LEFT, pady=14)

        self._log_widget = Text(
            right, bg=BG, fg=DIM,
            insertbackground=TEXT, relief=FLAT,
            font=("Cascadia Code", 8), wrap=WORD, padx=18, pady=14,
            highlightthickness=0, state=DISABLED,
            selectbackground=SURFACE3, selectforeground=TEXT,
        )
        sb = Scrollbar(right, orient=VERTICAL, command=self._log_widget.yview,
                       bg=SURFACE2, troughcolor=BG, relief=FLAT, width=8)
        self._log_widget.config(yscrollcommand=sb.set)
        sb.pack(side=RIGHT, fill=Y)
        self._log_widget.pack(fill=BOTH, expand=True)

        # Progress footer
        prog = Frame(right, bg=SURFACE2, height=48)
        prog.pack(fill=X, side="bottom")
        prog.pack_propagate(False)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "NEMO.Horizontal.TProgressbar",
            troughcolor=BORDER, background=BLUE,
            lightcolor=BLUE_BRIGHT, darkcolor=BLUE_DIM,
            bordercolor=BORDER, thickness=6,
        )
        self._progress_var = DoubleVar(value=0)
        self._pct_lbl = Label(prog, text="0%", bg=SURFACE2, fg=BLUE,
                              font=("Segoe UI", 9, "bold"), padx=10)
        self._pct_lbl.pack(side=RIGHT, pady=16)
        ttk.Progressbar(
            prog, variable=self._progress_var, maximum=100,
            style="NEMO.Horizontal.TProgressbar", length=190,
        ).pack(side=RIGHT, padx=(0, 4), pady=16)
        self._progress_lbl = Label(prog, text="Iniciando…",
                                   bg=SURFACE2, fg=MUTED, font=("Segoe UI", 9), padx=16)
        self._progress_lbl.pack(side=LEFT, pady=16)

    # ── Page: Done ──────────────────────────────────────────────────────────

    def _show_done(self, success: bool) -> None:
        self._clear()
        f = Frame(self.content, bg=BG)
        f.pack(fill=BOTH, expand=True, padx=60, pady=24)

        icon_text  = "✓" if success else "⚠"
        icon_color = GREEN if success else YELLOW
        title_text = "¡NEMO instalado con éxito!" if success else "Instalación completada con advertencias"
        sub_text   = (
            "Reinicia tu editor para activar NEMO. Todas las herramientas están listas."
            if success else
            "Revisa el registro — algunos pasos requieren atención manual."
        )

        # Status banner
        status_box = Frame(f, bg=SURFACE, padx=0, pady=0,
                           highlightbackground=GREEN_DIM if success else YELLOW,
                           highlightthickness=1)
        status_box.pack(fill=X, pady=(0, 18))
        Frame(status_box, bg=GREEN if success else YELLOW, width=5).pack(side=LEFT, fill=Y)
        inner = Frame(status_box, bg=SURFACE, padx=18, pady=14)
        inner.pack(side=LEFT, fill=X, expand=True)
        Label(inner, text=icon_text, bg=SURFACE, fg=icon_color,
              font=("Segoe UI", 28, "bold")).pack(anchor="w")
        Label(inner, text=title_text, bg=SURFACE, fg=TEXT,
              font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(2, 3))
        Label(inner, text=sub_text, bg=SURFACE, fg=DIM,
              font=("Segoe UI", 10)).pack(anchor="w")

        # Results grid
        Label(f, text="RESUMEN", bg=BG, fg=MUTED,
              font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 6))

        _ICONS = {"done": "✓", "error": "✗", "skip": "⊘", "running": "○", "pending": "○"}
        _CLR   = {"done": GREEN, "error": RED, "skip": MUTED}

        results_frame = Frame(f, bg=BG)
        results_frame.pack(fill=X)
        for idx, (key, label) in enumerate(INSTALL_STEPS):
            r   = self.install_results.get(key, "skip")
            clr = _CLR.get(r, MUTED)
            row = Frame(results_frame, bg=SURFACE2, padx=10, pady=6,
                        highlightbackground=BORDER, highlightthickness=1)
            row.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=4, pady=4)
            Label(row, text=_ICONS.get(r, "○"), bg=SURFACE2, fg=clr,
                  font=("Segoe UI", 11), width=2).pack(side=LEFT)
            Label(row, text=label, bg=SURFACE2,
                  fg=TEXT if r == "done" else RED if r == "error" else DIM,
                  font=("Segoe UI", 9), anchor="w").pack(side=LEFT)
        results_frame.columnconfigure(0, weight=1)
        results_frame.columnconfigure(1, weight=1)

        # Quick-launch buttons for configured editors
        launchable = [
            (name, EDITORS[name])
            for name in self._configured_editors
            if EDITORS[name].get("restart")
        ]
        if launchable:
            Label(f, text="ACCIONES RÁPIDAS", bg=BG, fg=MUTED,
                  font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(12, 6))
            actions_row = Frame(f, bg=BG)
            actions_row.pack(fill=X)
            for name, info in launchable:
                cmd = info["restart"].split()
                self._btn(
                    actions_row,
                    f"{info['icon']}  Abrir {name}",
                    lambda c=cmd: subprocess.Popen(c, shell=False),
                ).pack(side=LEFT, padx=(0, 8))

        bar = self._bottom_bar()
        self._btn(bar, "Ver registro completo", self._open_log_window).pack(side=LEFT)
        self._btn(bar, "Cerrar", self.destroy, primary=True).pack(side=RIGHT)

    def _open_log_window(self) -> None:
        top = Toplevel(self, bg=BG)
        top.title("Registro de instalación")
        top.geometry("780x460")
        top.configure(bg=BG)
        txt = Text(top, bg=BG, fg=DIM, relief=FLAT,
                   font=("Cascadia Code", 9), padx=16, pady=12)
        txt.pack(fill=BOTH, expand=True)
        txt.insert(END, self._full_log)
        txt.config(state=DISABLED)

    # ── Installation worker ─────────────────────────────────────────────────

    def _start_install(self) -> None:
        self._show_installing()
        self._full_log = ""
        self.install_results = {}
        threading.Thread(target=self._run_install, daemon=True).start()

    def _log(self, msg: str) -> None:
        self._full_log += msg + "\n"
        def _write() -> None:
            self._log_widget.config(state=NORMAL)
            self._log_widget.insert(END, msg + "\n")
            self._log_widget.see(END)
            self._log_widget.config(state=DISABLED)
        self.after(0, _write)

    def _set_step(self, key: str, state: str) -> None:
        self.install_results[key] = state
        def _upd() -> None:
            if key in self.step_items:
                self.step_items[key].set_state(state)
        self.after(0, _upd)

    def _set_progress(self, pct: float, msg: str = "") -> None:
        def _upd() -> None:
            self._progress_var.set(pct)
            self._pct_lbl.config(text=f"{int(pct)}%")
            if msg:
                self._progress_lbl.config(text=msg)
        self.after(0, _upd)

    def _run_install(self) -> None:  # noqa: C901
        n      = len(INSTALL_STEPS)
        errors = 0

        def pct(i: int) -> float:
            return (i / n) * 100

        idir     = Path(self.install_dir.get())
        src      = idir / "src"
        venv     = idir / ".venv"
        venv_py  = venv / "Scripts" / "python.exe"
        server   = src / "ai_memory_mcp_server.py"

        try:
            # ── 1. Python ──────────────────────────────────────────────────
            self._set_step("python", "running")
            self._set_progress(pct(0), "Buscando Python 3.10+…")
            self._log(f"\n[1/{n}] Buscando Python 3.10+...")
            self.python_path = find_python()
            if self.python_path:
                self._log(f"  ✓ Encontrado: {self.python_path}")
                self._set_step("python", "done")
            else:
                self._log("  ✗ Python 3.10+ no encontrado.")
                self._log("    Descárgalo de: https://python.org/downloads")
                self._log("    Asegúrate de marcar 'Add Python to PATH' al instalar.")
                self._set_step("python", "error")
                self.after(0, lambda: messagebox.showerror(
                    "Python no encontrado",
                    "Python 3.10 o superior no está instalado.\n\n"
                    "Descárgalo de:  https://python.org/downloads\n\n"
                    "Marca 'Add Python to PATH' y vuelve a ejecutar el instalador.",
                ))
                self.after(0, lambda: self._show_done(False))
                return

            # ── 2. Download NEMO core files (parallel) ───────────────────
            self._set_step("download", "running")
            self._set_progress(pct(1), "Descargando archivos de NEMO…")
            self._log(f"\n[2/{n}] Descargando {len(CORE_FILES)} archivos en paralelo...")
            self._log(f"  Origen: {RAW_BASE}")
            idir.mkdir(parents=True, exist_ok=True)
            src.mkdir(parents=True, exist_ok=True)
            download_errors  = 0
            completed_count  = 0
            download_lock    = threading.Lock()

            def _download_one(fname: str) -> tuple[str, bool, str]:
                url  = RAW_BASE + fname
                dest = src / fname
                try:
                    urllib.request.urlretrieve(url, dest)
                    kb = dest.stat().st_size // 1024
                    return fname, True, f"{kb} KB"
                except Exception as ex:
                    return fname, False, str(ex)

            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = {pool.submit(_download_one, f): f for f in CORE_FILES}
                for future in as_completed(futures):
                    fname, ok, detail = future.result()
                    with download_lock:
                        completed_count += 1
                        sub_pct = pct(1) + (completed_count / len(CORE_FILES)) * (pct(2) - pct(1))
                        self._set_progress(sub_pct, f"Descargando… {completed_count}/{len(CORE_FILES)}")
                        if ok:
                            self._log(f"  ✓ {fname}  ({detail})")
                        else:
                            self._log(f"  ✗ {fname}: {detail}")
                            download_errors += 1

            if download_errors == 0:
                self._log(f"  → {len(CORE_FILES)} archivos en: {src}")
                self._set_step("download", "done")
            else:
                self._log(f"  ✗ {download_errors} archivo(s) con error — verifica tu conexión.")
                self._set_step("download", "error")
                errors += download_errors

            # ── 3. Venv ────────────────────────────────────────────────────
            self._set_step("venv", "running")
            self._set_progress(pct(2), "Creando entorno virtual…")
            self._log(f"\n[3/{n}] Creando entorno virtual Python...")
            try:
                if not venv.exists():
                    r = subprocess.run(
                        [self.python_path, "-m", "venv", str(venv)],
                        capture_output=True, text=True,
                    )
                    if r.returncode != 0:
                        raise RuntimeError(r.stderr.strip()[:400])
                self._log(f"  ✓ Entorno virtual: {venv}")
                self._set_step("venv", "done")
            except Exception as ex:
                self._log(f"  ✗ Error: {ex}")
                self._set_step("venv", "error")
                errors += 1
                venv_py = Path(self.python_path)   # fallback to system python

            # ── 4. Packages ────────────────────────────────────────────────
            self._set_step("packages", "running")
            self._set_progress(pct(3), "Instalando paquetes Python…")
            self._log(f"\n[4/{n}] Instalando dependencias (1-3 min según conexión)...")
            req_file = src / "requirements.txt"
            try:
                # Upgrade pip silently first
                subprocess.run(
                    [str(venv_py), "-m", "pip", "install", "--upgrade", "pip",
                     "-q", "--no-warn-script-location"],
                    capture_output=True, text=True,
                )
                # Stream main install so users see progress
                pip_proc = subprocess.Popen(
                    [str(venv_py), "-m", "pip", "install",
                     "-r", str(req_file), "--no-warn-script-location"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
                pip_deadline = time.time() + 600
                for pip_line in pip_proc.stdout:  # type: ignore[union-attr]
                    pip_line = pip_line.rstrip()
                    if pip_line:
                        low = pip_line.lower()
                        if any(k in low for k in (
                            "collecting", "downloading", "installing collected",
                            "successfully installed", "error", "warning",
                        )):
                            self._log(f"    {pip_line}")
                    if time.time() > pip_deadline:
                        pip_proc.kill()
                        raise subprocess.TimeoutExpired("pip", 600)
                pip_proc.wait(timeout=30)
                if pip_proc.returncode != 0:
                    raise RuntimeError(f"pip exit code {pip_proc.returncode}")
                self._log("  ✓ Paquetes instalados")
                self._set_step("packages", "done")
            except Exception as ex:
                self._log(f"  ✗ Error instalando paquetes: {ex}")
                self._set_step("packages", "error")
                errors += 1

            # ── 5. Ollama ────────────────────────────────────────────────────
            self._set_step("ollama", "running")
            self._set_progress(pct(4), "Verificando Ollama…")
            self._log(f"\n[5/{n}] Verificando Ollama...")
            if is_ollama_installed():
                self._log("  ✓ Ollama ya instalado")
                self._set_step("ollama", "done")
            else:
                self._log("  → Intentando instalar Ollama via winget…")
                try:
                    r_wg = subprocess.run(
                        ["winget", "install", "Ollama.Ollama", "--silent",
                         "--accept-package-agreements", "--accept-source-agreements"],
                        capture_output=True, text=True, timeout=300,
                    )
                    if r_wg.returncode == 0 and is_ollama_installed():
                        self._log("  ✓ Ollama instalado via winget")
                        self._set_step("ollama", "done")
                    else:
                        raise RuntimeError("winget falló")
                except Exception:
                    self._log("  → Descargando OllamaSetup.exe (winget no disponible)…")
                    ollama_exe = idir / "OllamaSetup.exe"
                    try:
                        urllib.request.urlretrieve(OLLAMA_URL, ollama_exe)
                        self._log("  → Ejecutando instalador de Ollama (completa en la ventana)…")
                        subprocess.run([str(ollama_exe)], timeout=300)
                        ollama_exe.unlink(missing_ok=True)
                        self._log("  ✓ Ollama instalado")
                        self._set_step("ollama", "done")
                    except subprocess.TimeoutExpired:
                        self._log("  ⚠ Tiempo agotado esperando instalador de Ollama")
                        self._log("    Instala manualmente: https://ollama.ai/download")
                        self._set_step("ollama", "error")
                        errors += 1
                    except Exception as ex:
                        self._log(f"  ✗ Error: {ex}")
                        self._log("    Instala manualmente: https://ollama.ai/download")
                        self._set_step("ollama", "error")
                        errors += 1

            # ── 6. Embedding model ─────────────────────────────────────────
            self._set_step("model", "running")
            self._set_progress(pct(5), f"Descargando modelo ({EMBED_MODEL})…")
            self._log(f"\n[6/{n}] Descargando modelo de embeddings: {EMBED_MODEL}")
            self._log("  (puede tardar varios minutos en conexiones lentas)")
            try:
                proc = subprocess.Popen(
                    ["ollama", "pull", EMBED_MODEL],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True,
                )
                deadline = time.time() + 900
                for line in proc.stdout:  # type: ignore[union-attr]
                    line = line.rstrip()
                    if line:
                        self._log(f"    {line}")
                        m = re.search(r"(\d+)%", line)
                        if m:
                            pull_pct = int(m.group(1))
                            model_pct = pct(5) + (pull_pct / 100) * (pct(6) - pct(5))
                            self._set_progress(model_pct, f"Modelo: {pull_pct}%")
                    if time.time() > deadline:
                        proc.kill()
                        raise subprocess.TimeoutExpired("ollama", 900)
                proc.wait(timeout=30)
                if proc.returncode == 0:
                    self._log(f"  ✓ Modelo {EMBED_MODEL} listo")
                    self._set_step("model", "done")
                else:
                    raise RuntimeError(f"ollama pull exit code {proc.returncode}")
            except subprocess.TimeoutExpired:
                self._log("  ⚠ Tiempo agotado. El modelo continuará descargando en segundo plano.")
                self._log(f"    Ejecuta manualmente:  ollama pull {EMBED_MODEL}")
                self._set_step("model", "done")
            except Exception as ex:
                self._log(f"  ✗ Error: {ex}")
                self._log(f"    Ejecuta manualmente:  ollama pull {EMBED_MODEL}")
                self._set_step("model", "error")
                errors += 1

            # ── 7. Editor config ───────────────────────────────────────────
            self._set_step("editors", "running")
            self._set_progress(pct(6), "Configurando editores…")
            self._log(f"\n[7/{n}] Configurando editores MCP...")
            self._configured_editors = []
            for name, info in EDITORS.items():
                if not self.editor_vars[name].get():
                    self._log(f"  ⊘ {name}: omitido")
                    continue
                try:
                    write_mcp_config(
                        info["config"],
                        str(venv_py),
                        str(server),
                        info["format"],
                    )
                    self._log(f"  ✓ {name}")
                    self._log(f"      → {info['config']}")
                    self._configured_editors.append(name)
                except Exception as ex:
                    self._log(f"  ✗ {name}: {ex}")
                    errors += 1

            self._set_step("editors", "done" if self._configured_editors else "skip")
            if not self._configured_editors:
                self._log("  ⊘ Ningún editor configurado — puedes hacerlo manualmente.")
                self._log("    Consulta: https://github.com/gabrielzaldivar06/persistent-ai-memory#instalación")

            # ── 8. Shortcuts ───────────────────────────────────────────────
            self._set_step("shortcuts", "running")
            self._set_progress(pct(7), "Creando accesos directos…")
            self._log(f"\n[8/{n}] Creando accesos directos...")
            try:
                self._register_uninstall(idir)

                if self.autostart_var.get():
                    startup = Path.home() / (
                        "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
                    )
                    bat = startup / "nemo_autostart.bat"
                    bat.write_text(
                        f'@echo off\n'
                        f'"{venv_py}" "{server}" --daemon 2>> "{idir}\\nemo.log"\n',
                        encoding="utf-8",
                    )
                    self._log(f"  ✓ Autostart: {bat}")

                # Desktop shortcut to uninstall / manage
                uninstall_bat = idir / "uninstall.bat"
                desktop = Path.home() / "Desktop"
                if desktop.exists():
                    create_windows_shortcut(
                        str(uninstall_bat),
                        str(desktop / "Desinstalar NEMO.lnk"),
                        "Desinstala NEMO del sistema",
                    )

                self._log(f"  ✓ Instalación completada en: {idir}")
                self._set_step("shortcuts", "done")
            except Exception as ex:
                self._log(f"  ✗ Error en accesos directos: {ex}")
                self._set_step("shortcuts", "error")
                errors += 1

        except Exception as ex:
            self._log(f"\n[!] Error inesperado: {ex}")
            errors += 1

        # ── Finalize ────────────────────────────────────────────────────────
        label = "Completado" if errors == 0 else f"Completado con {errors} advertencia(s)"
        self._set_progress(100, label)
        time.sleep(0.6)
        self.after(0, lambda: self._show_done(errors == 0))

    # ── Uninstall registration ──────────────────────────────────────────────

    def _register_uninstall(self, idir: Path) -> None:
        uninstall_bat = idir / "uninstall.bat"
        uninstall_bat.write_text(
            "@echo off\n"
            "echo Desinstalando NEMO Memory Server...\n"
            f'rd /s /q "{idir}"\n'
            "echo.\n"
            "echo NEMO ha sido desinstalado.\n"
            "pause\n",
            encoding="utf-8",
        )

        # Best-effort Windows Add/Remove Programs entry
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\NEMO"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "DisplayName",    0, winreg.REG_SZ,    "NEMO Memory Server")
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ,    APP_VERSION)
                winreg.SetValueEx(key, "Publisher",      0, winreg.REG_SZ,    "gabrielzaldivar06")
                winreg.SetValueEx(key, "UninstallString",0, winreg.REG_SZ,    str(uninstall_bat))
                winreg.SetValueEx(key, "InstallLocation",0, winreg.REG_SZ,    str(idir))
                winreg.SetValueEx(key, "URLInfoAbout",   0, winreg.REG_SZ,
                                  "https://github.com/gabrielzaldivar06/persistent-ai-memory")
                winreg.SetValueEx(key, "NoModify",       0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "NoRepair",       0, winreg.REG_DWORD, 1)
        except OSError:
            pass  # Non-critical

    # ── Window close ───────────────────────────────────────────────────────

    def _on_close(self) -> None:
        if messagebox.askyesno(
            "Cancelar instalación",
            "¿Seguro que quieres salir del instalador?\n"
            "Puedes volver a ejecutarlo en cualquier momento.",
        ):
            self._cancelled.set()
            self.destroy()


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # HiDPI awareness (Windows 8.1+)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = NemoInstaller()
    app.mainloop()
