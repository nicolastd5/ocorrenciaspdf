#!/usr/bin/env python3
"""
Processador de Ocorrências v1.17
==================================
Aplicação desktop para extrair ocorrências de PDFs de jornada
e preencher a coluna MOTIVO em planilhas Excel de pedido.

Autor: Nicolas Almeida Hader Dias
Uso: python app.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
from datetime import datetime
import json
from processador import ProcessadorOcorrencias
from vt_caixa_processador import ProcessadorVTCaixa
from license_client import LicenseClient, LicenseStatus
from license_ui import show_activation_window, show_error_window
from auto_update import check_and_update

# ── Config local (API keys e preferências — não versionado) ─────────────────
_CONFIG_PATH = os.path.join(os.path.expanduser('~'), '.ocorrencias_config.json')


# ── Carregamento de fontes embutidas (Inter + JetBrains Mono) ────────────────
def _assets_dir() -> str:
    """Resolve a pasta `assets/` tanto em dev quanto no exe do PyInstaller."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'assets')


def _carregar_fontes_embutidas() -> tuple[str, str]:
    """Registra os TTFs Inter + JetBrains Mono no processo via Windows API.
    Retorna (sans_family, mono_family). Cai em Segoe UI / Consolas se falhar.
    """
    sans, mono = 'Segoe UI', 'Consolas'
    if sys.platform != 'win32':
        return sans, mono
    try:
        import ctypes
        FR_PRIVATE = 0x10
        gdi = ctypes.windll.gdi32
        font_dir = os.path.join(_assets_dir(), 'fonts')
        if not os.path.isdir(font_dir):
            return sans, mono
        ok_any = False
        for fname in (
            'Inter-Regular.ttf', 'Inter-Medium.ttf',
            'Inter-SemiBold.ttf', 'Inter-Bold.ttf',
            'JetBrainsMono-Regular.ttf', 'JetBrainsMono-Medium.ttf',
        ):
            path = os.path.join(font_dir, fname)
            if not os.path.isfile(path):
                continue
            n = gdi.AddFontResourceExW(ctypes.c_wchar_p(path), FR_PRIVATE, 0)
            if n:
                ok_any = True
        if ok_any:
            sans, mono = 'Inter', 'JetBrains Mono'
    except Exception:
        pass
    return sans, mono


FONT_SANS, FONT_MONO = _carregar_fontes_embutidas()


def _resolver_licenca(client, result) -> bool:
    """Resolve um resultado de licença não-válido pedindo a chave em loop.
    Retorna True se a licença foi resolvida, False se o usuário cancelou."""
    while True:
        if result.status == LicenseStatus.VALID or result.status == LicenseStatus.OFFLINE_TOLERATED:
            return True

        if result.status == LicenseStatus.NO_KEY:
            new_key = show_activation_window("Insira sua chave de licença para começar.")
        elif result.status == LicenseStatus.INVALID:
            reason_msg = {
                "not_found": "Chave não reconhecida.",
                "revoked": "Esta chave foi revogada. Entre em contato com o suporte.",
            }.get(result.reason, "Chave inválida.")
            new_key = show_activation_window(reason_msg)
        elif result.status == LicenseStatus.OFFLINE_EXPIRED:
            show_error_window(
                "Não foi possível validar sua licença com o servidor e o "
                "período de uso offline expirou. Conecte-se à internet e tente novamente."
            )
            return False
        else:
            return False

        if new_key is None:
            return False

        client.save_key(new_key)
        result = client.validate()


def bootstrap_license() -> bool:
    """Valida licença antes de abrir o app. Retorna True se app deve continuar."""
    client = LicenseClient()
    result = client.validate()
    return _resolver_licenca(client, result)


def _carregar_config():
    """Carrega config local. Retorna {} se o arquivo não existe (primeira execução)."""
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        # JSON corrompido ou permissão negada — avisa mas não quebra a UI
        import sys
        print(f'[config] Falha ao carregar {_CONFIG_PATH}: {e}', file=sys.stderr)
        return {}


def _salvar_config(dados):
    """Salva config local. Retorna mensagem de erro se falhar, ou None se OK."""
    try:
        cfg = _carregar_config()
        cfg.update(dados)
        with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
        return None
    except Exception as e:
        return str(e)

from license_client import LicenseClient as _LC
VERSION = _LC.APP_VERSION

# ============================================================
# Configurações visuais
# ============================================================
CORES = {
    'bg':              '#0a0b12',
    'bg_card':         '#14161f',
    'bg_input':        '#0e1019',
    'fg':              '#b4b8cc',
    'fg_dim':          '#6e7591',
    'fg_bright':       '#e6e8f0',
    'accent':          '#5b8def',
    'accent_light':    '#a8c0ff',
    'accent_hover':    '#4a78d4',
    'accent_faded':    '#16192a',
    'success':         '#4ade80',
    'error':           '#f87171',
    'warning':         '#fbbf24',
    'border':          '#262a3a',
    'border_hover':    '#353a52',
    'btn_bg':          '#5b8def',
    'btn_fg':          '#ffffff',
    'btn_hover':       '#7aa3f5',
    'chip_on':         '#16192a',
    'chip_off':        '#14161f',
    'chip_border_on':  '#5b8def',
    'chip_border_off': '#262a3a',
    'table_header':    '#1a1d29',
}


# ── Botão arredondado (Canvas) ──────────────────────────────────────────────
class RoundedButton(tk.Canvas):
    """Botão pintado em Canvas com cantos arredondados (radius 6-10px).
    Variantes: 'primary' (accent), 'ghost' (surface+border), 'danger' (error),
    'mini' (transparente fundo bg_input).
    """

    _VARIANTS = {
        # variant: (bg, fg, bg_hover, fg_hover, has_border)
        'primary': (CORES['accent'],     '#ffffff',           CORES['accent_hover'], '#ffffff',           False),
        'ghost':   (CORES['bg_input'],   CORES['fg_bright'],  CORES['bg_card'],      CORES['fg_bright'],  True),
        'danger':  (CORES['error'],      '#ffffff',           '#d65454',             '#ffffff',           False),
        'mini':    (CORES['bg_input'],   CORES['fg'],         CORES['border'],       CORES['fg_bright'],  True),
        'success': (CORES['success'],    CORES['bg'],         '#86efac',             CORES['bg'],         False),
    }

    def __init__(self, parent, text='', command=None,
                 variant='primary', radius=8,
                 font=None, padx=18, pady=10,
                 width=None, full_width=False, parent_bg=None, **kw):
        bg_outer = parent_bg or parent.cget('bg')
        super().__init__(parent, bg=bg_outer, highlightthickness=0,
                         borderwidth=0, cursor='hand2', **kw)
        self._text = text
        self._command = command
        self._radius = radius
        self._padx = padx
        self._pady = pady
        self._font = font or (FONT_SANS, 10, 'bold')
        self._enabled = True
        self._full_width = full_width
        bg, fg, bg_hover, fg_hover, has_border = self._VARIANTS.get(
            variant, self._VARIANTS['primary'])
        self._bg, self._fg = bg, fg
        self._bg_hover, self._fg_hover = bg_hover, fg_hover
        self._has_border = has_border
        self._variant = variant

        # Mede o texto pra dimensionar
        self._txt_id = self.create_text(0, 0, text=text, font=self._font, fill=fg)
        bbox = self.bbox(self._txt_id)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        self.delete(self._txt_id)
        self._text_h = text_h

        h = text_h + pady * 2
        self._h = h
        if full_width:
            self.configure(height=h)
            self._rb_w = max(120, text_w + padx * 2)
            # Desenha pela primeira vez no after_idle, depois do <Configure>
            self.bind('<Configure>', self._on_resize)
            self.after_idle(lambda: self._draw(hover=False))
        else:
            w = width or (text_w + padx * 2)
            self.configure(width=w, height=h)
            self._rb_w = w
            self._draw(hover=False)

        self.bind('<Enter>', lambda e: self._draw(hover=True))
        self.bind('<Leave>', lambda e: self._draw(hover=False))
        self.bind('<Button-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)

    def _on_resize(self, e):
        if self._full_width and e.width > 1:
            self._rb_w = e.width
            try:
                self._draw(hover=False)
            except tk.TclError:
                pass

    def _draw(self, hover=False):
        self.delete('all')
        bg = self._bg_hover if hover else self._bg
        fg = self._fg_hover if hover else self._fg
        r = self._radius
        w, h = self._rb_w, self._h

        # Pinta um rect arredondado: 4 ovais nos cantos + 2 rects no meio
        self.create_oval(0, 0, 2*r, 2*r, fill=bg, outline=bg)
        self.create_oval(w - 2*r, 0, w, 2*r, fill=bg, outline=bg)
        self.create_oval(0, h - 2*r, 2*r, h, fill=bg, outline=bg)
        self.create_oval(w - 2*r, h - 2*r, w, h, fill=bg, outline=bg)
        self.create_rectangle(r, 0, w - r, h, fill=bg, outline=bg)
        self.create_rectangle(0, r, w, h - r, fill=bg, outline=bg)

        # Borda 1px (ghost/mini)
        if self._has_border:
            border = CORES['border_hover'] if hover else CORES['border']
            # Linhas arredondadas — usa arcos
            self.create_arc(0, 0, 2*r, 2*r, start=90, extent=90,
                            style='arc', outline=border, width=1)
            self.create_arc(w - 2*r, 0, w, 2*r, start=0, extent=90,
                            style='arc', outline=border, width=1)
            self.create_arc(0, h - 2*r, 2*r, h, start=180, extent=90,
                            style='arc', outline=border, width=1)
            self.create_arc(w - 2*r, h - 2*r, w, h, start=270, extent=90,
                            style='arc', outline=border, width=1)
            self.create_line(r, 0, w - r, 0, fill=border)
            self.create_line(r, h, w - r, h, fill=border)
            self.create_line(0, r, 0, h - r, fill=border)
            self.create_line(w, r, w, h - r, fill=border)

        self.create_text(w / 2, h / 2, text=self._text,
                         font=self._font, fill=fg)

    def _on_press(self, _e):
        if not self._enabled:
            return
        # press feedback: redesenha 1px deslocado seria caro — só escurece
        self._draw(hover=True)

    def _on_release(self, _e):
        if not self._enabled:
            return
        self._draw(hover=False)
        if self._command:
            self._command()

    def configure(self, **kw):
        if 'text' in kw:
            self._text = kw.pop('text')
            self._draw(hover=False)
        if 'state' in kw:
            self._enabled = (kw.pop('state') != 'disabled')
            # estado disabled: usa fg_dim
            if not self._enabled:
                self._fg = CORES['fg_dim']
                self._fg_hover = CORES['fg_dim']
            else:
                bg, fg, bg_hover, fg_hover, _ = self._VARIANTS[self._variant]
                self._fg, self._fg_hover = fg, fg_hover
            self._draw(hover=False)
        if 'command' in kw:
            self._command = kw.pop('command')
        if kw:
            super().configure(**kw)

    config = configure


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Processador de Ocorrências")
        self.geometry("1080x780")
        self.configure(bg=CORES['bg'])
        self.minsize(1000, 650)

        self.pdf_path = tk.StringVar()
        self.xlsx_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.codigos_vars = {}
        self.codigos_update_fns = {}
        self.processando = False
        self._anim_job = None
        self._anim_frame = 0
        self._historico = []
        self._historico_vtc = []
        self._janela_progresso = None
        self.deduzir_dias = tk.BooleanVar(value=False)
        self.dias_mes = tk.StringVar(value="")
        self.qt_va_var = tk.BooleanVar(value=True)
        self.qt_vr_var = tk.BooleanVar(value=True)
        self.qt_vt_var = tk.BooleanVar(value=True)

        # Modo de verificação: 'unica', 'dupla', 'ia'
        self.modo_verificacao = tk.StringVar(value='unica')
        self.verif_api_key = tk.StringVar(value='')
        self.verif_modelo = tk.StringVar(value='')
        self._verif_api_row = None

        # VT Caixa
        _cfg = _carregar_config()
        self.vtc_pdf_path    = tk.StringVar()
        self.vtc_xls_path    = tk.StringVar()
        self.vtc_output_path = tk.StringVar()
        self.vtc_usar_ia     = tk.BooleanVar(value=False)
        self.vtc_api_key     = tk.StringVar(value='')
        self.vtc_model_id    = tk.StringVar(value=_cfg.get('vtc_model_id', 'gemini-2.5-flash'))
        self.vtc_models_map       = {}   # "display — id" → model_id puro
        self.vtc_processando      = False
        self._vtc_anim_frames     = []
        self._vtc_anim_job        = None
        self._vtc_anim_frame      = 0
        self._vtc_janela_progresso = None

        self.verif_api_key.set(_cfg.get('gemini_api_key_ocorrencias', ''))
        self.verif_modelo.set(_cfg.get('gemini_modelo_ocorrencias', ''))
        self.vtc_api_key.set(_cfg.get('vtc_api_key', ''))

        self.processador = ProcessadorOcorrencias()
        self._criar_interface()
        self._centralizar_janela()
        self.after(1500, self._verificar_atualizacao)

    def _centralizar_janela(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')

    # ------------------------------------------------------------------
    # Auto-update
    # ------------------------------------------------------------------

    def _formatar_ultima_validacao(self):
        """Lê last_validated_at do config e devolve string legível (ou '—')."""
        try:
            from license_client import LicenseClient
            cfg = LicenseClient()._read_config()
            ts = cfg.get('last_validated_at')
            if not ts:
                return '—'
            # Formato salvo é ISO 8601 (ex.: 2026-05-20T18:27:39+00:00)
            dt = datetime.fromisoformat(ts)
            try:
                dt_local = dt.astimezone()
            except Exception:
                dt_local = dt
            return dt_local.strftime('%d/%m/%Y %H:%M')
        except Exception:
            return '—'

    def _verificar_conexao_servidor(self):
        """Verifica conectividade e baixa config (API key Gemini) do servidor."""
        # Cancela qualquer countdown pendente — vamos reagendar ao terminar.
        if getattr(self, '_conn_countdown_job', None):
            try:
                self.after_cancel(self._conn_countdown_job)
            except Exception:
                pass
            self._conn_countdown_job = None

        # Marca os campos do card Sobre como "verificando" (se já existem).
        rows = getattr(self, '_sobre_status_rows', None)
        if rows:
            rows.get('CONEXÃO') and rows['CONEXÃO'].configure(
                text='Verificando…', fg=CORES['fg_dim'])
            rows.get('PRÓXIMA CHECAGEM') and rows['PRÓXIMA CHECAGEM'].configure(
                text='—', fg=CORES['fg_dim'])

        def _checar():
            from license_client import LicenseClient
            from auto_update import _fetch_latest, _parse_version
            client = LicenseClient()
            result = client.validate()
            latest_version = None
            try:
                latest = _fetch_latest()
                if latest:
                    latest_version = latest.get('version')
                    if latest_version and _parse_version(latest_version) > _parse_version(VERSION):
                        self.after(0, lambda v=latest_version: self._mostrar_banner_update(v))
            except Exception:
                pass
            self.after(0, lambda: self._atualizar_indicador_conexao(
                result.status, latest_version=latest_version, reason=result.reason))

            if result.status == LicenseStatus.VALID:
                key = client.get_saved_key()
                if key:
                    self._buscar_config_servidor(key)

        threading.Thread(target=_checar, daemon=True).start()

    def _buscar_config_servidor(self, license_key: str):
        """Baixa a API key do Gemini do servidor e preenche os campos."""
        import requests as _req
        from license_client import LicenseClient
        try:
            resp = _req.post(
                f"{LicenseClient.SERVER_URL}/api/config",
                json={"key": license_key},
                timeout=LicenseClient.TIMEOUT_SECONDS,
            )
            if resp.status_code == 200:
                data = resp.json()
                gemini_key = data.get("gemini_api_key", "")
                if gemini_key:
                    self.after(0, lambda: self._aplicar_gemini_key(gemini_key))
        except Exception:
            pass

    def _aplicar_gemini_key(self, key: str):
        """Aplica a API key do Gemini nos dois campos e salva no config local."""
        self.verif_api_key.set(key)
        self.vtc_api_key.set(key)
        cfg = _carregar_config()
        cfg['gemini_api_key_ocorrencias'] = key
        cfg['vtc_api_key'] = key
        _salvar_config(cfg)
        rows = getattr(self, '_sobre_status_rows', None)
        if rows and rows.get('API GEMINI'):
            mascara = (key[:6] + '…' + key[-4:]) if len(key) > 12 else 'configurada'
            rows['API GEMINI'].configure(text=mascara, fg=CORES['fg_bright'])

    CONN_REFRESH_INTERVAL = 60  # segundos entre revalidações automáticas

    def _atualizar_indicador_conexao(self, status, latest_version=None, reason=None):
        if status == LicenseStatus.VALID:
            cor, bg, borda, texto = CORES['success'], '#0f1a14', '#1f3a2a', 'Conectado ao servidor'
            card_conn_text, card_conn_cor = 'Conectado', CORES['success']
        elif status == LicenseStatus.OFFLINE_TOLERATED:
            if reason == 'no_internet':
                texto = 'Sem internet — uso tolerado'
                card_conn_text = 'Sem internet (tolerado)'
            else:
                texto = 'Servidor indisponível — uso tolerado'
                card_conn_text = 'Servidor indisponível (tolerado)'
            cor, bg, borda = CORES['warning'], '#1a1610', '#3a3220'
            card_conn_cor = CORES['warning']
        else:
            if reason == 'no_internet':
                texto = 'Sem conexão com a internet'
                card_conn_text = 'Sem internet'
            else:
                texto = 'Servidor indisponível'
                card_conn_text = 'Servidor indisponível'
            cor, bg, borda = CORES['error'], '#1a0f10', '#3a1f22'
            card_conn_cor = CORES['error']

        self._conn_pill.configure(bg=bg, highlightbackground=borda)
        self._conn_dot.configure(fg=cor, bg=bg)
        self._conn_label.configure(text=texto, fg=cor, bg=bg)

        # Atualiza o card "Status do servidor" da aba Sobre.
        rows = getattr(self, '_sobre_status_rows', None)
        if rows:
            if rows.get('CONEXÃO'):
                rows['CONEXÃO'].configure(text=card_conn_text, fg=card_conn_cor)
            if latest_version and rows.get('VERSÃO MAIS RECENTE'):
                rows['VERSÃO MAIS RECENTE'].configure(
                    text=f'v{latest_version}', fg=CORES['fg_bright'])

        # Atualiza "ÚLTIMA VALIDAÇÃO" no card Informações.
        info_rows = getattr(self, '_sobre_info_rows', None)
        if info_rows and info_rows.get('ÚLTIMA VALIDAÇÃO'):
            info_rows['ÚLTIMA VALIDAÇÃO'].configure(
                text=self._formatar_ultima_validacao())

        # Agenda nova checagem automática.
        self._agendar_proxima_checagem(self.CONN_REFRESH_INTERVAL)

    def _agendar_proxima_checagem(self, segundos_restantes):
        """Mostra countdown em PRÓXIMA CHECAGEM e dispara revalidação ao zerar."""
        rows = getattr(self, '_sobre_status_rows', None)
        if rows and rows.get('PRÓXIMA CHECAGEM'):
            rows['PRÓXIMA CHECAGEM'].configure(
                text=f'em {segundos_restantes}s', fg=CORES['fg_dim'])
        if segundos_restantes <= 0:
            self._conn_countdown_job = None
            self._verificar_conexao_servidor()
            return
        self._conn_countdown_job = self.after(
            1000, lambda: self._agendar_proxima_checagem(segundos_restantes - 1))

    def _verificar_atualizacao(self):
        """Verifica nova versão no VPS em background (chamada automática ao iniciar)."""
        def _checar():
            from auto_update import _fetch_latest, _parse_version
            latest = _fetch_latest()
            if latest and _parse_version(latest.get("version", "0")) > _parse_version(VERSION):
                self.after(0, lambda: self._mostrar_banner_update(latest["version"]))

        threading.Thread(target=_checar, daemon=True).start()

    @staticmethod
    def _parse_versao(v):
        try:
            return tuple(int(x) for x in v.strip().split('.'))
        except Exception:
            return (0,)

    def _buscar_versao_vps(self):
        """Consulta o VPS e retorna (versao, erro). Síncrono — chamar em thread."""
        from auto_update import _fetch_latest
        try:
            latest = _fetch_latest()
            if latest:
                return latest.get("version"), None
            return None, "Sem resposta do servidor."
        except Exception as e:
            return None, str(e)

    def _mostrar_banner_update(self, nova_versao):
        """Exibe um banner discreto de atualização disponível."""
        if hasattr(self, '_banner_update') and self._banner_update.winfo_exists():
            return

        BANNER_BG = '#0f1a14'
        banner = tk.Frame(self, bg=BANNER_BG,
                          highlightbackground=CORES['success'], highlightthickness=1)
        banner.pack(fill='x', padx=20, pady=(4, 0))
        self._banner_update = banner

        inner = tk.Frame(banner, bg=BANNER_BG)
        inner.pack(fill='x', padx=14, pady=8)

        tk.Label(inner,
                 text=f"Nova versão disponível: v{nova_versao}",
                 font=(FONT_SANS, 10, "bold"),
                 fg=CORES['success'], bg=BANNER_BG).pack(side='left')

        RoundedButton(inner, text="Atualizar agora",
                      variant='success', radius=6,
                      font=(FONT_SANS, 9, "bold"),
                      padx=14, pady=6, parent_bg=BANNER_BG,
                      command=lambda: self._aplicar_update(nova_versao)
                      ).pack(side='right', padx=(8, 0))

        lbl_x = tk.Label(inner, text="✕",
                         font=(FONT_SANS, 11),
                         fg=CORES['success'], bg=BANNER_BG,
                         cursor='hand2', padx=8)
        lbl_x.pack(side='right')
        lbl_x.bind('<Button-1>', lambda e: banner.destroy())

    def _aplicar_update(self, nova_versao):
        """Baixa e aplica a atualização (fecha o app e relança o novo exe)."""
        from auto_update import _fetch_latest, _download_and_relaunch
        latest = _fetch_latest()
        if latest and latest.get("filename"):
            _download_and_relaunch(latest["filename"])
        else:
            messagebox.showerror("Erro", "Nao foi possivel obter o link de download.")

    def _bind_scroll(self, canvas, inner_frame):
        """Vincula scroll do mouse ao canvas e a todos os seus filhos recursivamente."""
        def _scroll(ev):
            canvas.yview_scroll(-1 * (ev.delta // 120), 'units')

        def _bind_tree(w):
            w.bind('<MouseWheel>', _scroll)
            for child in w.winfo_children():
                _bind_tree(child)

        canvas.bind('<MouseWheel>', _scroll)
        inner_frame.bind('<MouseWheel>', _scroll)

        # Re-vincula filhos novos quando inner_frame muda
        def _on_configure(e):
            _bind_tree(inner_frame)

        inner_frame.bind('<Configure>', _on_configure, add=True)

    def _bind_hover(self, widget, bg_normal, bg_hover, fg_normal=None, fg_hover=None):
        def on_enter(e):
            if str(widget.cget('state')) != 'disabled':
                widget.configure(bg=bg_hover)
                if fg_hover:
                    widget.configure(fg=fg_hover)
        def on_leave(e):
            if str(widget.cget('state')) != 'disabled':
                widget.configure(bg=bg_normal)
                if fg_normal:
                    widget.configure(fg=fg_normal)
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def _criar_interface(self):
        # Faixa gradiente no topo (signature header band)
        self._criar_faixa_gradiente_topo()

        # Linha 1: título + versão
        titlebar = tk.Frame(self, bg=CORES['bg'])
        titlebar.pack(fill='x', padx=20, pady=(12, 4))

        tk.Label(titlebar, text="Processador de Ocorrências",
                 font=(FONT_SANS, 13, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(side='left')

        tk.Label(titlebar, text=f"v{VERSION}",
                 font=(FONT_SANS, 9), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(side='left', padx=(6, 0), pady=(4, 0))

        # Indicador de conexão com o servidor
        self._conn_pill = tk.Frame(titlebar, bg=CORES['bg_card'],
                                   highlightbackground=CORES['border'],
                                   highlightthickness=1)
        self._conn_pill.pack(side='right', ipadx=10, ipady=4)
        self._conn_dot = tk.Label(self._conn_pill, text="●",
                                  font=(FONT_SANS, 7),
                                  fg=CORES['fg_dim'], bg=CORES['bg_card'])
        self._conn_dot.pack(side='left', padx=(0, 4))
        self._conn_label = tk.Label(self._conn_pill, text="Verificando...",
                                    font=(FONT_SANS, 9),
                                    fg=CORES['fg_dim'], bg=CORES['bg_card'])
        self._conn_label.pack(side='left')
        # Adiada para depois da construção das abas, garantindo que o card
        # "Status do servidor" da aba Sobre já exista quando o callback rodar.
        self.after(100, self._verificar_conexao_servidor)

        # Linha 2: abas centralizadas
        self._tab_btns = {}
        self._tab_frames = {}
        tabbar = tk.Frame(self, bg=CORES['bg'])
        tabbar.pack(fill='x', padx=20, pady=(0, 0))

        for tab_id, label in [('processar', '⚙  Processar'), ('historico', '🕘  Histórico'), ('vtcaixa', '💳  VT Caixa'), ('historico_vtc', '🕘  Hist. VT'), ('codigos', '🏷  Códigos'), ('sobre', 'ℹ  Sobre')]:
            btn = tk.Button(tabbar, text=label,
                            font=(FONT_SANS, 10),
                            fg=CORES['fg_dim'], bg=CORES['bg'],
                            relief='flat', cursor='hand2',
                            padx=12, pady=6, borderwidth=0,
                            command=lambda t=tab_id: self._mostrar_aba(t))
            btn.pack(side='left', padx=(0, 2))
            self._tab_btns[tab_id] = btn

        # Linha separadora
        tk.Frame(self, bg=CORES['border'], height=1).pack(fill='x', padx=20, pady=(4, 0))

        # Área de conteúdo
        content = tk.Frame(self, bg=CORES['bg'])
        content.pack(fill='both', expand=True, padx=20, pady=14)

        frame_processar = tk.Frame(content, bg=CORES['bg'])
        self._criar_aba_processar(frame_processar)
        self._tab_frames['processar'] = frame_processar

        frame_historico = tk.Frame(content, bg=CORES['bg'])
        self._criar_aba_historico(frame_historico)
        self._tab_frames['historico'] = frame_historico

        frame_vtcaixa = tk.Frame(content, bg=CORES['bg'])
        self._criar_aba_vtcaixa(frame_vtcaixa)
        self._tab_frames['vtcaixa'] = frame_vtcaixa

        frame_historico_vtc = tk.Frame(content, bg=CORES['bg'])
        self._criar_aba_historico_vtc(frame_historico_vtc)
        self._tab_frames['historico_vtc'] = frame_historico_vtc

        frame_codigos = tk.Frame(content, bg=CORES['bg'])
        self._criar_aba_codigos(frame_codigos)
        self._tab_frames['codigos'] = frame_codigos

        frame_sobre = tk.Frame(content, bg=CORES['bg'])
        self._criar_aba_sobre(frame_sobre)
        self._tab_frames['sobre'] = frame_sobre

        self._mostrar_aba('processar')

    def _criar_faixa_gradiente_topo(self):
        """Faixa 1px no topo: fade-in -> pico azul -> fade-out (signature)."""
        WIDTH, HEIGHT = 1400, 1
        canvas = tk.Canvas(self, height=HEIGHT, bg=CORES['bg'],
                           highlightthickness=0, borderwidth=0)
        canvas.pack(fill='x', side='top')

        def _interp(c1, c2, t):
            r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
            r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            return f'#{r:02x}{g:02x}{b:02x}'

        bg = CORES['bg']
        peak = CORES['accent_light']
        for x in range(WIDTH):
            ratio = x / WIDTH
            if ratio < 0.30:
                color = bg
            elif ratio < 0.50:
                color = _interp(bg, peak, (ratio - 0.30) / 0.20)
            elif ratio < 0.70:
                color = _interp(peak, bg, (ratio - 0.50) / 0.20)
            else:
                color = bg
            canvas.create_line(x, 0, x + 1, 0, fill=color)

    def _mostrar_aba(self, tab_id):
        for fid, frame in self._tab_frames.items():
            frame.pack_forget()
            if fid == tab_id:
                self._tab_btns[fid].configure(
                    fg=CORES['accent_light'], bg=CORES['bg_card'],
                    font=(FONT_SANS, 10, "bold"))
            else:
                self._tab_btns[fid].configure(
                    fg=CORES['fg_dim'], bg=CORES['bg'],
                    font=(FONT_SANS, 10))
        self._tab_frames[tab_id].pack(fill='both', expand=True)

    def _criar_aba_processar(self, parent):
        # Header da aba (h1 + subtitle + pills à direita)
        self._criar_header_aba(
            parent,
            "Processar ocorrências",
            "Cruze um PDF de jornada com a planilha de pedido e preencha a coluna MOTIVO.",
            pills=[
                lambda: f"{sum(1 for v in self.codigos_vars.values() if v.get())} códigos",
                lambda: {
                    'unica': 'Varredura única',
                    'dupla': 'Dupla varredura',
                    'ia':    'Dupla + IA',
                }.get(self.modo_verificacao.get(), ''),
            ],
        )

        # Botão Processar fixo no rodapé (fora do scroll)
        self.btn_processar = RoundedButton(
            parent, text="▶  PROCESSAR ARQUIVOS",
            variant='primary', radius=10,
            font=(FONT_SANS, 14, "bold"),
            pady=18, full_width=True,
            command=self._iniciar_processamento,
        )
        self.btn_processar.pack(side='bottom', fill='x', pady=(4, 0))

        # Área de Resultados (também fora do scroll, acima do botão)
        self.resultado_frame = tk.Frame(parent, bg=CORES['bg'])
        self.resultado_frame.pack(side='bottom', fill='x', pady=(8, 0))

        # Canvas scrollável para o conteúdo dos cards
        _canvas = tk.Canvas(parent, bg=CORES['bg'], highlightthickness=0)
        _vsb = ttk.Scrollbar(parent, orient='vertical', command=_canvas.yview)
        _scroll_inner = tk.Frame(_canvas, bg=CORES['bg'])
        _win_id = _canvas.create_window((0, 0), window=_scroll_inner, anchor='nw')
        _scroll_inner.bind(
            '<Configure>',
            lambda e: _canvas.configure(scrollregion=_canvas.bbox('all'))
        )
        _canvas.bind('<Configure>', lambda e: _canvas.itemconfig(_win_id, width=e.width))
        _canvas.configure(yscrollcommand=_vsb.set)
        _vsb.pack(side='right', fill='y')
        _canvas.pack(side='left', fill='both', expand=True)
        self._bind_scroll(_canvas, _scroll_inner)

        # A partir daqui, todos os cards vão em _scroll_inner
        parent = _scroll_inner

        # Seleção de Arquivos
        files_frame = self._criar_card(parent, "📁  Arquivos de Entrada")
        self._criar_file_picker(files_frame, "PDF de Faltas", self.pdf_path,
                                [("PDF", "*.pdf")], "Selecionar")
        self._criar_file_picker(files_frame, "Planilha Excel", self.xlsx_path,
                                [("Excel", "*.xlsx")], "Selecionar")

        # Códigos de Ocorrência
        codigos_frame = self._criar_card(parent, "🏷  Códigos de Ocorrência")

        btn_row = tk.Frame(codigos_frame, bg=CORES['bg_card'])
        btn_row.pack(fill='x', pady=(0, 6))

        self._criar_mini_btn(btn_row, "Selecionar Todos",
                             self._selecionar_todos).pack(side='left')
        self._criar_mini_btn(btn_row, "Limpar Seleção",
                             self._limpar_selecao).pack(side='left', padx=(8, 0))

        codes_grid = tk.Frame(codigos_frame, bg=CORES['bg_card'])
        codes_grid.pack(fill='x')

        codigos_info = [
            ('AT', 'Atestado', True),
            ('A-', 'Decl. Horas Negativas', True),
            ('FA', 'Faltas', True),
            ('AP', 'Afast. Previdenciário', False),
            ('LM', 'Afast. Maternidade', False),
            ('LC', 'Licença Casamento', True),
            ('SD', 'Suspensão Disciplinar', True),
            ('AA', 'Ausência Autorizada', True),
            ('FE', 'Férias', False),
            ('14', 'Luto', True),
            ('13', 'Falecimento', True),
        ]

        for i, (codigo, desc, tem_qtd) in enumerate(codigos_info):
            var = tk.BooleanVar(value=True)
            self.codigos_vars[codigo] = var
            self._criar_chip(codes_grid, codigo, desc, tem_qtd, var, i // 4, i % 4)

        for col in range(4):
            codes_grid.columnconfigure(col, weight=1)

        # ── Card Verificação ────────────────────────────────────────
        verif_frame = self._criar_card(parent, "🔍  Modo de verificação")

        modo_row = tk.Frame(verif_frame, bg=CORES['bg_card'])
        modo_row.pack(fill='x', pady=(2, 2))

        modos = [
            ('unica',  'Varredura única',    'Comportamento padrão'),
            ('dupla',  'Dupla varredura',    'V1 (tabelas) + V2 (texto/regex)'),
            ('ia',     'Dupla + IA (Gemini)','V1 + V2 + Gemini Vision'),
        ]

        _modo_widgets = {}  # {val: {'card':..., 'dot':..., 'label':..., 'desc':...}}

        def _atualizar_modo():
            modo = self.modo_verificacao.get()
            if modo == 'ia':
                self._verif_api_row.pack(fill='x', pady=(10, 0))
            else:
                self._verif_api_row.pack_forget()
            self._atualizar_header_pills()
            for m, w in _modo_widgets.items():
                on = (m == modo)
                bg = CORES['chip_on'] if on else CORES['bg_card']
                border = CORES['accent'] if on else CORES['border']
                w['card'].configure(bg=bg, highlightbackground=border)
                w['inner'].configure(bg=bg)
                w['dot_outer'].configure(bg=bg)
                w['dot'].configure(
                    bg=CORES['accent'] if on else CORES['bg_card'],
                    highlightbackground=CORES['accent'] if on else CORES['border_hover'],
                )
                w['label'].configure(
                    bg=bg,
                    fg=CORES['fg_bright'] if on else CORES['fg'],
                )
                w['desc'].configure(
                    bg=bg,
                    fg=CORES['accent_light'] if on else CORES['fg_dim'],
                )

        for val, label, descricao in modos:
            card = tk.Frame(modo_row, bg=CORES['bg_card'], cursor='hand2',
                            highlightbackground=CORES['border'], highlightthickness=1)
            card.pack(side='left', fill='x', expand=True, padx=(0, 6))
            inner = tk.Frame(card, bg=CORES['bg_card'])
            inner.pack(fill='both', expand=True, padx=12, pady=10)

            # Radio dot (círculo com fundo accent quando ON)
            dot_outer = tk.Frame(inner, bg=CORES['bg_card'])
            dot_outer.pack(side='left', padx=(0, 10))
            dot = tk.Frame(dot_outer, width=12, height=12, bg=CORES['bg_card'],
                           highlightbackground=CORES['border_hover'], highlightthickness=2)
            dot.pack()
            dot.pack_propagate(False)

            col = tk.Frame(inner, bg=CORES['bg_card'])
            col.pack(side='left', fill='both', expand=True)
            lbl = tk.Label(col, text=label, font=(FONT_SANS, 10, "bold"),
                           fg=CORES['fg'], bg=CORES['bg_card'], anchor='w')
            lbl.pack(anchor='w')
            desc = tk.Label(col, text=descricao, font=(FONT_MONO, 8),
                            fg=CORES['fg_dim'], bg=CORES['bg_card'], anchor='w')
            desc.pack(anchor='w', pady=(2, 0))

            _modo_widgets[val] = {
                'card': card, 'inner': inner,
                'dot_outer': dot_outer, 'dot': dot,
                'label': lbl, 'desc': desc,
            }
            for w in [card, inner, dot_outer, dot, col, lbl, desc]:
                w.bind('<Button-1>', lambda e, v=val: (self.modo_verificacao.set(v), _atualizar_modo()))

        # Subpainel da API Key (visível só em modo 'ia')
        self._verif_api_row = tk.Frame(verif_frame, bg=CORES['bg_card'])

        api_linha = tk.Frame(self._verif_api_row, bg=CORES['bg_card'])
        api_linha.pack(fill='x', pady=(0, 4))
        tk.Label(api_linha, text="API Key Gemini:",
                 font=(FONT_SANS, 10), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='left', padx=(0, 8))
        tk.Entry(api_linha, textvariable=self.verif_api_key,
                 font=(FONT_SANS, 10), fg=CORES['fg_bright'],
                 bg=CORES['bg_input'], insertbackground=CORES['fg'],
                 relief='flat', highlightbackground=CORES['accent'],
                 highlightthickness=1, show='*', width=36).pack(side='left')

        modelo_linha = tk.Frame(self._verif_api_row, bg=CORES['bg_card'])
        modelo_linha.pack(fill='x', pady=(0, 2))
        tk.Label(modelo_linha, text="Modelo:",
                 font=(FONT_SANS, 10), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='left', padx=(0, 8))
        self._verif_modelo_combo = ttk.Combobox(
            modelo_linha,
            font=(FONT_SANS, 10), width=30, state='readonly')
        self._verif_modelo_combo.pack(side='left')
        self._criar_mini_btn(
            modelo_linha, "Carregar modelos",
            self._verif_carregar_modelos
        ).pack(side='left', padx=(8, 0))

        _atualizar_modo()

        # Opções adicionais
        opcoes_frame = self._criar_card(parent, "⚙  Opções")

        self._criar_checkbox(
            opcoes_frame,
            "Preencher e deduzir dias nas colunas Qt",
            "Preenche as colunas Qt selecionadas com a quantidade de dias do mês informada, "
            "deduzindo os dias de ocorrências FA, AT, SD e LC para quem as tiver.",
            self.deduzir_dias,
            on_toggle=self._toggle_dias_mes,
        )

        # Subpainel (visível só quando checkbox ativo)
        self._dias_mes_row = tk.Frame(opcoes_frame, bg=CORES['bg_card'])

        # Linha 1: campo de dias
        linha_dias = tk.Frame(self._dias_mes_row, bg=CORES['bg_card'])
        linha_dias.pack(fill='x', pady=(2, 6))
        tk.Label(linha_dias, text="Dias do mês:",
                 font=(FONT_SANS, 10), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='left', padx=(28, 8))
        vcmd = (self.register(lambda s: s.isdigit() and int(s) <= 31 if s else True), '%P')
        self._entry_dias = tk.Entry(
            linha_dias, textvariable=self.dias_mes,
            font=(FONT_SANS, 11, "bold"), width=5,
            fg=CORES['fg_bright'], bg=CORES['bg_input'],
            insertbackground=CORES['fg'], relief='flat',
            highlightbackground=CORES['accent'], highlightthickness=1,
            justify='center', validate='key', validatecommand=vcmd,
        )
        self._entry_dias.pack(side='left')
        tk.Label(linha_dias, text="dias",
                 font=(FONT_SANS, 10), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='left', padx=(6, 0))

        # Linha 2: seleção de colunas Qt
        linha_qt = tk.Frame(self._dias_mes_row, bg=CORES['bg_card'])
        linha_qt.pack(fill='x', pady=(0, 4))
        tk.Label(linha_qt, text="Colunas:",
                 font=(FONT_SANS, 10), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='left', padx=(28, 12))

        for sigla, label, var in [
            ("VA", "Qt VA", self.qt_va_var),
            ("VR", "Qt VR", self.qt_vr_var),
            ("VT", "Qt VT", self.qt_vt_var),
        ]:
            self._criar_toggle_qt(linha_qt, sigla, label, var)


    def _criar_aba_historico(self, parent):
        self._historico_frame = parent

        header = tk.Frame(parent, bg=CORES['bg'])
        header.pack(fill='x', pady=(0, 12))

        tk.Label(header, text="🕘  Histórico de Processamentos",
                 font=(FONT_SANS, 14, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(side='left')

        RoundedButton(header, text="Limpar histórico", variant='mini', radius=6,
                      font=(FONT_SANS, 9), padx=12, pady=5,
                      command=self._limpar_historico).pack(side='right')

        self._historico_lista = tk.Frame(parent, bg=CORES['bg'])
        self._historico_lista.pack(fill='both', expand=True)

        self._historico_vazio = tk.Label(
            self._historico_lista,
            text="Nenhum processamento realizado ainda.",
            font=(FONT_SANS, 11), fg=CORES['fg_dim'], bg=CORES['bg'])
        self._historico_vazio.pack(pady=40)

    def _limpar_historico(self):
        self._historico.clear()
        self._atualizar_historico()

    def _atualizar_historico(self):
        for w in self._historico_lista.winfo_children():
            w.destroy()

        if not self._historico:
            tk.Label(self._historico_lista,
                     text="Nenhum processamento realizado ainda.",
                     font=(FONT_SANS, 11), fg=CORES['fg_dim'],
                     bg=CORES['bg']).pack(pady=40)
            return

        canvas = tk.Canvas(self._historico_lista, bg=CORES['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(self._historico_lista, orient='vertical', command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=CORES['bg'])
        scroll_frame.bind('<Configure>',
                          lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self._bind_scroll(canvas, scroll_frame)

        for i, entrada in enumerate(reversed(self._historico)):
            card = tk.Frame(scroll_frame, bg=CORES['bg_card'],
                            highlightbackground=CORES['border'], highlightthickness=1)
            card.pack(fill='x', pady=(0, 8))

            # Cabeçalho do card
            top = tk.Frame(card, bg=CORES['bg_card'])
            top.pack(fill='x', padx=14, pady=(10, 6))

            tk.Label(top, text=f"#{len(self._historico) - i}  {entrada['arquivo']}",
                     font=(FONT_SANS, 10, "bold"), fg=CORES['fg_bright'],
                     bg=CORES['bg_card']).pack(side='left')
            tk.Label(top, text=entrada['data'],
                     font=(FONT_SANS, 9), fg=CORES['fg_dim'],
                     bg=CORES['bg_card']).pack(side='right')

            # Stats inline
            stats_row = tk.Frame(card, bg=CORES['bg_card'])
            stats_row.pack(fill='x', padx=14, pady=(0, 8))

            nao_enc = entrada['nao_encontrados']
            for label, valor, cor in [
                ("No PDF", str(entrada['total_pdf']), CORES['accent_light']),
                ("Aplicados", str(entrada['matched']), CORES['success']),
                ("Não localizados", str(nao_enc),
                 CORES['error'] if nao_enc else CORES['success']),
            ]:
                bloco = tk.Frame(stats_row, bg=CORES['bg_input'])
                bloco.pack(side='left', padx=(0, 6))
                tk.Label(bloco, text=valor, font=(FONT_SANS, 13, "bold"),
                         fg=cor, bg=CORES['bg_input']).pack(side='left', padx=(8, 4), pady=4)
                tk.Label(bloco, text=label, font=(FONT_SANS, 8),
                         fg=CORES['fg_dim'], bg=CORES['bg_input']).pack(side='left', padx=(0, 8))

            # Não localizados
            if entrada['lista_nao_encontrados']:
                det = tk.Frame(card, bg=CORES['bg_card'])
                det.pack(fill='x', padx=14, pady=(0, 10))

                tk.Label(det, text="Não localizados:",
                         font=(FONT_SANS, 9, "bold"), fg=CORES['error'],
                         bg=CORES['bg_card']).pack(anchor='w', pady=(0, 4))

                for p in entrada['lista_nao_encontrados']:
                    tk.Label(det,
                             text=f"  RE {p['re']}  —  {p['nome']}  —  {p['motivo']}",
                             font=(FONT_MONO, 9), fg=CORES['fg_dim'],
                             bg=CORES['bg_card'], anchor='w').pack(fill='x')

    def _criar_aba_vtcaixa(self, parent):
        # ── Card: Arquivos ──────────────────────────────────────────────
        files_frame = self._criar_card(parent, "📁  Arquivos")
        self._criar_file_picker(files_frame, "Fonte Nautilus (PDF/Excel)", self.vtc_pdf_path,
                                [("PDF/Excel", "*.pdf *.xls *.xlsx *.xlsm *.xltx *.xltm"),
                                 ("PDF", "*.pdf"),
                                 ("Excel", "*.xls *.xlsx *.xlsm *.xltx *.xltm")], "Selecionar")
        self._criar_file_picker(files_frame, "Excel Cadastral", self.vtc_xls_path,
                                [("Excel", "*.xls *.xlsx"), ("Excel .xls", "*.xls"),
                                 ("Excel .xlsx", "*.xlsx")], "Selecionar")

        # File saver de saída (salvar como) — mesmo padrão visual dos pickers
        self._criar_file_saver(files_frame, "CSV de Saída", self.vtc_output_path)

        # Botão limpar todas as seleções
        limpar_row = tk.Frame(files_frame, bg=CORES['bg_card'])
        limpar_row.pack(fill='x', pady=(4, 0))
        RoundedButton(limpar_row, text="✕  Limpar seleções", variant='ghost', radius=6,
                      font=(FONT_SANS, 9), padx=14, pady=6,
                      parent_bg=CORES['bg_card'],
                      command=lambda: [
                          self.vtc_pdf_path.set(''),
                          self.vtc_xls_path.set(''),
                          self.vtc_output_path.set(''),
                      ]).pack(side='right')

        # ── Card: Opções IA ─────────────────────────────────────────────
        ia_card = self._criar_card(parent, "🤖  Verificação com IA (opcional)")

        ia_chk_row = tk.Frame(ia_card, bg=CORES['bg_card'])
        ia_chk_row.pack(fill='x', pady=(0, 4))

        def _toggle_ia():
            self.vtc_usar_ia.set(not self.vtc_usar_ia.get())
            _atualizar_ia()

        def _atualizar_ia(*_):
            on = self.vtc_usar_ia.get()
            ia_dot.configure(text="☑" if on else "☐",
                             fg=CORES['accent_light'] if on else CORES['fg_dim'])
            ia_lbl.configure(fg=CORES['fg_bright'] if on else CORES['fg'])
            if on:
                self._vtc_ia_key_frame.pack(fill='x', pady=(4, 0))
            else:
                self._vtc_ia_key_frame.pack_forget()

        ia_dot = tk.Label(ia_chk_row, text="☐", font=(FONT_SANS, 13),
                          fg=CORES['fg_dim'], bg=CORES['bg_card'], cursor='hand2')
        ia_dot.pack(side='left', padx=(0, 8))
        ia_lbl = tk.Label(ia_chk_row,
                          text="Verificar dados utilizando IA da Google Gemini ou Gemma 4",
                          font=(FONT_SANS, 10), fg=CORES['fg'],
                          bg=CORES['bg_card'], cursor='hand2')
        ia_lbl.pack(side='left')
        for w in (ia_dot, ia_lbl, ia_chk_row):
            w.bind('<Button-1>', lambda e: _toggle_ia())

        self._vtc_ia_key_frame = tk.Frame(ia_card, bg=CORES['bg_card'])
        # (não empacotado inicialmente — aparece ao marcar o checkbox)

        # Linha 1: API Key + botão Carregar Modelos
        key_row = tk.Frame(self._vtc_ia_key_frame, bg=CORES['bg_card'])
        key_row.pack(fill='x', pady=(2, 4))
        tk.Label(key_row, text="API Key:", font=(FONT_SANS, 10),
                 fg=CORES['fg_dim'], bg=CORES['bg_card'],
                 width=14, anchor='w').pack(side='left')
        tk.Entry(key_row, textvariable=self.vtc_api_key,
                 font=(FONT_MONO, 9), fg=CORES['fg'], bg=CORES['bg_input'],
                 insertbackground=CORES['fg'], relief='flat',
                 highlightbackground=CORES['border'], highlightthickness=1,
                 show='*').pack(side='left', fill='x', expand=True, padx=(0, 8), ipady=5)

        self._vtc_btn_carregar = RoundedButton(
            key_row, text="↻  Carregar modelos", variant='ghost', radius=6,
            font=(FONT_SANS, 9, "bold"), padx=12, pady=6,
            parent_bg=CORES['bg_card'],
            command=self._vtc_carregar_modelos,
        )
        self._vtc_btn_carregar.pack(side='right')

        # Linha 2: Seleção de modelo
        model_row = tk.Frame(self._vtc_ia_key_frame, bg=CORES['bg_card'])
        model_row.pack(fill='x', pady=(0, 2))
        tk.Label(model_row, text="Modelo:", font=(FONT_SANS, 10),
                 fg=CORES['fg_dim'], bg=CORES['bg_card'],
                 width=14, anchor='w').pack(side='left')

        # Sem textvariable — vtc_model_id é gerenciado manualmente para
        # garantir que contenha sempre o model_id puro, nunca o texto do display.
        self._vtc_model_combo = ttk.Combobox(
            model_row, font=(FONT_SANS, 9), state='readonly', width=40,
        )
        self._vtc_model_combo['values'] = ('gemini-2.5-flash — Gemini 2.5 Flash',)
        self._vtc_model_combo.set(f"{self.vtc_model_id.get()} — Gemini 2.5 Flash")
        if self.vtc_model_id.get().strip() != 'gemini-2.5-flash':
            self._vtc_model_combo.set(self.vtc_model_id.get().strip())
        self._vtc_model_combo.pack(side='left', ipady=4)

        def _on_model_select(event):
            sel = self._vtc_model_combo.get()
            mid = self.vtc_models_map.get(sel, sel.split(' — ')[0])
            self.vtc_model_id.set(mid)

        self._vtc_model_combo.bind('<<ComboboxSelected>>', _on_model_select)
        self._vtc_lbl_modelo_status = tk.Label(
            model_row, text="(clique ↻ para carregar)",
            font=(FONT_SANS, 8), fg=CORES['fg_dim'], bg=CORES['bg_card'])
        self._vtc_lbl_modelo_status.pack(side='left', padx=(8, 0))

        # ── Botão Gerar CSV ─────────────────────────────────────────────
        self.vtc_btn_gerar = RoundedButton(
            parent, text="▶  GERAR CSV VT CAIXA",
            variant='primary', radius=10,
            font=(FONT_SANS, 14, "bold"),
            pady=16, full_width=True,
            command=self._gerar_vtcaixa,
        )
        self.vtc_btn_gerar.pack(fill='x', pady=(4, 0))
        self._bind_hover(self.vtc_btn_gerar, CORES['btn_bg'], CORES['btn_hover'])

        # ── Card: Log ───────────────────────────────────────────────────
        log_wrapper = tk.Frame(parent, bg=CORES['bg_card'],
                               highlightbackground=CORES['border'],
                               highlightthickness=1)
        log_wrapper.pack(fill='both', expand=True, pady=(12, 0))
        tk.Frame(log_wrapper, bg=CORES['accent'], width=3).pack(side='left', fill='y')
        log_inner = tk.Frame(log_wrapper, bg=CORES['bg_card'])
        log_inner.pack(side='left', fill='both', expand=True)
        tk.Label(log_inner, text="Log", font=(FONT_SANS, 11, "bold"),
                 fg=CORES['fg_bright'], bg=CORES['bg_card']).pack(
                     anchor='w', padx=16, pady=(12, 6))

        log_text_frame = tk.Frame(log_inner, bg=CORES['bg_card'])
        log_text_frame.pack(fill='both', expand=True, padx=16, pady=(0, 14))

        self.vtc_log = tk.Text(log_text_frame, font=(FONT_MONO, 9),
                               fg=CORES['fg'], bg=CORES['bg_input'],
                               insertbackground=CORES['fg'], relief='flat',
                               highlightthickness=0, state='disabled',
                               wrap='word', height=16)
        sb_log = ttk.Scrollbar(log_text_frame, orient='vertical',
                               command=self.vtc_log.yview)
        self.vtc_log.configure(yscrollcommand=sb_log.set)
        self.vtc_log.pack(side='left', fill='both', expand=True)
        sb_log.pack(side='right', fill='y')

        # Tags de cor
        self.vtc_log.tag_configure('ok',   foreground=CORES['success'])
        self.vtc_log.tag_configure('warn', foreground=CORES['warning'])
        self.vtc_log.tag_configure('err',  foreground=CORES['error'])
        self.vtc_log.tag_configure('info', foreground=CORES['accent_light'])


    def _criar_aba_historico_vtc(self, parent):
        header = tk.Frame(parent, bg=CORES['bg'])
        header.pack(fill='x', pady=(0, 12))

        tk.Label(header, text="🕘  Histórico VT Caixa",
                 font=(FONT_SANS, 14, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(side='left')
        RoundedButton(header, text="Limpar histórico", variant='mini', radius=6,
                      font=(FONT_SANS, 9), padx=12, pady=5,
                      command=self._vtc_limpar_historico).pack(side='right')

        self._vtc_hist_lista = tk.Frame(parent, bg=CORES['bg'])
        self._vtc_hist_lista.pack(fill='both', expand=True)

        tk.Label(self._vtc_hist_lista,
                 text="Nenhum processamento realizado ainda.",
                 font=(FONT_SANS, 11), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(pady=40)

    def _vtc_limpar_historico(self):
        self._historico_vtc.clear()
        self._vtc_atualizar_historico()

    def _vtc_atualizar_historico(self):
        for w in self._vtc_hist_lista.winfo_children():
            w.destroy()

        if not self._historico_vtc:
            tk.Label(self._vtc_hist_lista,
                     text="Nenhum processamento realizado ainda.",
                     font=(FONT_SANS, 10), fg=CORES['fg_dim'],
                     bg=CORES['bg']).pack(pady=20)
            return

        canvas = tk.Canvas(self._vtc_hist_lista, bg=CORES['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(self._vtc_hist_lista, orient='vertical', command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=CORES['bg'])
        scroll_frame.bind('<Configure>',
                          lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self._bind_scroll(canvas, scroll_frame)

        total = len(self._historico_vtc)
        for i, entrada in enumerate(reversed(self._historico_vtc)):
            card = tk.Frame(scroll_frame, bg=CORES['bg_card'],
                            highlightbackground=CORES['border'], highlightthickness=1)
            card.pack(fill='x', pady=(0, 8))

            top = tk.Frame(card, bg=CORES['bg_card'])
            top.pack(fill='x', padx=14, pady=(10, 6))
            tk.Label(top, text=f"#{total - i}  {entrada['arquivo']}",
                     font=(FONT_SANS, 10, "bold"), fg=CORES['fg_bright'],
                     bg=CORES['bg_card']).pack(side='left')
            tk.Label(top,
                     text=f"{entrada['data']}  •  {entrada['tipo_fonte']}",
                     font=(FONT_SANS, 9), fg=CORES['fg_dim'],
                     bg=CORES['bg_card']).pack(side='right')

            stats_row = tk.Frame(card, bg=CORES['bg_card'])
            stats_row.pack(fill='x', padx=14, pady=(0, 8))
            nao_enc = len(entrada['nao_encontrados'])
            avisos = len(entrada['avisos_csv'])
            for label, valor, cor in [
                (entrada['tipo_fonte'], str(entrada['total_fonte']), CORES['accent_light']),
                ("Gerados",            str(entrada['total_ok']),    CORES['success']),
                ("Sem cadastro",       str(nao_enc),
                 CORES['error'] if nao_enc else CORES['success']),
                ("Avisos encoding",    str(avisos),
                 CORES['warning'] if avisos else CORES['fg_dim']),
            ]:
                bloco = tk.Frame(stats_row, bg=CORES['bg_input'])
                bloco.pack(side='left', padx=(0, 6))
                tk.Label(bloco, text=valor, font=(FONT_SANS, 12, "bold"),
                         fg=cor, bg=CORES['bg_input']).pack(side='left', padx=(8, 4), pady=4)
                tk.Label(bloco, text=label, font=(FONT_SANS, 8),
                         fg=CORES['fg_dim'], bg=CORES['bg_input']).pack(side='left', padx=(0, 8))

            # Sem cadastro
            if entrada['nao_encontrados']:
                det = tk.Frame(card, bg=CORES['bg_card'])
                det.pack(fill='x', padx=14, pady=(0, 4))
                nome_cadastral = entrada.get('arquivo_cadastral', '')
                titulo_sem = (
                    f"Sem cadastro no Excel Cadastral ({nome_cadastral}):"
                    if nome_cadastral
                    else "Sem cadastro no Excel Cadastral:"
                )
                tk.Label(det, text=titulo_sem,
                         font=(FONT_SANS, 9, "bold"), fg=CORES['error'],
                         bg=CORES['bg_card']).pack(anchor='w', pady=(0, 3))
                nome_fonte = entrada.get('arquivo_fonte', '')
                if nome_fonte:
                    tk.Label(det,
                             text=f"  (presentes na fonte {nome_fonte} mas não encontrados no cadastral)",
                             font=(FONT_SANS, 8), fg=CORES['fg_dim'],
                             bg=CORES['bg_card']).pack(anchor='w', pady=(0, 3))
                for item in entrada['nao_encontrados']:
                    tk.Label(det, text=f"  • {item}",
                             font=(FONT_MONO, 9), fg=CORES['fg_dim'],
                             bg=CORES['bg_card'], anchor='w').pack(fill='x')

            # Avisos de encoding
            if entrada['avisos_csv']:
                det2 = tk.Frame(card, bg=CORES['bg_card'])
                det2.pack(fill='x', padx=14, pady=(0, 4))
                tk.Label(det2, text="Avisos de encoding (latin-1):",
                         font=(FONT_SANS, 9, "bold"), fg=CORES['warning'],
                         bg=CORES['bg_card']).pack(anchor='w', pady=(0, 3))
                for av in entrada['avisos_csv']:
                    tk.Label(det2, text=f"  • {av}",
                             font=(FONT_MONO, 8), fg=CORES['fg_dim'],
                             bg=CORES['bg_card'], anchor='w').pack(fill='x')

            # Alertas IA
            if entrada['alertas_ia']:
                det3 = tk.Frame(card, bg=CORES['bg_card'])
                det3.pack(fill='x', padx=14, pady=(0, 8))
                tk.Label(det3, text=f"Relatório IA:",
                         font=(FONT_SANS, 9, "bold"), fg=CORES['accent_light'],
                         bg=CORES['bg_card']).pack(anchor='w', pady=(0, 3))
                for linha in entrada['alertas_ia']:
                    ll = linha.lower()
                    eh_negacao = 'nenhuma' in ll or 'tudo ok' in ll or 'sem inconsist' in ll
                    cor_ia = CORES['fg_dim'] if eh_negacao else (
                        CORES['error'] if any(k in ll for k in ('erro', 'inconsistência', 'alerta', 'vazio', 'zerado'))
                        else CORES['fg_dim']
                    )
                    tk.Label(det3, text=f"  {linha}",
                             font=(FONT_MONO, 8), fg=cor_ia,
                             bg=CORES['bg_card'], anchor='w').pack(fill='x')
            else:
                tk.Frame(card, bg=CORES['bg_card']).pack(pady=2)

    def _vtc_carregar_modelos(self):
        """Busca modelos disponíveis na API do Google AI e popula o combobox."""
        api_key = self.vtc_api_key.get().strip()
        if not api_key:
            messagebox.showerror("Erro", "Informe a API Key antes de carregar os modelos.")
            return

        self._vtc_btn_carregar.configure(state='disabled', text="Carregando...")
        self._vtc_lbl_modelo_status.configure(text="Buscando modelos...", fg=CORES['fg_dim'])

        def _worker():
            try:
                from vt_caixa_processador import ProcessadorVTCaixa
                modelos = ProcessadorVTCaixa.listar_modelos(api_key)
                self.after(0, lambda m=modelos: self._vtc_popular_modelos(m))
            except Exception as e:
                self.after(0, lambda err=str(e): self._vtc_lbl_modelo_status.configure(
                    text=f"Erro: {err[:60]}", fg=CORES['error']))
                self.after(0, lambda: self._vtc_btn_carregar.configure(
                    state='normal', text="↻  Carregar modelos"))

        threading.Thread(target=_worker, daemon=True).start()

    def _vtc_popular_modelos(self, modelos):
        """Popula o combobox com os modelos recebidos."""
        self._vtc_btn_carregar.configure(state='normal', text="↻  Carregar modelos")
        if not modelos:
            self._vtc_lbl_modelo_status.configure(
                text="Nenhum modelo encontrado.", fg=CORES['warning'])
            return

        # vtc_models_map: "display — id" → model_id puro
        self.vtc_models_map = {f"{mid} — {name}": mid for name, mid in modelos}
        opcoes = list(self.vtc_models_map.keys())
        self._vtc_model_combo['values'] = opcoes

        # Mantém seleção atual (por model_id puro) se ainda disponível
        atual_id = self.vtc_model_id.get()
        match = next((op for op in opcoes if op.split(' — ')[0] == atual_id), None)
        if not match:
            match = next((op for op in opcoes if 'gemini-2.5-flash' in op
                          and 'lite' not in op and 'preview' not in op), opcoes[0])
        self._vtc_model_combo.set(match)
        self.vtc_model_id.set(self.vtc_models_map[match])

        self._vtc_lbl_modelo_status.configure(
            text=f"{len(modelos)} modelo(s) disponível(is)", fg=CORES['success'])

    def _verif_carregar_modelos(self):
        api_key = self.verif_api_key.get().strip()
        if not api_key:
            messagebox.showerror("Erro", "Informe a API Key antes de carregar os modelos.")
            return

        def _buscar():
            try:
                from vt_caixa_processador import ProcessadorVTCaixa
                modelos = ProcessadorVTCaixa.listar_modelos(api_key)
                self.after(0, lambda m=modelos: self._verif_popular_modelos(m))
            except Exception as e:
                self.after(0, lambda err=str(e): messagebox.showerror(
                    "Erro", f"Falha ao carregar modelos:\n{err}"))

        threading.Thread(target=_buscar, daemon=True).start()

    def _verif_popular_modelos(self, modelos):
        """modelos: lista de (display_name, model_id) vinda de ProcessadorVTCaixa.listar_modelos."""
        if not modelos:
            messagebox.showwarning("Aviso", "Nenhum modelo encontrado para esta API Key.")
            return
        self._verif_models_map = {f"{d} — {mid}": mid for d, mid in modelos}
        labels = list(self._verif_models_map.keys())
        self._verif_modelo_combo['values'] = labels

        atual_id = self.verif_modelo.get().strip()
        # Tenta selecionar o modelo já salvo
        match = next((lbl for lbl, mid in self._verif_models_map.items() if mid == atual_id), None)
        if match:
            self._verif_modelo_combo.set(match)
        else:
            self._verif_modelo_combo.set(labels[0])
            self.verif_modelo.set(list(self._verif_models_map.values())[0])

        # Ao selecionar no combo, salva só o model_id na variável
        def _on_select(event):
            sel = self._verif_modelo_combo.get()
            self.verif_modelo.set(self._verif_models_map.get(sel, sel.split(' — ')[0]))
        self._verif_modelo_combo.bind('<<ComboboxSelected>>', _on_select)

    def _vtc_log_append(self, msg, tag=None):
        """Adiciona linha ao log da aba VT Caixa (thread-safe via self.after)."""
        self.vtc_log.configure(state='normal')
        if tag:
            self.vtc_log.insert(tk.END, msg + '\n', tag)
        else:
            self.vtc_log.insert(tk.END, msg + '\n')
        self.vtc_log.see(tk.END)
        self.vtc_log.configure(state='disabled')

    def _gerar_vtcaixa(self):
        fonte  = self.vtc_pdf_path.get().strip()
        xls  = self.vtc_xls_path.get().strip()
        out  = self.vtc_output_path.get().strip()

        ext_fonte = os.path.splitext(fonte)[1].lower() if fonte else ''
        if not fonte or not os.path.exists(fonte):
            messagebox.showerror("Erro", "Selecione uma fonte válida (PDF ou Excel).")
            return
        if ext_fonte not in ('.pdf', '.xls', '.xlsx', '.xlsm', '.xltx', '.xltm'):
            messagebox.showerror("Erro", "A fonte deve ser PDF ou Excel (.xls/.xlsx).")
            return
        if not xls or not os.path.exists(xls):
            messagebox.showerror("Erro", "Selecione um arquivo Excel cadastral (.xls/.xlsx) válido.")
            return
        ext_xls = os.path.splitext(xls)[1].lower()
        if ext_xls not in ('.xls', '.xlsx'):
            messagebox.showerror("Erro", "O Excel cadastral deve ser .xls ou .xlsx.")
            return
        if not out:
            messagebox.showerror("Erro", "Informe o caminho de saída do CSV.")
            return

        usar_ia  = self.vtc_usar_ia.get()
        api_key  = self.vtc_api_key.get().strip()
        model_id = self.vtc_model_id.get().strip() or 'gemini-2.5-flash'
        if usar_ia and not api_key:
            messagebox.showerror("Erro", "Informe a API Key do Google AI Studio para usar a IA.")
            return

        # Limpa log e bloqueia botão
        self.vtc_log.configure(state='normal')
        self.vtc_log.delete('1.0', tk.END)
        self.vtc_log.configure(state='disabled')
        self.vtc_btn_gerar.configure(state='disabled', bg=CORES['bg_input'],
                                     text="Gerando...")
        self.vtc_processando = True
        self._vtc_janela_progresso = self._vtc_abrir_janela_progresso(usar_ia)
        self._vtc_iniciar_animacao()

        def _cb(pct, msg):
            self.after(0, lambda p=pct, m=msg: self._vtc_atualizar_progresso(p, m))
            self.after(0, lambda p=pct, m=msg: self._vtc_log_append(f"[{p:3d}%] {m}", 'info'))

        def _worker():
            try:
                proc = ProcessadorVTCaixa()
                resultado = proc.processar(fonte, xls, out,
                                           progress_cb=_cb,
                                           usar_ia=usar_ia,
                                           api_key=api_key,
                                           model_id=model_id)
                self.after(0, self._vtc_marcar_sucesso_progresso)
                self.after(750, lambda r=resultado: self._vtc_mostrar_resultado(
                    r, out, fonte_path=fonte, cadastral_path=xls))
            except Exception as e:
                self.after(0, lambda err=str(e): self._vtc_log_append(f"Erro: {err}", 'err'))
                self.after(0, lambda: messagebox.showerror("Erro ao gerar CSV", str(e)))
                self.after(0, self._vtc_finalizar)

        threading.Thread(target=_worker, daemon=True).start()

    def _vtc_abrir_janela_progresso(self, usar_ia):
        win = tk.Toplevel(self)
        win.withdraw()  # esconde até estar totalmente pronta
        win.title("Gerando CSV VT Caixa...")
        win.configure(bg=CORES['bg'])
        win.geometry("450x350")
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 225
        y = self.winfo_y() + (self.winfo_height() // 2) - 175
        win.geometry(f"450x350+{x}+{y}")

        main = tk.Frame(win, bg=CORES['bg'])
        main.pack(fill='both', expand=True, padx=28, pady=24)

        top_row = tk.Frame(main, bg=CORES['bg'])
        top_row.pack(fill='x')

        txt_col = tk.Frame(top_row, bg=CORES['bg'])
        txt_col.pack(side='left', fill='x', expand=True)

        tk.Label(txt_col, text="Gerando CSV VT Caixa",
                 font=(FONT_SANS, 15, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(anchor='w')

        lbl_sub = tk.Label(txt_col, text="Preparando fluxo...",
                           font=(FONT_SANS, 9), fg=CORES['fg_dim'],
                           bg=CORES['bg'])
        lbl_sub.pack(anchor='w', pady=(4, 0))

        raio = 28
        size = raio * 2 + 12
        canvas = tk.Canvas(top_row, width=size, height=size,
                           bg=CORES['bg'], highlightthickness=0)
        canvas.pack(side='right', padx=(12, 0))

        pad = 6
        canvas.create_oval(pad, pad, size - pad, size - pad,
                           outline=CORES['border'], width=4)
        arc_id = canvas.create_arc(pad, pad, size - pad, size - pad,
                                   start=90, extent=90,
                                   outline=CORES['accent'], width=4,
                                   style='arc')

        win._arc_angle = 0

        def _girar():
            if not win.winfo_exists():
                return
            win._arc_angle = (win._arc_angle - 8) % 360
            canvas.itemconfigure(arc_id, start=win._arc_angle)
            win._spin_job = win.after(16, _girar)

        win._spin_job = win.after(16, _girar)

        progress_card = tk.Frame(main, bg=CORES['bg_card'],
                                 highlightbackground=CORES['border'],
                                 highlightthickness=1)
        progress_card.pack(fill='x', pady=(18, 14))

        progress_inner = tk.Frame(progress_card, bg=CORES['bg_card'])
        progress_inner.pack(fill='x', padx=16, pady=14)

        lbl_stage = tk.Label(progress_inner, text="Preparando",
                             font=(FONT_SANS, 10, "bold"), fg=CORES['accent_light'],
                             bg=CORES['bg_card'])
        lbl_stage.pack(anchor='w')

        lbl_status = tk.Label(progress_inner, text="Iniciando...",
                              font=(FONT_SANS, 10), fg=CORES['fg'],
                              bg=CORES['bg_card'])
        lbl_status.pack(anchor='w', pady=(6, 12))

        style = ttk.Style()
        style.theme_use('default')
        style.configure("VTC.Horizontal.TProgressbar",
                        troughcolor=CORES['border'],
                        background=CORES['accent'],
                        borderwidth=0,
                        lightcolor=CORES['accent'],
                        darkcolor=CORES['accent'],
                        thickness=10)
        pbar = ttk.Progressbar(progress_inner, orient='horizontal',
                               mode='determinate', maximum=100,
                               style="VTC.Horizontal.TProgressbar")
        pbar.pack(fill='x')

        meta_row = tk.Frame(progress_inner, bg=CORES['bg_card'])
        meta_row.pack(fill='x', pady=(8, 0))

        lbl_pct = tk.Label(meta_row, text="0%",
                           font=(FONT_MONO, 10, "bold"), fg=CORES['accent_light'],
                           bg=CORES['bg_card'])
        lbl_pct.pack(side='left')

        hint = "Com IA habilitada, a validacao final pode levar um pouco mais." if usar_ia \
            else "Sem IA, a geracao costuma terminar mais rapido."
        tk.Label(meta_row, text=hint,
                 font=(FONT_SANS, 8), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='right')

        steps_frame = tk.Frame(main, bg=CORES['bg'])
        steps_frame.pack(fill='x')

        steps = [
            ("prepare", "Preparar"),
            ("fonte", "Ler Fonte (PDF/Excel)"),
            ("excel", "Carregar Excel Cadastral"),
            ("match", "Cruzar dados"),
            ("csv", "Gerar CSV"),
        ]
        if usar_ia:
            steps.append(("ia", "Verificar IA"))
        steps.append(("done", "Concluir"))

        step_widgets = []
        for idx, (step_id, label) in enumerate(steps):
            item = tk.Frame(steps_frame, bg=CORES['bg_card'],
                            highlightbackground=CORES['border'], highlightthickness=1)
            item.pack(fill='x', pady=(0 if idx == 0 else 4, 0))

            inner = tk.Frame(item, bg=CORES['bg_card'])
            inner.pack(fill='x', padx=12, pady=7)

            dot = tk.Frame(inner, width=4, height=14, bg=CORES['border'])
            dot.pack(side='left', padx=(0, 8), pady=1)
            dot.pack_propagate(False)

            lbl = tk.Label(inner, text=label, font=(FONT_SANS, 9),
                           fg=CORES['fg_dim'], bg=CORES['bg_card'])
            lbl.pack(side='left')

            step_widgets.append({
                'id': step_id,
                'frame': item,
                'dot': dot,
                'label': lbl,
                'base_label': label,
            })

        win._dots = 0
        win._current_step = "prepare"
        win._stage_pulse = False
        win._order = [step_id for step_id, _ in steps]
        win._lbl_sub = lbl_sub
        win._lbl_stage = lbl_stage
        win._lbl_status = lbl_status
        win._pbar = pbar
        win._lbl_pct = lbl_pct
        win._step_widgets = step_widgets

        self._vtc_atualizar_etapas_progresso("prepare")

        def _animar_texto():
            if not win.winfo_exists():
                return
            dots = '.' * ((win._dots % 3) + 1)
            stage = win._lbl_stage.cget('text').rstrip('.')
            win._lbl_sub.configure(text=f"{stage}{dots}")
            win._dots += 1
            win._dots_job = win.after(320, _animar_texto)

        def _piscar_etapa():
            if not win.winfo_exists():
                return
            current = getattr(win, '_current_step', None)
            pulse_on = getattr(win, '_stage_pulse', False)
            for step in win._step_widgets:
                if step['id'] == current:
                    step['dot'].configure(bg=CORES['accent_light'] if pulse_on else CORES['accent'])
            win._stage_pulse = not pulse_on
            win._pulse_job = win.after(380, _piscar_etapa)

        win._dots_job = win.after(320, _animar_texto)
        win._pulse_job = win.after(380, _piscar_etapa)

        # Exibe a janela apenas agora que está totalmente montada
        win.deiconify()
        win.grab_set()
        return win

    def _vtc_inferir_etapa_progresso(self, pct, msg):
        texto = (msg or "").lower()
        if pct >= 100 or "conclu" in texto:
            return "done", "Concluindo"
        if "ia" in texto or "verificando com ia" in texto:
            return "ia", "Verificando com IA"
        if "csv" in texto or "encoding" in texto:
            return "csv", "Gerando CSV"
        if "cruz" in texto or "correspond" in texto:
            return "match", "Cruzando dados"
        if "excel cadastral" in texto:
            return "excel", "Carregando Excel cadastral"
        if "fonte" in texto or "pdf" in texto:
            return "fonte", "Lendo fonte de extração"
        if "excel" in texto:
            return "excel", "Carregando Excel cadastral"
        if "lendo" in texto:
            return "fonte", "Lendo fonte de extração"
        return "prepare", "Preparando"

    def _vtc_atualizar_etapas_progresso(self, etapa_atual):
        win = self._vtc_janela_progresso
        if not win or not win.winfo_exists():
            return

        order = getattr(win, '_order', ["prepare", "fonte", "excel", "match", "csv", "ia", "done"])
        idx_atual = order.index(etapa_atual) if etapa_atual in order else 0
        win._current_step = etapa_atual

        for step in win._step_widgets:
            idx = order.index(step['id'])
            if idx < idx_atual:
                step['frame'].configure(highlightbackground=CORES['success'])
                step['dot'].configure(bg=CORES['success'])
                step['label'].configure(text=f"OK  {step['base_label']}", fg=CORES['fg_bright'])
            elif idx == idx_atual:
                step['frame'].configure(highlightbackground=CORES['accent'])
                step['dot'].configure(bg=CORES['accent'])
                step['label'].configure(text=step['base_label'], fg=CORES['accent_light'])
            else:
                step['frame'].configure(highlightbackground=CORES['border'])
                step['dot'].configure(bg=CORES['border'])
                step['label'].configure(text=step['base_label'], fg=CORES['fg_dim'])

    def _vtc_atualizar_progresso(self, pct, msg):
        win = self._vtc_janela_progresso
        if win and win.winfo_exists():
            etapa_id, etapa_label = self._vtc_inferir_etapa_progresso(pct, msg)
            if etapa_id not in getattr(win, '_order', []):
                etapa_id = 'csv' if 'csv' in getattr(win, '_order', []) else 'done'
            self._vtc_atualizar_etapas_progresso(etapa_id)
            win._lbl_stage.configure(text=etapa_label)
            win._lbl_status.configure(text=msg)
            win._pbar.configure(value=pct)
            win._lbl_pct.configure(text=f"{pct}%")

    def _vtc_marcar_sucesso_progresso(self):
        win = self._vtc_janela_progresso
        if not win or not win.winfo_exists():
            self._vtc_finalizar()
            return

        self._vtc_atualizar_etapas_progresso("done")
        win._lbl_stage.configure(text="Concluido")
        win._lbl_sub.configure(text="Tudo pronto.")
        win._lbl_status.configure(text="CSV gerado com sucesso.")
        win._pbar.configure(value=100)
        win._lbl_pct.configure(text="100%")

        for step in win._step_widgets:
            step['frame'].configure(highlightbackground=CORES['success'])
            step['dot'].configure(bg=CORES['success'])
            step['label'].configure(text=f"OK  {step['base_label']}", fg=CORES['fg_bright'])

        self.after(700, self._vtc_finalizar)

    def _vtc_animar_btn(self):
        if not self.vtc_processando:
            return
        self.vtc_btn_gerar.configure(text=self._vtc_anim_frames[self._vtc_anim_frame])
        self._vtc_anim_frame = (self._vtc_anim_frame + 1) % len(self._vtc_anim_frames)
        self._vtc_anim_job = self.after(200, self._vtc_animar_btn)

    def _vtc_iniciar_animacao(self):
        self._vtc_anim_frames = [
            "Gerando.",
            "Gerando..",
            "Gerando...",
            "Gerando....",
        ]
        self._vtc_anim_frame = 0
        self._vtc_animar_btn()

    def _vtc_mostrar_resultado(self, resultado, output_path,
                               fonte_path=None, cadastral_path=None):
        self._historico_vtc.append({
            'arquivo':        os.path.basename(output_path),
            'data':           datetime.now().strftime('%d/%m/%Y %H:%M'),
            'tipo_fonte':     resultado.get('tipo_fonte', 'PDF'),
            'total_fonte':    resultado.get('total_fonte', resultado.get('total_pdf', 0)),
            'total_ok':       resultado['total_ok'],
            'nao_encontrados': list(resultado['nao_encontrados']),
            'avisos_csv':     list(resultado.get('avisos_csv', [])),
            'alertas_ia':     list(resultado.get('alertas_ia', [])),
            'arquivo_fonte':     os.path.basename(fonte_path) if fonte_path else '',
            'arquivo_cadastral': os.path.basename(cadastral_path) if cadastral_path else '',
        })
        self._vtc_atualizar_historico()

        # Persiste apenas o modelo selecionado (não a API key)
        err_cfg = _salvar_config({
            'vtc_model_id': self.vtc_model_id.get().strip(),
        })
        if err_cfg:
            self._vtc_log_append(f'Aviso: não foi possível salvar configuração: {err_cfg}', 'warn')

        total   = resultado.get('total_fonte', resultado.get('total_pdf', 0))
        tipo_fonte = resultado.get('tipo_fonte', 'PDF')
        ok      = resultado['total_ok']
        nao_enc = resultado['nao_encontrados']
        alertas = resultado['alertas_ia']
        avisos_csv = resultado.get('avisos_csv', [])

        self._vtc_log_append('─' * 50)
        self._vtc_log_append(f"✔ {ok} registro(s) processado(s) com sucesso.", 'ok')
        self._vtc_log_append(f"  Total na fonte ({tipo_fonte}): {total}")

        if nao_enc:
            self._vtc_log_append(
                f"⚠ {len(nao_enc)} matrícula(s) sem correspondência no Excel:", 'warn')
            for item in nao_enc:
                self._vtc_log_append(f"   • {item}", 'warn')
        else:
            self._vtc_log_append("  Todas as matrículas foram encontradas no Excel.", 'ok')

        self._vtc_log_append(f"\nCSV salvo em: {output_path}", 'info')

        if avisos_csv:
            self._vtc_log_append(f'\n⚠ {len(avisos_csv)} campo(s) com caracteres fora do latin-1 (substituídos por ?):', 'warn')
            for av in avisos_csv:
                self._vtc_log_append(f"   • {av}", 'warn')

        if alertas:
            self._vtc_log_append(f'\n🤖 Relatório IA ({self.vtc_model_id.get()}):', 'info')
            for linha in alertas:
                ll = linha.lower()
                # Frases de negação ("Nenhuma inconsistência encontrada.") não são erros.
                eh_negacao = 'nenhuma' in ll or 'tudo ok' in ll or 'sem inconsist' in ll
                tag = 'err' if (not eh_negacao and any(k in ll for k in ('erro', 'inconsistência', 'alerta', 'vazio', 'zerado'))) else None
                self._vtc_log_append(f"   {linha}", tag)
            self.after(100, lambda: self._vtc_mostrar_janela_ia(alertas, self.vtc_model_id.get()))

    def _vtc_mostrar_janela_ia(self, alertas, model_id):
        win = tk.Toplevel(self)
        win.title("Relatório de Verificação IA")
        win.configure(bg=CORES['bg'])
        win.geometry("620x500")
        win.resizable(True, True)
        win.grab_set()

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 310
        y = self.winfo_y() + (self.winfo_height() // 2) - 250
        win.geometry(f"620x500+{x}+{y}")

        # Cabeçalho
        header = tk.Frame(win, bg=CORES['accent'], height=4)
        header.pack(fill='x')

        inner = tk.Frame(win, bg=CORES['bg'])
        inner.pack(fill='both', expand=True, padx=24, pady=20)

        # Título
        tk.Label(inner, text="🤖  Relatório IA", font=(FONT_SANS, 14, "bold"),
                 fg=CORES['fg_bright'], bg=CORES['bg']).pack(anchor='w')
        tk.Label(inner, text=f"Modelo: {model_id}", font=(FONT_SANS, 9),
                 fg=CORES['fg_dim'], bg=CORES['bg']).pack(anchor='w', pady=(2, 12))

        # Área de texto com scroll
        txt_frame = tk.Frame(inner, bg=CORES['border'], bd=1, relief='flat')
        txt_frame.pack(fill='both', expand=True)

        sb = tk.Scrollbar(txt_frame, bg=CORES['bg_card'])
        txt = tk.Text(txt_frame, font=(FONT_MONO, 10), bg=CORES['bg_card'],
                      fg=CORES['fg'], relief='flat', bd=0, wrap='word',
                      state='normal', yscrollcommand=sb.set, padx=12, pady=10)
        sb.configure(command=txt.yview)
        sb.pack(side='right', fill='y')
        txt.pack(side='left', fill='both', expand=True)

        txt.tag_configure('warn',    foreground=CORES['warning'])
        txt.tag_configure('err',     foreground=CORES['error'])
        txt.tag_configure('ok',      foreground=CORES['success'])
        txt.tag_configure('dim',     foreground=CORES['fg_dim'])
        txt.tag_configure('bold',    font=(FONT_MONO, 10, "bold"))

        tem_problema = False
        for linha in alertas:
            linha_lower = linha.lower()
            # Frases de negação ("Nenhuma inconsistência encontrada.") não contam como problema.
            eh_negacao = 'nenhuma' in linha_lower or 'tudo ok' in linha_lower or 'sem inconsist' in linha_lower
            if not eh_negacao and any(k in linha_lower for k in ('inconsistência', 'erro', 'alerta', 'vazio', 'zerado', 'truncado', 'estranho')):
                txt.insert(tk.END, linha + '\n', 'err')
                tem_problema = True
            elif not eh_negacao and any(k in linha_lower for k in ('aviso', 'atenção', 'verificar')):
                txt.insert(tk.END, linha + '\n', 'warn')
                tem_problema = True
            elif linha.strip() == '':
                txt.insert(tk.END, '\n')
            else:
                txt.insert(tk.END, linha + '\n')

        txt.configure(state='disabled')

        # Rodapé
        footer = tk.Frame(inner, bg=CORES['bg'])
        footer.pack(fill='x', pady=(14, 0))

        resumo_txt = f"{'⚠  Inconsistências encontradas' if tem_problema else '✔  Nenhuma inconsistência encontrada'}"
        resumo_cor = CORES['warning'] if tem_problema else CORES['success']
        tk.Label(footer, text=resumo_txt, font=(FONT_SANS, 10, "bold"),
                 fg=resumo_cor, bg=CORES['bg']).pack(side='left')

        btn_fechar = RoundedButton(footer, text="Fechar", variant='primary', radius=8,
                                   font=(FONT_SANS, 10, "bold"),
                                   padx=22, pady=8, command=win.destroy)
        btn_fechar.pack(side='right')

    def _vtc_finalizar(self):
        self.vtc_processando = False
        if self._vtc_anim_job:
            self.after_cancel(self._vtc_anim_job)
            self._vtc_anim_job = None
        self.vtc_btn_gerar.configure(state='normal', bg=CORES['btn_bg'],
                                     text="▶  GERAR CSV VT CAIXA")
        if self._vtc_janela_progresso and self._vtc_janela_progresso.winfo_exists():
            for job_attr in ('_spin_job', '_dots_job', '_pulse_job'):
                if hasattr(self._vtc_janela_progresso, job_attr):
                    try:
                        self._vtc_janela_progresso.after_cancel(getattr(self._vtc_janela_progresso, job_attr))
                    except Exception:
                        pass
            self._vtc_janela_progresso.destroy()
        self._vtc_janela_progresso = None

    def _criar_aba_codigos(self, parent):
        # Scroll
        canvas = tk.Canvas(parent, bg=CORES['bg'], highlightthickness=0)
        sb = tk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        inner = tk.Frame(canvas, bg=CORES['bg'])
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))

        def _on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')

        # bind_all enquanto o cursor estiver sobre o canvas (cobre todos os widgets filhos)
        canvas.bind('<Enter>', lambda e: canvas.bind_all('<MouseWheel>', _on_wheel))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))

        # ── Card: Códigos de benefício ───────────────────────────────
        from vt_caixa_processador import ProcessadorVTCaixa
        codigos = ProcessadorVTCaixa._CODIGOS_BENEFICIO

        card_cod = self._criar_card(inner, "🏷  Operadora → Código de Benefício (VT Caixa)")

        def _copiar(valor):
            self.clipboard_clear()
            self.clipboard_append(valor)

        tabela_cod = tk.Frame(card_cod, bg=CORES['bg_card'])
        tabela_cod.pack(fill='x', expand=True)
        tabela_cod.columnconfigure(0, weight=6)
        tabela_cod.columnconfigure(1, weight=2)
        tabela_cod.columnconfigure(2, weight=1)
        tabela_cod.columnconfigure(3, weight=0)

        for col, txt in enumerate(["Operadora", "Valor Unitário", "Código", ""]):
            tk.Label(tabela_cod, text=txt, font=(FONT_SANS, 9, "bold"),
                     fg=CORES['fg_bright'], bg=CORES['bg_input'],
                     anchor='w', padx=8, pady=4).grid(row=0, column=col, sticky='ew', padx=(0, 1))

        for i, (operadora, valor, codigo) in enumerate(codigos):
            bg = CORES['bg_card'] if i % 2 == 0 else CORES['bg_input']
            r = i + 1
            tk.Label(tabela_cod, text=operadora, font=(FONT_MONO, 9),
                     fg=CORES['fg'], bg=bg, anchor='w', padx=8, pady=3).grid(row=r, column=0, sticky='ew', padx=(0, 1))
            tk.Label(tabela_cod, text=valor if valor else "qualquer", font=(FONT_MONO, 9),
                     fg=CORES['fg_dim'] if not valor else CORES['fg'],
                     bg=bg, anchor='w', padx=8).grid(row=r, column=1, sticky='ew', padx=(0, 1))
            tk.Label(tabela_cod, text=codigo, font=(FONT_MONO, 9, "bold"),
                     fg=CORES['accent_light'], bg=bg,
                     anchor='w', padx=8).grid(row=r, column=2, sticky='ew', padx=(0, 1))
            tk.Button(tabela_cod, text="📋", font=(FONT_SANS, 8),
                      fg=CORES['fg_dim'], bg=bg, relief='flat', cursor='hand2',
                      borderwidth=0, padx=6, pady=2,
                      command=lambda c=codigo: _copiar(c)).grid(row=r, column=3, sticky='ew', padx=(0, 4))

        # ── Card: Substituições de departamento ──────────────────────
        depart_map = {
            'CEF LESTE 10 SP 4719/2022': 'CEF 10 84',
            'CEF 17 CONTRATO 477/2026':  'CEF 17 LIMPEZA',
            'CEF 12 AMAZONAS - AM e RR': 'CEF 12 87',
            'CEF BAIXADA 11 SP 4820/2022': 'CEF 11 85',
            'POLICIA FED SHOP FLAMINGO':   'PF SHOPPING FLAMINGO',
            'B BRASIL RJ 2022.7421.6922':  'BB RJ 89',
            'CEF 14 DF':                   'CEF 14 DF 90',
            'CEF 15 RS 4916':              'CEF 15 RS',
        }

        card_dep = self._criar_card(inner, "🏢  Substituições de Departamento (VT Caixa)")

        tabela_dep = tk.Frame(card_dep, bg=CORES['bg_card'])
        tabela_dep.pack(fill='x', expand=True)
        tabela_dep.columnconfigure(0, weight=5)
        tabela_dep.columnconfigure(1, weight=0)
        tabela_dep.columnconfigure(2, weight=3)
        tabela_dep.columnconfigure(3, weight=0)

        for col, txt in enumerate(["Departamento original", "", "Substituto", ""]):
            tk.Label(tabela_dep, text=txt, font=(FONT_SANS, 9, "bold"),
                     fg=CORES['fg_bright'], bg=CORES['bg_input'],
                     anchor='w', padx=8, pady=4).grid(row=0, column=col, sticky='ew', padx=(0, 1))

        for i, (original, substituto) in enumerate(depart_map.items()):
            bg = CORES['bg_card'] if i % 2 == 0 else CORES['bg_input']
            r = i + 1
            tk.Label(tabela_dep, text=original, font=(FONT_MONO, 9),
                     fg=CORES['fg'], bg=bg, anchor='w', padx=8, pady=3).grid(row=r, column=0, sticky='ew', padx=(0, 1))
            tk.Label(tabela_dep, text="→", font=(FONT_SANS, 9),
                     fg=CORES['fg_dim'], bg=bg, anchor='center', padx=6).grid(row=r, column=1, sticky='ew', padx=(0, 1))
            tk.Label(tabela_dep, text=substituto, font=(FONT_MONO, 9, "bold"),
                     fg=CORES['accent_light'], bg=bg,
                     anchor='w', padx=8).grid(row=r, column=2, sticky='ew', padx=(0, 1))
            tk.Button(tabela_dep, text="📋", font=(FONT_SANS, 8),
                      fg=CORES['fg_dim'], bg=bg, relief='flat', cursor='hand2',
                      borderwidth=0, padx=6, pady=2,
                      command=lambda s=substituto: _copiar(s)).grid(row=r, column=3, sticky='ew', padx=(0, 4))

    def _criar_aba_sobre(self, parent):
        outer = tk.Frame(parent, bg=CORES['bg'])
        outer.pack(fill='both', expand=True)

        canvas = tk.Canvas(outer, bg=CORES['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        frame = tk.Frame(canvas, bg=CORES['bg'])
        win = canvas.create_window((0, 0), window=frame, anchor='nw')

        def _resize(e):
            canvas.itemconfig(win, width=e.width)
        canvas.bind('<Configure>', _resize)
        frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        self._bind_scroll(canvas, frame)

        inner = tk.Frame(frame, bg=CORES['bg'])
        inner.pack(padx=8, pady=4, fill='x')

        # Header padrão da aba
        self._criar_header_aba(
            inner,
            "Sobre",
            "Informações da instalação, licença e dependências.",
        )

        # Card de boas-vindas (subtítulo do produto, sem ícone gigante)
        welcome = self._criar_card(inner, "ℹ  Processador de Ocorrências")
        tk.Label(welcome,
                 text="Aplicação desktop para extrair ocorrências de PDFs de jornada "
                      "de trabalho e preencher automaticamente planilhas Excel.",
                 font=(FONT_SANS, 10), fg=CORES['fg'], bg=CORES['bg_card'],
                 wraplength=900, justify='left').pack(anchor='w')
        tk.Label(welcome,
                 text="Inclui processador especializado VT Caixa com assistência "
                      "de IA (Google Gemini) para extração de campos cadastrais.",
                 font=(FONT_SANS, 10), fg=CORES['accent_light'], bg=CORES['bg_card'],
                 wraplength=900, justify='left').pack(anchor='w', pady=(8, 0))

        # ── Duas colunas: Informações | Status do servidor ──
        cols = tk.Frame(inner, bg=CORES['bg'])
        cols.pack(fill='x', pady=(4, 10))

        # Coluna esquerda: Informações
        col_left = tk.Frame(cols, bg=CORES['bg'])
        col_left.pack(side='left', fill='both', expand=True, padx=(0, 6))

        info_card = self._criar_card(col_left, "ℹ  Informações")

        client = LicenseClient()
        chave = (client.get_saved_key() or '').strip() or '—'
        ultima_val = self._formatar_ultima_validacao()
        config_path = '~/.ocorrencias_config.json'

        info_rows = [
            ('VERSÃO',           f'v{VERSION}',                 'mono'),
            ('AUTOR',            'Nicolas Almeida Hader Dias',  'sans'),
            ('LICENÇA',          chave,                          'mono'),
            ('ÚLTIMA VALIDAÇÃO', ultima_val,                     'mono'),
            ('CONFIG LOCAL',     config_path,                    'mono'),
        ]
        self._sobre_info_rows = {}
        for label, valor, kind in info_rows:
            row = tk.Frame(info_card, bg=CORES['bg_card'])
            row.pack(fill='x', pady=4)
            tk.Label(row, text=label,
                     font=(FONT_SANS, 8, "bold"),
                     fg=CORES['fg_dim'], bg=CORES['bg_card'],
                     width=18, anchor='w').pack(side='left')
            font = (FONT_MONO, 10) if kind == 'mono' else (FONT_SANS, 10, "bold")
            val_lbl = tk.Label(row, text=valor,
                     font=font,
                     fg=CORES['fg_bright'], bg=CORES['bg_card'],
                     anchor='w')
            val_lbl.pack(side='left')
            self._sobre_info_rows[label] = val_lbl

        # Coluna direita: Status do servidor
        col_right = tk.Frame(cols, bg=CORES['bg'])
        col_right.pack(side='left', fill='both', expand=True, padx=(6, 0))

        status_card = self._criar_card(col_right, "🌐  Status do servidor")

        self._sobre_status_rows = {}
        for label, valor, cor in [
            ('CONEXÃO',           'Verificando…',     CORES['fg_dim']),
            ('VERSÃO MAIS RECENTE', '—',               CORES['fg']),
            ('API GEMINI',        '—',                 CORES['fg']),
            ('PRÓXIMA CHECAGEM',  'em 30s',           CORES['fg_dim']),
        ]:
            row = tk.Frame(status_card, bg=CORES['bg_card'])
            row.pack(fill='x', pady=4)
            tk.Label(row, text=label,
                     font=(FONT_SANS, 8, "bold"),
                     fg=CORES['fg_dim'], bg=CORES['bg_card'],
                     width=20, anchor='w').pack(side='left')
            lbl = tk.Label(row, text=valor,
                           font=(FONT_SANS, 10, "bold"),
                           fg=cor, bg=CORES['bg_card'], anchor='w')
            lbl.pack(side='left')
            self._sobre_status_rows[label] = lbl

        # Ação: revalidar agora
        action_row = tk.Frame(status_card, bg=CORES['bg_card'])
        action_row.pack(fill='x', pady=(10, 0))
        RoundedButton(action_row, text="Revalidar agora",
                      variant='ghost', radius=6,
                      font=(FONT_SANS, 9, "bold"),
                      padx=14, pady=6, parent_bg=CORES['bg_card'],
                      command=self._verificar_conexao_servidor,
                      ).pack(side='left')

        # ── Card de atualização ──
        update_card = self._criar_card(inner, "⬆  Atualização")

        self._lbl_update_status = tk.Label(
            update_card,
            text="Clique no botão para verificar se há uma versão mais recente.",
            font=(FONT_SANS, 10), fg=CORES['fg_dim'], bg=CORES['bg_card'],
            wraplength=900, justify='left')
        self._lbl_update_status.pack(anchor='w', pady=(0, 12))

        self._btn_buscar_update = RoundedButton(
            update_card, text="Buscar atualizações",
            variant='primary', radius=8,
            font=(FONT_SANS, 10, "bold"), padx=18, pady=8,
            parent_bg=CORES['bg_card'],
            command=self._buscar_update_manual,
        )
        self._btn_buscar_update.pack(anchor='w')

        # ── Tecnologias (chips) ──
        tech_card = self._criar_card(inner, "🛠  Tecnologias")
        chips_row = tk.Frame(tech_card, bg=CORES['bg_card'])
        chips_row.pack(fill='x')

        for tech in ['Python 3.10+', 'tkinter', 'pdfplumber', 'openpyxl', 'xlrd',
                     'Google Gemini API', 'PyInstaller', 'FastAPI', 'SQLAlchemy']:
            chip = tk.Frame(chips_row, bg=CORES['bg_input'],
                            highlightbackground=CORES['border'], highlightthickness=1)
            chip.pack(side='left', padx=(0, 6), pady=4)
            tk.Label(chip, text=tech,
                     font=(FONT_MONO, 9),
                     fg=CORES['accent_light'], bg=CORES['bg_input'],
                     padx=10, pady=4).pack()

    def _buscar_update_manual(self):
        """Chamado pelo botão na aba Sobre."""
        self._btn_buscar_update.configure(state='disabled', text="Verificando...")
        self._lbl_update_status.configure(text="", fg=CORES['fg_dim'])

        def _checar():
            tag, erro = self._buscar_versao_vps()
            self.after(0, lambda: self._exibir_resultado_update(tag, erro))

        threading.Thread(target=_checar, daemon=True).start()

    def _exibir_resultado_update(self, tag, erro):
        self._btn_buscar_update.configure(state='normal', text="Buscar Atualizações")
        if erro:
            self._lbl_update_status.configure(
                text=f"Erro: {erro}", fg=CORES['error'])
        elif tag and self._parse_versao(tag) > self._parse_versao(VERSION):
            self._lbl_update_status.configure(
                text=f"Nova versão disponível: v{tag}", fg=CORES['success'])
            self._mostrar_banner_update(tag)
            if not hasattr(self, '_btn_download_update') or not self._btn_download_update.winfo_exists():
                self._btn_download_update = RoundedButton(
                    self._btn_buscar_update.master,
                    text=f"Atualizar para v{tag}",
                    variant='primary', radius=6,
                    font=(FONT_SANS, 10, "bold"), padx=16, pady=7,
                    parent_bg=CORES['bg_card'],
                    command=lambda: self._aplicar_update(tag),
                )
                self._btn_download_update.pack(pady=(8, 0))
        else:
            self._lbl_update_status.configure(
                text=f"Você já está na versão mais recente (v{VERSION}).",
                fg=CORES['fg_dim'])

    # ------------------------------------------------------------------
    # Componentes reutilizáveis
    # ------------------------------------------------------------------

    def _criar_header_aba(self, parent, titulo, subtitulo=None, pills=None):
        """Header de aba estilo design: h1 26px + subtitle + pills opcionais à direita.
        pills: lista de callables que retornam string (recalculadas a cada atualização)."""
        header = tk.Frame(parent, bg=CORES['bg'])
        header.pack(fill='x', pady=(0, 14))

        # Coluna texto
        col = tk.Frame(header, bg=CORES['bg'])
        col.pack(side='left', fill='x', expand=True)

        tk.Label(col, text=titulo, font=(FONT_SANS, 18, "bold"),
                 fg=CORES['fg_bright'], bg=CORES['bg']).pack(anchor='w')
        if subtitulo:
            tk.Label(col, text=subtitulo, font=(FONT_SANS, 10),
                     fg=CORES['fg_dim'], bg=CORES['bg']).pack(anchor='w', pady=(2, 0))

        # Pills à direita (read-only, atualizam quando _atualizar_header_pills é chamada)
        if pills:
            pill_row = tk.Frame(header, bg=CORES['bg'])
            pill_row.pack(side='right', anchor='ne', pady=(4, 0))
            self._aba_pill_labels = getattr(self, '_aba_pill_labels', [])
            for fn in pills:
                pill = tk.Frame(pill_row, bg=CORES['bg_card'],
                                highlightbackground=CORES['border'], highlightthickness=1)
                pill.pack(side='left', padx=(0, 6))
                # dot accent
                tk.Label(pill, text='●', font=(FONT_SANS, 8),
                         fg=CORES['accent'], bg=CORES['bg_card'],
                         padx=8, pady=2).pack(side='left')
                lbl = tk.Label(pill, text=fn(), font=(FONT_SANS, 9, "bold"),
                               fg=CORES['accent_light'], bg=CORES['bg_card'],
                               padx=(0), pady=2)
                lbl.pack(side='left', padx=(0, 10))
                self._aba_pill_labels.append((lbl, fn))

    def _atualizar_header_pills(self):
        """Recalcula textos dos pills do header (chamar após mudar códigos/modo)."""
        for lbl, fn in getattr(self, '_aba_pill_labels', []):
            try:
                lbl.configure(text=fn())
            except Exception:
                pass

    def _criar_card(self, parent, titulo):
        """Card layered: borda 1px sutil, sem faixa lateral.
        Se o título começa com emoji+espaço, o emoji vira badge accent-faded."""
        wrapper = tk.Frame(parent, bg=CORES['bg_card'],
                           highlightbackground=CORES['border'], highlightthickness=1)
        wrapper.pack(fill='x', pady=(0, 10))

        card = tk.Frame(wrapper, bg=CORES['bg_card'])
        card.pack(fill='both', expand=True)

        # Top highlight 1px (substitui o ::before do CSS)
        tk.Frame(card, bg=CORES['border_hover'], height=1).pack(fill='x', side='top')

        header = tk.Frame(card, bg=CORES['bg_card'])
        header.pack(fill='x', padx=18, pady=(12, 6))

        # Se o título começa com emoji (1 char não-ASCII) + espaço, renderiza
        # com badge accent-faded à esquerda do texto.
        emoji = ''
        texto = titulo
        if titulo and len(titulo) > 2 and titulo[1] in (' ', ' ') and ord(titulo[0]) > 127:
            emoji = titulo[0]
            texto = titulo[2:].lstrip()
        if emoji:
            badge = tk.Frame(header, bg=CORES['accent_faded'],
                             highlightbackground=CORES['border'], highlightthickness=1)
            badge.pack(side='left', padx=(0, 10))
            tk.Label(badge, text=emoji, font=(FONT_SANS, 12),
                     fg=CORES['accent_light'], bg=CORES['accent_faded'],
                     padx=6, pady=2).pack()

        tk.Label(header, text=texto, font=(FONT_SANS, 11, "bold"),
                 fg=CORES['fg_bright'], bg=CORES['bg_card']).pack(side='left')

        content = tk.Frame(card, bg=CORES['bg_card'])
        content.pack(fill='x', padx=18, pady=(0, 14))
        return content

    _EXT_COLORS = {
        'pdf':  ('#3a1f22', '#f87171'),  # vermelho
        'xls':  ('#0f1a14', '#4ade80'),  # verde
        'xlsx': ('#0f1a14', '#4ade80'),
        'csv':  ('#1a1610', '#fbbf24'),  # âmbar
    }

    def _criar_file_picker(self, parent, label, var, filetypes, btn_text):
        """File picker card-style: badge colorido por extensão + nome em mono + Trocar/Selecionar."""
        # Detecta extensão pelo primeiro filetype (ex.: '*.pdf')
        ext = 'pdf'
        if filetypes:
            patt = filetypes[0][1].lower()
            for k in self._EXT_COLORS:
                if k in patt:
                    ext = k
                    break
        bg_badge, fg_badge = self._EXT_COLORS.get(ext, ('#1a1d29', '#a8c0ff'))

        card = tk.Frame(parent, bg=CORES['bg_card'],
                        highlightbackground=CORES['border'], highlightthickness=1)
        card.pack(fill='x', pady=6)

        inner = tk.Frame(card, bg=CORES['bg_card'])
        inner.pack(fill='x', padx=14, pady=10)

        # Badge da extensão
        badge = tk.Frame(inner, bg=bg_badge,
                         highlightbackground=fg_badge, highlightthickness=1)
        badge.pack(side='left')
        tk.Label(badge, text=ext.upper(),
                 font=(FONT_MONO, 11, "bold"),
                 fg=fg_badge, bg=bg_badge,
                 padx=10, pady=6).pack()

        # Coluna texto: label em cima + nome em mono embaixo
        col = tk.Frame(inner, bg=CORES['bg_card'])
        col.pack(side='left', fill='x', expand=True, padx=(12, 12))

        lbl_top = tk.Label(col, text=label.upper(),
                           font=(FONT_SANS, 8, "bold"),
                           fg=CORES['fg_dim'], bg=CORES['bg_card'])
        lbl_top.pack(anchor='w')

        lbl_file = tk.Label(col,
                            font=(FONT_MONO, 10),
                            fg=CORES['fg'], bg=CORES['bg_card'],
                            anchor='w')
        lbl_file.pack(anchor='w', fill='x')

        # Check verde quando preenchido (à direita do nome)
        check_holder = tk.Frame(inner, bg=CORES['bg_card'])
        check_holder.pack(side='left', padx=(0, 10))
        lbl_check = tk.Label(check_holder, text='',
                             font=(FONT_SANS, 14, "bold"),
                             fg=CORES['success'], bg=CORES['bg_card'])
        lbl_check.pack()

        btn_holder = tk.Frame(inner, bg=CORES['bg_card'])
        btn_holder.pack(side='right')

        clear_holder = tk.Frame(inner, bg=CORES['bg_card'])
        clear_holder.pack(side='right', padx=(0, 6))

        def _criar_btn(text, variant):
            for w in btn_holder.winfo_children():
                w.destroy()
            b = RoundedButton(btn_holder, text=text, variant=variant, radius=6,
                              font=(FONT_SANS, 9, "bold"), padx=14, pady=6,
                              parent_bg=CORES['bg_card'],
                              command=lambda: self._escolher_arquivo(var, filetypes))
            b.pack()
            return b

        def _limpar():
            var.set('')

        def on_change(*_):
            valor = var.get().strip()
            if valor:
                lbl_file.configure(text=os.path.basename(valor), fg=CORES['fg_bright'])
                lbl_check.configure(text='✓')
                card.configure(highlightbackground=CORES['border_hover'])
                _criar_btn('Trocar', 'ghost')
                for w in clear_holder.winfo_children():
                    w.destroy()
                RoundedButton(clear_holder, text='✕', variant='danger', radius=6,
                              font=(FONT_SANS, 9, "bold"), padx=10, pady=6,
                              parent_bg=CORES['bg_card'],
                              command=_limpar).pack()
            else:
                lbl_file.configure(text='Nenhum arquivo selecionado',
                                   fg=CORES['fg_dim'])
                lbl_check.configure(text='')
                card.configure(highlightbackground=CORES['border'])
                _criar_btn('Selecionar', 'primary')
                for w in clear_holder.winfo_children():
                    w.destroy()

        # estado inicial: pode já ter valor salvo
        on_change()
        var.trace_add('write', on_change)

    def _criar_file_saver(self, parent, label, var):
        """File saver card-style: badge CSV âmbar + label + caminho em mono + Salvar como/Trocar."""
        bg_badge, fg_badge = self._EXT_COLORS['csv']

        card = tk.Frame(parent, bg=CORES['bg_card'],
                        highlightbackground=CORES['border'], highlightthickness=1)
        card.pack(fill='x', pady=6)

        inner = tk.Frame(card, bg=CORES['bg_card'])
        inner.pack(fill='x', padx=14, pady=10)

        # Badge CSV
        badge = tk.Frame(inner, bg=bg_badge,
                         highlightbackground=fg_badge, highlightthickness=1)
        badge.pack(side='left')
        tk.Label(badge, text='CSV',
                 font=(FONT_MONO, 11, "bold"),
                 fg=fg_badge, bg=bg_badge,
                 padx=10, pady=6).pack()

        # Coluna texto: label em cima + caminho em mono embaixo
        col = tk.Frame(inner, bg=CORES['bg_card'])
        col.pack(side='left', fill='x', expand=True, padx=(12, 12))

        tk.Label(col, text=label.upper(),
                 font=(FONT_SANS, 8, "bold"),
                 fg=CORES['fg_dim'], bg=CORES['bg_card']).pack(anchor='w')

        lbl_file = tk.Label(col, font=(FONT_MONO, 10),
                            fg=CORES['fg_dim'], bg=CORES['bg_card'],
                            anchor='w')
        lbl_file.pack(anchor='w', fill='x')

        # Check verde quando preenchido
        check_holder = tk.Frame(inner, bg=CORES['bg_card'])
        check_holder.pack(side='left', padx=(0, 10))
        lbl_check = tk.Label(check_holder, text='',
                             font=(FONT_SANS, 14, "bold"),
                             fg=CORES['success'], bg=CORES['bg_card'])
        lbl_check.pack()

        btn_holder = tk.Frame(inner, bg=CORES['bg_card'])
        btn_holder.pack(side='right')

        def _escolher_saida():
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                title="Salvar CSV de importação VT Caixa como...")
            if path:
                var.set(path)

        def _criar_btn(text, variant):
            for w in btn_holder.winfo_children():
                w.destroy()
            b = RoundedButton(btn_holder, text=text, variant=variant, radius=6,
                              font=(FONT_SANS, 9, "bold"), padx=14, pady=6,
                              parent_bg=CORES['bg_card'],
                              command=_escolher_saida)
            b.pack()

        def on_change(*_):
            valor = var.get().strip()
            if valor:
                lbl_file.configure(text=os.path.basename(valor), fg=CORES['fg_bright'])
                lbl_check.configure(text='✓')
                card.configure(highlightbackground=CORES['border_hover'])
                _criar_btn('Trocar', 'ghost')
            else:
                lbl_file.configure(text='Nenhum destino selecionado', fg=CORES['fg_dim'])
                lbl_check.configure(text='')
                card.configure(highlightbackground=CORES['border'])
                _criar_btn('Salvar como', 'primary')

        on_change()
        var.trace_add('write', on_change)

    def _escolher_arquivo(self, var, filetypes):
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            var.set(path)

    def _criar_mini_btn(self, parent, text, command):
        return RoundedButton(parent, text=text, variant='mini', radius=6,
                             font=(FONT_SANS, 9),
                             padx=12, pady=5, command=command)

    def _toggle_dias_mes(self, on):
        if on:
            self._dias_mes_row.pack(fill='x', pady=(4, 0))
            self._entry_dias.focus_set()
        else:
            self._dias_mes_row.pack_forget()
            self.dias_mes.set("")

    def _criar_checkbox(self, parent, label, descricao, var, on_toggle=None):
        row = tk.Frame(parent, bg=CORES['bg_card'])
        row.pack(fill='x', pady=4)

        def toggle():
            var.set(not var.get())
            _atualizar()

        def _atualizar():
            on = var.get()
            dot.configure(
                text="☑" if on else "☐",
                fg=CORES['accent_light'] if on else CORES['fg_dim'],
            )
            lbl.configure(fg=CORES['fg_bright'] if on else CORES['fg'])
            if on_toggle:
                on_toggle(on)

        dot = tk.Label(row, text="☐", font=(FONT_SANS, 13),
                       fg=CORES['fg_dim'], bg=CORES['bg_card'], cursor='hand2')
        dot.pack(side='left', padx=(0, 8))

        text_col = tk.Frame(row, bg=CORES['bg_card'])
        text_col.pack(side='left', fill='x', expand=True)

        lbl = tk.Label(text_col, text=label, font=(FONT_SANS, 10),
                       fg=CORES['fg'], bg=CORES['bg_card'], anchor='w', cursor='hand2')
        lbl.pack(anchor='w')

        tk.Label(text_col, text=descricao, font=(FONT_SANS, 8),
                 fg=CORES['fg_dim'], bg=CORES['bg_card'], anchor='w',
                 wraplength=560, justify='left').pack(anchor='w')

        for w in (dot, lbl, row, text_col):
            w.bind('<Button-1>', lambda e: toggle())

    def _criar_toggle_qt(self, parent, sigla, label, var):
        """Botão toggle pequeno para selecionar coluna Qt VA/VR/VT."""
        def _atualizar():
            on = var.get()
            btn.configure(
                bg=CORES['accent'] if on else CORES['bg_input'],
                fg=CORES['btn_fg'] if on else CORES['fg_dim'],
                highlightbackground=CORES['accent'] if on else CORES['border'],
            )

        def toggle():
            var.set(not var.get())
            _atualizar()

        btn = tk.Label(
            parent,
            text=f"{sigla}  {label}",
            font=(FONT_SANS, 9, "bold"),
            fg=CORES['btn_fg'], bg=CORES['accent'],
            padx=12, pady=5, cursor='hand2',
            highlightbackground=CORES['accent'], highlightthickness=1,
        )
        btn.pack(side='left', padx=(0, 6))
        btn.bind('<Button-1>', lambda e: toggle())
        _atualizar()

    def _criar_chip(self, parent, codigo, desc, tem_qtd, var, row, col):
        """Chip estilo design: badge accent-faded com código + descrição + pill QTD/sem qtd."""
        wrapper = tk.Frame(parent, bg=CORES['bg_card'])
        wrapper.grid(row=row, column=col, padx=4, pady=4, sticky='ew')

        # OFF: fundo do card, borda sutil. ON: bg lift + borda accent.
        OFF_BG, ON_BG = CORES['bg_card'], CORES['chip_on']
        OFF_BORDER, ON_BORDER = CORES['border'], CORES['accent']

        def toggle():
            var.set(not var.get())
            atualizar_visual()
            self._atualizar_header_pills()

        def atualizar_visual():
            on = var.get()
            bg = ON_BG if on else OFF_BG
            border = ON_BORDER if on else OFF_BORDER
            badge_bg = CORES['accent_faded'] if on else CORES['bg_input']
            cod_fg = CORES['accent_light'] if on else CORES['fg']
            desc_fg = CORES['fg_bright'] if on else CORES['fg']

            chip.configure(bg=bg, highlightbackground=border)
            inner.configure(bg=bg)
            badge.configure(bg=badge_bg, highlightbackground=border)
            lbl_cod.configure(bg=badge_bg, fg=cod_fg)
            lbl_desc.configure(bg=bg, fg=desc_fg)
            if lbl_qtd:
                pill_bg = CORES['accent_faded'] if (on and tem_qtd) else CORES['bg_input']
                pill_fg = CORES['accent_light'] if (on and tem_qtd) else (
                    CORES['warning'] if not tem_qtd else CORES['fg_dim']
                )
                lbl_qtd.configure(bg=pill_bg, fg=pill_fg)

        chip = tk.Frame(wrapper, bg=ON_BG, cursor='hand2',
                        highlightbackground=ON_BORDER, highlightthickness=1)
        chip.pack(fill='x')

        inner = tk.Frame(chip, bg=ON_BG)
        inner.pack(fill='x', padx=10, pady=8)

        # Badge do código (accent-faded com borda)
        badge = tk.Frame(inner, bg=CORES['accent_faded'],
                         highlightbackground=ON_BORDER, highlightthickness=1)
        badge.pack(side='left')
        lbl_cod = tk.Label(badge, text=codigo, font=(FONT_MONO, 11, "bold"),
                           fg=CORES['accent_light'], bg=CORES['accent_faded'],
                           padx=8, pady=2)
        lbl_cod.pack()

        lbl_desc = tk.Label(inner, text=desc, font=(FONT_SANS, 10),
                            fg=CORES['fg_bright'], bg=ON_BG)
        lbl_desc.pack(side='left', padx=(10, 0))

        # Pill QTD à direita (accent-faded quando ON+tem_qtd, warning fade se "sem qtd")
        lbl_qtd = tk.Label(
            inner,
            text="QTD" if tem_qtd else "sem qtd",
            font=(FONT_MONO, 8, "bold"),
            fg=CORES['accent_light'] if tem_qtd else CORES['warning'],
            bg=CORES['accent_faded'] if tem_qtd else CORES['bg_input'],
            padx=6, pady=1,
        )
        lbl_qtd.pack(side='right')

        self.codigos_update_fns[codigo] = atualizar_visual

        for widget in [chip, inner, badge, lbl_cod, lbl_desc, lbl_qtd]:
            widget.bind('<Button-1>', lambda e: toggle())

    # ------------------------------------------------------------------
    # Lógica de processamento
    # ------------------------------------------------------------------

    def _selecionar_todos(self):
        for var in self.codigos_vars.values():
            var.set(True)
        self._recriar_chips()
        self._atualizar_header_pills()

    def _limpar_selecao(self):
        for var in self.codigos_vars.values():
            var.set(False)
        self._recriar_chips()
        self._atualizar_header_pills()

    def _recriar_chips(self):
        for fn in self.codigos_update_fns.values():
            fn()

    def _iniciar_processamento(self):
        pdf = self.pdf_path.get().strip()
        xlsx = self.xlsx_path.get().strip()

        if not pdf or not os.path.exists(pdf):
            messagebox.showerror("Erro", "Selecione um arquivo PDF válido.")
            return
        if not xlsx or not os.path.exists(xlsx):
            messagebox.showerror("Erro", "Selecione um arquivo Excel válido.")
            return

        codigos = [c for c, v in self.codigos_vars.items() if v.get()]
        if not codigos:
            messagebox.showerror("Erro", "Selecione pelo menos um código de ocorrência.")
            return

        dias_mes = None
        colunas_qt = []
        if self.deduzir_dias.get():
            val = self.dias_mes.get().strip()
            if not val or not val.isdigit() or int(val) < 1:
                messagebox.showerror("Erro", "Informe a quantidade de dias do mês (1–31).")
                return
            dias_mes = int(val)
            colunas_qt = [
                col for col, var in [
                    ('qt va', self.qt_va_var),
                    ('qt vr', self.qt_vr_var),
                    ('qt vt', self.qt_vt_var),
                ] if var.get()
            ]
            if not colunas_qt:
                messagebox.showerror("Erro", "Selecione pelo menos uma coluna Qt (VA, VR ou VT).")
                return

        base, ext = os.path.splitext(xlsx)
        sugestao = f"{base}_ATUALIZADO{ext}"
        output = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=os.path.basename(sugestao),
            initialdir=os.path.dirname(xlsx),
            title="Salvar planilha atualizada como..."
        )
        if not output:
            return

        self.processando = True
        self.btn_processar.configure(state='disabled', bg=CORES['bg_input'],
                                     text="Processando...")

        if self.modo_verificacao.get() == 'ia':
            _salvar_config({
                'gemini_api_key_ocorrencias': self.verif_api_key.get().strip(),
                'gemini_modelo_ocorrencias':  self.verif_modelo.get().strip(),
            })

        for w in self.resultado_frame.winfo_children():
            w.destroy()

        self._janela_progresso = self._abrir_janela_progresso()
        self._iniciar_animacao()

        modo_verif   = self.modo_verificacao.get()
        verif_key    = self.verif_api_key.get().strip()
        verif_modelo = self.verif_modelo.get().strip()

        thread = threading.Thread(target=self._processar,
                                  args=(pdf, xlsx, output, codigos, dias_mes, colunas_qt,
                                        modo_verif, verif_key, verif_modelo))
        thread.daemon = True
        thread.start()

    def _abrir_janela_progresso(self):
        win = tk.Toplevel(self)
        win.withdraw()  # esconde até estar totalmente pronta
        win.title("Processando...")
        win.configure(bg=CORES['bg'])
        win.geometry("450x320")
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", lambda: None)  # bloquear fechar

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 225
        y = self.winfo_y() + (self.winfo_height() // 2) - 160
        win.geometry(f"450x320+{x}+{y}")

        main = tk.Frame(win, bg=CORES['bg'])
        main.pack(fill='both', expand=True, padx=28, pady=24)

        top_row = tk.Frame(main, bg=CORES['bg'])
        top_row.pack(fill='x')

        txt_col = tk.Frame(top_row, bg=CORES['bg'])
        txt_col.pack(side='left', fill='x', expand=True)

        tk.Label(txt_col, text="Processando arquivos",
                 font=(FONT_SANS, 15, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(anchor='w')

        lbl_sub = tk.Label(txt_col, text="Preparando fluxo...",
                           font=(FONT_SANS, 9), fg=CORES['fg_dim'],
                           bg=CORES['bg'])
        lbl_sub.pack(anchor='w', pady=(4, 0))

        # Canvas da animação estilo Win11 (arco girando)
        RAIO = 28
        SIZE = RAIO * 2 + 12
        canvas = tk.Canvas(top_row, width=SIZE, height=SIZE,
                           bg=CORES['bg'], highlightthickness=0)
        canvas.pack(side='right', padx=(12, 0))

        # Trilha do círculo
        PAD = 6
        canvas.create_oval(PAD, PAD, SIZE - PAD, SIZE - PAD,
                           outline=CORES['border'], width=4)
        # Arco animado
        arc_id = canvas.create_arc(PAD, PAD, SIZE - PAD, SIZE - PAD,
                                   start=90, extent=90,
                                   outline=CORES['accent'], width=4,
                                   style='arc')

        win._arc_angle = 0

        def _girar():
            if not win.winfo_exists():
                return
            win._arc_angle = (win._arc_angle - 8) % 360
            canvas.itemconfigure(arc_id, start=win._arc_angle)
            win._spin_job = win.after(16, _girar)

        win._spin_job = win.after(16, _girar)

        progress_card = tk.Frame(main, bg=CORES['bg_card'],
                                 highlightbackground=CORES['border'],
                                 highlightthickness=1)
        progress_card.pack(fill='x', pady=(18, 14))

        progress_inner = tk.Frame(progress_card, bg=CORES['bg_card'])
        progress_inner.pack(fill='x', padx=16, pady=14)

        lbl_stage = tk.Label(progress_inner, text="Preparando",
                             font=(FONT_SANS, 10, "bold"), fg=CORES['accent_light'],
                             bg=CORES['bg_card'])
        lbl_stage.pack(anchor='w')

        lbl_status = tk.Label(progress_inner, text="Iniciando...",
                              font=(FONT_SANS, 10), fg=CORES['fg'],
                              bg=CORES['bg_card'])
        lbl_status.pack(anchor='w', pady=(6, 12))

        style = ttk.Style()
        style.theme_use('default')
        style.configure("Win.Horizontal.TProgressbar",
                        troughcolor=CORES['border'],
                        background=CORES['accent'],
                        borderwidth=0,
                        lightcolor=CORES['accent'],
                        darkcolor=CORES['accent'],
                        thickness=10)
        pbar = ttk.Progressbar(progress_inner, orient='horizontal',
                               mode='determinate', maximum=100,
                               style="Win.Horizontal.TProgressbar")
        pbar.pack(fill='x')

        meta_row = tk.Frame(progress_inner, bg=CORES['bg_card'])
        meta_row.pack(fill='x', pady=(8, 0))

        lbl_pct = tk.Label(meta_row, text="0%",
                           font=(FONT_MONO, 10, "bold"), fg=CORES['accent_light'],
                           bg=CORES['bg_card'])
        lbl_pct.pack(side='left')

        tk.Label(meta_row, text="Aguarde enquanto os dados sao processados.",
                 font=(FONT_SANS, 8), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='right')

        steps_frame = tk.Frame(main, bg=CORES['bg'])
        steps_frame.pack(fill='x')

        steps = [
            ("prepare",   "Preparar"),
            ("pdf",       "Ler PDF (V1)"),
            ("pdf2",      "Varredura 2"),
            ("ia",        "Verificar com IA"),
            ("reconcile", "Reconciliar"),
            ("sheet",     "Abrir planilha"),
            ("match",     "Cruzar dados"),
            ("save",      "Salvar"),
            ("done",      "Concluir"),
        ]
        step_widgets = []
        for idx, (step_id, label) in enumerate(steps):
            item = tk.Frame(steps_frame, bg=CORES['bg_card'],
                            highlightbackground=CORES['border'], highlightthickness=1)
            item.pack(fill='x', pady=(0 if idx == 0 else 4, 0))

            inner = tk.Frame(item, bg=CORES['bg_card'])
            inner.pack(fill='x', padx=12, pady=7)

            dot = tk.Frame(inner, width=4, height=14, bg=CORES['border'])
            dot.pack(side='left', padx=(0, 8), pady=1)
            dot.pack_propagate(False)

            lbl = tk.Label(inner, text=label, font=(FONT_SANS, 9),
                           fg=CORES['fg_dim'], bg=CORES['bg_card'])
            lbl.pack(side='left')

            step_widgets.append({
                'id': step_id,
                'frame': item,
                'dot': dot,
                'label': lbl,
                'base_label': label,
            })

        win._dots = 0
        win._current_step = "prepare"
        win._stage_pulse = False
        win._lbl_sub = lbl_sub
        win._lbl_stage = lbl_stage
        win._lbl_status = lbl_status
        win._pbar = pbar
        win._lbl_pct = lbl_pct
        win._step_widgets = step_widgets

        self._atualizar_etapas_progresso("prepare")

        def _animar_texto():
            if not win.winfo_exists():
                return
            dots = '.' * ((win._dots % 3) + 1)
            stage = win._lbl_stage.cget('text').rstrip('.')
            win._lbl_sub.configure(text=f"{stage}{dots}")
            win._dots += 1
            win._dots_job = win.after(320, _animar_texto)

        def _piscar_etapa():
            if not win.winfo_exists():
                return
            current = getattr(win, '_current_step', None)
            pulse_on = getattr(win, '_stage_pulse', False)
            for step in win._step_widgets:
                if step['id'] == current:
                    step['dot'].configure(bg=CORES['accent_light'] if pulse_on else CORES['accent'])
            win._stage_pulse = not pulse_on
            win._pulse_job = win.after(380, _piscar_etapa)

        win._dots_job = win.after(320, _animar_texto)
        win._pulse_job = win.after(380, _piscar_etapa)

        # Exibe a janela apenas agora que está totalmente montada
        win.deiconify()
        win.grab_set()
        return win

    def _inferir_etapa_progresso(self, pct, msg):
        texto = (msg or "").lower()
        if pct >= 100 or "conclu" in texto:
            return "done", "Concluindo"
        if "salvand" in texto:
            return "save", "Salvando arquivo"
        if "finaliz" in texto:
            return "save", "Finalizando"
        if "cruz" in texto:
            return "match", "Cruzando dados"
        if "planilha" in texto:
            return "sheet", "Abrindo planilha"
        if "reconcil" in texto:
            return "reconcile", "Reconciliando"
        if "gemini" in texto or "ia" in texto or "intelig" in texto:
            return "ia", "Verificando com IA"
        if "varredura 2" in texto:
            return "pdf2", "Varredura 2"
        if "pdf" in texto or "lendo" in texto:
            return "pdf", "Lendo PDF"
        return "prepare", "Preparando"

    def _atualizar_etapas_progresso(self, etapa_atual):
        win = self._janela_progresso
        if not win or not win.winfo_exists():
            return

        order = ["prepare", "pdf", "pdf2", "ia", "reconcile", "sheet", "match", "save", "done"]
        idx_atual = order.index(etapa_atual) if etapa_atual in order else 0
        win._current_step = etapa_atual

        for step in win._step_widgets:
            idx = order.index(step['id'])
            if idx < idx_atual:
                step['frame'].configure(highlightbackground=CORES['success'])
                step['dot'].configure(bg=CORES['success'])
                step['label'].configure(text=f"OK  {step['base_label']}", fg=CORES['fg_bright'])
            elif idx == idx_atual:
                step['frame'].configure(highlightbackground=CORES['accent'])
                step['dot'].configure(bg=CORES['accent'])
                step['label'].configure(text=step['base_label'], fg=CORES['accent_light'])
            else:
                step['frame'].configure(highlightbackground=CORES['border'])
                step['dot'].configure(bg=CORES['border'])
                step['label'].configure(text=step['base_label'], fg=CORES['fg_dim'])

    def _atualizar_progresso(self, pct, msg):
        """Chamado da thread de processamento via self.after."""
        win = self._janela_progresso
        if win and win.winfo_exists():
            etapa_id, etapa_label = self._inferir_etapa_progresso(pct, msg)
            self._atualizar_etapas_progresso(etapa_id)
            win._lbl_stage.configure(text=etapa_label)
            win._lbl_status.configure(text=msg)
            win._pbar.configure(value=pct)
            win._lbl_pct.configure(text=f"{pct}%")

    def _marcar_sucesso_progresso(self):
        win = self._janela_progresso
        if not win or not win.winfo_exists():
            self._finalizar_processamento()
            return

        self._atualizar_etapas_progresso("done")
        win._lbl_stage.configure(text="Concluido")
        win._lbl_sub.configure(text="Tudo pronto.")
        win._lbl_status.configure(text="Arquivo gerado com sucesso.")
        win._pbar.configure(value=100)
        win._lbl_pct.configure(text="100%")

        for step in win._step_widgets:
            step['frame'].configure(highlightbackground=CORES['success'])
            step['dot'].configure(bg=CORES['success'])
            step['label'].configure(text=f"OK  {step['base_label']}", fg=CORES['fg_bright'])

        self.after(700, self._finalizar_processamento)

    def _processar(self, pdf_path, xlsx_path, output_path, codigos,
                   dias_mes=None, colunas_qt=None,
                   modo_verif='unica', verif_key='', verif_modelo=''):
        def cb(pct, msg):
            self.after(0, lambda p=pct, m=msg: self._atualizar_progresso(p, m))

        try:
            cb(5, "Lendo PDF (varredura 1)...")
            v1 = self.processador.extrair_ocorrencias(pdf_path, codigos)

            dados_reconciliados = v1
            info_verif = {'modo': modo_verif, 'ia_usada': False, 'ia_fallback': False}

            if modo_verif in ('dupla', 'ia'):
                cb(20, "Varredura 2 (texto/regex)...")
                v2 = self.processador.extrair_ocorrencias_texto(pdf_path, codigos)

                if not v2:
                    camadas = [v1]
                else:
                    camadas = [v1, v2]

                if modo_verif == 'ia':
                    cb(35, "Verificando com IA (Gemini Vision)...")
                    v3 = self.processador.verificar_com_ia(
                        pdf_path, codigos, verif_key, verif_modelo
                    )
                    if v3 is not None:
                        camadas.append(v3)
                        info_verif['ia_usada'] = True
                    else:
                        info_verif['ia_fallback'] = True

                cb(45, "Reconciliando resultados...")
                rec = self.processador.reconciliar(camadas, codigos)

                concordantes = rec['concordantes']
                conflitos    = rec['conflitos']

                if conflitos:
                    import queue
                    q = queue.Queue()
                    self.after(0, lambda: self._abrir_modal_conflitos(conflitos, q))
                    escolhas = q.get()

                    if escolhas is None:
                        self.after(0, self._finalizar_processamento)
                        return

                    for re_val, cod, val in escolhas:
                        if re_val not in concordantes:
                            nome = next(
                                (c.get(re_val, {}).get('nome', '') for c in camadas if re_val in c), ''
                            )
                            concordantes[re_val] = {'nome': nome, 'ocorrencias': {}}
                        concordantes[re_val]['ocorrencias'][cod] = val

                dados_reconciliados = concordantes
                info_verif['concordantes'] = len(concordantes)
                info_verif['conflitos_resolvidos'] = len(conflitos)

            resultado = self.processador.processar(
                pdf_path, xlsx_path, output_path, codigos, cb, dias_mes, colunas_qt,
                dados_externos=dados_reconciliados if modo_verif != 'unica' else None
            )
            resultado['info_verif'] = info_verif

            self.after(0, self._marcar_sucesso_progresso)
            self.after(750, lambda: self._mostrar_resultados(resultado, output_path))
        except Exception as e:
            self.after(0, lambda: self._mostrar_erro(str(e)))
            self.after(0, self._finalizar_processamento)

    def _iniciar_animacao(self):
        frames = [
            "Processando.",
            "Processando..",
            "Processando...",
            "Processando....",
        ]
        self._anim_frames = frames
        self._anim_frame = 0
        self._animar_btn()

    def _animar_btn(self):
        if not self.processando:
            return
        self.btn_processar.configure(text=self._anim_frames[self._anim_frame])
        self._anim_frame = (self._anim_frame + 1) % len(self._anim_frames)
        self._anim_job = self.after(200, self._animar_btn)

    def _finalizar_processamento(self):
        self.processando = False
        if self._anim_job:
            self.after_cancel(self._anim_job)
            self._anim_job = None
        self.btn_processar.configure(text="▶  PROCESSAR ARQUIVOS", state='normal',
                                     bg=CORES['btn_bg'])
        if self._janela_progresso and self._janela_progresso.winfo_exists():
            for job_attr in ('_spin_job', '_dots_job', '_pulse_job'):
                if hasattr(self._janela_progresso, job_attr):
                    try:
                        self._janela_progresso.after_cancel(getattr(self._janela_progresso, job_attr))
                    except Exception:
                        pass
            self._janela_progresso.destroy()
        self._janela_progresso = None

    def _mostrar_erro(self, msg):
        messagebox.showerror("Erro no Processamento", msg)

    def _mostrar_resultados(self, resultado, output_path):
        from datetime import datetime
        self._historico.append({
            'arquivo': os.path.basename(output_path),
            'data': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'total_pdf': resultado['total_pdf'],
            'matched': resultado['matched'],
            'nao_encontrados': len(resultado['nao_encontrados']),
            'lista_nao_encontrados': resultado['nao_encontrados'],
            'info_verif': resultado.get('info_verif', {'modo': 'unica'}),
        })
        self._atualizar_historico()
        self._abrir_tela_resumo(resultado, output_path)

    def _abrir_tela_resumo(self, resultado, output_path):
        win = tk.Toplevel(self)
        win.title("Resumo do Processamento")
        win.configure(bg=CORES['bg'])
        win.geometry("820x580")
        win.minsize(700, 450)
        win.grab_set()

        # Centralizar
        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 410
        y = self.winfo_y() + (self.winfo_height() // 2) - 290
        win.geometry(f"820x580+{x}+{y}")

        main = tk.Frame(win, bg=CORES['bg'])
        main.pack(fill='both', expand=True, padx=24, pady=20)

        # Título
        tk.Label(main, text="Resumo do Processamento",
                 font=(FONT_SANS, 16, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(anchor='w')
        tk.Label(main, text=f"Arquivo: {os.path.basename(output_path)}",
                 font=(FONT_MONO, 9), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(anchor='w', pady=(2, 12))

        # Cards de estatísticas
        stats_frame = tk.Frame(main, bg=CORES['bg'])
        stats_frame.pack(fill='x', pady=(0, 16))

        nao_enc = len(resultado['nao_encontrados'])
        stats = [
            ("Encontrados no PDF", str(resultado['total_pdf']), CORES['accent_light']),
            ("Aplicados na planilha", str(resultado['matched']), CORES['success']),
            ("Não localizados", str(nao_enc),
             CORES['error'] if nao_enc else CORES['success']),
        ]

        for i, (label, value, color) in enumerate(stats):
            card = tk.Frame(stats_frame, bg=CORES['bg_card'],
                            highlightbackground=color, highlightthickness=1)
            card.pack(side='left', fill='x', expand=True, padx=(0 if i == 0 else 8, 0))
            tk.Label(card, text=value, font=(FONT_SANS, 22, "bold"),
                     fg=color, bg=CORES['bg_card']).pack(pady=(10, 0))
            tk.Label(card, text=label, font=(FONT_SANS, 9),
                     fg=CORES['fg_dim'], bg=CORES['bg_card']).pack(pady=(0, 10))

        # Bloco de verificação
        info_verif = resultado.get('info_verif', {'modo': 'unica'})
        modo = info_verif.get('modo', 'unica')
        if modo != 'unica':
            vf = tk.Frame(main, bg=CORES['bg_card'],
                          highlightbackground=CORES['border'], highlightthickness=1)
            vf.pack(fill='x', pady=(0, 14))
            vf_inner = tk.Frame(vf, bg=CORES['bg_card'])
            vf_inner.pack(fill='x', padx=14, pady=10)

            modo_labels = {'dupla': 'Dupla varredura', 'ia': 'Dupla + IA (Gemini)'}
            tk.Label(vf_inner,
                     text=f"🔍  {modo_labels.get(modo, modo)}",
                     font=(FONT_SANS, 10, "bold"), fg=CORES['accent_light'],
                     bg=CORES['bg_card']).pack(anchor='w', pady=(0, 6))

            stats_v = tk.Frame(vf_inner, bg=CORES['bg_card'])
            stats_v.pack(fill='x')

            conc = info_verif.get('concordantes', 0)
            conf = info_verif.get('conflitos_resolvidos', 0)
            ia_usada = info_verif.get('ia_usada', False)
            ia_fallback = info_verif.get('ia_fallback', False)

            for label, valor, cor in [
                ("Automáticos",          str(conc), CORES['success']),
                ("Conflitos resolvidos", str(conf),
                 CORES['warning'] if conf else CORES['fg_dim']),
            ]:
                bloco = tk.Frame(stats_v, bg=CORES['bg_input'])
                bloco.pack(side='left', padx=(0, 6))
                tk.Label(bloco, text=valor, font=(FONT_SANS, 12, "bold"),
                         fg=cor, bg=CORES['bg_input']).pack(side='left', padx=(8, 4), pady=4)
                tk.Label(bloco, text=label, font=(FONT_SANS, 8),
                         fg=CORES['fg_dim'], bg=CORES['bg_input']).pack(side='left', padx=(0, 8))

            if modo == 'ia':
                if ia_usada:
                    ia_txt, ia_cor = "IA utilizada", CORES['success']
                elif ia_fallback:
                    ia_txt, ia_cor = "IA indisponível — usou dupla varredura", CORES['warning']
                else:
                    ia_txt, ia_cor = "IA não ativada", CORES['fg_dim']
                tk.Label(vf_inner, text=ia_txt,
                         font=(FONT_SANS, 9), fg=ia_cor,
                         bg=CORES['bg_card']).pack(anchor='w', pady=(6, 0))

        # Tabela de não localizados
        if resultado['nao_encontrados']:
            tk.Frame(main, bg=CORES['border'], height=1).pack(fill='x', pady=(0, 10))

            tk.Label(main, text=f"⚠  Pessoas não localizadas na planilha ({nao_enc})",
                     font=(FONT_SANS, 11, "bold"), fg=CORES['error'],
                     bg=CORES['bg'], anchor='w').pack(fill='x', pady=(0, 6))

            tree_frame = tk.Frame(main, bg=CORES['bg'])
            tree_frame.pack(fill='both', expand=True)

            style = ttk.Style()
            style.configure("Resumo.Treeview",
                            background=CORES['bg_card'], foreground=CORES['fg'],
                            fieldbackground=CORES['bg_card'], borderwidth=0,
                            font=(FONT_MONO, 10), rowheight=26)
            style.configure("Resumo.Treeview.Heading",
                            background=CORES['table_header'], foreground=CORES['fg_dim'],
                            font=(FONT_SANS, 9, "bold"), borderwidth=0, relief='flat')
            style.map("Resumo.Treeview",
                      background=[('selected', CORES['bg_input'])],
                      foreground=[('selected', CORES['accent_light'])])

            tree = ttk.Treeview(tree_frame, columns=('re', 'nome', 'ocorrencia'),
                                show='headings', style="Resumo.Treeview")
            tree.heading('re', text='RE', anchor='w')
            tree.heading('nome', text='Nome', anchor='w')
            tree.heading('ocorrencia', text='Ocorrência', anchor='w')
            tree.column('re', width=80, minwidth=60, stretch=False)
            tree.column('nome', width=380, minwidth=200, stretch=True)
            tree.column('ocorrencia', width=160, minwidth=100, stretch=False)

            sb = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            tree.pack(side='left', fill='both', expand=True)
            sb.pack(side='right', fill='y')

            for item in resultado['nao_encontrados']:
                tree.insert('', 'end', values=(item['re'], item['nome'], item['motivo']))

        # Botões rodapé
        btn_frame = tk.Frame(main, bg=CORES['bg'])
        btn_frame.pack(fill='x', pady=(14, 0))

        RoundedButton(
            btn_frame, text="📂  Abrir pasta", variant='ghost', radius=6,
            font=(FONT_SANS, 10, "bold"), padx=14, pady=7,
            command=lambda: os.startfile(os.path.dirname(output_path))
        ).pack(side='left')

        RoundedButton(
            btn_frame, text="Fechar", variant='mini', radius=6,
            font=(FONT_SANS, 10), padx=16, pady=7,
            command=win.destroy
        ).pack(side='right')

    def _abrir_modal_conflitos(self, conflitos, resultado_queue):
        """
        Abre janela modal listando conflitos entre camadas.
        Coloca as escolhas do usuário em resultado_queue como lista de
        (re, codigo, valor) ou None se cancelado.
        """
        win = tk.Toplevel(self)
        win.title("Conflitos encontrados")
        win.configure(bg=CORES['bg'])
        win.geometry("760x540")
        win.minsize(640, 400)
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 380
        y = self.winfo_y() + (self.winfo_height() // 2) - 270
        win.geometry(f"760x540+{x}+{y}")

        main = tk.Frame(win, bg=CORES['bg'])
        main.pack(fill='both', expand=True, padx=20, pady=16)

        tk.Label(main,
                 text=f"Conflitos encontrados — {len(conflitos)} item(s) precisam de revisão",
                 font=(FONT_SANS, 13, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(anchor='w', pady=(0, 4))
        tk.Label(main,
                 text="Selecione o valor correto para cada conflito. A sugestão já está pré-selecionada.",
                 font=(FONT_SANS, 9), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(anchor='w', pady=(0, 12))

        canvas = tk.Canvas(main, bg=CORES['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(main, orient='vertical', command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=CORES['bg'])
        scroll_frame.bind('<Configure>',
                          lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self._bind_scroll(canvas, scroll_frame)

        escolha_vars = {}

        for conflito in conflitos:
            re_val = conflito['re']
            nome   = conflito['nome']
            cod    = conflito['codigo']
            vals   = conflito['valores']
            sug    = conflito['sugestao']

            card = tk.Frame(scroll_frame, bg=CORES['bg_card'],
                            highlightbackground=CORES['border'], highlightthickness=1)
            card.pack(fill='x', pady=(0, 8))

            top = tk.Frame(card, bg=CORES['bg_card'])
            top.pack(fill='x', padx=14, pady=(10, 6))
            tk.Label(top, text=f"RE {re_val}  —  {nome}",
                     font=(FONT_SANS, 10, "bold"), fg=CORES['fg_bright'],
                     bg=CORES['bg_card']).pack(side='left')
            tk.Label(top, text=f"Código: {cod}",
                     font=(FONT_SANS, 9), fg=CORES['accent_light'],
                     bg=CORES['bg_card']).pack(side='right')

            opcoes_row = tk.Frame(card, bg=CORES['bg_card'])
            opcoes_row.pack(fill='x', padx=14, pady=(0, 12))

            var = tk.IntVar(value=sug)
            escolha_vars[(re_val, cod)] = var

            rotulos = {'v1': 'V1 (tabelas)', 'v2': 'V2 (texto)', 'ia': 'IA (Gemini)'}
            valores_unicos = {}
            for chave, val in vals.items():
                if val is None:
                    continue
                label_camada = rotulos.get(chave, chave)
                if val not in valores_unicos:
                    valores_unicos[val] = []
                valores_unicos[val].append(label_camada)

            for val_opcao, camadas_label in sorted(valores_unicos.items()):
                texto_btn = f"{val_opcao} {cod}  ({', '.join(camadas_label)})"
                is_sug = (val_opcao == sug)
                rb = tk.Radiobutton(
                    opcoes_row, text=texto_btn,
                    variable=var, value=val_opcao,
                    font=(FONT_SANS, 9, "bold" if is_sug else "normal"),
                    fg=CORES['accent_light'] if is_sug else CORES['fg'],
                    bg=CORES['bg_card'],
                    activebackground=CORES['bg_card'],
                    selectcolor=CORES['bg_input'],
                )
                rb.pack(side='left', padx=(0, 16))

        btn_row = tk.Frame(main, bg=CORES['bg'])
        btn_row.pack(fill='x', pady=(12, 0))

        def confirmar():
            escolhas = [(re_val, cod, var.get())
                        for (re_val, cod), var in escolha_vars.items()]
            win.destroy()
            resultado_queue.put(escolhas)

        def cancelar():
            win.destroy()
            resultado_queue.put(None)

        RoundedButton(btn_row, text="Confirmar e gravar",
                      variant='primary', radius=8,
                      font=(FONT_SANS, 11, "bold"),
                      padx=20, pady=9,
                      command=confirmar).pack(side='left')

        RoundedButton(btn_row, text="Cancelar",
                      variant='mini', radius=8,
                      font=(FONT_SANS, 11),
                      padx=20, pady=9,
                      command=cancelar).pack(side='left', padx=(10, 0))

    def _criar_tabela(self, parent, titulo, dados, cor_titulo):
        wrapper = tk.Frame(parent, bg=CORES['bg_card'],
                           highlightbackground=CORES['border'], highlightthickness=1)
        wrapper.pack(fill='both', expand=True, pady=(0, 8))

        tk.Frame(wrapper, bg=cor_titulo, width=3).pack(side='left', fill='y')

        card = tk.Frame(wrapper, bg=CORES['bg_card'])
        card.pack(side='left', fill='both', expand=True)

        tk.Label(card, text=f"{titulo} ({len(dados)})",
                 font=(FONT_SANS, 11, "bold"), fg=cor_titulo,
                 bg=CORES['bg_card'], anchor='w').pack(fill='x', padx=14, pady=(12, 6))

        tree_frame = tk.Frame(card, bg=CORES['bg_card'])
        tree_frame.pack(fill='both', expand=True, padx=14, pady=(0, 12))

        style = ttk.Style()
        style.theme_use('default')
        style.configure("Custom.Treeview",
                        background=CORES['bg_card'],
                        foreground=CORES['fg'],
                        fieldbackground=CORES['bg_card'],
                        borderwidth=0,
                        font=(FONT_MONO, 10),
                        rowheight=26)
        style.configure("Custom.Treeview.Heading",
                        background=CORES['table_header'],
                        foreground=CORES['fg_dim'],
                        font=(FONT_SANS, 9, "bold"),
                        borderwidth=0, relief='flat')
        style.map("Custom.Treeview",
                  background=[('selected', CORES['bg_input'])],
                  foreground=[('selected', CORES['accent_light'])])

        tree = ttk.Treeview(tree_frame, columns=('re', 'nome', 'motivo'),
                            show='headings', style="Custom.Treeview",
                            height=min(len(dados), 5))
        tree.heading('re', text='RE', anchor='w')
        tree.heading('nome', text='Nome', anchor='w')
        tree.heading('motivo', text='Motivo', anchor='w')
        tree.column('re', width=70, minwidth=60)
        tree.column('nome', width=350, minwidth=200)
        tree.column('motivo', width=200, minwidth=100)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        for item in dados:
            tree.insert('', 'end', values=(item['re'], item['nome'], item['motivo']))


class SplashScreen(tk.Tk):
    """Tela de carregamento exibida antes do app principal."""

    _BG      = '#0a0b12'
    _ACCENT  = '#5b8def'
    _TRACK   = '#1a1d29'
    _SPINNER_R = 18   # raio externo
    _SPINNER_W =  4   # espessura do arco
    _ARC_SPAN  = 90   # graus do arco visível

    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.configure(bg=self._BG)
        self.attributes('-topmost', True)

        W, H = 380, 220
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
        self.configure(highlightbackground='#262a3a', highlightthickness=1)

        tk.Label(self, text="Processador de Ocorrências",
                 font=(FONT_SANS, 14, "bold"),
                 fg='#e6e8f0', bg=self._BG).pack(pady=(38, 4))

        tk.Label(self, text=f"v{VERSION}",
                 font=(FONT_MONO, 9),
                 fg='#6e7591', bg=self._BG).pack()

        tk.Frame(self, bg='#262a3a', height=1).pack(fill='x', padx=30, pady=16)

        # linha com spinner + label lado a lado
        row = tk.Frame(self, bg=self._BG)
        row.pack()

        size = (self._SPINNER_R + self._SPINNER_W) * 2 + 2
        self._canvas = tk.Canvas(row, width=size, height=size,
                                 bg=self._BG, highlightthickness=0)
        self._canvas.pack(side='left', padx=(0, 10))

        self._lbl_status = tk.Label(row, text="Iniciando...",
                                    font=(FONT_SANS, 10),
                                    fg='#6e7591', bg=self._BG,
                                    anchor='w', width=22)
        self._lbl_status.pack(side='left')

        self._angle = 0
        self._anim_id = None
        self._draw_spinner()
        self._animar()

    def _draw_spinner(self):
        self._canvas.delete("all")
        m = self._SPINNER_W
        r = self._SPINNER_R
        cx = cy = r + m + 1
        # trilha
        self._canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                  outline=self._TRACK, width=self._SPINNER_W)
        # arco giratório
        self._canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                                  start=self._angle, extent=self._ARC_SPAN,
                                  outline=self._ACCENT, width=self._SPINNER_W,
                                  style='arc')

    def _animar(self):
        self._angle = (self._angle + 12) % 360
        self._draw_spinner()
        self._anim_id = self.after(30, self._animar)

    def set_status(self, texto: str):
        self._lbl_status.configure(text=texto)
        self.update()

    def fechar(self):
        if self._anim_id:
            self.after_cancel(self._anim_id)
        self.destroy()


def _splash_wait(splash: SplashScreen, ms: int, min_ms: int = 800):
    """Mantém o spinner girando por pelo menos min_ms após a etapa concluir."""
    import time
    elapsed = ms
    remaining = max(0, min_ms - elapsed)
    deadline = time.monotonic() + remaining / 1000
    while time.monotonic() < deadline:
        splash.update()
        splash.after(30)


def main():
    import sys, time

    splash = SplashScreen()
    splash.update()

    # 1. Verificar e aplicar atualização
    splash.set_status("Procurando atualizações...")
    t0 = time.monotonic()
    check_and_update()
    _splash_wait(splash, int((time.monotonic() - t0) * 1000), min_ms=1200)

    # 2. Validar licença
    splash.set_status("Validando licença...")
    t0 = time.monotonic()
    client = LicenseClient()
    result = client.validate()
    _splash_wait(splash, int((time.monotonic() - t0) * 1000), min_ms=1000)

    # Fecha a splash antes de qualquer diálogo de licença (evita sobreposição)
    splash_destruida = False
    if result.status not in (LicenseStatus.VALID, LicenseStatus.OFFLINE_TOLERATED):
        splash.fechar()
        splash_destruida = True
        ok = _resolver_licenca(client, result)
        if not ok:
            sys.exit(0)

    # 3. Carregando
    if not splash_destruida:
        splash.set_status("Carregando...")
        _splash_wait(splash, 0, min_ms=600)
        splash.fechar()

    App().mainloop()


if __name__ == '__main__':
    main()
