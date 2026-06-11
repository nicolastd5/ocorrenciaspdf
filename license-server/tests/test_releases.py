import hashlib
import io
import json

import pytest
from fastapi.testclient import TestClient

from app import releases


def test_publish_release_grava_exe_e_version_json(tmp_path):
    vf = tmp_path / "version.json"
    exe_dir = tmp_path / "releases"
    payload = b"conteudo-do-exe"

    info = releases.publish_release("9.99", io.BytesIO(payload),
                                    version_file=vf, exe_dir=exe_dir)

    assert info["version"] == "9.99"
    assert info["filename"] == "ProcessadorOcorrencias-v9.99.exe"
    assert info["sha256"] == hashlib.sha256(payload).hexdigest()
    assert (exe_dir / info["filename"]).read_bytes() == payload
    saved = json.loads(vf.read_text(encoding="utf-8"))
    assert saved["version"] == "9.99"
    assert saved["sha256"] == info["sha256"]
    assert saved["size"] == len(payload)


def test_publish_release_rejeita_versao_invalida(tmp_path):
    with pytest.raises(releases.ReleaseError):
        releases.publish_release("abc", io.BytesIO(b"x"),
                                 version_file=tmp_path / "v.json",
                                 exe_dir=tmp_path / "rel")


def test_publish_release_rejeita_arquivo_vazio(tmp_path):
    with pytest.raises(releases.ReleaseError):
        releases.publish_release("1.0", io.BytesIO(b""),
                                 version_file=tmp_path / "v.json",
                                 exe_dir=tmp_path / "rel")


def test_publish_release_remove_versoes_antigas_por_padrao(tmp_path):
    vf = tmp_path / "version.json"
    exe_dir = tmp_path / "releases"
    exe_dir.mkdir()
    antigo = exe_dir / "ProcessadorOcorrencias-v1.00.exe"
    antigo.write_bytes(b"velho")

    releases.publish_release("2.00", io.BytesIO(b"novo"),
                             version_file=vf, exe_dir=exe_dir)

    assert not antigo.exists()
    assert (exe_dir / "ProcessadorOcorrencias-v2.00.exe").exists()


def test_publish_release_keep_old_mantem_antigas(tmp_path):
    vf = tmp_path / "version.json"
    exe_dir = tmp_path / "releases"
    exe_dir.mkdir()
    antigo = exe_dir / "ProcessadorOcorrencias-v1.00.exe"
    antigo.write_bytes(b"velho")

    releases.publish_release("2.00", io.BytesIO(b"novo"), keep_old=True,
                             version_file=vf, exe_dir=exe_dir)

    assert antigo.exists()


# ---------- rota de upload ----------

@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "licenses.db"))
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef-test-only")
    monkeypatch.setattr(releases, "VERSION_FILE", tmp_path / "version.json")
    monkeypatch.setattr(releases, "EXE_DIR", tmp_path / "releases")
    import importlib
    import app.routes_admin
    import app.main
    app.routes_admin._admin_password_hash = None
    app.routes_admin.limiter._storage.reset()
    importlib.reload(app.main)
    return TestClient(app.main.app), tmp_path


def _login(c):
    import re
    resp = c.get("/admin/login")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', resp.text).group(1)
    c.post("/admin/login", data={"csrf_token": csrf, "password": "test-password"},
           follow_redirects=False)
    return csrf


def test_upload_requer_auth(client):
    c, _ = client
    resp = c.post("/admin/releases/upload", data={"csrf_token": "x", "version": "1.0"},
                  files={"file": ("a.exe", b"x")}, follow_redirects=False)
    assert resp.status_code in (302, 303)


def test_upload_publica_release(client):
    c, tmp_path = client
    csrf = _login(c)
    payload = b"exe-de-teste"
    resp = c.post(
        "/admin/releases/upload",
        data={"csrf_token": csrf, "version": "9.99"},
        files={"file": ("ProcessadorOcorrencias-v9.99.exe", payload,
                        "application/octet-stream")},
    )
    assert resp.status_code == 200
    saved = json.loads((tmp_path / "version.json").read_text(encoding="utf-8"))
    assert saved["version"] == "9.99"
    assert saved["sha256"] == hashlib.sha256(payload).hexdigest()
    assert (tmp_path / "releases" / "ProcessadorOcorrencias-v9.99.exe").exists()


def test_upload_ajax_retorna_json(client):
    c, tmp_path = client
    csrf = _login(c)
    resp = c.post(
        "/admin/releases/upload",
        data={"csrf_token": csrf, "version": "9.99"},
        files={"file": ("ProcessadorOcorrencias-v9.99.exe", b"exe",
                        "application/octet-stream")},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["version"] == "9.99"


def test_upload_ajax_erro_retorna_json(client):
    c, _ = client
    csrf = _login(c)
    resp = c.post(
        "/admin/releases/upload",
        data={"csrf_token": csrf, "version": "banana"},
        files={"file": ("a.exe", b"x", "application/octet-stream")},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]


def test_upload_sem_versao_detecta_do_nome_do_arquivo(client):
    c, tmp_path = client
    csrf = _login(c)
    resp = c.post(
        "/admin/releases/upload",
        data={"csrf_token": csrf, "version": ""},
        files={"file": ("ProcessadorOcorrencias-v1.66.exe", b"exe-166",
                        "application/octet-stream")},
    )
    assert resp.status_code == 200
    saved = json.loads((tmp_path / "version.json").read_text(encoding="utf-8"))
    assert saved["version"] == "1.66"


def test_releases_get_com_published_mostra_confirmacao(client):
    c, _ = client
    _login(c)
    resp = c.get("/admin/releases?published=1.66")
    assert resp.status_code == 200
    assert "Release v1.66 publicado" in resp.text


def test_upload_versao_invalida_mostra_erro(client):
    c, tmp_path = client
    csrf = _login(c)
    resp = c.post(
        "/admin/releases/upload",
        data={"csrf_token": csrf, "version": "banana"},
        files={"file": ("a.exe", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 200
    assert not (tmp_path / "version.json").exists()
