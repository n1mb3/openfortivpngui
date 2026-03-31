import json
import os
from pathlib import Path

# Perfis de exemplo — edite pelo menu "Editar configurações…" ou diretamente em
# ~/.config/openfortivpngui/config.json
_DEFAULTS = [
    {"id": "example", "name": "Minha VPN", "gateway": "vpn.exemplo.com", "port": 443, "saml": True},
]


def _path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "openfortivpngui" / "config.json"


def load():
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("profiles", [dict(d) for d in _DEFAULTS])
        except Exception:
            pass
    return [dict(d) for d in _DEFAULTS]


def save(profiles):
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"profiles": profiles}, indent=2, ensure_ascii=False), encoding="utf-8")
