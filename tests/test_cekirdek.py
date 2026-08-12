"""
tests/test_cekirdek.py -- Terminal arayuzu testleri

Arayuzu klavye olmadan test ediyoruz: main() fonksiyonuna kendi girdi ve
yazdirma fonksiyonlarimizi veriyoruz. Boylece "kullanici sunu yazdi, ekranda
su cikti" senaryolarini otomatik dogrulayabiliyoruz.
"""

import pytest

import cekirdek as uygulama
from cekirdek import Cekirdek, aday_oner
from core.llm import llm_olustur
from models.state import Durum


@pytest.fixture
def c(tmp_path):
    """Gecici klasorde, sahte modelle calisan bir Cekirdek."""
    return Cekirdek(
        llm=llm_olustur("mock", sabit_cevap="anladim"),
        klasor=tmp_path,
        izinli_kok=tmp_path,
    )


# -- Aday onerme (ogrenme DEGIL) ---------------------------------------------


@pytest.mark.parametrize(
    "cumle",
    [
        "Benim kedimin adi Pamuk",
        "Her sabah cay iciyorum",
        "Dogum gunum 14 Mart",
        "Kedim cok tatli bir hayvan",
    ],
)
def test_bilgi_iceren_cumle_aday_olur(cumle):
    assert aday_oner(cumle) == cumle


@pytest.mark.parametrize(
    "cumle",
    [
        "Merhaba",
        "Bugun hava nasil olacak",
        "Benim adim ne?",       # soru: bilgi vermiyor, soruyor
        "ok",
    ],
)
def test_bilgi_icermeyen_cumle_aday_olmaz(cumle):
    assert aday_oner(cumle) is None


def test_aday_turkce_harfle_de_yakalanir():
    assert aday_oner("Benim adım Ali ve tasarımcıyım") is not None


# -- Sohbet akisi ------------------------------------------------------------


def test_konusma_iki_mesaj_kaydeder(c):
    """Hem senin mesajin hem cevabi gunluge yazilir."""
    c.konus("Merhaba")
    assert c.hafiza.sayi() == 2
    assert [m.rol for m in c.hafiza.tumu()] == ["kullanici", "cekirdek"]


def test_bilgi_verince_aday_kuyruga_girer(c):
    sonuc = c.konus("Benim kedimin adi Pamuk")
    assert len(c.kuyruk.bekleyenler()) == 1
    assert sonuc["aday"]["metin"] == "Benim kedimin adi Pamuk"
    assert "onay kuyruguna kondu" in c.konus_metin("Kedim cok tatli")


def test_bilgi_verince_HAFIZAYA_GIRMEZ(c):
    """En onemli test: konusmak ogretmek degildir."""
    c.konus("Benim kedimin adi Pamuk")
    assert c.kuyruk.hafiza() == []


def test_onaydan_sonra_hafizaya_girer(c):
    c.konus("Benim kedimin adi Pamuk")
    no = c.kuyruk.bekleyenler()[0].no
    c.komut(f"/onayla {no}")
    assert [h["metin"] for h in c.kuyruk.hafiza()] == ["Benim kedimin adi Pamuk"]


def test_siradan_sohbet_kuyruga_bir_sey_koymaz(c):
    c.konus("Merhaba, nasilsin")
    assert c.kuyruk.bekleyenler() == []


# -- Baglam kurma ------------------------------------------------------------


def test_baglam_onaylanmis_bilgiyi_icerir(c):
    c.kuyruk.onayla(c.kuyruk.ekle("Kedinin adi Pamuk").no)
    assert "Pamuk" in c.baglam("kedimden bahset")


def test_baglam_onaylanmamis_bilgiyi_ICERMEZ(c):
    """Kuyrukta bekleyen aday modele verilmez; onaylanmamis bilgi bilgi degildir."""
    c.kuyruk.ekle("Kedinin adi Tekir")
    assert "Tekir" not in c.baglam("kedimden bahset")


def test_baglam_hatirlanan_konusmayi_icerir(c):
    c.hafiza.ekle("kullanici", "Yarin Ankara ya gidecegim")
    assert "Ankara" in c.baglam("ankara ya ne zaman gidiyorum")


def test_baglam_durumu_icerir(c):
    assert "aclik=" in c.baglam("merhaba")


def test_baglam_modele_gercekten_gonderiliyor(c):
    c.kuyruk.onayla(c.kuyruk.ekle("Kedinin adi Pamuk").no)
    c.konus("kedimden bahset")
    assert "Pamuk" in c.llm.gecmis[-1]["sistem"]


# -- Gercek kullanimda cikan uc hata -----------------------------------------
#
# Asagidaki uc test, gelistirici arayuzu ilk kez gercek modelle kullandiginda
# gorunen uc ayri hatadan geliyor. Uculu de ayni ekran goruntusunde vardi.


def test_HATA1_sohbet_gecmisi_modele_gonderiliyor(c):
    """
    GORULEN: Kullanici kendini uzun uzun anlatti, hemen ardindan "benimle
    ilgili ne biliyorsun?" diye sordu. Model "sen ne is yapiyorsun?" dedi --
    bir onceki mesaji hic gormemisti.

    SEBEP: Her mesaj modele tek basina gonderiliyordu, onceki siralar hic
    gitmiyordu. Sohbetin sohbet olmasi icin gecmis de gitmeli.
    """
    c.konus("Benim adim Ali")
    c.konus("Ne is yaptigimi biliyor musun")

    gonderilen = c.llm.gecmis[-1]["sohbet"]
    metinler = [m["metin"] for m in gonderilen]
    assert "Benim adim Ali" in metinler, "onceki mesaj modele gitmemis"
    assert any(m["rol"] == "cekirdek" for m in gonderilen), "cevaplar da gitmeli"


def test_HATA2_model_kendi_cevabini_hatirlamiyor(c):
    """
    GORULEN: Iki farkli soruya BIREBIR AYNI cevap geldi.

    SEBEP: Geri cagirma, Cekirdek'in kendi eski cevaplarini da buluyor ve
    "hatirladiklarin" diye modele geri veriyordu. Model kendi cumlesini
    gorup aynen tekrar ediyordu.

    Artik geri cagirma sadece KULLANICININ soylediklerini getiriyor.
    """
    # Modelin eski cevabi cok ayirt edici bir kelime icersin
    c.llm.sabit_cevap = "Zeplin marmelat kombinasyonu"
    c.konus("kediler hakkinda ne dusunuyorsun")

    # Aradan mesaj gecsin ki eskiler "son mesajlar" olmaktan ciksin
    c.llm.sabit_cevap = "peki"
    for _ in range(8):
        c.konus("baska bir konu")

    c.konus("kediler hakkinda ne dusunuyorsun")
    sistem = c.llm.gecmis[-1]["sistem"]
    assert "Zeplin marmelat" not in sistem, (
        "Cekirdek kendi eski cevabini baglama koymus; model bunu tekrar eder"
    )


def test_HATA3_son_mesajlar_iki_kez_gonderilmiyor(c):
    """
    Son mesajlar zaten sohbet gecmisi olarak gidiyor. Bir de
    "hatirladiklarin" diye tekrar gonderilirse model ayni metni iki kez
    gorur ve kafasi karisir.
    """
    c.konus("Yarin Ankara ya gidecegim")
    c.konus("Ankara ya ne zaman gidiyordum")

    sistem = c.llm.gecmis[-1]["sistem"]
    sohbet = [m["metin"] for m in c.llm.gecmis[-1]["sohbet"]]

    assert "Yarin Ankara ya gidecegim" in sohbet          # gecmiste var
    assert "Yarin Ankara ya gidecegim" not in sistem      # baglamda YOK


def test_gecmis_sinirli_tutuluyor(c):
    """8 GB ekran kartinda baglami sisirmemek icin ust sinir var."""
    for i in range(20):
        c.konus(f"mesaj {i}")
    assert len(c.llm.gecmis[-1]["sohbet"]) <= uygulama.SOHBET_GECMISI


def test_eski_konusma_hala_hatirlaniyor(c):
    """
    Duzeltmeler geri cagirmayi bozmamali: yeterince eski bir kullanici
    mesaji hala bulunabilmeli.
    """
    c.konus("Kedimin adi Pamuk ve tekir bir kedi")
    for _ in range(8):
        c.konus("alakasiz bir konu")

    c.konus("kedimin adi neydi")
    assert "Pamuk" in c.llm.gecmis[-1]["sistem"]


# -- Komutlar ----------------------------------------------------------------


def test_yardim(c):
    assert "/onayla" in c.komut("/yardim")


def test_durum_gosterir(c):
    cikti = c.komut("/durum")
    for ad in Durum.alan_adlari():
        assert ad in cikti


def test_durum_ayarlanir_ve_kaydedilir(c):
    assert "aclik=40" in c.komut("/durum aclik 40")
    assert c.durum_yolu.exists()

    yeni = Cekirdek(llm=c.llm, klasor=c.kuyruk.klasor, izinli_kok=c.kuyruk.klasor)
    assert yeni.durum.aclik == 40


def test_durum_bilinmeyen_alan(c):
    assert "Bilinmeyen alan" in c.komut("/durum mutluluk 40")


def test_durum_aralik_disi_deger(c):
    assert "Hata" in c.komut("/durum aclik 500")


def test_durum_eksik_arguman(c):
    assert "Kullanim" in c.komut("/durum aclik")


def test_ogren_kuyruga_koyar_hafizaya_koymaz(c):
    cikti = c.komut("/ogren Kullanici sabahlari cay icer")
    assert "OGRENILMEDI" in cikti
    assert len(c.kuyruk.bekleyenler()) == 1
    assert c.kuyruk.hafiza() == []


def test_ogren_bos(c):
    assert "Kullanim" in c.komut("/ogren")


def test_listele(c):
    c.komut("/ogren Kedinin adi Pamuk")
    assert "Pamuk" in c.komut("/listele")


def test_onayla_ve_hafiza(c):
    c.komut("/ogren Kedinin adi Pamuk")
    assert "Ogrenildi" in c.komut("/onayla 1")
    assert "Pamuk" in c.komut("/hafiza")


def test_reddet(c):
    c.komut("/ogren Yanlis bilgi")
    assert "hafizaya girmedi" in c.komut("/reddet 1")
    assert "bos" in c.komut("/hafiza")


def test_onayla_olmayan_numara(c):
    assert "Hata" in c.komut("/onayla 99")


def test_onayla_numara_degil(c):
    assert "numara degil" in c.komut("/onayla pamuk")


def test_onayla_numarasiz(c):
    assert "Kullanim" in c.komut("/onayla")


def test_hatirla(c):
    c.konus("Yarin Ankara ya gidecegim")
    assert "Ankara" in c.komut("/hatirla ankara")


def test_hatirla_bulamayinca(c):
    c.konus("Merhaba")
    assert "bulamadim" in c.komut("/hatirla kuantum fizigi")


def test_hatirla_bos(c):
    assert "Kullanim" in c.komut("/hatirla")


def test_gecmis(c):
    c.konus("birinci mesaj")
    assert "birinci mesaj" in c.komut("/gecmis")


def test_gecmis_bos(c):
    assert "bos" in c.komut("/gecmis")


def test_gecmis_sayi_degilse(c):
    assert "sayi degil" in c.komut("/gecmis abc")


def test_bilinmeyen_komut(c):
    assert "Bilinmeyen komut" in c.komut("/zipzip")


# -- Terminal dongusu --------------------------------------------------------


def _calistir(satirlar, monkeypatch, tmp_path, argv=None):
    """Verilen satirlari klavyeden yazilmis gibi calistirir, ciktiyi dondurur."""
    monkeypatch.setattr(uygulama, "WORKSPACE", tmp_path)
    sira = iter(satirlar)
    cikti: list[str] = []

    def sahte_girdi(_istem=""):
        return next(sira)

    kod = uygulama.main(
        argv or [], girdi=sahte_girdi, yazdir=lambda *a: cikti.append(" ".join(str(x) for x in a))
    )
    return kod, "\n".join(cikti)


def test_acilista_sessizce_bekler(monkeypatch, tmp_path):
    """Uyanma davranisi: tek satir bilgi verir, kendiliginden konusmaz."""
    kod, cikti = _calistir(["/cik"], monkeypatch, tmp_path)
    assert kod == 0
    assert "Cekirdek uyandi" in cikti
    assert "Gorusuruz" in cikti


def test_dongude_sohbet(monkeypatch, tmp_path):
    kod, cikti = _calistir(["Merhaba", "/cik"], monkeypatch, tmp_path)
    assert kod == 0
    assert "cekirdek>" in cikti


def test_dongude_komut(monkeypatch, tmp_path):
    kod, cikti = _calistir(["/ogren Kedinin adi Pamuk", "/listele", "/cik"], monkeypatch, tmp_path)
    assert "Pamuk" in cikti


def test_bos_satir_atlanir(monkeypatch, tmp_path):
    kod, cikti = _calistir(["", "   ", "/cik"], monkeypatch, tmp_path)
    assert kod == 0


def test_ctrl_c_ile_cikis(monkeypatch, tmp_path):
    """Klavyeden Ctrl+C basilinca cirkin bir hata yigini degil, veda mesaji."""

    def kesinti(_istem=""):
        raise KeyboardInterrupt

    monkeypatch.setattr(uygulama, "WORKSPACE", tmp_path)
    cikti: list[str] = []
    kod = uygulama.main([], girdi=kesinti, yazdir=lambda *a: cikti.append(str(a)))
    assert kod == 0
    assert "Gorusuruz" in " ".join(cikti)


def test_hazir_olmayan_model_uyarir(monkeypatch, tmp_path):
    kod, cikti = _calistir(
        ["/cik"], monkeypatch, tmp_path,
        argv=["--model", "ollama", "--sunucu", "http://127.0.0.1:1"],
    )
    assert kod == 1
    assert "hazir degil" in cikti


def test_bilinmeyen_model_uyarir(monkeypatch, tmp_path):
    kod, cikti = _calistir(["/cik"], monkeypatch, tmp_path, argv=["--model", "gpt-9000"])
    assert kod == 1
    assert "Bilinmeyen model" in cikti


def test_konusma_kalicidir(monkeypatch, tmp_path):
    """Programi kapatip acinca dun konusulan hatirlanmali."""
    _calistir(["Yarin Ankara ya gidecegim", "/cik"], monkeypatch, tmp_path)
    kod, cikti = _calistir(["/hatirla ankara", "/cik"], monkeypatch, tmp_path)
    assert "Ankara" in cikti
