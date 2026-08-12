"""
tests/test_tohumlama.py -- Proje kurallarinin yuklenmesi ve toplu onay

NEDEN BU DOSYA VAR?
Eval'de "sistem yeni bir bilgi ogrenmek istediginde ne yapar?" gibi sorular
var. Model bunu bilemez, cunku bunlar BU PROJENIN kurallari. Kurallari
modele baglam olarak vermemiz gerekiyor.

Ama kurallari dogrudan hafizaya yazmak, projenin en onemli kuralini cignerdi.
Bu yuzden kurallar da herkes gibi onay kuyrugundan geciyor. Buradaki testler
tam olarak bunu koruyor.
"""

import json

import pytest

from core import approval
from core.approval import BEKLIYOR, KURALLAR_DOSYASI, OnayKuyrugu, numaralari_oku


@pytest.fixture
def kuyruk(tmp_path):
    return OnayKuyrugu(klasor=tmp_path, izinli_kok=tmp_path)


# -- Kural dosyasinin saglamligi ---------------------------------------------


def test_kural_dosyasi_var():
    assert KURALLAR_DOSYASI.exists(), f"Kural dosyasi yok: {KURALLAR_DOSYASI}"


def test_kural_dosyasi_gecerli_json():
    veri = json.loads(KURALLAR_DOSYASI.read_text(encoding="utf-8"))
    assert veri["kurallar"]


def test_her_kuralin_metni_ve_konusu_var():
    veri = json.loads(KURALLAR_DOSYASI.read_text(encoding="utf-8"))
    for kural in veri["kurallar"]:
        assert kural["metin"].strip()
        assert kural["konu"].strip()


def test_kurallar_eval_kategorilerini_kapsiyor():
    """
    Eval'de zorlanilan kategoriler durum/onay/guvenlik. Kural dosyasi
    bunlarin ucunu de icermeli, yoksa tohumlamanin bir anlami kalmaz.
    """
    veri = json.loads(KURALLAR_DOSYASI.read_text(encoding="utf-8"))
    konular = {k["konu"] for k in veri["kurallar"]}
    assert {"durum", "onay", "guvenlik"} <= konular


# -- Tohumlama ---------------------------------------------------------------


def test_tohumlama_kuyruga_koyar(kuyruk):
    yeniler = kuyruk.tohumla()
    assert len(yeniler) >= 15
    assert all(a.durum == BEKLIYOR for a in yeniler)


def test_TOHUMLAMA_HAFIZAYA_YAZMAZ(kuyruk):
    """
    EN ONEMLI TEST: projenin kendi kurallari bile onaysiz iceri giremez.
    Kural herkese esit uygulanmiyorsa kural degildir.
    """
    kuyruk.tohumla()
    assert kuyruk.hafiza() == []
    assert not kuyruk.hafiza_dosyasi.exists()


def test_tohumlama_iki_kez_calistirilabilir(kuyruk):
    """Ayni kural iki kez kuyruga girmemeli."""
    ilk = kuyruk.tohumla()
    ikinci = kuyruk.tohumla()
    assert ikinci == []
    assert len(kuyruk.bekleyenler()) == len(ilk)


def test_onaylanmis_kural_tekrar_kuyruga_girmez(kuyruk):
    yeniler = kuyruk.tohumla()
    kuyruk.onayla(yeniler[0].no)
    kuyruk.tohumla()
    metinler = [a.metin for a in kuyruk.bekleyenler()]
    assert yeniler[0].metin not in metinler


def test_kaynak_isaretlenir(kuyruk):
    """Denetim icin: bu bilgi nereden geldi?"""
    yeniler = kuyruk.tohumla()
    assert all(a.kaynak == "proje_kurallari" for a in yeniler)


def test_olmayan_dosya_acik_hata(kuyruk, tmp_path):
    with pytest.raises(ValueError, match="bulunamadi"):
        kuyruk.tohumla(tmp_path / "yok.json")


def test_bozuk_dosya_acik_hata(kuyruk, tmp_path):
    bozuk = tmp_path / "bozuk.json"
    bozuk.write_text("{bu json degil", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        kuyruk.tohumla(bozuk)


def test_bos_metinli_kural_atlanir(kuyruk, tmp_path):
    dosya = tmp_path / "kural.json"
    dosya.write_text(
        json.dumps({"kurallar": [{"metin": "  "}, {"metin": "gecerli kural"}]}),
        encoding="utf-8",
    )
    assert len(kuyruk.tohumla(dosya)) == 1


# -- Numara okuma (toplu onay) -----------------------------------------------


def test_tek_numara():
    assert numaralari_oku(["onayla", "3"]) == [3]


def test_birden_fazla_numara():
    assert numaralari_oku(["onayla", "1", "4", "7"]) == [1, 4, 7]


def test_aralik():
    assert numaralari_oku(["onayla", "1-5"]) == [1, 2, 3, 4, 5]


def test_aralik_ve_tekil_karisik():
    assert numaralari_oku(["onayla", "1-3", "7"]) == [1, 2, 3, 7]


def test_tekrarlar_teklesir():
    assert numaralari_oku(["onayla", "2", "2", "1-3"]) == [1, 2, 3]


def test_numarasiz_hata():
    with pytest.raises(ValueError, match="Numara eksik"):
        numaralari_oku(["onayla"])


def test_yazi_hata():
    with pytest.raises(ValueError, match="numara degil"):
        numaralari_oku(["onayla", "hepsi"])


def test_ters_aralik_hata():
    with pytest.raises(ValueError, match="tersten"):
        numaralari_oku(["onayla", "9-2"])


def test_bozuk_aralik_hata():
    with pytest.raises(ValueError, match="aralik degil"):
        numaralari_oku(["onayla", "1-a"])


def test_HEPSI_DIYE_BIR_SEY_YOK():
    """
    Tasarim karari: "onayla hepsi" gibi bir kisayol YOK. Neyi onayladigini
    her zaman numarayla soylemen gerekiyor. Listeye bakmadan onaylamak,
    onay olmaz -- kuyrugun butun amaci bu.
    """
    for kelime in ["hepsi", "all", "*", "tumu"]:
        with pytest.raises(ValueError):
            numaralari_oku(["onayla", kelime])


# -- Terminal komutlari ------------------------------------------------------


@pytest.fixture
def terminal(tmp_path, monkeypatch):
    monkeypatch.setattr(approval, "WORKSPACE", tmp_path / "workspace")
    return approval.main


def test_komut_tohumla(terminal, capsys):
    assert terminal(["tohumla"]) == 0
    cikti = capsys.readouterr().out
    assert "onay kuyruguna kondu" in cikti
    assert "HENUZ ogrenilmedi" in cikti


def test_komut_tohumla_ikinci_kez(terminal, capsys):
    terminal(["tohumla"])
    capsys.readouterr()
    assert terminal(["tohumla"]) == 0
    assert "yeni kural yok" in capsys.readouterr().out


def test_komut_toplu_onay(terminal, capsys):
    terminal(["tohumla"])
    capsys.readouterr()

    assert terminal(["onayla", "1-3"]) == 0
    assert "Toplam 3 bilgi" in capsys.readouterr().out

    assert terminal(["hafiza"]) == 0
    assert "3 onaylanmis bilgi" in capsys.readouterr().out


def test_komut_toplu_red(terminal, capsys):
    terminal(["tohumla"])
    capsys.readouterr()
    assert terminal(["reddet", "1-3"]) == 0
    assert capsys.readouterr().out.count("GIRMEDI") == 3
    terminal(["hafiza"])
    assert "Hafiza bos" in capsys.readouterr().out


def test_komut_hepsi_yazarsan_reddedilir(terminal, capsys):
    terminal(["tohumla"])
    capsys.readouterr()
    assert terminal(["onayla", "hepsi"]) == 1
    assert "numara degil" in capsys.readouterr().out


def test_yardim_hepsi_olmadigini_soyler(terminal, capsys):
    terminal([])
    assert "onayla hepsi" in capsys.readouterr().out
