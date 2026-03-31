#!/bin/bash
# vpn.sh — Gerenciador VPN (openfortivpn + SAML)
# Edite os perfis abaixo com os seus gateways.

# ── Perfis ────────────────────────────────────────────────────────────────────
# Adicione quantos perfis quiser no formato:
#   [id]="host:porta"

declare -A VPN_GATEWAY=(
    [minha-vpn]="vpn.exemplo.com:443"
)
declare -A VPN_NAME=(
    [minha-vpn]="Minha VPN"
)

SAML_PORT=8020
LOG_DIR="$HOME/.cache/vpn-manager"
mkdir -p "$LOG_DIR"

# ── Cores ─────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Helpers ───────────────────────────────────────────────────────────────────

log_file() { echo "$LOG_DIR/openfortivpn-${1}.log"; }

is_running() { pgrep -x openfortivpn &>/dev/null; }

is_connected() { is_running && ip link show ppp0 &>/dev/null 2>&1; }

vpn_ip() { ip -4 addr show ppp0 2>/dev/null | grep -oP '(?<=inet )\d+\.\d+\.\d+\.\d+'; }

active_profile() {
    local pid; pid=$(pgrep -x openfortivpn) || return
    local cmd; cmd=$(ps -p "$pid" -o args= 2>/dev/null)
    for key in "${!VPN_GATEWAY[@]}"; do
        [[ "$cmd" == *"${VPN_GATEWAY[$key]%:*}"* ]] && echo "$key" && return
    done
    echo "desconhecido"
}

ensure_sudo() {
    if ! sudo -n true 2>/dev/null; then
        echo -e "${YELLOW}Senha sudo necessária:${NC}"
        sudo -v || { echo -e "${RED}Falha na autenticação sudo.${NC}"; return 1; }
    fi
}

# ── Status ────────────────────────────────────────────────────────────────────

show_status() {
    echo ""
    if is_connected; then
        local prof; prof=$(active_profile)
        local name="${VPN_NAME[$prof]:-$prof}"
        echo -e "  Status  : ${GREEN}${BOLD}● CONECTADO${NC}"
        echo -e "  Perfil  : ${CYAN}${name}${NC}"
        echo -e "  IP VPN  : ${CYAN}$(vpn_ip)${NC}"
        echo -e "  PID     : $(pgrep -x openfortivpn)"
    elif is_running; then
        echo -e "  Status  : ${YELLOW}${BOLD}◌ CONECTANDO...${NC} (PID $(pgrep -x openfortivpn))"
    else
        echo -e "  Status  : ${RED}${BOLD}○ DESCONECTADO${NC}"
    fi
    echo ""
}

# ── Ações ─────────────────────────────────────────────────────────────────────

do_connect() {
    local profile="$1"
    local gateway="${VPN_GATEWAY[$profile]}"
    local name="${VPN_NAME[$profile]}"
    local logfile; logfile=$(log_file "$profile")

    if is_connected; then
        local cur; cur=$(active_profile)
        if [[ "$cur" == "$profile" ]]; then
            echo -e "${YELLOW}Já conectado em: ${name}.${NC}"; return 0
        else
            echo -e "${YELLOW}Já conectado em: ${VPN_NAME[$cur]}. Desconecte primeiro.${NC}"; return 1
        fi
    fi

    ensure_sudo || return 1

    echo -e "\n${BLUE}Conectando em: ${BOLD}${name}${NC} ${DIM}(${gateway})${NC}"
    > "$logfile"
    sudo openfortivpn "$gateway" --saml-login >> "$logfile" 2>&1 &

    # Aguarda URL SAML
    local url=""
    echo -ne "  Aguardando URL SAML"
    for i in $(seq 1 20); do
        sleep 1; echo -n "."
        url=$(grep -oP "(?<=Authenticate at ').*(?=')" "$logfile" 2>/dev/null | head -1)
        [[ -n "$url" ]] && break
    done
    echo ""

    if [[ -z "$url" ]]; then
        echo -e "${RED}Falha ao obter URL SAML. Veja o log (opção 5).${NC}"
        return 1
    fi

    echo -e "  ${GREEN}Abrindo Firefox...${NC}"
    echo -e "  ${DIM}${url}${NC}"
    firefox "$url" &>/dev/null &

    # Aguarda túnel
    echo -ne "  Aguardando autenticação no navegador"
    for i in $(seq 1 90); do
        sleep 2; echo -n "."
        if grep -q "Tunnel is up" "$logfile" 2>/dev/null; then
            echo -e "\n\n  ${GREEN}${BOLD}✓ VPN conectada!${NC}  IP: ${CYAN}$(vpn_ip)${NC}"
            return 0
        fi
        if grep -qiE "^ERROR|[Ff]ailed to connect|[Cc]onnection refused" "$logfile" 2>/dev/null; then
            echo -e "\n${RED}Erro na conexão:${NC}"
            grep -iE "^ERROR|[Ff]ailed|[Ee]rror" "$logfile" | tail -5
            return 1
        fi
    done
    echo -e "\n${YELLOW}Timeout — verifique o log (opção 5).${NC}"
    return 1
}

do_disconnect() {
    if ! is_running; then
        echo -e "${YELLOW}VPN não está em execução.${NC}"; return 0
    fi
    echo -e "${BLUE}Desconectando...${NC}"
    sudo killall openfortivpn 2>/dev/null
    for i in $(seq 1 10); do sleep 1; is_running || break; done
    is_running \
        && echo -e "${RED}Processo ainda ativo. Tente: sudo kill -9 $(pgrep -x openfortivpn)${NC}" \
        || echo -e "${GREEN}Desconectado.${NC}"
}

do_reconnect() {
    local profile="$1"
    [[ -z "$profile" ]] && profile=$(active_profile)
    do_disconnect
    sleep 1
    do_connect "$profile"
}

do_open_browser() {
    local profile="$1"
    local gw="${VPN_GATEWAY[$profile]}"
    local host="${gw%:*}"
    local port="${gw#*:}"
    local url="https://${host}:${port}/remote/saml/start?redirect=1"
    echo -e "${BLUE}Abrindo Firefox: ${DIM}${url}${NC}"
    firefox "$url" &>/dev/null &
}

do_show_log() {
    local profile="$1"
    local logfile; logfile=$(log_file "$profile")
    if [[ ! -s "$logfile" ]]; then
        echo -e "${YELLOW}Nenhum log disponível para ${VPN_NAME[$profile]}.${NC}"; return
    fi
    echo -e "${CYAN}=== Log: ${VPN_NAME[$profile]} ===${NC}"
    cat "$logfile"
}

# ── Seleção de perfil ─────────────────────────────────────────────────────────

select_profile() {
    local title="$1"
    echo -e "\n  ${BOLD}Selecione o perfil${title:+ — $title}:${NC}" >&2
    local i=1
    local keys=()
    for key in "${!VPN_GATEWAY[@]}"; do
        echo -e "    ${BOLD}${i})${NC} ${VPN_NAME[$key]} ${DIM}(${VPN_GATEWAY[$key]})${NC}" >&2
        keys+=("$key")
        ((i++))
    done
    echo -e "    ${BOLD}0)${NC} Cancelar" >&2
    echo "" >&2
    read -rp "  Escolha: " sel </dev/tty
    [[ "$sel" == "0" || -z "$sel" ]] && return 1
    local idx=$(( sel - 1 ))
    [[ $idx -lt 0 || $idx -ge ${#keys[@]} ]] && echo -e "${RED}Inválido.${NC}" >&2 && return 1
    echo "${keys[$idx]}"
}

# ── Menu principal ────────────────────────────────────────────────────────────

menu() {
    while true; do
        clear
        echo -e "${BOLD}╔════════════════════════════════════╗"
        echo -e "║     Gerenciador VPN — openfortivpn ║"
        echo -e "╚════════════════════════════════════╝${NC}"

        show_status

        echo -e "  ${BOLD}1)${NC} Conectar"
        echo -e "  ${BOLD}2)${NC} Desconectar"
        echo -e "  ${BOLD}3)${NC} Reconectar"
        echo -e "  ${BOLD}4)${NC} Abrir navegador (URL SAML manual)"
        echo -e "  ${BOLD}5)${NC} Ver log"
        echo -e "  ${BOLD}0)${NC} Sair"
        echo ""
        read -rp "  Escolha: " choice

        case "$choice" in
            1)
                if is_connected; then
                    echo -e "${YELLOW}Já conectado. Desconecte primeiro (opção 2).${NC}"
                else
                    profile=$(select_profile "conectar") && do_connect "$profile"
                fi ;;
            2) do_disconnect ;;
            3)
                if is_connected; then
                    prof=$(active_profile)
                    echo -e "  Reconectando: ${CYAN}${VPN_NAME[$prof]}${NC}"
                    do_reconnect "$prof"
                else
                    profile=$(select_profile "reconectar") && do_reconnect "$profile"
                fi ;;
            4)
                profile=$(select_profile "abrir browser") && do_open_browser "$profile" ;;
            5)
                profile=$(select_profile "ver log") && do_show_log "$profile" ;;
            0) exit 0 ;;
            *) echo -e "${RED}Opção inválida.${NC}" ;;
        esac

        echo ""
        read -rp "  Pressione Enter para continuar..."
    done
}

# ── Entry point ───────────────────────────────────────────────────────────────

case "${1:-}" in
    connect)    do_connect "${2:-}" ;;
    disconnect) do_disconnect ;;
    reconnect)  do_reconnect "${2:-}" ;;
    status)     show_status ;;
    log)        do_show_log "${2:-minha-vpn}" ;;
    *)          menu ;;
esac
