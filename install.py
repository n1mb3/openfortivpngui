#!/usr/bin/env python3
"""
Instala o openfortivpngui no sistema:
  - Cria entrada no launcher do GNOME/KDE (~/.local/share/applications/)
  - Instala o ícone (~/.local/share/icons/)
  - Configura autostart (~/.config/autostart/)

Uso:  python3 install.py [--remove]
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME  = "openfortivpngui"
HERE      = Path(__file__).resolve().parent
ICON_SRC  = HERE / "icons" / "icon.png"
MAIN_PY   = HERE / "main.py"

DESKTOP_DIR  = Path.home() / ".local" / "share" / "applications"
ICON_DIR     = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"
AUTOSTART_DIR = Path.home() / ".config" / "autostart"

DESKTOP_FILE   = DESKTOP_DIR   / f"{APP_NAME}.desktop"
ICON_FILE      = ICON_DIR      / f"{APP_NAME}.png"
AUTOSTART_FILE = AUTOSTART_DIR / f"{APP_NAME}.desktop"

DESKTOP_CONTENT = """\
[Desktop Entry]
Type=Application
Name=openfortivpngui
GenericName=VPN Manager
Comment=Gerenciador de VPN openfortivpn via bandeja do sistema
Exec={python} {main}
Icon={app_name}
Terminal=false
Categories=Network;VPN;
Keywords=vpn;openfortivpn;
StartupNotify=false
"""

AUTOSTART_CONTENT = """\
[Desktop Entry]
Type=Application
Name=openfortivpngui
Exec={python} {main}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
"""


def check_requirements():
    errors = []
    if not MAIN_PY.exists():
        errors.append(f"  ✗ main.py não encontrado em {HERE}")
    if not ICON_SRC.exists():
        errors.append(f"  ✗ Ícone não encontrado em {ICON_SRC}")
    try:
        import pystray  # noqa: F401
    except ImportError:
        errors.append("  ✗ pystray não instalado  →  sudo dnf install python3-pystray")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        errors.append("  ✗ Pillow não instalado   →  sudo dnf install python3-pillow")
    return errors


def install():
    print(f"Instalando {APP_NAME}…\n")

    erros = check_requirements()
    if erros:
        print("Dependências em falta:")
        for e in erros:
            print(e)
        sys.exit(1)

    python = sys.executable

    # 1. Ícone
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ICON_SRC, ICON_FILE)
    print(f"  ✓ Ícone instalado em {ICON_FILE}")

    # 2. Entrada do launcher
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    DESKTOP_FILE.write_text(
        DESKTOP_CONTENT.format(python=python, main=MAIN_PY, app_name=APP_NAME),
        encoding="utf-8",
    )
    print(f"  ✓ Launcher instalado em {DESKTOP_FILE}")

    # 3. Autostart
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    AUTOSTART_FILE.write_text(
        AUTOSTART_CONTENT.format(python=python, main=MAIN_PY),
        encoding="utf-8",
    )
    print(f"  ✓ Autostart configurado em {AUTOSTART_FILE}")

    # 4. Atualiza cache de ícones e aplicações
    subprocess.run(
        ["update-desktop-database", str(DESKTOP_DIR)],
        capture_output=True,
    )
    subprocess.run(
        ["gtk-update-icon-cache", "-f", str(ICON_FILE.parent.parent.parent)],
        capture_output=True,
    )

    print(f"\nPronto! Pesquise por '{APP_NAME}' no launcher do seu ambiente.")
    print("Na próxima vez que logar, o app iniciará automaticamente.")


def remove():
    print(f"Removendo {APP_NAME}…\n")
    removed = False
    for f in (DESKTOP_FILE, ICON_FILE, AUTOSTART_FILE):
        if f.exists():
            f.unlink()
            print(f"  ✓ Removido: {f}")
            removed = True
    if not removed:
        print("  Nada a remover.")
    subprocess.run(
        ["update-desktop-database", str(DESKTOP_DIR)],
        capture_output=True,
    )
    print("\nDesinstalação concluída.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Instala/remove o launcher do {APP_NAME}")
    parser.add_argument(
        "--remove", action="store_true",
        help="Remove o launcher e autostart em vez de instalar",
    )
    args = parser.parse_args()

    if args.remove:
        remove()
    else:
        install()
