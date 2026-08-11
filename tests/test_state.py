"""
tests/test_state.py -- Durum vektoru testleri

Her test tek bir sey dogrular ve adi ne dogruladigini soyler.
Calistirmak icin:  pytest tests/test_state.py -v
"""

import json

import pytest

from models.state import (
    Durum,
    SEMA_SURUMU,
    kaydet,
    yukle,
    yukle_veya_varsayilan,
)


# -- Sema ve alanlar ---------------------------------------------------------


def test_alanlar_tam_olarak_bunlar():
    """CLAUDE.md'de yazan alti alan, ne eksik ne fazla."""
    assert Durum.alan_adlari() == [
        "aclik",
        "yorgunluk",
        "temizlik",
        "yalnizlik",
        "korku",
        "guven",
    ]


def test_varsayilan_durum_gecerli():
    assert Durum().gecerli_mi()
    assert Durum().hatalari_bul() == []


def test_tum_alanlar_tam_sayi():
    d = Durum()
    for ad in Durum.alan_adlari():
        assert isinstance(getattr(d, ad), int)


# -- Dogrulama ---------------------------------------------------------------


@pytest.mark.parametrize("gecersiz", [-1, 101, 1000, -50])
def test_aralik_disi_deger_reddedilir(gecersiz):
    d = Durum(aclik=gecersiz)
    assert not d.gecerli_mi()
    with pytest.raises(ValueError):
        d.dogrula_veya_hata()


def test_hata_mesaji_hangi_alan_oldugunu_soyler():
    """Hata mesaji anlasilir olmali; 'ValueError' demek yetmez."""
    d = Durum(korku=150)
    hatalar = d.hatalari_bul()
    assert len(hatalar) == 1
    assert "korku" in hatalar[0]
    assert "150" in hatalar[0]


def test_birden_fazla_hata_hepsi_raporlanir():
    d = Durum(aclik=-5, guven=200)
    assert len(d.hatalari_bul()) == 2


@pytest.mark.parametrize("gecersiz", ["50", 50.5, None, True])
def test_tam_sayi_olmayan_deger_reddedilir(gecersiz):
    """Metin, ondalik, None ve bool kabul edilmez. True/False durum degeri degildir."""
    assert not Durum(yorgunluk=gecersiz).gecerli_mi()


def test_sinir_degerleri_gecerli():
    assert Durum(aclik=0, guven=100).gecerli_mi()


# -- Sozluge cevirme ---------------------------------------------------------


def test_sozluk_gidis_donus():
    d = Durum(aclik=42, korku=7)
    assert Durum.sozlukten_olustur(d.sozluge_cevir()) == d


def test_bilinmeyen_alan_reddedilir():
    with pytest.raises(ValueError, match="Bilinmeyen alan"):
        Durum.sozlukten_olustur({"aclik": 10, "mutluluk": 90})


def test_eksik_alan_varsayilani_alir():
    d = Durum.sozlukten_olustur({"aclik": 10})
    assert d.aclik == 10
    assert d.guven == Durum().guven


def test_sozluk_yerine_liste_verilirse_hata():
    with pytest.raises(TypeError):
        Durum.sozlukten_olustur([1, 2, 3])


# -- Degistirme --------------------------------------------------------------


def test_degistir_goreceli_calisir():
    d = Durum(aclik=50).degistir(aclik=+10)
    assert d.aclik == 60


def test_degistir_ust_sinirda_kirpar():
    assert Durum(aclik=95).degistir(aclik=+20).aclik == 100


def test_degistir_alt_sinirda_kirpar():
    assert Durum(aclik=5).degistir(aclik=-20).aclik == 0


def test_degistir_orijinali_bozmaz():
    """Yeni nesne doner, eskisi elde kalir. Geri almak icin onemli."""
    d = Durum(aclik=50)
    d.degistir(aclik=+30)
    assert d.aclik == 50


def test_degistir_bilinmeyen_alan_hata_verir():
    with pytest.raises(ValueError, match="Bilinmeyen alan"):
        Durum().degistir(mutluluk=+10)


def test_ayarla_mutlak_deger_koyar():
    assert Durum(aclik=90).ayarla(aclik=0).aclik == 0


def test_ayarla_aralik_disini_reddeder():
    """ayarla kirpmaz, hata verir; cunku 250 yazmak genelde yazim hatasidir."""
    with pytest.raises(ValueError):
        Durum().ayarla(aclik=250)


def test_ozet_tum_alanlari_icerir():
    ozet = Durum().ozet()
    for ad in Durum.alan_adlari():
        assert ad in ozet


# -- Diske yazma / okuma -----------------------------------------------------


def test_kaydet_yukle_gidis_donus(tmp_path):
    yol = tmp_path / "state.json"
    d = Durum(aclik=33, yorgunluk=44, temizlik=55, yalnizlik=66, korku=7, guven=88)
    kaydet(d, yol)
    assert yukle(yol) == d


def test_kaydedilen_dosya_okunabilir_json(tmp_path):
    yol = tmp_path / "state.json"
    kaydet(Durum(aclik=11), yol)
    veri = json.loads(yol.read_text(encoding="utf-8"))
    assert veri["aclik"] == 11
    assert veri["_sema_surumu"] == SEMA_SURUMU


def test_gecersiz_durum_diske_yazilmaz(tmp_path):
    """En onemli kaydetme testi: bozuk veri hicbir zaman diske gitmez."""
    yol = tmp_path / "state.json"
    with pytest.raises(ValueError):
        kaydet(Durum(aclik=999), yol)
    assert not yol.exists()


def test_kaydetme_gecici_dosya_birakmaz(tmp_path):
    yol = tmp_path / "state.json"
    kaydet(Durum(), yol)
    assert list(tmp_path.glob("*.tmp")) == []


def test_olmayan_klasor_olusturulur(tmp_path):
    yol = tmp_path / "yeni" / "alt" / "state.json"
    kaydet(Durum(), yol)
    assert yol.exists()


def test_olmayan_dosya_acik_hata_verir(tmp_path):
    with pytest.raises(FileNotFoundError):
        yukle(tmp_path / "yok.json")


def test_bozuk_json_acik_hata_verir(tmp_path):
    yol = tmp_path / "state.json"
    yol.write_text("{bu json degil", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        yukle(yol)


def test_gelecekten_gelen_sema_surumu_reddedilir(tmp_path):
    """Yeni surumle yazilmis dosyayi eski kod sessizce yanlis okumasin."""
    yol = tmp_path / "state.json"
    yol.write_text(json.dumps({"_sema_surumu": 99, "aclik": 10}), encoding="utf-8")
    with pytest.raises(ValueError, match="sema surumu"):
        yukle(yol)


def test_diskteki_aralik_disi_deger_reddedilir(tmp_path):
    """Dosya elle bozulmus olabilir; okurken de dogrulariz."""
    yol = tmp_path / "state.json"
    yol.write_text(json.dumps({"aclik": 500}), encoding="utf-8")
    with pytest.raises(ValueError):
        yukle(yol)


def test_yukle_veya_varsayilan_dosya_yoksa_patlamaz(tmp_path):
    assert yukle_veya_varsayilan(tmp_path / "yok.json") == Durum()


def test_state_hicbir_projeye_bagimli_degil():
    """
    Bu dosya oyunda ve robotta da kullanilacak; bu yuzden proje ici
    hicbir modulu ice aktarmamali. (Sadece Python'un kendi kutuphaneleri.)
    """
    import models.state as m

    kaynak = open(m.__file__, encoding="utf-8").read()
    for yasak in ["from core", "import core", "from evals", "import evals"]:
        assert yasak not in kaynak
