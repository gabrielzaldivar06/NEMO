#!/usr/bin/env bash
# ── NEMO Installer Build Script  (macOS) ─────────────────────────────────
# Compiles nemo_installer_mac.py into a portable .app bundle (double-click)
#
# Prerequisites:
#   pip3 install pyinstaller
#   Runs on macOS 12+ (Intel or Apple Silicon)
# ─────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  NEMO Installer — macOS Build        ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ── Check Python ─────────────────────────────────────────────────────────
PYTHON=$(command -v python3 || true)
if [[ -z "$PYTHON" ]]; then
  echo "[!] python3 not found. Install from https://python.org or via brew."
  exit 1
fi
echo "[OK] Python: $($PYTHON --version)"

# ── Check / install PyInstaller ──────────────────────────────────────────
if ! "$PYTHON" -m PyInstaller --version &>/dev/null; then
  echo "[*] Installing PyInstaller..."
  "$PYTHON" -m pip install pyinstaller --quiet
fi
echo "[OK] PyInstaller: $($PYTHON -m PyInstaller --version)"
echo ""

# ── Clean previous build ─────────────────────────────────────────────────
rm -rf dist build "NEMO Installer.spec"

# ── Build ─────────────────────────────────────────────────────────────────
echo "[*] Compiling nemo_installer_mac.py..."
echo ""

"$PYTHON" -m PyInstaller \
  --onefile \
  --windowed \
  --name "NEMO Installer" \
  --hidden-import tkinter \
  --hidden-import tkinter.ttk \
  --hidden-import tkinter.filedialog \
  --hidden-import tkinter.messagebox \
  --hidden-import tkinter.scrolledtext \
  nemo_installer_mac.py

echo ""
echo "  ──────────────────────────────────────────────────────"

if [[ -d "dist/NEMO Installer.app" ]]; then
  echo "  [OK] App bundle: dist/NEMO Installer.app"
  # Also copy to project root for easy distribution
  cp -r "dist/NEMO Installer.app" "../NEMO Installer.app"
  echo "  [OK] Copied to: ../NEMO Installer.app"
elif [[ -f "dist/NEMO Installer" ]]; then
  echo "  [OK] Executable: dist/NEMO Installer"
  cp "dist/NEMO Installer" "../NEMO Installer"
  echo "  [OK] Copied to: ../NEMO Installer"
fi

echo ""
echo "  To test before distributing:"
echo "    open \"dist/NEMO Installer.app\""
echo ""
echo "  To distribute:"
echo "    - Zip the .app:  ditto -c -k --keepParent \"dist/NEMO Installer.app\" NEMO-Installer-mac.zip"
echo "    - Upload NEMO-Installer-mac.zip to your GitHub Release"
echo "  ──────────────────────────────────────────────────────"
echo ""
