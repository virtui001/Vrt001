"""
tests/test_llm.py -- Model arayuzu testleri

Buradaki en onemli fikir: testler MockLLM'i degil, LLM SOZLESMESINI dogrular.
Yarin OllamaLLM'in ici doldugunda ayni testlerin cogu ona da uygulanabilir.
"""

import pytest

from core.llm import KAYITLI_MODELLER, LLM, Cevap, MockLLM, OllamaLLM, llm_olustur
from core.ollama_baglanti import OllamaHatasi

# Kesin kapali bir adres: 1 numarali kapiya kimse baglanamaz.
# Testlerin gercek Ollama'ya (11434) carpmasini istemiyoruz -- calisiyorsa
# testin sonucu bilgisayara gore degisirdi.
KAPALI_SUNUCU = "http://127.0.0.1:1"


# -- Arayuz (sozlesme) -------------------------------------------------------


def test_llm_dogrudan_uretilemez():
    """LLM soyut bir sinif; ondan nesne uretilemez, sadece miras alinir."""
    with pytest.raises(TypeError):
        LLM()


def test_cevapla_yazilmayan_sinif_uretilemez():
    """'cevapla' metodunu yazmayi unutan bir sinif kullanilamaz."""

    class EksikModel(LLM):
        pass

    with pytest.raises(TypeError):
        EksikModel()


@pytest.mark.parametrize("sinif", list(KAYITLI_MODELLER.values()))
def test_kayitli_modeller_arayuze_uyar(sinif):
    assert issubclass(sinif, LLM)
    assert hasattr(sinif, "cevapla")
    assert hasattr(sinif, "hazir_mi")


# -- MockLLM -----------------------------------------------------------------


def test_mock_sabit_cevap_dondurur():
    m = MockLLM(sabit_cevap="sabit")
    assert m.cevapla("herhangi bir soru").metin == "sabit"
    assert m.cevapla("bambaska bir soru").metin == "sabit"


def test_mock_kayitli_cevabi_dondurur():
    m = MockLLM(sabit_cevap="bilmiyorum", cevaplar={"2+2 kac eder": "4"})
    assert m.cevapla("2+2 kac eder").metin == "4"
    assert m.cevapla("baska sey").metin == "bilmiyorum"


def test_mock_buyuk_kucuk_harf_ve_bosluga_takilmaz():
    m = MockLLM(cevaplar={"Merhaba Dunya": "selam"})
    assert m.cevapla("  merhaba    DUNYA ").metin == "selam"


def test_mock_deterministik():
    """Ayni soru her zaman ayni cevap. Testin sarti budur."""
    m = MockLLM(cevaplar={"soru": "cevap"})
    assert {m.cevapla("soru").metin for _ in range(20)} == {"cevap"}


def test_mock_sorulanlari_kaydeder():
    """Testte 'modele ne gonderdik' diye bakabilelim diye."""
    m = MockLLM()
    m.cevapla("ilk", sistem="kural")
    m.cevapla("ikinci")
    assert len(m.gecmis) == 2
    assert m.gecmis[0] == {"istem": "ilk", "sistem": "kural"}
    assert m.gecmis[1]["sistem"] is None


def test_mock_hazir():
    assert MockLLM().hazir_mi() is True


def test_cevap_nesnesi_metne_cevrilebilir():
    assert str(Cevap(metin="merhaba")) == "merhaba"


def test_cevap_model_adini_tasir():
    assert MockLLM().cevapla("x").model_adi == "mock"


# -- OllamaLLM (iskelet) -----------------------------------------------------


def test_ollama_sunucu_yoksa_hazir_degil():
    """Ollama calismiyorsa durusu net: hazir degil. Sessizce yanlis cevap vermez."""
    assert OllamaLLM(sunucu=KAPALI_SUNUCU).hazir_mi() is False


def test_ollama_sunucu_yoksa_ne_yapilacagini_soyler():
    """
    Hata mesaji 'ConnectionRefusedError' degil, kontrol listesi olmali.
    Hata okumayi ogrenmek bu projenin bir parcasi; okunabilir olsun.
    """
    with pytest.raises(OllamaHatasi) as hata:
        OllamaLLM(sunucu=KAPALI_SUNUCU).cevapla("merhaba")
    mesaj = str(hata.value)
    assert "ulasilamadi" in mesaj
    assert "ollama serve" in mesaj


def test_ollama_ayarlari_saklar():
    """Arayuz bugunden sabit: model adi, sunucu, sicaklik burada duruyor."""
    o = OllamaLLM(model="qwen2.5:14b", sunucu="http://192.168.1.5:11434", sicaklik=0.2)
    assert o.model == "qwen2.5:14b"
    assert o.sunucu == "http://192.168.1.5:11434"
    assert o.sicaklik == 0.2


# -- Fabrika -----------------------------------------------------------------


def test_fabrika_varsayilan_mock_uretir():
    assert isinstance(llm_olustur(), MockLLM)


def test_fabrika_isme_gore_uretir():
    assert isinstance(llm_olustur("ollama"), OllamaLLM)
    assert isinstance(llm_olustur("MOCK"), MockLLM)  # buyuk harf de olur


def test_fabrika_ayarlari_iletir():
    m = llm_olustur("mock", sabit_cevap="ozel")
    assert m.cevapla("x").metin == "ozel"


def test_bilinmeyen_model_acik_hata_verir():
    with pytest.raises(ValueError, match="Bilinmeyen model"):
        llm_olustur("gpt-9000")


def test_cagiran_taraf_hangi_model_oldugunu_bilmek_zorunda_degil():
    """
    Asil test bu: asagidaki fonksiyon MockLLM'i de OllamaLLM'i de tanimaz,
    sadece 'cevapla' diyebilecegini bilir.
    """

    def soru_sor(model: LLM, soru: str) -> str:
        return model.cevapla(soru).metin

    assert soru_sor(llm_olustur("mock", sabit_cevap="tamam"), "n'aber") == "tamam"
