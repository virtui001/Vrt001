"""
tests/test_web.py -- Gorsel arayuz (web sunucusu) testleri

Arayuzu tarayici acmadan test ediyoruz: sunucuyu gecici bir kapida baslatip
tarayicinin yapacagi isteklerin aynisini gonderiyoruz.

En onemli iki sey:
  1. Onay kurali arayuzde de gecerli mi? (sohbet etmek ogretmek DEGIL)
  2. Sunucu sadece bu bilgisayara mi acik? (icinde kisisel hafiza var)
"""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from core.llm import llm_olustur
from web import sunucu as web


@pytest.fixture
def servis(tmp_path, monkeypatch):
    """Gecici klasorde, sahte modelle calisan bir arayuz sunucusu."""
    from cekirdek import Cekirdek
    from core import approval, guvenlik, memory

    for modul in (approval, memory, guvenlik):
        monkeypatch.setattr(modul, "WORKSPACE", tmp_path)

    monkeypatch.setattr(
        web,
        "_cekirdek",
        Cekirdek(
            llm=llm_olustur("mock", sabit_cevap="anladim"),
            klasor=tmp_path,
            izinli_kok=tmp_path,
        ),
    )
    monkeypatch.setattr(web, "_model_adi", "mock")

    sunucu = ThreadingHTTPServer(("127.0.0.1", 0), web.Islemci)
    threading.Thread(
        target=lambda: sunucu.serve_forever(poll_interval=0.01), daemon=True
    ).start()
    yield f"http://127.0.0.1:{sunucu.server_port}"
    sunucu.shutdown()
    sunucu.server_close()


def al(adres: str, yol: str):
    with urllib.request.urlopen(adres + yol, timeout=5) as c:
        return json.loads(c.read().decode("utf-8"))


def yolla(adres: str, yol: str, veri: dict):
    istek = urllib.request.Request(
        adres + yol,
        data=json.dumps(veri).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(istek, timeout=5) as c:
        return json.loads(c.read().decode("utf-8"))


# -- Sayfa -------------------------------------------------------------------


def test_ana_sayfa_acilir(servis):
    with urllib.request.urlopen(servis + "/", timeout=5) as c:
        metin = c.read().decode("utf-8")
    assert "Çekirdek" in metin
    assert "Onay Kuyruğu" in metin


def test_bilinmeyen_adres_404(servis):
    with pytest.raises(urllib.error.HTTPError) as hata:
        urllib.request.urlopen(servis + "/api/olmayan", timeout=5)
    assert hata.value.code == 404


# -- Durum ozeti -------------------------------------------------------------


def test_durum_ozeti(servis):
    d = al(servis, "/api/durum")
    assert set(d["durum"]) == {
        "aclik", "yorgunluk", "temizlik", "yalnizlik", "korku", "guven"
    }
    assert d["model"]["ad"] == "mock"
    assert d["model"]["gercek"] is False
    assert d["sayilar"]["kalici"] == 0


def test_durum_ayarlanir(servis):
    d = yolla(servis, "/api/durum", {"alan": "aclik", "deger": 75})
    assert d["aclik"] == 75
    assert al(servis, "/api/durum")["durum"]["aclik"] == 75


def test_durum_bilinmeyen_alan(servis):
    assert "hata" in yolla(servis, "/api/durum", {"alan": "mutluluk", "deger": 10})


def test_durum_aralik_disi(servis):
    assert "hata" in yolla(servis, "/api/durum", {"alan": "aclik", "deger": 500})


# -- Sohbet ------------------------------------------------------------------


def test_sohbet_cevap_doner(servis):
    c = yolla(servis, "/api/konus", {"metin": "Merhaba"})
    assert c["cevap"] == "anladim"


def test_sohbet_gunluge_yazilir(servis):
    yolla(servis, "/api/konus", {"metin": "Merhaba"})
    gecmis = al(servis, "/api/gecmis")
    assert len(gecmis) == 2  # sen + o


def test_bos_mesaj_reddedilir(servis):
    assert "hata" in yolla(servis, "/api/konus", {"metin": "   "})


def test_SOHBET_OGRETMEK_DEGIL(servis):
    """
    EN ONEMLI TEST: arayuzde de kural ayni. Bilgi iceren bir cumle
    kuyruga aday olarak girer, hafizaya GIRMEZ.
    """
    c = yolla(servis, "/api/konus", {"metin": "Benim kedimin adi Pamuk"})
    assert c["aday"] is not None
    assert al(servis, "/api/hafiza") == []      # hafiza hala bos
    assert len(al(servis, "/api/kuyruk")) == 1  # kuyrukta bekliyor


def test_siradan_sohbet_aday_uretmez(servis):
    c = yolla(servis, "/api/konus", {"metin": "Merhaba nasilsin"})
    assert c["aday"] is None


# -- Onay kuyrugu ------------------------------------------------------------


def test_elle_ekleme_hafizaya_yazmaz(servis):
    yolla(servis, "/api/ogren", {"metin": "Kedinin adi Pamuk"})
    assert len(al(servis, "/api/kuyruk")) == 1
    assert al(servis, "/api/hafiza") == []


def test_onaylayinca_hafizaya_gecer(servis):
    yolla(servis, "/api/ogren", {"metin": "Kedinin adi Pamuk"})
    no = al(servis, "/api/kuyruk")[0]["no"]

    c = yolla(servis, "/api/karar", {"numaralar": [no], "karar": "onayla"})
    assert c["adet"] == 1
    assert [k["metin"] for k in al(servis, "/api/hafiza")] == ["Kedinin adi Pamuk"]
    assert al(servis, "/api/kuyruk") == []


def test_reddedince_silinir(servis):
    yolla(servis, "/api/ogren", {"metin": "Yanlis bilgi"})
    no = al(servis, "/api/kuyruk")[0]["no"]
    yolla(servis, "/api/karar", {"numaralar": [no], "karar": "reddet"})
    assert al(servis, "/api/hafiza") == []
    assert al(servis, "/api/kuyruk") == []


def test_toplu_onay(servis):
    for i in range(3):
        yolla(servis, "/api/ogren", {"metin": f"bilgi {i}"})
    numaralar = [a["no"] for a in al(servis, "/api/kuyruk")]
    c = yolla(servis, "/api/karar", {"numaralar": numaralar, "karar": "onayla"})
    assert c["adet"] == 3


def test_gecersiz_karar_reddedilir(servis):
    assert "hata" in yolla(servis, "/api/karar", {"numaralar": [1], "karar": "sil"})


def test_olmayan_numara_hata_listesinde(servis):
    c = yolla(servis, "/api/karar", {"numaralar": [999], "karar": "onayla"})
    assert c["adet"] == 0
    assert c["hatalar"]


def test_tohumlama_kuyruga_koyar(servis):
    c = yolla(servis, "/api/tohumla", {})
    assert c["eklenen"] >= 15
    assert al(servis, "/api/hafiza") == []  # yine hafizaya girmedi


def test_bos_ogrenme_reddedilir(servis):
    with pytest.raises(urllib.error.HTTPError) as hata:
        yolla(servis, "/api/ogren", {"metin": "  "})
    assert hata.value.code == 400


# -- Teshis ------------------------------------------------------------------


def test_tani_calisir(servis):
    c = al(servis, "/api/tani")
    assert "TESHIS RAPORU" in c["metin"]


# -- Guvenlik ----------------------------------------------------------------


def test_sunucu_sadece_bu_bilgisayara_acik():
    """
    Icinde kisisel hafiza var. Sunucu 127.0.0.1'e baglanmali; "0.0.0.0"
    olsaydi ayni agdaki herkes okuyabilirdi.
    """
    from pathlib import Path

    kaynak = Path(web.__file__).read_text(encoding="utf-8")
    assert 'ThreadingHTTPServer(("127.0.0.1"' in kaynak

    # Yorum satirlarini haric tutuyoruz: aciklamada "0.0.0.0 yazsaydik..."
    # diye gecmesi sorun degil, KODDA gecmesi sorun.
    kod_satirlari = [
        s for s in kaynak.splitlines() if not s.strip().startswith("#")
    ]
    assert not any("0.0.0.0" in s for s in kod_satirlari)


def test_sayfa_kullanici_metnini_kacirir():
    """
    Kullanicinin yazdigi metin sayfaya konurken HTML olarak yorumlanmamali.
    Aksi halde bir metnin icindeki <script> calisir.
    """
    from pathlib import Path

    sayfa = (Path(web.__file__).parent / "sayfa.html").read_text(encoding="utf-8")
    assert "function kacar" in sayfa
    assert "textContent" in sayfa
