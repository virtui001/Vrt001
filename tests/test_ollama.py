"""
tests/test_ollama.py -- Ollama baglantisi testleri

SORUN: Ollama'ya baglanan kodu, elinde Ollama olmadan nasil test edersin?

COZUM: Ollama'nin yerine gecen kucuk bir SAHTE SUNUCU yaziyoruz. Ollama'nin
verdigi cevaplarin aynisini veriyor. Kodumuz farki anlamiyor -- onun icin
karsi tarafta gercek bir yapay zeka mi var yoksa 30 satirlik bir taklit mi,
belli degil. Zaten olayin guzelligi de bu.

NEYI TEST EDIYOR, NEYI ETMIYOR?
  Ediyor : dogru adrese, dogru bicimde istek gidiyor mu; gelen cevap dogru
           okunuyor mu; sunucu hata verince anlasilir Turkce mesaj cikiyor mu.
  ETMIYOR: gercek modelin cevaplarinin kalitesi. Onu ancak bilgisayarda,
           gercek modelle olcebiliriz (python -m evals.puanla --model ollama).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from core.llm import OllamaLLM
from core.memory import KULLANICI, Hafiza, OllamaGomucu
from core.ollama_baglanti import OllamaHatasi, model_var_mi, modeller


class SahteOllama(BaseHTTPRequestHandler):
    """
    Ollama'nin cevap seklini taklit eden istek karsilayici.
    Sinif degiskenleriyle davranisini test icinde degistirebiliyoruz.
    """

    kurulu_modeller = ["llama3.1:8b", "nomic-embed-text:latest"]
    cevap_metni = "Merhaba, ben sahte modelim."
    gomme = [3.0, 4.0]  # uzunlugu 5; normalize edilince [0.6, 0.8] olmali
    hata_kodu = None  # sayi verilirse o HTTP hatasini doner
    bozuk_cevap = False
    # Bu Ollama hangi gomme adreslerini tanisin? Surume gore degisiyor.
    destekli_gomme = ("embed", "embeddings")
    gelen_istekler: list = []

    def log_message(self, *_):
        pass  # test ciktisini kirletmesin

    def _yaz(self, veri: dict, kod: int = 200):
        govde = json.dumps(veri).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)

    def do_GET(self):
        if self.path == "/api/tags":
            self._wraz_tags()
        else:
            self._yaz({"error": "yok"}, 404)

    def _wraz_tags(self):
        self._yaz({"models": [{"name": ad} for ad in type(self).kurulu_modeller]})

    def do_POST(self):
        uzunluk = int(self.headers.get("Content-Length", 0))
        govde = json.loads(self.rfile.read(uzunluk) or b"{}")
        type(self).gelen_istekler.append({"yol": self.path, "govde": govde})

        if type(self).hata_kodu:
            self._yaz({"error": "olmadi"}, type(self).hata_kodu)
            return

        if type(self).bozuk_cevap:
            self._yaz({})
            return

        if self.path == "/api/chat":
            self._yaz(
                {
                    "model": govde.get("model"),
                    "message": {"role": "assistant", "content": type(self).cevap_metni},
                    "eval_count": 42,
                }
            )
        elif self.path == "/api/embed":
            # Yeni Ollama surumu. 'destekli_gomme' ile kapatilabiliyor ki
            # eski surumu de taklit edebilelim.
            if "embed" in type(self).destekli_gomme:
                self._yaz({"embeddings": [list(type(self).gomme)]})
            else:
                self._yaz({"error": "yok"}, 404)
        elif self.path == "/api/embeddings":
            # Eski Ollama surumu.
            if "embeddings" in type(self).destekli_gomme:
                self._yaz({"embedding": list(type(self).gomme)})
            else:
                self._yaz({"error": "yok"}, 404)
        else:
            self._yaz({"error": "bilinmeyen yol"}, 404)


@pytest.fixture
def sunucu():
    """
    Sahte Ollama'yi bos bir kapida baslatir, test bitince kapatir.
    Adresini (http://127.0.0.1:PORT) dondurur.
    """
    SahteOllama.kurulu_modeller = ["llama3.1:8b", "nomic-embed-text:latest"]
    SahteOllama.cevap_metni = "Merhaba, ben sahte modelim."
    SahteOllama.gomme = [3.0, 4.0]
    SahteOllama.hata_kodu = None
    SahteOllama.bozuk_cevap = False
    SahteOllama.destekli_gomme = ("embed", "embeddings")
    SahteOllama.gelen_istekler = []

    servis = HTTPServer(("127.0.0.1", 0), SahteOllama)
    # poll_interval kucuk: shutdown() varsayilan 0.5 saniye bekliyor ve bu
    # test dosyasini tek basina 10 saniyeye cikariyordu.
    iplik = threading.Thread(
        target=lambda: servis.serve_forever(poll_interval=0.01), daemon=True
    )
    iplik.start()
    yield f"http://127.0.0.1:{servis.server_port}"
    servis.shutdown()
    servis.server_close()


# -- Baglantinin temeli ------------------------------------------------------


def test_kurulu_modeller_okunur(sunucu):
    assert "llama3.1:8b" in modeller(sunucu)


def test_model_var_mi(sunucu):
    assert model_var_mi("llama3.1:8b", sunucu)
    assert not model_var_mi("boyle-bir-model-yok", sunucu)


def test_model_adi_etiketsiz_de_bulunur(sunucu):
    """'nomic-embed-text' yazinca 'nomic-embed-text:latest' bulunmali."""
    assert model_var_mi("nomic-embed-text", sunucu)


def test_sunucu_kapaliyken_model_var_mi_false():
    """Hata firlatmamali: bu fonksiyon 'hazir misin' sorusunu cevapliyor."""
    assert model_var_mi("llama3.1:8b", "http://127.0.0.1:1", zaman_asimi_sn=1) is False


# -- Sohbet ------------------------------------------------------------------


def test_cevap_alinir(sunucu):
    cevap = OllamaLLM(sunucu=sunucu).cevapla("Merhaba")
    assert cevap.metin == "Merhaba, ben sahte modelim."
    assert cevap.model_adi == "llama3.1:8b"


def test_sistem_metni_gonderilir(sunucu):
    """Baglam (onaylanmis bilgiler, hatirlananlar, durum) modele ulasmali."""
    OllamaLLM(sunucu=sunucu).cevapla("soru", sistem="Kedinin adi Pamuk")
    mesajlar = SahteOllama.gelen_istekler[-1]["govde"]["messages"]
    assert mesajlar[0] == {"role": "system", "content": "Kedinin adi Pamuk"}
    assert mesajlar[1] == {"role": "user", "content": "soru"}


def test_sistem_metni_yoksa_gonderilmez(sunucu):
    OllamaLLM(sunucu=sunucu).cevapla("soru")
    mesajlar = SahteOllama.gelen_istekler[-1]["govde"]["messages"]
    assert len(mesajlar) == 1
    assert mesajlar[0]["role"] == "user"


def test_sohbet_gecmisi_dogru_rollerle_gonderilir(sunucu):
    """
    Bizim "cekirdek" dedigimize Ollama "assistant" diyor. Yanlis
    eslestirirsek model kendi sozlerini kullanicinin sozu saniyor.
    """
    OllamaLLM(sunucu=sunucu).cevapla(
        "son soru",
        sistem="kural",
        gecmis=[
            {"rol": "kullanici", "metin": "eski soru"},
            {"rol": "cekirdek", "metin": "eski cevap"},
        ],
    )
    mesajlar = SahteOllama.gelen_istekler[-1]["govde"]["messages"]
    assert [m["role"] for m in mesajlar] == ["system", "user", "assistant", "user"]
    assert mesajlar[1]["content"] == "eski soru"
    assert mesajlar[2]["content"] == "eski cevap"
    assert mesajlar[3]["content"] == "son soru"


def test_bos_gecmis_mesaji_atlanir(sunucu):
    OllamaLLM(sunucu=sunucu).cevapla(
        "soru", gecmis=[{"rol": "kullanici", "metin": "   "}]
    )
    mesajlar = SahteOllama.gelen_istekler[-1]["govde"]["messages"]
    assert len(mesajlar) == 1


def test_akis_kapali_isteniyor(sunucu):
    """stream=False: cevabi harf harf degil, tek seferde aliyoruz."""
    OllamaLLM(sunucu=sunucu).cevapla("soru")
    assert SahteOllama.gelen_istekler[-1]["govde"]["stream"] is False


def test_sicaklik_iletilir(sunucu):
    OllamaLLM(sunucu=sunucu, sicaklik=0.2).cevapla("soru")
    secenekler = SahteOllama.gelen_istekler[-1]["govde"]["options"]
    assert secenekler["temperature"] == 0.2


def test_cevap_uzunlugu_sinirli(sunucu):
    """
    Sinirsiz birakinca kucuk modeller sayfalarca yazip arayuzu asili
    gosterebiliyor. Ust sinir konuldu.
    """
    OllamaLLM(sunucu=sunucu).cevapla("soru")
    secenekler = SahteOllama.gelen_istekler[-1]["govde"]["options"]
    assert secenekler["num_predict"] == 400


def test_olcum_bilgisi_dolar(sunucu):
    """Hiz olcumu bugunden aliskanlik: 'olcmeden ust kademeye cikilmaz'."""
    cevap = OllamaLLM(sunucu=sunucu).cevapla("soru")
    assert cevap.ek_bilgi["uretilen_parca"] == 42
    assert cevap.ek_bilgi["parca_hiz"] > 0
    assert cevap.sure_sn >= 0


def test_hazir_mi_dogru(sunucu):
    assert OllamaLLM(sunucu=sunucu).hazir_mi() is True
    assert OllamaLLM(model="olmayan-model", sunucu=sunucu).hazir_mi() is False


def test_bos_cevap_hata_verir(sunucu):
    SahteOllama.bozuk_cevap = True
    with pytest.raises(OllamaHatasi, match="bos cevap"):
        OllamaLLM(sunucu=sunucu).cevapla("soru")


def test_model_indirilmemisse_ne_yapilacagini_soyler(sunucu):
    SahteOllama.hata_kodu = 404
    with pytest.raises(OllamaHatasi, match="ollama pull"):
        OllamaLLM(sunucu=sunucu).cevapla("soru")


def test_sunucu_hatasi_kodu_gosterir(sunucu):
    SahteOllama.hata_kodu = 500
    with pytest.raises(OllamaHatasi, match="500"):
        OllamaLLM(sunucu=sunucu).cevapla("soru")


# -- Gomme -------------------------------------------------------------------


def test_gomme_alinir_ve_normalize_edilir(sunucu):
    """[3, 4] uzunlugu 5 olan bir vektor; normalize edilince [0.6, 0.8] olmali."""
    vektor = OllamaGomucu(sunucu=sunucu).gom("merhaba")
    assert vektor == pytest.approx([0.6, 0.8])


def test_gomme_boyutu_sunucudan_ogrenilir(sunucu):
    g = OllamaGomucu(sunucu=sunucu)
    assert g.boyut == 0  # daha sormadik
    g.gom("merhaba")
    assert g.boyut == 2  # ilk istekten sonra biliyor


def test_gomme_boyu_degisirse_hata(sunucu):
    """Model degisirse eski kayitlarla uyusmaz; sessizce devam etmek yerine durur."""
    g = OllamaGomucu(sunucu=sunucu)
    g.gom("birinci")
    SahteOllama.gomme = [1.0, 2.0, 3.0]
    with pytest.raises(OllamaHatasi, match="Vektor boyu degisti"):
        g.gom("ikinci")


def test_gomme_modeli_dogru_adrese_gider(sunucu):
    OllamaGomucu(model="nomic-embed-text", sunucu=sunucu).gom("merhaba")
    son = SahteOllama.gelen_istekler[-1]
    assert son["yol"] == "/api/embed"
    assert son["govde"]["model"] == "nomic-embed-text"
    assert son["govde"]["input"] == "merhaba"


def test_YENI_ollama_surumu_calisir(sunucu):
    """Sadece /api/embed tanıyan surum (yeni)."""
    SahteOllama.destekli_gomme = ("embed",)
    SahteOllama.gomme = [3.0, 4.0]
    assert OllamaGomucu(sunucu=sunucu).gom("merhaba") == pytest.approx([0.6, 0.8])


def test_ESKI_ollama_surumu_calisir(sunucu):
    """
    Sadece /api/embeddings tanıyan surum (eski). Kod once yeni adresi dener,
    404 alinca eskisine duser -- kullaniciya "once surumunu kontrol et"
    dedirtmeden.
    """
    SahteOllama.destekli_gomme = ("embeddings",)
    SahteOllama.gomme = [3.0, 4.0]
    assert OllamaGomucu(sunucu=sunucu).gom("merhaba") == pytest.approx([0.6, 0.8])


def test_calisan_adres_hatirlanir(sunucu):
    """Her seferinde iki istek atmayalim: bulunan adres akilda kalmali."""
    SahteOllama.destekli_gomme = ("embeddings",)
    g = OllamaGomucu(sunucu=sunucu)
    g.gom("birinci")
    sayi_once = len(SahteOllama.gelen_istekler)
    g.gom("ikinci")
    # Ikinci cagride sadece 1 istek atilmali (yeni adres tekrar denenmemeli)
    assert len(SahteOllama.gelen_istekler) - sayi_once == 1


def test_hicbir_gomme_adresi_yoksa_acik_hata(sunucu):
    SahteOllama.destekli_gomme = ()
    with pytest.raises(OllamaHatasi):
        OllamaGomucu(sunucu=sunucu).gom("merhaba")


def test_gomucu_hazir_mi(sunucu):
    assert OllamaGomucu(sunucu=sunucu).hazir_mi() is True
    assert OllamaGomucu(model="yok", sunucu=sunucu).hazir_mi() is False


# -- Uctan uca: hafiza gercek gomucuyle calisir -------------------------------


def test_hafiza_ollama_gomucusuyle_calisir(sunucu, tmp_path):
    """
    ASIL SINAV: hafiza kodu degismeden gercek gomucuyle calismali.
    Bu gecerse, bilgisayarda gomucuyu degistirmek tek satirlik is demektir.
    """
    SahteOllama.gomme = [1.0, 0.0, 0.0]
    h = Hafiza(
        klasor=tmp_path, izinli_kok=tmp_path, gomucu=OllamaGomucu(sunucu=sunucu)
    )
    mesaj = h.ekle(KULLANICI, "Kedimin adi Pamuk")

    assert mesaj.gomucu == "ollama"
    assert mesaj.boyut == 3  # ilk mesajda bile dogru yazilmali
    assert h.hatirla("kedi")  # ayni vektor donduguu icin eslesmeli


def test_eval_secilen_modelle_calisir(sunucu, capsys):
    """
    Modelleri kiyaslamak icin: --ollama-model ile secilen model gercekten
    kullanilmali. (Bu secenek olmadan model degistirmek kod duzenlemek
    gerektiriyordu; kurulum belgesini yazarken fark ettik.)
    """
    from evals.puanla import main as eval_main

    SahteOllama.kurulu_modeller = ["qwen2.5:7b"]
    eval_main(
        ["--model", "ollama", "--ollama-model", "qwen2.5:7b",
         "--sunucu", sunucu, "--sessiz"]
    )
    capsys.readouterr()
    assert SahteOllama.gelen_istekler[-1]["govde"]["model"] == "qwen2.5:7b"


def test_terminal_secilen_modelle_calisir(sunucu, tmp_path, monkeypatch):
    import cekirdek as uygulama

    SahteOllama.kurulu_modeller = ["gemma2:9b"]
    monkeypatch.setattr(uygulama, "WORKSPACE", tmp_path)
    satirlar = iter(["merhaba", "/cik"])
    uygulama.main(
        ["--model", "ollama", "--ollama-model", "gemma2:9b", "--sunucu", sunucu],
        girdi=lambda _="": next(satirlar),
        yazdir=lambda *a: None,
    )
    assert SahteOllama.gelen_istekler[-1]["govde"]["model"] == "gemma2:9b"


def test_terminal_uctan_uca_ollama_ile_calisir(sunucu, tmp_path, monkeypatch):
    """
    En genis sinav: terminal arayuzu, gercek model yolundan gecerek
    cevap veriyor mu? (Karsi tarafta sahte sunucu var ama kod bunu bilmiyor.)
    """
    import cekirdek as uygulama

    SahteOllama.cevap_metni = "Kedinin adi Pamuk."
    SahteOllama.gomme = [1.0, 0.0]
    monkeypatch.setattr(uygulama, "WORKSPACE", tmp_path)

    satirlar = iter(["kedimin adi neydi", "/cik"])
    cikti: list[str] = []
    kod = uygulama.main(
        ["--model", "ollama", "--sunucu", sunucu],
        girdi=lambda _="": next(satirlar),
        yazdir=lambda *a: cikti.append(" ".join(str(x) for x in a)),
    )

    assert kod == 0
    assert "Kedinin adi Pamuk." in "\n".join(cikti)


def test_gomme_modeli_yoksa_basit_gomucuye_duser(sunucu, tmp_path, monkeypatch):
    """
    Sohbet modeli var ama gomme modeli indirilmemis. Program patlamamali;
    kelime benzerligiyle devam etmeli -- ama bunu SESSIZCE degil, soyleyerek.
    """
    import cekirdek as uygulama

    SahteOllama.kurulu_modeller = ["llama3.1:8b"]  # nomic-embed-text yok
    monkeypatch.setattr(uygulama, "WORKSPACE", tmp_path)

    satirlar = iter(["/cik"])
    cikti: list[str] = []
    kod = uygulama.main(
        ["--model", "ollama", "--sunucu", sunucu],
        girdi=lambda _="": next(satirlar),
        yazdir=lambda *a: cikti.append(" ".join(str(x) for x in a)),
    )

    assert kod == 0
    assert "ollama pull nomic-embed-text" in "\n".join(cikti)


def test_ollama_gommeleri_diske_yazilir_ve_geri_okunur(sunucu, tmp_path):
    SahteOllama.gomme = [0.0, 1.0, 0.0]
    h1 = Hafiza(klasor=tmp_path, izinli_kok=tmp_path, gomucu=OllamaGomucu(sunucu=sunucu))
    h1.ekle(KULLANICI, "Yarin Ankara ya gidecegim")

    h2 = Hafiza(klasor=tmp_path, izinli_kok=tmp_path, gomucu=OllamaGomucu(sunucu=sunucu))
    h2.gomucu.gom("ilk istek boyutu ogrensin")
    onceki_istek_sayisi = len(SahteOllama.gelen_istekler)
    h2.hatirla("ankara")

    # Diskteki vektor kullanilmali; mesaj basina yeniden gomme istegi ATILMAMALI.
    yeni_istekler = len(SahteOllama.gelen_istekler) - onceki_istek_sayisi
    assert yeni_istekler == 1  # sadece sorunun kendisi icin
