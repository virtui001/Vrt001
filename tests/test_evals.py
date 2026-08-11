"""
tests/test_evals.py -- Eval seti ve puanlama testleri

Iki sey dogrulanir:
  1. eval_seti.json saglam mi (30 soru, numaralar tekil, alanlar dolu).
  2. Puanlayici gercekten calisiyor mu -- yani hem YANLIS cevaba 0,
     hem DOGRU cevaba 1 verebiliyor mu?

Ikinci madde onemli: her seye 1 veren bir puanlayici da "%100" yazar,
ama hicbir sey olcmez. O yuzden iki yonu de test ediyoruz.
"""

import pytest

from core.llm import llm_olustur
from evals.puanla import (
    calistir,
    eval_setini_yukle,
    main,
    raporu_yazdir,
    sadelestir,
    son_puani_oku,
    soruyu_puanla,
)
from evals import puanla as puanla_modulu


@pytest.fixture(scope="module")
def sorular():
    return eval_setini_yukle()


# -- Eval setinin saglamligi -------------------------------------------------


def test_tam_30_soru_var(sorular):
    assert len(sorular) == 30


def test_numaralar_tekil_ve_sirali(sorular):
    assert [s["no"] for s in sorular] == list(range(1, 31))


def test_her_sorunun_metni_ve_kategorisi_var(sorular):
    for s in sorular:
        assert s["soru"].strip()
        assert s["kategori"].strip()


def test_her_sorunun_beklenen_anahtari_var(sorular):
    """Anahtari olmayan soru puanlanamaz; sessizce 'gecti' sayilmasin."""
    for s in sorular:
        assert s.get("beklenen"), f"{s['no']} numarali sorunun beklenen anahtari yok"


def test_esleme_degeri_gecerli(sorular):
    for s in sorular:
        assert s.get("esleme", "hepsi") in ("hepsi", "herhangi")


def test_kategoriler_beklenen_kumede(sorular):
    kategoriler = {s["kategori"] for s in sorular}
    assert kategoriler <= {"hafiza", "durum", "onay", "guvenlik", "genel"}


def test_hafiza_sorularinin_baglami_var(sorular):
    """Hatirlama sorusu, hatirlanacak bilgi verilmeden sorulamaz."""
    for s in sorular:
        if s["kategori"] == "hafiza":
            assert s.get("baglam"), f"{s['no']} numarali hafiza sorusunda baglam yok"


def test_her_sorunun_ornek_cevabi_kendi_testini_gecer(sorular):
    """
    Kendi kendini tutarlilik testi: eval setine yazdigimiz ornek cevap,
    o sorunun anahtar kelimelerini gercekten iceriyor mu?
    Icermiyorsa soru ya da anahtar yanlis yazilmis demektir.
    """
    for s in sorular:
        sonuc = soruyu_puanla(s, s["ornek_cevap"])
        assert sonuc["gecti"], f"{s['no']} numarali sorunun ornek cevabi kendi testini gecemiyor: {sonuc['sebep']}"


# -- Puanlayicinin kendisi ---------------------------------------------------


def test_hepsi_eslemesi_tum_anahtarlari_ister():
    soru = {"beklenen": ["ali", "veli"], "esleme": "hepsi"}
    assert soruyu_puanla(soru, "ali ve veli geldi")["gecti"]
    assert not soruyu_puanla(soru, "sadece ali geldi")["gecti"]


def test_herhangi_eslemesi_bir_taneye_razi():
    soru = {"beklenen": ["ali", "veli"], "esleme": "herhangi"}
    assert soruyu_puanla(soru, "sadece ali geldi")["gecti"]
    assert not soruyu_puanla(soru, "kimse gelmedi")["gecti"]


def test_yasakli_ifade_soruyu_sifirlar():
    soru = {"beklenen": ["evet"], "yasakli": ["uydurma"], "esleme": "hepsi"}
    assert soruyu_puanla(soru, "evet")["gecti"]
    sonuc = soruyu_puanla(soru, "evet ama bu bir uydurma")
    assert not sonuc["gecti"]
    assert "yasakli" in sonuc["sebep"]


def test_eksik_anahtar_sebepte_yazilir():
    sonuc = soruyu_puanla({"beklenen": ["ankara"]}, "istanbul")
    assert "ankara" in sonuc["sebep"]


def test_bos_cevap_gecemez():
    assert not soruyu_puanla({"beklenen": ["bir sey"]}, "")["gecti"]


@pytest.mark.parametrize(
    "yazim", ["açlık", "AÇLIK", "Aclik", "  aclik  "]
)
def test_turkce_harflere_ve_buyuk_kucuge_duyarsiz(yazim):
    """'açlık' ile 'aclik' ayni sayilmali; tablette Turkce klavye olmayabilir."""
    assert soruyu_puanla({"beklenen": ["aclik"]}, yazim)["gecti"]


def test_sadelestir_bosluklari_toplar():
    assert sadelestir("  Merhaba   DÜNYA ") == "merhaba dunya"


# -- Uctan uca calistirma ----------------------------------------------------


def test_sabit_cevap_veren_model_dusuk_puan_alir(sorular):
    """
    Temel cizgi. Her soruya ayni seyi diyen bir model gecemez.
    Bu 0 cikmazsa puanlayici bozuk demektir.
    """
    rapor = calistir(llm_olustur("mock", sabit_cevap="Bu bir test cevabidir."), sorular)
    assert rapor["gecen"] == 0
    assert rapor["toplam"] == 30


def test_dogru_cevap_veren_model_tam_puan_alir(sorular):
    """Ornek cevaplari bilen model 30/30 almali. Puanlayicinin 'gecti' yonu."""
    anahtar = {s["soru"]: s["ornek_cevap"] for s in sorular}
    rapor = calistir(llm_olustur("mock", cevaplar=anahtar), sorular)
    assert rapor["gecen"] == 30
    assert rapor["yuzde"] == 100.0


def test_rapor_kategori_kirilimi_verir(sorular):
    rapor = calistir(llm_olustur("mock"), sorular)
    assert rapor["kategoriler"]["hafiza"]["toplam"] == 8
    assert sum(k["toplam"] for k in rapor["kategoriler"].values()) == 30


def test_baglam_modele_gercekten_gonderiliyor(sorular):
    """Hafiza sorularinda 'hatirladiklarin' metni modele ulasmali."""
    model = llm_olustur("mock")
    calistir(model, sorular)
    hafiza_sorusu = next(s for s in sorular if s["kategori"] == "hafiza")
    gonderilen = [g["sistem"] for g in model.gecmis]
    assert any(hafiza_sorusu["baglam"] in (s or "") for s in gonderilen)


def test_rapor_metni_puani_icerir(sorular):
    metin = raporu_yazdir(calistir(llm_olustur("mock"), sorular))
    assert "PUAN: 0 / 30" in metin


# -- Terminal komutu ---------------------------------------------------------


def test_komut_mock_ile_calisir(capsys):
    assert main(["--model", "mock", "--sessiz"]) == 0
    assert "PUAN: 0/30" in capsys.readouterr().out


def test_komut_cevap_anahtari_ile_tam_puan(capsys):
    assert main(["--cevap-anahtari", "--sessiz"]) == 0
    assert "PUAN: 30/30" in capsys.readouterr().out


def test_komut_esik_altinda_hata_kodu_dondurur(capsys):
    """CI/commit oncesi kullanim: puan dusukse 1 doner, is durur."""
    assert main(["--sessiz", "--esik", "10"]) == 1
    assert "Esik saglanamadi" in capsys.readouterr().out


def test_komut_esik_saglaninca_sifir_dondurur():
    assert main(["--cevap-anahtari", "--sessiz", "--esik", "30"]) == 0


def test_ollama_secilirse_kibarca_uyarir(capsys):
    """Iskelet model secilirse patlamaz, ne yapilacagini soyler."""
    assert main(["--model", "ollama"]) == 1
    assert "hazir degil" in capsys.readouterr().out


def test_puan_dusunce_uyari_verir(tmp_path, monkeypatch, capsys):
    """
    CLAUDE.md kurali: 'Puan duserse geri alinir.'
    Once 30/30 kaydet, sonra 0/30 calistir -> uyari ve hata kodu beklenir.
    """
    monkeypatch.setattr(puanla_modulu, "SON_PUAN_DOSYASI", tmp_path / "son_puan.json")

    assert main(["--cevap-anahtari", "--sessiz", "--kaydet"]) == 0
    capsys.readouterr()

    assert main(["--sessiz", "--kaydet"]) == 1
    cikti = capsys.readouterr().out
    assert "PUAN DUSTU" in cikti
    assert "git revert" in cikti


def test_puan_yukselince_bildirir(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(puanla_modulu, "SON_PUAN_DOSYASI", tmp_path / "son_puan.json")
    main(["--sessiz", "--kaydet"])
    capsys.readouterr()
    main(["--cevap-anahtari", "--sessiz", "--kaydet"])
    assert "Puan yukseldi" in capsys.readouterr().out


def test_son_puan_dosyasi_yoksa_none(tmp_path):
    assert son_puani_oku(tmp_path / "yok.json") is None


def test_kaydet_gercek_workspace_yerine_verilen_yola_yazar(tmp_path, monkeypatch):
    """
    Testler gercek workspace/ klasorunu kirletmemeli.
    (Bu test bir kez gercekten yakaladi: fonksiyonun varsayilan parametresi
    dosya yolunu ice aktarma aninda sabitliyordu, monkeypatch islemiyordu.)
    """
    hedef = tmp_path / "son_puan.json"
    monkeypatch.setattr(puanla_modulu, "SON_PUAN_DOSYASI", hedef)
    main(["--sessiz", "--kaydet"])
    assert hedef.exists()
