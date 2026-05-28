"""Comunicação com o servidor de licença para status de conexão e config (API key do Gemini)."""
import requests
from PySide6.QtCore import QObject, Signal

from license_client import LicenseClient, LicenseStatus


def fetch_gemini_key() -> str:
    """Baixa a API key do Gemini do servidor usando a license key salva.
    Retorna a key ou "" se não houver chave salva, servidor indisponível ou resposta inválida."""
    client = LicenseClient()
    key = client.get_saved_key()
    if not key:
        return ""
    try:
        resp = requests.post(
            f"{LicenseClient.SERVER_URL}/api/config",
            json={"key": key},
            timeout=LicenseClient.TIMEOUT_SECONDS,
        )
        if resp.status_code == 200:
            return resp.json().get("gemini_api_key", "") or ""
    except (requests.RequestException, ValueError):
        pass
    return ""


# Mapa de status -> (texto curto, cor) para a pill da status bar e o card.
_STATUS_INFO = {
    LicenseStatus.VALID: ("Conectado", "#238636"),
    LicenseStatus.OFFLINE_TOLERATED: ("Servidor indisponível (tolerado)", "#d29922"),
    LicenseStatus.OFFLINE_EXPIRED: ("Servidor indisponível", "#f85149"),
    LicenseStatus.INVALID: ("Licença inválida", "#f85149"),
    LicenseStatus.NO_KEY: ("Sem licença", "#f85149"),
}


def status_info(status, reason=None):
    texto, cor = _STATUS_INFO.get(status, ("Desconhecido", "#8b949e"))
    if status == LicenseStatus.OFFLINE_TOLERATED and reason == "no_internet":
        texto = "Sem internet (tolerado)"
    elif status == LicenseStatus.OFFLINE_EXPIRED and reason == "no_internet":
        texto = "Sem internet"
    return texto, cor


class ConnCheckWorker(QObject):
    """Revalida a licença e baixa a versão mais recente e a key do Gemini do servidor."""
    resultado = Signal(str, str, str, bool)  # (texto, cor, versao_mais_recente, gemini_ok)
    finished = Signal()

    def run(self):
        try:
            client = LicenseClient()
            result = client.validate()
            texto, cor = status_info(result.status, result.reason)

            latest_version = ""
            try:
                from auto_update import _fetch_latest
                latest = _fetch_latest()
                if latest:
                    latest_version = latest.get("version", "") or ""
            except Exception:
                pass

            gemini_ok = bool(fetch_gemini_key())
            self.resultado.emit(texto, cor, latest_version, gemini_ok)
        finally:
            self.finished.emit()


class ModelosWorker(QObject):
    """Busca a key do servidor e lista os modelos disponíveis do Gemini."""
    ok = Signal(list)      # list[(display, model_id)]
    erro = Signal(str)
    finished = Signal()

    def run(self):
        try:
            api_key = fetch_gemini_key()
            if not api_key:
                self.erro.emit("Não foi possível obter a chave do Gemini do servidor.")
                return
            from vt_caixa_processador import ProcessadorVTCaixa
            modelos = ProcessadorVTCaixa.listar_modelos(api_key)
            self.ok.emit(modelos)
        except Exception as e:
            self.erro.emit(str(e))
        finally:
            self.finished.emit()
