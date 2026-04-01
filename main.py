#!/usr/bin/env python3
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("PIL").setLevel(logging.WARNING)

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit(
        "Dependências não instaladas.\n"
        "Execute:  sudo dnf install python3-pystray python3-pillow\n"
    )

import config
import vpn
from settings_window import open_settings

logger = logging.getLogger("main")


def _kill_stale_processes():
    """Mata qualquer openfortivpn residual antes de iniciar."""
    try:
        r = subprocess.run(["pgrep", "-x", "openfortivpn"], capture_output=True)
        if r.returncode == 0:
            logger.info("Processo residual encontrado. Matando...")
            subprocess.run(
                ["sudo", "killall", "-q", "openfortivpn"],
                capture_output=True, timeout=5,
            )
            time.sleep(1)
            logger.info("Processo residual encerrado.")
    except Exception as e:
        logger.warning("Erro ao matar processo residual: %s", e)


# ── Estado global ──────────────────────────────────────────────────────────────

_profiles: list[dict] = config.load()
_managers: dict[str, vpn.VpnManager] = {}   # profile_id  VpnManager
_icon_ref: pystray.Icon | None = None


def _get_manager(profile_id: str) -> vpn.VpnManager:
    if profile_id not in _managers:
        _managers[profile_id] = vpn.VpnManager(profile_id)
    return _managers[profile_id]


# ── Ícone ──────────────────────────────────────────────────────────────────────

def _load_icon() -> Image.Image:
    for candidate in [
        Path(__file__).parent / "icons" / "icon.png",
        Path(__file__).parent / "src-tauri" / "icons" / "icon.png",
    ]:
        if candidate.exists():
            return Image.open(candidate).resize((64, 64)).convert("RGBA")
    # Fallback: escudo simples
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(32, 4), (60, 18), (60, 38), (32, 60), (4, 38), (4, 18)], fill=(126, 184, 247))
    d.polygon([(32, 14), (52, 24), (52, 38), (32, 52), (12, 38), (12, 24)], fill=(15, 52, 96))
    return img


# ── Menu ───────────────────────────────────────────────────────────────────────

def _make_disc_cb(pid: str):
    def cb(icon, item):
        _do_disconnect(pid)
    return cb


def _make_conn_cb(pid: str):
    def cb(icon, item):
        _do_connect(pid)
    return cb


def _build_menu() -> pystray.Menu:
    """Constrói o menu mostrando cada perfil de forma independente."""
    items = []

    for p in _profiles:
        mgr = _get_manager(p["id"])
        s   = mgr.status()
        ip  = vpn.tunnel_ip() if s == vpn.CONNECTED else None

        if s == vpn.CONNECTED:
            label = f"● {p['name']}" + (f"  ({ip})" if ip else "")
            items.append(pystray.MenuItem(label, None, enabled=False))
            items.append(pystray.MenuItem(f'  Desconectar "{p["name"]}"', _make_disc_cb(p["id"])))
        elif s == vpn.CONNECTING:
            items.append(pystray.MenuItem(f"◌ {p['name']} — conectando…", None, enabled=False))
            items.append(pystray.MenuItem(f'  Cancelar "{p["name"]}"', _make_disc_cb(p["id"])))
        else:
            items.append(pystray.MenuItem(f'○ Conectar "{p["name"]}"', _make_conn_cb(p["id"])))

    items.append(pystray.Menu.SEPARATOR)
    items.append(pystray.MenuItem("Editar configurações…", lambda icon, item: _open_settings()))
    items.append(pystray.Menu.SEPARATOR)
    items.append(pystray.MenuItem("Sair", lambda icon, item: _do_quit()))

    return pystray.Menu(*items)


def _tray_title() -> str:
    connected  = [p["name"] for p in _profiles if _get_manager(p["id"]).status() == vpn.CONNECTED]
    connecting = [p["name"] for p in _profiles if _get_manager(p["id"]).status() == vpn.CONNECTING]
    if connected:
        return "openfortivpngui — Conectado: " + ", ".join(connected)
    if connecting:
        return "openfortivpngui — Conectando: " + ", ".join(connecting)
    return "openfortivpngui — Desconectado"


# ── Ações ──────────────────────────────────────────────────────────────────────

def _refresh():
    if _icon_ref:
        try:
            _icon_ref.menu  = _build_menu()
            _icon_ref.title = _tray_title()
        except Exception as e:
            logger.warning("Erro ao atualizar tray: %s", e)


def _open_browser(url: str, browser: str = ""):
    logger.info("Abrindo browser para URL SAML: %s", url)
    candidates = [b for b in [browser, "firefox", "xdg-open"] if b]
    for b in candidates:
        try:
            subprocess.Popen(
                [b, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Browser aberto com: %s", b)
            return
        except FileNotFoundError:
            continue
    logger.error("Nenhum browser encontrado: %s", candidates)


def _do_connect(profile_id: str):
    p = next((x for x in _profiles if x["id"] == profile_id), None)
    if not p:
        return
    mgr = _get_manager(profile_id)
    browser = p.get("browser", "")
    mgr.connect(
        p,
        on_url=lambda url: _open_browser(url, browser),
        on_connected=_refresh,
        on_error=lambda err: (
            logger.error("VPN error [%s]: %s", profile_id, err),
            _refresh(),
        ),
    )
    _refresh()


def _do_disconnect(profile_id: str):
    _get_manager(profile_id).disconnect()
    _refresh()


def _do_quit(*_):
    for mgr in list(_managers.values()):
        mgr.disconnect()
    if _icon_ref:
        _icon_ref.stop()


def _open_settings(*_):
    global _profiles

    def on_save(new_profiles):
        global _profiles
        _profiles = new_profiles
        config.save(_profiles)
        _refresh()

    open_settings(_profiles, on_save)


# ── Autostart ──────────────────────────────────────────────────────────────────

def _setup_autostart():
    d = Path.home() / ".config" / "autostart"
    desktop = d / "openfortivpngui.desktop"
    d.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve()
    # Sempre recria para manter o caminho atualizado
    desktop.write_text(
        "[Desktop Entry]\nType=Application\nName=openfortivpngui\n"
        f"Exec={sys.executable} {here}\n"
        "Hidden=false\nNoDisplay=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "StartupNotify=false\n",
        encoding="utf-8",
    )
    logger.info("Autostart configurado: %s", desktop)


# ── Poll loop ──────────────────────────────────────────────────────────────────

def _poll_loop():
    """Atualiza o tray a cada 3 s para refletir mudanças de estado."""
    while True:
        time.sleep(3)
        _refresh()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    global _icon_ref

    _kill_stale_processes()
    _setup_autostart()

    icon = pystray.Icon(
        "openfortivpngui",
        _load_icon(),
        _tray_title(),
        menu=_build_menu(),
    )
    _icon_ref = icon

    threading.Thread(target=_poll_loop, daemon=True).start()
    icon.run()


if __name__ == "__main__":
    main()
