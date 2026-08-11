"""
tests/test_approval.py -- Onay kuyrugu testleri

Bu dosya projenin en kritik kuralini korur:
    ONAYLANMAYAN HICBIR SEY HAFIZAYA GIRMEZ.

Eger ileride biri bu kurali yanlislikla bozarsa, buradaki testler kirmizi yanar.
"""

import json

import pytest

from core import approval
from core.approval import BEKLIYOR, ONAYLANDI, REDDEDILDI, OnayKuyrugu


@pytest.fixture
def kuyruk(tmp_path):
    """Her test icin bos, gecici bir kuyruk. Testler birbirini etkilemez."""
    return OnayKuyrugu(klasor=tmp_path, izinli_kok=tmp_path)


# -- EN ONEMLI KURAL ---------------------------------------------------------


def test_eklemek_hafizaya_yazmaz(kuyruk):
    """Aday eklemek ogrenmek DEGILDIR."""
    kuyruk.ekle("Kullanicinin kedisinin adi Pamuk")
    assert kuyruk.hafiza() == []


def test_onaysiz_hicbir_sey_hafizaya_girmez(kuyruk):
    """Bes aday ekle, hicbirini onaylama: hafiza bos kalmali."""
    for i in range(5):
        kuyruk.ekle(f"bilgi {i}")
    assert len(kuyruk.bekleyenler()) == 5
    assert kuyruk.hafiza() == []


def test_sadece_onaylanan_hafizaya_girer(kuyruk):
    a = kuyruk.ekle("dogru bilgi")
    b = kuyruk.ekle("yanlis bilgi")
    kuyruk.onayla(a.no)
    kuyruk.reddet(b.no)

    hafiza = kuyruk.hafiza()
    assert len(hafiza) == 1
    assert hafiza[0]["metin"] == "dogru bilgi"


def test_reddedilen_hafizada_gorunmez(kuyruk):
    a = kuyruk.ekle("yanlis bilgi")
    kuyruk.reddet(a.no)
    metinler = [h["metin"] for h in kuyruk.hafiza()]
    assert "yanlis bilgi" not in metinler


def test_hafiza_dosyasi_onaysiz_hic_olusmaz(kuyruk):
    """Onay olmadan hafiza.json dosyasi diske hic yazilmaz."""
    kuyruk.ekle("bir sey")
    kuyruk.ekle("baska sey")
    assert not kuyruk.hafiza_dosyasi.exists()


# -- Ekleme ------------------------------------------------------------------


def test_ekle_bekleyen_durumda_aday_uretir(kuyruk):
    a = kuyruk.ekle("bilgi", kaynak="konusma")
    assert a.durum == BEKLIYOR
    assert a.kaynak == "konusma"
    assert a.olusturma  # zaman damgasi bos olmamali


def test_numaralar_1_den_baslar_ve_artar(kuyruk):
    assert [kuyruk.ekle(f"b{i}").no for i in range(3)] == [1, 2, 3]


def test_bos_metin_eklenemez(kuyruk):
    with pytest.raises(ValueError):
        kuyruk.ekle("   ")


def test_ayni_metin_iki_kez_kuyruga_girmez(kuyruk):
    a = kuyruk.ekle("Kedinin adi Pamuk")
    b = kuyruk.ekle("  kedinin ADI pamuk  ")
    assert a.no == b.no
    assert len(kuyruk.bekleyenler()) == 1


def test_zaten_onaylanmis_bilgi_tekrar_onaya_sunulmaz(kuyruk):
    a = kuyruk.ekle("Kedinin adi Pamuk")
    kuyruk.onayla(a.no)
    tekrar = kuyruk.ekle("Kedinin adi Pamuk")
    assert tekrar.durum == ONAYLANDI
    assert kuyruk.bekleyenler() == []


# -- Onaylama / reddetme -----------------------------------------------------


def test_onaylanan_kuyruktan_cikar(kuyruk):
    a = kuyruk.ekle("bilgi")
    kuyruk.onayla(a.no)
    assert kuyruk.bekleyenler() == []


def test_reddedilen_kuyruktan_cikar(kuyruk):
    a = kuyruk.ekle("bilgi")
    kuyruk.reddet(a.no)
    assert kuyruk.bekleyenler() == []


def test_ayni_adayi_iki_kez_onaylamak_hata_verir(kuyruk):
    a = kuyruk.ekle("bilgi")
    kuyruk.onayla(a.no)
    with pytest.raises(KeyError):
        kuyruk.onayla(a.no)
    assert len(kuyruk.hafiza()) == 1  # hafizaya iki kez girmedi


def test_olmayan_numara_acik_hata_verir(kuyruk):
    with pytest.raises(KeyError, match="99"):
        kuyruk.onayla(99)


def test_numaralar_onay_sonrasi_kaymaz(kuyruk):
    """
    'onayla 3' her zaman ayni seyi kastetmeli. Ortadaki aday onaylanınca
    kalanların numarası degismemeli, yoksa yanlislikla baskasi onaylanir.
    """
    kuyruk.ekle("bir")
    b = kuyruk.ekle("iki")
    kuyruk.ekle("uc")
    kuyruk.onayla(b.no)
    assert [a.no for a in kuyruk.bekleyenler()] == [1, 3]


def test_yeni_aday_eski_numarayi_geri_kullanmaz(kuyruk):
    a = kuyruk.ekle("bir")
    kuyruk.reddet(a.no)
    yeni = kuyruk.ekle("iki")
    assert yeni.no == 2


# -- Denetim kaydi -----------------------------------------------------------


def test_kararlar_gecmise_yazilir(kuyruk):
    a = kuyruk.ekle("dogru")
    b = kuyruk.ekle("yanlis")
    kuyruk.onayla(a.no)
    kuyruk.reddet(b.no, sebep="uydurma")

    gecmis = kuyruk.gecmis()
    assert [k["olay"] for k in gecmis] == [ONAYLANDI, REDDEDILDI]
    assert gecmis[1]["aday"]["not_"] == "uydurma"


def test_hafiza_kaydi_zaman_damgasi_tasir(kuyruk):
    a = kuyruk.ekle("bilgi")
    kayit = kuyruk.onayla(a.no)
    assert kayit["onay_zamani"]
    assert kayit["kaynak"] == "bilinmiyor"


# -- Kalicilik (dosyaya yazma) -----------------------------------------------


def test_kuyruk_program_kapanip_acilinca_kaybolmaz(tmp_path):
    k1 = OnayKuyrugu(klasor=tmp_path, izinli_kok=tmp_path)
    k1.ekle("hatirlanmali")

    k2 = OnayKuyrugu(klasor=tmp_path, izinli_kok=tmp_path)  # yeniden acildi
    assert [a.metin for a in k2.bekleyenler()] == ["hatirlanmali"]


def test_hafiza_program_kapanip_acilinca_kaybolmaz(tmp_path):
    k1 = OnayKuyrugu(klasor=tmp_path, izinli_kok=tmp_path)
    k1.onayla(k1.ekle("kalici bilgi").no)

    k2 = OnayKuyrugu(klasor=tmp_path, izinli_kok=tmp_path)
    assert [h["metin"] for h in k2.hafiza()] == ["kalici bilgi"]


def test_dosyalar_okunabilir_json(kuyruk):
    """Dosyalari elle acip okuyabilmeliyiz; kapali kutu olmamali."""
    kuyruk.ekle("bilgi")
    veri = json.loads(kuyruk.kuyruk_dosyasi.read_text(encoding="utf-8"))
    assert veri[0]["metin"] == "bilgi"


def test_bozuk_kuyruk_dosyasi_acik_hata_verir(kuyruk):
    kuyruk.kuyruk_dosyasi.write_text("{bozuk", encoding="utf-8")
    with pytest.raises(ValueError, match="bozuk|JSON"):
        kuyruk.bekleyenler()


def test_gecici_dosya_birakilmaz(kuyruk):
    kuyruk.onayla(kuyruk.ekle("bilgi").no)
    assert list(kuyruk.klasor.glob("*.tmp")) == []


# -- Guvenlik sinirini korur -------------------------------------------------


def test_workspace_disina_yazma_reddedilir(tmp_path):
    """CLAUDE.md guvenlik sinirir: sistem yalnizca workspace'e yazabilir."""
    izinli = tmp_path / "workspace"
    disari = tmp_path / "gizli"
    disari.mkdir()
    with pytest.raises(PermissionError, match="yalnizca"):
        OnayKuyrugu(klasor=disari, izinli_kok=izinli)


def test_ust_klasore_cikma_denemesi_reddedilir(tmp_path):
    izinli = tmp_path / "workspace"
    izinli.mkdir()
    with pytest.raises(PermissionError):
        OnayKuyrugu(klasor=izinli / ".." / ".." / "etc", izinli_kok=izinli)


def test_varsayilan_klasor_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(approval, "WORKSPACE", tmp_path / "workspace")
    k = OnayKuyrugu()
    assert k.klasor.name == "workspace"


# -- Terminal komutlari ------------------------------------------------------


@pytest.fixture
def terminal(tmp_path, monkeypatch):
    """main() fonksiyonunu gecici bir workspace ile calistiran yardimci."""
    monkeypatch.setattr(approval, "WORKSPACE", tmp_path / "workspace")
    return approval.main


def test_komut_ekle_ve_listele(terminal, capsys):
    assert terminal(["ekle", "Kedinin adi Pamuk"]) == 0
    assert terminal(["listele"]) == 0
    cikti = capsys.readouterr().out
    assert "Pamuk" in cikti
    assert "[  1]" in cikti


def test_komut_bos_kuyruk_mesaji(terminal, capsys):
    assert terminal(["listele"]) == 0
    assert "bekleyen bir sey yok" in capsys.readouterr().out


def test_komut_onayla(terminal, capsys):
    terminal(["ekle", "bilgi"])
    assert terminal(["onayla", "1"]) == 0
    assert "hafizaya alindi" in capsys.readouterr().out
    assert terminal(["hafiza"]) == 0
    assert "bilgi" in capsys.readouterr().out


def test_komut_reddet(terminal, capsys):
    terminal(["ekle", "bilgi"])
    assert terminal(["reddet", "1", "uydurma"]) == 0
    assert "GIRMEDI" in capsys.readouterr().out
    terminal(["hafiza"])
    assert "Hafiza bos" in capsys.readouterr().out


def test_komut_olmayan_numara_hata_kodu_dondurur(terminal, capsys):
    assert terminal(["onayla", "7"]) == 1
    assert "Hata:" in capsys.readouterr().out


def test_komut_numara_yerine_yazi_yazilirsa(terminal, capsys):
    assert terminal(["onayla", "pamuk"]) == 1
    assert "numara degil" in capsys.readouterr().out


def test_bilinmeyen_komut_yardim_gosterir(terminal, capsys):
    assert terminal(["zipzip"]) == 1
    assert "Bilinmeyen komut" in capsys.readouterr().out


def test_komutsuz_calistirinca_yardim(terminal, capsys):
    assert terminal([]) == 1
    assert "listele" in capsys.readouterr().out
