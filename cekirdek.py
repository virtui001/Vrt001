"""
cekirdek.py -- TERMINAL ARAYUZU

Butun parcalari birlestiren yer. Calistirmak icin:

    python cekirdek.py

NE OLUYOR ICERIDE?
Sen bir sey yazdiginda sirasiyla sunlar olur:

    1. Mesajin konusma gunlugune yazilir (zaman damgasi + gomme ile).
    2. Gecmiste buna benzeyen mesajlar aranir (geri cagirma).
    3. Onaylanmis kalici bilgiler alinir (hafiza.json).
    4. Bunlarin hepsi + durum vektorun modele "baglam" olarak verilir.
    5. Modelin cevabi da gunluge yazilir.
    6. Mesajinda ogrenilmeye deger bir sey varsa ONAY KUYRUGUNA aday olarak
       konur -- dogrudan ogrenilmez. Sen /listele ve /onayla dersen ogrenir.

UYANMA DAVRANISI (CLAUDE.md Faz 3, madde 5'in yazilim tarafi):
Acilista hafizayi yukler, kisa bir satir yazar ve SESSIZCE bekler.
Kendiliginden konusmaz.

KOMUTLAR (/ ile baslar; / ile baslamayan her sey sohbettir):
    /yardim              komut listesi
    /durum               durum vektorunu goster
    /durum aclik 40      bir alani ayarla ve kaydet
    /ogren <metin>       elle aday ekle (onay kuyruguna)
    /tohumla             proje kurallarini kuyruga koy
    /listele             onay bekleyen adaylar
    /onayla <no...>      adaylari hafizaya al (3 / 1 4 7 / 1-18)
    /reddet <no...>      adaylari sil
    /hafiza              onaylanmis kalici bilgiler
    /hatirla <soru>      gecmis konusmalarda ara
    /gecmis [n]          son n mesaj (varsayilan 10)
    /cik                 cikis
"""

from __future__ import annotations

import sys
from pathlib import Path

from core.approval import OnayKuyrugu, numaralari_oku
from core.guvenlik import WORKSPACE
from core.llm import LLM, llm_olustur
from core.memory import CEKIRDEK, KULLANICI, Hafiza, OllamaGomucu
from core.metin import turkcesiz
from core.ollama_baglanti import VARSAYILAN_SUNUCU
from core.terminal import utf8_cikti
from models.state import Durum, kaydet as durum_kaydet, yukle_veya_varsayilan

# Modele verilen karakter talimati.
#
# ILK SURUM SOYLEYDI ve KOTUYDU:
#   "Bilmedigin seyi uydurma, bilmiyorum de. Asagida sana verilen bilgiler
#    disinda bir sey biliyormus gibi yapma."
# Kucuk modeller bu kadar cok olumsuz talimati "her cumleye Hayir diye basla"
# seklinde anliyor. Gercekten yasandi: "Orada misin?" sorusuna model
# "Hayir, buradayim!" diye cevap verdi.
#
# Simdiki hali olumlu cumlelerle yaziyor: ne YAPMAMASI degil, ne YAPMASI
# gerektigini soyluyor.
SISTEM_METNI = (
    "Sen Cekirdek adlisin. Turkce konusuyorsun ve karsindaki kisiyle "
    "sohbet ediyorsun.\n"
    "Dogal ve samimi konus, kisa tut: en fazla 2-3 cumle.\n"
    "Asagida hafizandaki bilgiler var; kisiyle ilgili bir sey sorulursa "
    "once oraya bak ve oradaki bilgiyi kullan.\n"
    "Hafizanda olmayan bir sey sorulursa sadece o konuda 'bunu bilmiyorum' de."
)

# Modele kac onceki mesaj gonderilecek? (kullanici + cevap ciftleri)
# Cok fazlasi 8 GB ekran kartinda baglami sisirir ve yavaslatir.
SOHBET_GECMISI = 6

# Kullanicinin cumlesinde bunlardan biri geciyorsa "burada ogrenilecek bir sey
# olabilir" deriz ve ADAY olarak kuyruga koyariz -- ogrenmeyiz.
#
# Bu kaba bir kural, bilerek boyle. Model geldiginde adaylari model onerecek.
# O zamana kadar akisin dogru calistigini gorebilmek icin bu yeterli.
ADAY_IPUCLARI = (
    "benim", "adim", "adım", "dogum gunum", "seviyorum", "sevmiyorum",
    "sevmem", "her sabah", "her aksam", "calisiyorum", "yasiyorum",
    "kedim", "kopegim", "esim", "cocugum", "isim ",
)


def aday_oner(metin: str) -> str | None:
    """
    Kullanicinin cumlesi kalici bilgi adayi mi? Oyleyse aday metnini dondurur.

    DIKKAT: Bu fonksiyon HICBIR SEY OGRENMEZ. Sadece "bunu onaya sunalim mi"
    diye isaret eder. Ogrenme tek bir yerden olur: onayla komutu.
    """
    sade = turkcesiz(metin)
    if len(sade) < 8:
        return None
    if metin.strip().endswith("?"):
        return None  # soru sormak bilgi vermek degildir
    for ipucu in ADAY_IPUCLARI:
        if turkcesiz(ipucu) in sade:
            return metin.strip()
    return None


class Cekirdek:
    """Butun parcalari bir arada tutan sinif."""

    def __init__(
        self,
        llm: LLM | None = None,
        klasor: str | Path | None = None,
        izinli_kok: str | Path | None = None,
        gomucu=None,
    ) -> None:
        kok = izinli_kok if izinli_kok is not None else WORKSPACE
        hedef = klasor if klasor is not None else kok

        self.llm = llm or llm_olustur("mock")
        self.hafiza = Hafiza(klasor=hedef, izinli_kok=kok, gomucu=gomucu)
        self.kuyruk = OnayKuyrugu(klasor=hedef, izinli_kok=kok)
        self.durum_yolu = self.kuyruk.klasor / "state.json"
        self.durum = yukle_veya_varsayilan(self.durum_yolu)

    # -- Baglam kurma --------------------------------------------------------

    def baglam(self, soru: str, haric: set[int] | None = None) -> str:
        """
        Modele verilecek sistem metnini kurar:
        sabit talimat + onaylanmis bilgiler + eski konusmalar + durum.

        haric: bu numarali mesajlar geri cagirmaya girmez. Son mesajlar zaten
        sohbet gecmisi olarak ayrica gonderiliyor; iki kez gondermek modeli
        kendini tekrar etmeye itiyor.
        """
        parcalar = [SISTEM_METNI]

        onaylanmis = self.kuyruk.hafiza()
        if onaylanmis:
            satirlar = "\n".join(f"- {k['metin']}" for k in onaylanmis)
            parcalar.append("Hafizandaki bilgiler:\n" + satirlar)

        hatirlanan = self.hafiza.baglam_metni(soru, haric=haric)
        if hatirlanan:
            parcalar.append(hatirlanan)

        parcalar.append("Su anki durumun: " + self.durum.ozet())
        return "\n\n".join(parcalar)

    # -- Sohbet --------------------------------------------------------------

    def konus(self, girdi: str) -> dict:
        """
        Bir mesaji bastan sona isler.

        Doner: {"cevap": ..., "sure_sn": ..., "aday": {"no","metin"}|None}
        Sozluk donuyor ki hem terminal hem web arayuzu ayni yolu kullansin.
        (Onceden web sunucusu bu mantigi kopyalamisti; iki yerde ayri ayri
        duran kod, iki yerde ayri ayri bozulur.)
        """
        self.hafiza.ekle(KULLANICI, girdi)

        # Son mesajlar sohbet gecmisi olarak gidiyor. Sonuncusu az once
        # eklenen sorunun kendisi, onu gecmise koymuyoruz.
        son_mesajlar = self.hafiza.son(SOHBET_GECMISI + 1)
        gecmis = [
            {"rol": m.rol, "metin": m.metin} for m in son_mesajlar[:-1]
        ]
        haric = {m.no for m in son_mesajlar}

        cevap = self.llm.cevapla(
            girdi, sistem=self.baglam(girdi, haric=haric), gecmis=gecmis
        )
        self.hafiza.ekle(CEKIRDEK, cevap.metin)

        sonuc = {"cevap": cevap.metin, "sure_sn": cevap.sure_sn, "aday": None}

        onerilen = aday_oner(girdi)
        if onerilen:
            kayit = self.kuyruk.ekle(onerilen, kaynak="konusma")
            if kayit.durum == "bekliyor":
                sonuc["aday"] = {"no": kayit.no, "metin": kayit.metin}
        return sonuc

    def konus_metin(self, girdi: str) -> str:
        """Terminal icin: konus() sonucunu tek metne cevirir."""
        s = self.konus(girdi)
        if s["aday"]:
            return (
                f"{s['cevap']}\n"
                f"   (not: [{s['aday']['no']}] numarali aday onay kuyruguna kondu, "
                f"HENUZ ogrenmedim. /listele ile bakabilirsin.)"
            )
        return s["cevap"]

    # -- Komutlar ------------------------------------------------------------

    def komut(self, satir: str) -> str:
        """'/' ile baslayan komutlari isler ve ekrana yazilacak metni dondurur."""
        parcalar = satir[1:].split()
        if not parcalar:
            return YARDIM
        ad = parcalar[0].lower()
        arg = parcalar[1:]
        kalan = satir[1:].split(" ", 1)[1].strip() if " " in satir else ""

        if ad in ("yardim", "help", "?"):
            return YARDIM

        if ad == "durum":
            if not arg:
                return "Durum vektoru:\n  " + self.durum.ozet().replace(" | ", "\n  ")
            if len(arg) != 2:
                return "Kullanim: /durum <alan> <deger>   ornek: /durum aclik 40"
            alan, deger = arg[0], arg[1]
            if alan not in Durum.alan_adlari():
                return f"Bilinmeyen alan: {alan}. Alanlar: " + ", ".join(Durum.alan_adlari())
            try:
                self.durum = self.durum.ayarla(**{alan: int(deger)})
            except ValueError as hata:
                return f"Hata: {hata}"
            durum_kaydet(self.durum, self.durum_yolu)
            return f"Kaydedildi. {self.durum.ozet()}"

        if ad == "ogren":
            if not kalan:
                return "Kullanim: /ogren <ogrenilecek bilgi>"
            aday = self.kuyruk.ekle(kalan, kaynak="elle")
            return f"Onay kuyruguna kondu (henuz OGRENILMEDI): {aday.satir()}"

        if ad == "listele":
            return self.kuyruk.listele()

        if ad == "tohumla":
            yeniler = self.kuyruk.tohumla()
            if not yeniler:
                return "Eklenecek yeni kural yok (hepsi zaten kuyrukta ya da hafizada)."
            satirlar = [
                f"{len(yeniler)} proje kurali onay kuyruguna kondu.",
                "Hicbiri HENUZ ogrenilmedi. /listele ile oku, sonra onayla.",
                f"Hepsini kabul ediyorsan: /onayla {yeniler[0].no}-{yeniler[-1].no}",
            ]
            return "\n".join(satirlar)

        if ad in ("onayla", "reddet"):
            if not arg:
                return f"Kullanim: /{ad} <no>   (ornek: /{ad} 3 ya da /{ad} 1-18)"
            try:
                # "/onayla 1 4 7" ve "/onayla 1-18" bicimleri de calissin.
                numaralar = numaralari_oku(["", *arg] if ad == "onayla" else ["", arg[0]])
            except ValueError as hata:
                return f"Hata: {hata}"

            satirlar = []
            for no in numaralar:
                try:
                    if ad == "onayla":
                        kayit = self.kuyruk.onayla(no)
                        satirlar.append(f"Ogrenildi (artik kalici): [{no}] {kayit['metin'][:70]}")
                    else:
                        aday = self.kuyruk.reddet(no, sebep=" ".join(arg[1:]))
                        satirlar.append(f"Silindi, hafizaya girmedi: [{no}] {aday.metin[:70]}")
                except KeyError as hata:
                    satirlar.append(f"Hata: {hata}")
            return "\n".join(satirlar)

        if ad == "hafiza":
            kayitlar = self.kuyruk.hafiza()
            if not kayitlar:
                return "Kalici hafiza bos. Onayladigin bir sey yok."
            return f"Kalici hafizada {len(kayitlar)} bilgi:\n" + "\n".join(
                f"  [{k['no']:>3}] {k['metin']}" for k in kayitlar
            )

        if ad == "hatirla":
            if not kalan:
                return "Kullanim: /hatirla <aranacak konu>"
            bulunanlar = self.hafiza.hatirla(kalan, kac=5)
            if not bulunanlar:
                return "Bu konuda gecmiste bir sey bulamadim."
            return "Bulduklarim:\n" + "\n".join(
                f"  {puan:.2f}  {m.satir()}" for m, puan in bulunanlar
            )

        if ad == "gecmis":
            kac = 10
            if arg:
                try:
                    kac = int(arg[0])
                except ValueError:
                    return f"'{arg[0]}' bir sayi degil."
            mesajlar = self.hafiza.son(kac)
            if not mesajlar:
                return "Konusma gunlugu bos."
            return "\n".join("  " + m.satir() for m in mesajlar)

        if ad in ("cik", "quit", "exit"):
            return ""

        return f"Bilinmeyen komut: /{ad}\n\n{YARDIM}"


YARDIM = """Komutlar:
  /durum                 durum vektorunu goster
  /durum <alan> <deger>  bir alani ayarla (ornek: /durum aclik 40)
  /ogren <metin>         elle aday ekle (onay kuyruguna)
  /tohumla               proje kurallarini kuyruga koy
  /listele               onay bekleyen adaylar
  /onayla <no...>        adaylari hafizaya al (3 / 1 4 7 / 1-18)
  /reddet <no...>        adaylari sil
  /hafiza                onaylanmis kalici bilgiler
  /hatirla <soru>        gecmis konusmalarda ara
  /gecmis [n]            son n mesaj
  /cik                   cikis

'/' ile baslamayan her sey sohbet olarak islenir."""


def main(argv: list[str] | None = None, girdi=input, yazdir=print) -> int:
    """
    Terminal dongusu.

    girdi/yazdir disaridan verilebiliyor; testler boylece klavye olmadan
    konusabiliyor. Normal kullanimda Python'un kendi input/print'i kullanilir.
    """
    utf8_cikti()
    argv = list(sys.argv[1:] if argv is None else argv)

    def _secenek(ad: str, varsayilan: str) -> str:
        if ad in argv:
            yer = argv.index(ad)
            if yer + 1 < len(argv):
                return argv[yer + 1]
        return varsayilan

    model_adi = _secenek("--model", "mock")
    # Ollama baska bir bilgisayarda/kapida calisiyorsa buradan verilir.
    sunucu = _secenek("--sunucu", VARSAYILAN_SUNUCU)
    # Hangi Ollama modeli: llama3.1:8b, qwen2.5:7b, gemma2:9b ...
    ollama_modeli = _secenek("--ollama-model", "")

    try:
        if model_adi == "ollama":
            ayarlar = {"sunucu": sunucu}
            if ollama_modeli:
                ayarlar["model"] = ollama_modeli
            llm = llm_olustur("ollama", **ayarlar)
        else:
            llm = llm_olustur(model_adi)
    except ValueError as hata:
        yazdir(f"Hata: {hata}")
        return 1

    if not llm.hazir_mi():
        yazdir(
            f"'{model_adi}' modeli hazir degil (iskelet). "
            "Simdilik: python cekirdek.py --model mock"
        )
        return 1

    # Gomucu secimi: gercek model kullaniyorsak anlamsal gomucuyu deneriz.
    # Kurulu degilse BasitGomucu ile devam ederiz -- calismamaktansa
    # kelime benzerligiyle calismak daha iyi. Ama sessizce degil, soyleyerek.
    gomucu = None
    gomucu_notu = ""
    if model_adi == "ollama":
        aday_gomucu = OllamaGomucu(sunucu=sunucu)
        if aday_gomucu.hazir_mi():
            gomucu = aday_gomucu
        else:
            gomucu_notu = (
                "\nNot: gomme modeli bulunamadi, kelime benzerligiyle calisiyorum.\n"
                "     Anlamsal arama icin: ollama pull nomic-embed-text"
            )

    c = Cekirdek(llm=llm, gomucu=gomucu)

    # Uyanma: hafizayi yukle, kisa bir satir yaz, sonra sessizce bekle.
    bekleyen = len(c.kuyruk.bekleyenler())
    yazdir(
        f"Cekirdek uyandi. model: {model_adi} | "
        f"konusma: {c.hafiza.sayi()} mesaj | "
        f"kalici bilgi: {len(c.kuyruk.hafiza())} | "
        f"onay bekleyen: {bekleyen}"
    )
    yazdir("Yardim icin /yardim, cikmak icin /cik yaz." + gomucu_notu + "\n")

    while True:
        try:
            satir = girdi("sen> ")
        except (EOFError, KeyboardInterrupt):
            yazdir("\nGorusuruz.")
            return 0

        if satir is None:
            return 0
        satir = satir.strip()
        if not satir:
            continue

        if satir.startswith("/"):
            ad = satir[1:].split()[0].lower() if satir[1:].split() else ""
            if ad in ("cik", "quit", "exit"):
                yazdir("Gorusuruz.")
                return 0
            yazdir(c.komut(satir))
        else:
            yazdir("cekirdek> " + c.konus_metin(satir))
        yazdir("")


if __name__ == "__main__":
    raise SystemExit(main())
