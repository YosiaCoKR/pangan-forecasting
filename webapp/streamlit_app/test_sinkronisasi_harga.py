"""Cek jalur `mock_prices.sinkronkan_ke_github()` — TANPA jaringan & tanpa
menyentuh `data/harga_historis.pkl` sungguhan.

Yang dijaga di sini: `sha` blob lama ikut terkirim saat berkas sudah ada di
repo (kalau tidak, GitHub menolak dengan 409 dan harga admin diam-diam tidak
pernah tersalin), kegagalan selalu dilaporkan sebagai string (bukan exception
yang mematikan halaman admin), dan token TIDAK pernah bocor ke pesan galat.

Jalankan: `python test_sinkronisasi_harga.py` (dari folder streamlit_app).
"""

import base64
import pickle
import tempfile
from pathlib import Path
from types import SimpleNamespace

_tmp = Path(tempfile.mkdtemp(prefix="ppj-sync-"))

import config

config._CONFIG_PATH = _tmp / "config.json"

from data import mock_prices

TOKEN = "github_pat_RAHASIA_JANGAN_BOCOR"
mock_prices._PKL_PATH = _tmp / "harga_historis.pkl"
mock_prices._PKL_PATH.write_bytes(pickle.dumps({"beras": [1, 2, 3]}))


class _Respons:
    def __init__(self, status_code, data=None, text=""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


class _RequestsPalsu:
    """Pengganti modul `requests` — merekam panggilan, tidak pernah ke jaringan."""

    RequestException = mock_prices.requests.RequestException

    def __init__(self, respons_get, respons_put=None, lempar=None):
        self.respons_get, self.respons_put, self.lempar = respons_get, respons_put, lempar
        self.panggilan_put = None

    def get(self, url, **kwargs):
        self.url_get = url
        self.params_get = kwargs.get("params")
        return self.respons_get

    def put(self, url, **kwargs):
        if self.lempar:
            raise self.lempar
        self.panggilan_put = kwargs
        return self.respons_put


def _pakai_secrets(nilai):
    mock_prices.st = SimpleNamespace(secrets=SimpleNamespace(get=lambda _: nilai))


# --- 1. belum dikonfigurasi -> None, dan TIDAK ada panggilan HTTP sama sekali ---
mock_prices.requests = _RequestsPalsu(_Respons(500))
_pakai_secrets(None)
assert mock_prices.sinkronkan_ke_github() is None, "tanpa secrets harus diam, bukan galat"
_pakai_secrets({"token": TOKEN})  # repo hilang -> tetap dianggap belum dikonfigurasi
assert mock_prices.sinkronkan_ke_github() is None, "secrets separuh harus dianggap belum siap"
print("ok belum dikonfigurasi")

_pakai_secrets({"token": TOKEN, "repo": "akun/repo", "branch": "main"})

# --- 2. berkas SUDAH ada di repo -> `sha` lama wajib ikut terkirim ---
palsu = _RequestsPalsu(_Respons(200, {"sha": "sha-lama-123"}), _Respons(200))
mock_prices.requests = palsu
assert mock_prices.sinkronkan_ke_github() is None
muatan = palsu.panggilan_put["json"]
assert muatan["sha"] == "sha-lama-123", "sha blob lama tidak terkirim -> GitHub akan menolak"
assert muatan["branch"] == "main"
assert base64.b64decode(muatan["content"]) == mock_prices._PKL_PATH.read_bytes(), (
    "isi yang dikirim bukan byte .pkl yang sama"
)
assert palsu.panggilan_put["headers"]["Authorization"] == f"Bearer {TOKEN}"
assert mock_prices._PKL_REPO_PATH in palsu.url_get
print("ok timpa berkas yang sudah ada")

# --- 3. berkas BELUM ada (404) -> kirim tanpa `sha` ---
palsu = _RequestsPalsu(_Respons(404), _Respons(201))
mock_prices.requests = palsu
assert mock_prices.sinkronkan_ke_github() is None
assert "sha" not in palsu.panggilan_put["json"], "berkas baru tidak boleh mengirim sha"
print("ok berkas baru")

# --- 4. kegagalan dilaporkan sebagai string, bukan exception, dan tanpa token ---
palsu = _RequestsPalsu(_Respons(200, {"sha": "x"}), _Respons(422, text="Unprocessable"))
mock_prices.requests = palsu
galat = mock_prices.sinkronkan_ke_github()
assert isinstance(galat, str) and "422" in galat, f"commit gagal harus dilaporkan: {galat!r}"
assert TOKEN not in galat, "TOKEN BOCOR ke pesan galat"

mock_prices.requests = _RequestsPalsu(_Respons(401))
galat = mock_prices.sinkronkan_ke_github()
assert isinstance(galat, str) and "401" in galat, f"GET gagal harus dilaporkan: {galat!r}"

palsu = _RequestsPalsu(
    _Respons(200, {"sha": "x"}), lempar=mock_prices.requests.RequestException("timeout")
)
mock_prices.requests = palsu
galat = mock_prices.sinkronkan_ke_github()
assert isinstance(galat, str) and "GitHub" in galat, f"galat jaringan harus ditangkap: {galat!r}"
assert TOKEN not in galat, "TOKEN BOCOR ke pesan galat jaringan"
print("ok kegagalan dilaporkan tanpa membocorkan token")

print("SEMUA OK")
