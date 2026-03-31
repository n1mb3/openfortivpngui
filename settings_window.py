import copy
import threading
import time
import tkinter as tk


BG    = "#1a1a2e"
CARD  = "#16213e"
BORDER = "#0f3460"
FG    = "#e0e0e0"
ACCENT = "#7eb8f7"
GREEN  = "#27ae60"
RED    = "#c0392b"
INPUT  = "#0f3460"


def open_settings(profiles, on_save):
    """Opens the settings window in a background thread. on_save(new_profiles) called on save."""

    def _run():
        data = copy.deepcopy(profiles)
        root = tk.Tk()
        root.title("openfortivpngui — Configurações VPN")
        root.geometry("600x530")
        root.configure(bg=BG)
        root.resizable(False, False)

        # ── Título ───────────────────────────────────────────────────────────
        tk.Label(
            root, text="⚙  openfortivpngui — Configurações VPN",
            bg=BG, fg=ACCENT, font=("sans-serif", 13, "bold"), pady=16
        ).pack(anchor="w", padx=24)

        # ── Área scrollável ──────────────────────────────────────────────────
        outer = tk.Frame(root, bg=BG)
        outer.pack(fill="both", expand=True, padx=24)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Mouse wheel scroll
        def _scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _scroll)
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        def redraw():
            for w in inner.winfo_children():
                w.destroy()
            for idx, p in enumerate(data):
                _draw_card(root, inner, canvas, data, idx, p, redraw)

        # ── Botões inferiores ────────────────────────────────────────────────
        act = tk.Frame(root, bg=BG)
        act.pack(fill="x", padx=24, pady=(6, 0))

        def add_profile():
            data.append({"id": f"vpn{int(time.time())}", "name": "Nova VPN", "gateway": "", "port": 443, "saml": True})
            redraw()
            root.after(50, lambda: canvas.yview_moveto(1.0))

        tk.Button(
            act, text="+ Adicionar perfil", bg=INPUT, fg=ACCENT, bd=1, relief="solid",
            cursor="hand2", font=("sans-serif", 11), activebackground="#1a4a8a",
            activeforeground=ACCENT, padx=10, pady=5, command=add_profile
        ).pack(side="left", padx=(0, 8))

        status_v = tk.StringVar()
        status_lbl = tk.Label(root, textvariable=status_v, bg=BG, fg=GREEN, font=("sans-serif", 10))
        status_lbl.pack(padx=24, anchor="w", pady=(4, 0))

        def do_save():
            on_save(copy.deepcopy(data))
            status_v.set("✓ Configurações salvas com sucesso.")
            root.after(3000, lambda: status_v.set(""))

        tk.Button(
            act, text="Salvar", bg=GREEN, fg="white", bd=0, cursor="hand2",
            font=("sans-serif", 11, "bold"), activebackground="#2ecc71",
            activeforeground="white", padx=14, pady=5, command=do_save
        ).pack(side="left")

        redraw()
        root.mainloop()

    threading.Thread(target=_run, daemon=True).start()


def _draw_card(root, inner, canvas, data, idx, p, redraw):
    card = tk.Frame(inner, bg=CARD, padx=14, pady=10)
    card.pack(fill="x", pady=(0, 8))

    # ── Nome + botão remover ─────────────────────────────────────────────────
    row = tk.Frame(card, bg=CARD)
    row.pack(fill="x", pady=(0, 8))

    name_v = tk.StringVar(value=p.get("name", ""))
    name_v.trace_add("write", lambda *_: data[idx].update({"name": name_v.get()}))
    tk.Entry(
        row, textvariable=name_v, bg=CARD, fg=FG, bd=0,
        font=("sans-serif", 12, "bold"), insertbackground=FG,
        highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT
    ).pack(side="left", fill="x", expand=True, pady=2)

    tk.Button(
        row, text="Remover", bg=CARD, fg=RED, bd=1, relief="solid",
        cursor="hand2", font=("sans-serif", 9), activebackground=RED, activeforeground="white",
        command=lambda i=idx: (data.pop(i), redraw())
    ).pack(side="right", padx=(8, 0))

    # ── Gateway + Porta ──────────────────────────────────────────────────────
    fields = tk.Frame(card, bg=CARD)
    fields.pack(fill="x", pady=(0, 6))

    gw_f = tk.Frame(fields, bg=CARD)
    gw_f.pack(side="left", fill="x", expand=True, padx=(0, 8))
    tk.Label(gw_f, text="GATEWAY", bg=CARD, fg="#888", font=("sans-serif", 8)).pack(anchor="w")
    gw_v = tk.StringVar(value=p.get("gateway", ""))
    gw_v.trace_add("write", lambda *_: data[idx].update({"gateway": gw_v.get()}))
    tk.Entry(
        gw_f, textvariable=gw_v, bg=INPUT, fg=FG, bd=0, insertbackground=FG,
        highlightthickness=1, highlightbackground="#1a4a8a", highlightcolor=ACCENT,
        font=("sans-serif", 11)
    ).pack(fill="x", ipady=5)

    pt_f = tk.Frame(fields, bg=CARD)
    pt_f.pack(side="left")
    tk.Label(pt_f, text="PORTA", bg=CARD, fg="#888", font=("sans-serif", 8)).pack(anchor="w")
    pt_v = tk.StringVar(value=str(p.get("port", 443)))

    def _update_port(v=pt_v, i=idx):
        try:
            data[i]["port"] = int(v.get())
        except ValueError:
            pass

    pt_v.trace_add("write", lambda *_: _update_port())
    tk.Entry(
        pt_f, textvariable=pt_v, width=7, bg=INPUT, fg=FG, bd=0, insertbackground=FG,
        highlightthickness=1, highlightbackground="#1a4a8a", highlightcolor=ACCENT,
        font=("sans-serif", 11)
    ).pack(fill="x", ipady=5)

    # ── Toggle SAML ──────────────────────────────────────────────────────────
    saml_v = tk.BooleanVar(value=p.get("saml", True))
    saml_v.trace_add("write", lambda *_: data[idx].update({"saml": saml_v.get()}))
    tk.Checkbutton(
        card, variable=saml_v, text="Autenticação SAML (Single Sign-On com navegador externo)",
        bg=CARD, fg="#aaa", font=("sans-serif", 10), selectcolor=CARD,
        activebackground=CARD, activeforeground=FG, cursor="hand2"
    ).pack(anchor="w")
