import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path

log = logging.getLogger("vpn")

DISCONNECTED = "disconnected"
CONNECTING   = "connecting"
CONNECTED    = "connected"


# ── Utilitários do sistema ────────────────────────────────────────────────────

def _log_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    d = base / "openfortivpngui"
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_tunnel_up() -> bool:
    """Verifica se existe QUALQUER interface ppp* ativa."""
    try:
        return any(p.name.startswith("ppp") for p in Path("/sys/class/net").iterdir())
    except Exception:
        return False


def tunnel_ip() -> str | None:
    """Retorna o IP da primeira interface ppp encontrada."""
    try:
        out = subprocess.run(
            ["ip", "-4", "addr"], capture_output=True, text=True
        ).stdout
        # Procura inet em blocos ppp*
        in_ppp = False
        for line in out.splitlines():
            if re.match(r"\d+: ppp", line):
                in_ppp = True
            elif re.match(r"\d+:", line):
                in_ppp = False
            elif in_ppp:
                m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def _extract_url(content: str) -> str | None:
    for line in content.splitlines():
        for pat in [
            r"Authenticate at '([^']+)'",
            r'Authenticate at "([^"]+)"',
            r"Authenticate at (https://\S+)",
        ]:
            m = re.search(pat, line)
            if m:
                return m.group(1)
    return None


def _has_error(content: str) -> bool:
    return any(
        l.startswith("ERROR")
        or "failed to connect" in l.lower()
        or "connection refused" in l.lower()
        for l in content.splitlines()
    )


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


# ── VpnManager (uma instância por perfil) ─────────────────────────────────────

class VpnManager:
    def __init__(self, profile_id: str):
        self.profile_id = profile_id
        self._lock   = threading.Lock()
        self._status = DISCONNECTED
        self._proc   = None   # subprocess.Popen do sudo

    # ── Estado ───────────────────────────────────────────────────────────────

    def status(self) -> str:
        with self._lock:
            s    = self._status
            proc = self._proc

        # Se achamos que estamos conectados/conectando mas o processo morreu
        if s in (CONNECTED, CONNECTING) and proc is not None:
            if proc.poll() is not None and not is_tunnel_up():
                log.info("[%s] Processo morreu — marcando como desconectado", self.profile_id)
                with self._lock:
                    self._status = DISCONNECTED
                    self._proc   = None
                return DISCONNECTED

        return s

    # ── Conectar ─────────────────────────────────────────────────────────────

    def connect(self, profile: dict, on_url, on_connected, on_error):
        with self._lock:
            if self._status in (CONNECTING, CONNECTED):
                log.warning("[%s] Já conectado/conectando — ignorando.", self.profile_id)
                return
            self._status = CONNECTING

        def _run():
            gw      = f"{profile['gateway']}:{profile['port']}"
            logfile = _log_dir() / f"{self.profile_id}.log"
            logfile.write_bytes(b"")

            cmd = ["sudo", "openfortivpn", gw]
            if profile.get("saml"):
                cmd.append("--saml-login")

            log.info("[%s] Iniciando: %s", self.profile_id, " ".join(cmd))
            log.info("[%s] Log em: %s", self.profile_id, logfile)

            try:
                with open(logfile, "w") as f:
                    proc = subprocess.Popen(cmd, stdout=f, stderr=f)
            except Exception as e:
                log.error("[%s] Falha ao iniciar: %s", self.profile_id, e)
                with self._lock:
                    self._status = DISCONNECTED
                on_error(f"Falha ao iniciar openfortivpn: {e}")
                return

            log.info("[%s] PID=%s", self.profile_id, proc.pid)
            with self._lock:
                self._proc = proc

            # Fase 1 — aguarda URL SAML (até 20s) ────────────────────────────
            url_sent = False
            for _ in range(40):
                time.sleep(0.5)
                content = logfile.read_text(errors="replace")

                if not url_sent:
                    url = _extract_url(content)
                    if url:
                        url_sent = True
                        log.info("[%s] URL SAML: %s", self.profile_id, url)
                        on_url(url)

                if "Tunnel is up" in content or is_tunnel_up():
                    log.info("[%s] Túnel ativo (fase 1)", self.profile_id)
                    with self._lock:
                        self._status = CONNECTED
                    on_connected()
                    self._watch()
                    return

                if _has_error(content):
                    err = next(
                        (l for l in content.splitlines()
                         if l.startswith("ERROR") or "failed" in l.lower()),
                        "Erro desconhecido",
                    )
                    log.error("[%s] Erro (fase 1): %s", self.profile_id, err)
                    with self._lock:
                        self._status = DISCONNECTED
                        self._proc   = None
                    on_error(err)
                    return

                if not url_sent and proc.poll() is not None and not is_tunnel_up():
                    log.error("[%s] Processo terminou antes da URL SAML:\n%s",
                              self.profile_id, logfile.read_text(errors="replace"))
                    with self._lock:
                        self._status = DISCONNECTED
                        self._proc   = None
                    on_error("openfortivpn terminou antes da URL SAML.")
                    return

            if not url_sent:
                log.error("[%s] Timeout aguardando URL SAML", self.profile_id)
                with self._lock:
                    self._status = DISCONNECTED
                    self._proc   = None
                on_error("Timeout aguardando URL SAML.")
                return

            # Fase 2 — aguarda autenticação no browser (até 180s) ─────────────
            for _ in range(360):
                time.sleep(0.5)
                content = logfile.read_text(errors="replace")

                if "Tunnel is up" in content or is_tunnel_up():
                    log.info("[%s] Túnel ativo (fase 2) — conectado!", self.profile_id)
                    with self._lock:
                        self._status = CONNECTED
                    on_connected()
                    self._watch()
                    return

                if _has_error(content):
                    err = next(
                        (l for l in content.splitlines()
                         if l.startswith("ERROR") or "failed" in l.lower()),
                        "Erro desconhecido",
                    )
                    log.error("[%s] Erro (fase 2): %s", self.profile_id, err)
                    with self._lock:
                        self._status = DISCONNECTED
                        self._proc   = None
                    on_error(err)
                    return

                if proc.poll() is not None and not is_tunnel_up():
                    break

            log.warning("[%s] Timeout aguardando autenticação", self.profile_id)
            with self._lock:
                self._status = DISCONNECTED
                self._proc   = None

        threading.Thread(target=_run, daemon=True, name=f"vpn-{self.profile_id}").start()

    # ── Monitorar desconexão ──────────────────────────────────────────────────

    def _watch(self):
        def _loop():
            while True:
                time.sleep(3)
                with self._lock:
                    proc = self._proc
                proc_dead = (proc is None) or (proc.poll() is not None)
                if proc_dead and not is_tunnel_up():
                    log.info("[%s] Túnel caiu — desconectado.", self.profile_id)
                    with self._lock:
                        self._status = DISCONNECTED
                        self._proc   = None
                    break
        threading.Thread(target=_loop, daemon=True, name=f"watch-{self.profile_id}").start()

    # ── Desconectar ───────────────────────────────────────────────────────────

    def disconnect(self):
        with self._lock:
            proc = self._proc
            self._proc   = None
            self._status = DISCONNECTED

        if proc:
            try:
                proc.kill()
                proc.wait(timeout=3)
            except Exception:
                pass

        # Mata pelo gateway para não afetar outras instâncias ativas
        try:
            subprocess.run(
                ["sudo", "killall", "-q", "openfortivpn"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass
        log.info("[%s] Desconectado.", self.profile_id)

