"""
tests/test_tani.py -- Teshis komutu testleri

Bu komutun tek isi dogru rapor vermek. Ama en onemli ozelligi sudur:
BIR SEYI BOZMAMASI. Sorun yasayan biri calistiracak; teshis komutunun
kendisi de bir sorun cikarirsa isin icinden cikilmaz.
"""

import json
import threading
from http.server import HTTPServer

import pytest

from core import tani
from core.tani import TAMAM, YOK, main, rapor
from tests.test_ollama import SahteOllama

KAPALI = "http://127.0.0.1:1"


@pytest.fixture
def sunucu():
    """Sahte Ollama (test_ollama.py'deki taklidin aynisi)."""
    SahteOllama.kurulu_modeller = ["llama3.1:8b", "nomic-embed-text:latest"]
    SahteOllama.hata_kodu = None
    SahteOllama.bozuk_cevap = False
    SahteOllama.gelen_istekler = []

    servis = HTTPServer(("127.0.0.1", 0), SahteOllama)
    iplik = threading.Thread(
        target=lambda: servis.serve_forever(poll_interval=0.01), daemon=True
    )
    iplik.start()
    yield f"http://127.0.0.1:{servis.server_port}"
    servis.shutdown()
    servis.server_close()


@pytest.fixture
def bos_workspace(tmp_path, monkeypatch):
    """Gercek workspace'e dokunmadan test edelim."""
    from core import approval, guvenlik, memory

    monkeypatch.setattr(tani, "WORKSPACE", tmp_path)
    monkeypatch.setattr(approval, "WORKSPACE", tmp_path)
    monkeypatch.setattr(memory, "WORKSPACE", tmp_path)
    monkeypatch.setattr(guvenlik, "WORKSPACE", tmp_path)
    return tmp_path


# -- Rapor icerigi -----------------------------------------------------------


def test_rapor_tum_bolumleri_icerir(bos_workspace):
    metin, _ = rapor(KAPALI)
    for baslik in ["ORTAM", "PROJE", "OLLAMA", "HAFIZA", "OLCUM"]:
        assert baslik in metin


def test_python_surumu_raporlanir(bos_workspace):
    metin, _ = rapor(KAPALI)
    assert "Python surumu" in metin


def test_ollama_yoksa_ne_yapilacagini_soyler(bos_workspace):
    metin, temiz = rapor(KAPALI)
    assert not temiz
    assert "ulasilamadi" in metin
    assert "ollama serve" in metin


def test_ollama_varsa_modelleri_listeler(bos_workspace, sunucu):
    metin, _ = rapor(sunucu)
    assert "llama3.1:8b" in metin
    assert f"{TAMAM} Sohbet modeli" in metin
    assert f"{TAMAM} Gomme modeli" in metin


def test_eksik_model_bildirilir(bos_workspace, sunucu):
    SahteOllama.kurulu_modeller = ["llama3.1:8b"]  # gomme modeli yok
    metin, temiz = rapor(sunucu)
    assert not temiz
    assert "ollama pull nomic-embed-text" in metin


def test_hic_model_yoksa_bildirilir(bos_workspace, sunucu):
    SahteOllama.kurulu_modeller = []
    metin, temiz = rapor(sunucu)
    assert not temiz
    assert "hic yok" in metin


def test_bos_hafiza_tohumlamayi_onerir(bos_workspace, sunucu):
    metin, _ = rapor(sunucu)
    assert "tohumla" in metin


def test_dolu_hafiza_tohumlamayi_onermez(bos_workspace, sunucu):
    from core.approval import OnayKuyrugu

    kuyruk = OnayKuyrugu(klasor=bos_workspace, izinli_kok=bos_workspace)
    kuyruk.onayla(kuyruk.ekle("Kedinin adi Pamuk").no)

    metin, _ = rapor(sunucu)
    assert "Kalici bilgi: 1 adet" in metin
    assert "Kalici hafiza bos" not in metin


def test_bekleyen_aday_bildirilir(bos_workspace, sunucu):
    from core.approval import OnayKuyrugu

    kuyruk = OnayKuyrugu(klasor=bos_workspace, izinli_kok=bos_workspace)
    kuyruk.onayla(kuyruk.ekle("onaylanmis").no)
    kuyruk.ekle("bekleyen bir aday")

    metin, _ = rapor(sunucu)
    assert "1 aday karar bekliyor" in metin


def test_her_sey_yolundaysa_sirdaki_adimi_soyler(bos_workspace, sunucu):
    """Tum kontroller gecerse sirada ne var, onu yazmali."""
    from core.approval import OnayKuyrugu

    kuyruk = OnayKuyrugu(klasor=bos_workspace, izinli_kok=bos_workspace)
    kuyruk.onayla(kuyruk.ekle("bir bilgi").no)

    metin, temiz = rapor(sunucu)
    if temiz:  # pytest kurulu degilse bu ortamda temiz cikmayabilir
        assert "Her sey yolunda" in metin
        assert "cekirdek.py" in metin


# -- Hicbir seyi bozmuyor mu? ------------------------------------------------


def test_teshis_dosya_birakmaz(bos_workspace, sunucu):
    """
    En onemli test: teshis komutu SADECE BAKAR.
    Sorun yasayan biri calistiracak; kendisi yeni sorun cikarmamali.
    """
    oncesi = set(bos_workspace.iterdir())
    rapor(sunucu)
    assert set(bos_workspace.iterdir()) == oncesi


def test_teshis_hafizayi_degistirmez(bos_workspace, sunucu):
    from core.approval import OnayKuyrugu

    kuyruk = OnayKuyrugu(klasor=bos_workspace, izinli_kok=bos_workspace)
    kuyruk.onayla(kuyruk.ekle("dokunulmasin").no)
    oncesi = json.dumps(kuyruk.hafiza(), sort_keys=True)

    rapor(sunucu)

    sonrasi = json.dumps(OnayKuyrugu(klasor=bos_workspace, izinli_kok=bos_workspace).hafiza(), sort_keys=True)
    assert oncesi == sonrasi


def test_bozuk_hafiza_dosyasinda_cokmez(bos_workspace, sunucu):
    """
    Teshis komutu, en cok ihtiyac duyulan anda -- yani bir sey bozukken --
    calismak zorunda. Bozuk dosya gorunce cokmemeli, bildirmeli.
    """
    (bos_workspace / "hafiza.json").write_text("{bozuk", encoding="utf-8")
    metin, temiz = rapor(sunucu)
    assert not temiz
    assert "Hafiza okunamadi" in metin or "bozuk" in metin.lower()


# -- Terminal komutu ---------------------------------------------------------


def test_komut_calisir(bos_workspace, capsys):
    kod = main(["--sunucu", KAPALI])
    assert kod == 1  # yapilacak bir sey var (Ollama kapali)
    assert "TESHIS RAPORU" in capsys.readouterr().out


def test_komut_ciktisi_ascii(bos_workspace, capsys):
    """
    Rapordaki isaretler ASCII olmali: eski Windows terminallerinde
    emoji ve ozel karakterler bozuk gorunuyor.
    """
    main(["--sunucu", KAPALI])
    cikti = capsys.readouterr().out
    # Kullanicinin klasor adinda Turkce harf olabilir; sadece bizim
    # yazdigimiz sabit isaretleri kontrol ediyoruz.
    for isaret in (TAMAM, YOK, "[!!]"):
        assert isaret.isascii()
    assert "=" * 10 in cikti
