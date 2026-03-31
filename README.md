<div align="center">
  <img src="icons/icon.png" width="96" alt="openfortivpngui icon" />
  <h1>openfortivpngui</h1>
  <p>Sistema tray GUI para <strong>openfortivpn</strong> — suporta múltiplas VPNs simultâneas e autenticação SAML</p>

  ![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
  ![Linux](https://img.shields.io/badge/Linux-Fedora%20%7C%20Ubuntu%20%7C%20Arch-orange?logo=linux&logoColor=white)
  ![License](https://img.shields.io/badge/license-MIT-green)
</div>

---

## ✨ Funcionalidades

- **Bandeja do sistema** — roda em segundo plano, sem janela
- **Múltiplas VPNs simultâneas** — conecte a quantos perfis quiser ao mesmo tempo
- **Autenticação SAML** — abre o Firefox automaticamente na URL de login
- **Perfis configuráveis** — adicione, edite e remova gateways pela interface gráfica
- **Autostart** — inicia automaticamente com o sistema operacional
- **Instalador embutido** — um script configura tudo (sudoers, launcher, autostart)

---

## 📸 Preview

| Desconectado | Conectando | Conectado |
|:---:|:---:|:---:|
| `○ Conectar "Sua Conexão"` | `◌ Sua Conexão — conectando…` | `● Sua Conexão  (10.x.x.x)` |

---

## 📋 Pré-requisitos

| Requisito | Fedora/RHEL | Debian/Ubuntu | Arch |
|---|---|---|---|
| openfortivpn | `sudo dnf install openfortivpn` | `sudo apt install openfortivpn` | `sudo pacman -S openfortivpn` |
| Python 3.10+ | já incluso | já incluso | já incluso |
| pystray | `sudo dnf install python3-pystray` | `sudo apt install python3-pystray` | `sudo pacman -S python-pystray` |
| Pillow | `sudo dnf install python3-pillow` | `sudo apt install python3-pillow` | `sudo pacman -S python-pillow` |

---

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/openfortivpngui.git
cd openfortivpngui
```

### 2. Instale as dependências do sistema (Fedora)

```bash
sudo dnf install openfortivpn python3-pystray python3-pillow
```

### 3. Configure o sudo sem senha para openfortivpn

O app precisa rodar `openfortivpn` como root sem pedir senha. Use o script de instalação:

```bash
sudo bash install-openfortivpn.sh
```

Ou configure manualmente:

```bash
sudo visudo -f /etc/sudoers.d/openfortivpn
# Adicione a linha abaixo (substitua SEU_USUARIO):
# SEU_USUARIO ALL=(ALL) NOPASSWD: /usr/bin/openfortivpn, /usr/bin/killall
```

### 4. Instale o launcher no sistema

```bash
python3 install.py
```

Isso cria:
- Ícone e entrada no launcher do GNOME/KDE (`python3 install.py`)
- Autostart ao logar

Para remover:
```bash
python3 install.py --remove
```

---

## ▶️ Executar manualmente

```bash
python3 main.py
```

---

## ⚙️ Configuração de perfis

As configurações ficam em `~/.config/openfortivpngui/config.json`.

Clique com o botão direito no ícone da bandeja → **Editar configurações…** para adicionar ou editar perfis pela interface gráfica.

Campos de cada perfil:

| Campo | Descrição | Exemplo |
|---|---|---|
| `name` | Nome exibido no menu | `Minha VPN` |
| `gateway` | Endereço do servidor VPN | `vpn.exemplo.com` |
| `port` | Porta do servidor | `443` |
| `saml` | Usar autenticação SAML | `true` |

---

## 🗂️ Estrutura do projeto

```
openfortivpngui/
├── main.py              # Ponto de entrada — bandeja do sistema
├── vpn.py               # Gerenciador de conexão VPN (um por perfil)
├── config.py            # Persistência de perfis (JSON)
├── settings_window.py   # Janela de configurações (tkinter)
├── install.py           # Instala/remove o launcher no sistema
├── install-openfortivpn.sh  # Configura openfortivpn e sudoers
├── icons/
│   └── icon.png         # Ícone do app (256×256)
└── requirements.txt
```

---

## 🔧 Como funciona

1. O app inicia na bandeja do sistema sem janelas
2. Ao clicar em **Conectar**, executa `sudo openfortivpn <gateway> --saml-login`
3. A saída do processo é redirecionada para `~/.cache/openfortivpngui/<perfil>.log`
4. O app monitora o log e, ao detectar a URL SAML, abre o **Firefox** automaticamente
5. Após o login no browser, monitora até aparecer `Tunnel is up and running`
6. O status é atualizado na bandeja; múltiplos perfis são monitorados de forma independente

---

## 🐧 Compatibilidade

Testado em **Fedora 41** com GNOME. Deve funcionar em qualquer distro Linux com:
- `openfortivpn` instalado
- Ambiente gráfico com suporte a system tray (GNOME + AppIndicator, KDE, XFCE…)

> **GNOME puro** pode exigir a extensão [AppIndicator and KStatusNotifierItem](https://extensions.gnome.org/extension/615/appindicator-support/) para exibir o ícone na bandeja.

---

## 📄 Licença

MIT — veja [LICENSE](LICENSE) para detalhes.
