"""
tests/test_memory.py -- Konusma hafizasi ve geri cagirma testleri

Iki grup:
  1. Gomucu (metin -> sayi dizisi) dogru ve KARARLI calisiyor mu?
  2. Hafiza kaydediyor, hatirliyor ve onay kuyruguna karismiyor mu?
"""

import json
import os
import subprocess
import sys

import pytest

from core.approval import OnayKuyrugu
from core.memory import (
    CEKIRDEK,
    KULLANICI,
    BasitGomucu,
    Gomucu,
    Hafiza,
    OllamaGomucu,
    benzerlik,
    seyreklestir,
    yogunlastir,
)


@pytest.fixture
def hafiza(tmp_path):
    return Hafiza(klasor=tmp_path, izinli_kok=tmp_path)


# -- Gomucu ------------------------------------------------------------------


def test_gomme_sabit_uzunlukta():
    g = BasitGomucu(boyut=128)
    assert len(g.gom("kisa")) == 128
    assert len(g.gom("cok daha uzun bir cumle yaziyorum simdi")) == 128


def test_gomme_normalize_edilmis():
    """Uzunlugu 1 olmali; yoksa uzun mesajlar sirf uzun diye benzer cikar."""
    vektor = BasitGomucu().gom("Kedimin adi Pamuk")
    uzunluk = sum(d * d for d in vektor) ** 0.5
    assert uzunluk == pytest.approx(1.0)


def test_bos_metin_sifir_vektor():
    assert set(BasitGomucu().gom("")) == {0.0}


def test_ayni_metin_ayni_vektor():
    assert BasitGomucu().gom("merhaba") == BasitGomucu().gom("merhaba")


def test_vektorler_calistirmalar_arasinda_degismez():
    """
    KRITIK: Python'un kendi hash() fonksiyonu her calistirmada farkli sonuc
    verir. Onu kullansaydik diske yazilmis vektorler bir sonraki acilista
    bozulurdu. Bu test iki AYRI Python surecini farkli hash tohumlariyla
    calistirip ayni sonucu aldigimizi dogrular.
    """
    betik = (
        "import sys; sys.path.insert(0, '.');"
        "from core.memory import BasitGomucu;"
        "print(sum(BasitGomucu().gom('Kedimin adi Pamuk')[:50]))"
    )
    ciktilar = []
    for tohum in ("0", "1", "12345"):
        ortam = dict(os.environ, PYTHONHASHSEED=tohum)
        sonuc = subprocess.run(
            [sys.executable, "-c", betik], capture_output=True, text=True, env=ortam
        )
        assert sonuc.returncode == 0, sonuc.stderr
        ciktilar.append(sonuc.stdout.strip())
    assert len(set(ciktilar)) == 1


def test_benzer_cumleler_alakasizdan_yuksek_puan_alir():
    g = BasitGomucu()
    kedi = g.gom("Kedimin adi Pamuk")
    kedi_sorusu = g.gom("kedimin adi neydi")
    alakasiz = g.gom("Yarin Ankara ya gidecegim")
    assert benzerlik(kedi, kedi_sorusu) > benzerlik(kedi, alakasiz)


def test_turkce_ekli_kelimeler_eslesir():
    """
    Turkce ekli bir dil: 'kedi' ile 'kedimin' eslesmeli.
    (Bu bir kez gercekten kirikti; kelime ve harf parcalari ayri havuzlardaydi.)
    """
    g = BasitGomucu()
    assert benzerlik(g.gom("kedi"), g.gom("Benim kedimin adi Pamuk")) > 0.1


def test_turkce_harflere_duyarsiz():
    g = BasitGomucu()
    assert g.gom("açlık yüksek") == g.gom("aclik yuksek")


def test_noktalama_onemsiz():
    g = BasitGomucu()
    assert g.gom("Kedinin adi Pamuk!") == g.gom("kedinin adi pamuk")


def test_alakasiz_sorgu_gurultu_uretmez():
    """4096 kova secilmesinin sebebi: carpisma kaynakli sahte benzerlik olmasin."""
    g = BasitGomucu()
    puan = benzerlik(g.gom("tesla bobini"), g.gom("Yarin Ankara ya gidecegim"))
    assert puan < 0.05


def test_BILINEN_SINIR_farkli_cekimli_fiiller_eslesmiyor():
    """
    BU TEST BIR EKSIGI KAYDA GECIRIYOR, bir ozelligi degil.

    BasitGomucu harf parcalarina bakar, ANLAMA bakmaz. Bu yuzden
    "gidiyordum" ile "gidecegim" (ayni fiil, farkli cekim) eslesmez:
    ilk dort harfleri bile ayni degil (gidi / gide).

    3 harflik parcalar da eklemeyi denedik ve olctuk: bu durum ancak 0.038'e
    cikiyor, buna karsilik alakasiz cumlelerdeki sahte benzerlik 0.09'dan
    0.18'e firliyordu. Kotu takas oldugu icin 4 harfte kaldik.

    Gercek cozum: bilgisayara gecince OllamaGomucu'nun doldurulmasi.
    O zaman bu test ters cevrilecek (eslesmesi BEKLENECEK).
    """
    g = BasitGomucu()
    puan = benzerlik(g.gom("nereye gidiyordum"), g.gom("Yarin Ankara ya gidecegim"))
    assert puan < 0.10, (
        "Beklenmedik sekilde eslesti. Gomucu degistiyse bu testi guncelle."
    )


def test_kucuk_boyut_reddedilir():
    with pytest.raises(ValueError):
        BasitGomucu(boyut=4)


def test_farkli_boylu_vektorler_karsilastirilamaz():
    with pytest.raises(ValueError, match="boylari farkli"):
        benzerlik([0.0] * 4, [0.0] * 8)


def test_seyrek_gidis_donus():
    yogun = BasitGomucu(boyut=64).gom("merhaba dunya")
    assert yogunlastir(seyreklestir(yogun), 64) == yogun


def test_seyrek_sadece_dolu_kovalari_saklar():
    seyrek = seyreklestir(BasitGomucu(boyut=4096).gom("kisa bir cumle"))
    assert 0 < len(seyrek) < 100  # 4096 degil, cok daha az


def test_ollama_gomucu_sunucu_yoksa_hazir_degil():
    from core.ollama_baglanti import OllamaHatasi

    kapali = "http://127.0.0.1:1"
    g = OllamaGomucu(sunucu=kapali)
    assert g.hazir_mi() is False
    with pytest.raises(OllamaHatasi, match="ulasilamadi"):
        g.gom("merhaba")


def test_gomucu_dogrudan_uretilemez():
    with pytest.raises(TypeError):
        Gomucu()


# -- Hafizaya yazma ----------------------------------------------------------


def test_mesaj_kaydedilir(hafiza):
    m = hafiza.ekle(KULLANICI, "Merhaba")
    assert m.no == 1
    assert m.rol == KULLANICI
    assert m.zaman
    assert m.gomme  # gomme cikarilmis


def test_numaralar_artar(hafiza):
    assert [hafiza.ekle(KULLANICI, f"mesaj {i}").no for i in range(3)] == [1, 2, 3]


def test_bilinmeyen_rol_reddedilir(hafiza):
    with pytest.raises(ValueError, match="Bilinmeyen rol"):
        hafiza.ekle("robot", "merhaba")


def test_bos_mesaj_reddedilir(hafiza):
    with pytest.raises(ValueError):
        hafiza.ekle(KULLANICI, "   ")


def test_gunluk_program_kapanip_acilinca_kalir(tmp_path):
    Hafiza(klasor=tmp_path, izinli_kok=tmp_path).ekle(KULLANICI, "hatirlanmali")
    yeni = Hafiza(klasor=tmp_path, izinli_kok=tmp_path)
    assert [m.metin for m in yeni.tumu()] == ["hatirlanmali"]


def test_dosya_okunabilir_json(hafiza):
    hafiza.ekle(KULLANICI, "merhaba")
    veri = json.loads(hafiza.dosya.read_text(encoding="utf-8"))
    assert veri[0]["metin"] == "merhaba"
    assert veri[0]["rol"] == KULLANICI


def test_son_n_mesaj(hafiza):
    for i in range(5):
        hafiza.ekle(KULLANICI, f"mesaj {i}")
    assert [m.metin for m in hafiza.son(2)] == ["mesaj 3", "mesaj 4"]
    assert hafiza.son(0) == []


def test_temizle_gunlugu_siler(hafiza):
    hafiza.ekle(KULLANICI, "bir")
    hafiza.ekle(KULLANICI, "iki")
    assert hafiza.temizle() == 2
    assert hafiza.sayi() == 0


def test_bozuk_dosya_acik_hata_verir(hafiza):
    hafiza.dosya.write_text("{bozuk", encoding="utf-8")
    with pytest.raises(ValueError, match="bozuk"):
        hafiza.tumu()


def test_gecici_dosya_birakilmaz(hafiza):
    hafiza.ekle(KULLANICI, "merhaba")
    assert list(hafiza.klasor.glob("*.tmp")) == []


def test_workspace_disina_yazamaz(tmp_path):
    izinli = tmp_path / "workspace"
    disari = tmp_path / "disari"
    disari.mkdir()
    with pytest.raises(PermissionError):
        Hafiza(klasor=disari, izinli_kok=izinli)


# -- Geri cagirma ------------------------------------------------------------


def test_ilgili_mesaj_bulunur(hafiza):
    hafiza.ekle(KULLANICI, "Kedimin adi Pamuk")
    hafiza.ekle(KULLANICI, "Yarin Ankara ya gidecegim")
    bulunanlar = hafiza.hatirla("kedimin adi neydi")
    assert bulunanlar
    assert bulunanlar[0][0].metin == "Kedimin adi Pamuk"


def test_alakasiz_soru_bos_doner(hafiza):
    """Alakasiz seyi baglama eklemek modeli yaniltir; bos donmek daha iyi."""
    hafiza.ekle(KULLANICI, "Kedimin adi Pamuk")
    assert hafiza.hatirla("kuantum fizigi nedir") == []


def test_bos_soru_bos_doner(hafiza):
    hafiza.ekle(KULLANICI, "Kedimin adi Pamuk")
    assert hafiza.hatirla("   ") == []


def test_sonuc_sayisi_sinirlanir(hafiza):
    for i in range(6):
        hafiza.ekle(KULLANICI, f"kedimin adi Pamuk {i}")
    assert len(hafiza.hatirla("kedi", kac=2)) == 2


def test_sonuclar_puana_gore_sirali(hafiza):
    hafiza.ekle(KULLANICI, "Kedimin adi Pamuk ve cok tatli bir kedi")
    hafiza.ekle(KULLANICI, "Bugun hava guzel, kedi gordum")
    puanlar = [p for _, p in hafiza.hatirla("kedi", kac=5)]
    assert puanlar == sorted(puanlar, reverse=True)


def test_esik_altindakiler_elenir(hafiza):
    hafiza.ekle(KULLANICI, "Kedimin adi Pamuk")
    assert hafiza.hatirla("kedi", esik=0.99) == []


def test_gomucu_degisirse_yeniden_hesaplanir(tmp_path):
    """
    Diskteki vektorler eski gomucuyle yazilmis olabilir (ornegin Ollama'ya
    gecince). O zaman sessizce yanlis sonuc vermek yerine yeniden hesaplanir.
    """
    h1 = Hafiza(klasor=tmp_path, izinli_kok=tmp_path, gomucu=BasitGomucu(boyut=128))
    h1.ekle(KULLANICI, "Kedimin adi Pamuk")

    h2 = Hafiza(klasor=tmp_path, izinli_kok=tmp_path, gomucu=BasitGomucu(boyut=1024))
    bulunanlar = h2.hatirla("kedi")
    assert bulunanlar and bulunanlar[0][0].metin == "Kedimin adi Pamuk"


def test_baglam_metni_bulunani_yazar(hafiza):
    hafiza.ekle(KULLANICI, "Kedimin adi Pamuk")
    metin = hafiza.baglam_metni("kedimin adi neydi")
    assert "Pamuk" in metin
    assert "gecmiste soyledikleri" in metin.lower()


def test_sadece_kullanici_secenegi_cekirdegi_eler(hafiza):
    """
    Cekirdek'in kendi cevaplarini "hatirladiklarin" diye geri vermek,
    modelin kendini tekrar etmesine yol aciyordu. Gercekten yasandi.
    """
    hafiza.ekle(KULLANICI, "Kedimin adi Pamuk")
    hafiza.ekle(CEKIRDEK, "Kedimin adi Pamuk, ne guzel")

    hepsi = hafiza.hatirla("kedi", kac=5)
    sadece = hafiza.hatirla("kedi", kac=5, sadece_kullanici=True)

    assert len(hepsi) == 2
    assert len(sadece) == 1
    assert sadece[0][0].rol == KULLANICI


def test_haric_verilen_mesajlar_atlanir(hafiza):
    """Son mesajlar zaten sohbet gecmisi olarak gidiyor; iki kez gitmesin."""
    m1 = hafiza.ekle(KULLANICI, "Kedimin adi Pamuk")
    hafiza.ekle(KULLANICI, "Kedim cok tatli")

    assert len(hafiza.hatirla("kedi", kac=5)) == 2
    assert len(hafiza.hatirla("kedi", kac=5, haric={m1.no})) == 1


def test_baglam_metni_sadece_kullaniciyi_yazar(hafiza):
    hafiza.ekle(KULLANICI, "Kedimin adi Pamuk")
    hafiza.ekle(CEKIRDEK, "Zeplin marmelat kombinasyonu kedi")
    metin = hafiza.baglam_metni("kedi")
    assert "Pamuk" in metin
    assert "Zeplin" not in metin


def test_baglam_metni_bulamayinca_bos(hafiza):
    """Bos metin donmeli; uydurma baglam eklenmemeli."""
    hafiza.ekle(KULLANICI, "Kedimin adi Pamuk")
    assert hafiza.baglam_metni("kuantum fizigi") == ""


# -- Onay kuyruguyla karismaz ------------------------------------------------


def test_konusma_gunlugu_kalici_hafizaya_yazmaz(tmp_path):
    """
    EN ONEMLI SINIR: konusma gunlugune yazmak OGRENMEK DEGILDIR.
    Konusma kaydedilir ama hafiza.json'a hicbir sey gecmez.
    """
    hafiza = Hafiza(klasor=tmp_path, izinli_kok=tmp_path)
    kuyruk = OnayKuyrugu(klasor=tmp_path, izinli_kok=tmp_path)

    hafiza.ekle(KULLANICI, "Kedimin adi Pamuk")
    hafiza.ekle(CEKIRDEK, "Anladim.")

    assert hafiza.sayi() == 2
    assert kuyruk.hafiza() == []
    assert kuyruk.bekleyenler() == []
    assert not kuyruk.hafiza_dosyasi.exists()


def test_iki_sistem_ayri_dosyalar_kullanir(tmp_path):
    hafiza = Hafiza(klasor=tmp_path, izinli_kok=tmp_path)
    kuyruk = OnayKuyrugu(klasor=tmp_path, izinli_kok=tmp_path)
    assert hafiza.dosya != kuyruk.hafiza_dosyasi
    assert hafiza.dosya.name == "konusma_gunlugu.json"
