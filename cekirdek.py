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
    /listele             onay bekleyen adaylar
    /onayla <no>         adayi hafizaya al
    /reddet <no>         adayi sil
    /hafiza              onaylanmis kalici bilgiler
    /hatirla <soru>      gecmis konusmalarda ara
    /gecmis [n]          son n mesaj (varsayilan 10)
    /cik                 cikis
"""

from __future__ import annotations

import sys
from pathlib import Path

from core.approval import OnayKuyrugu
from core.guvenlik import WORKSPACE
from core.llm import LLM, llm_olustur
from core.memory import CEKIRDEK, KULLANICI, Hafiza
from core.metin import turkcesiz
from models.state import Durum, kaydet as durum_kaydet, yukle_veya_varsayilan

SISTEM_METNI = (
    "Sen Cekirdek adli bir asistansin. Kisa, net ve Turkce konus. "
    "Bilmedigin seyi uydurma, bilmiyorum de. "
    "Asagida sana verilen bilgiler disinda bir sey biliyormus gibi yapma."
)

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
    ) -> None:
        kok = izinli_kok if izinli_kok is not None else WORKSPACE
        hedef = klasor if klasor is not None else kok

        self.llm = llm or llm_olustur("mock")
        self.hafiza = Hafiza(klasor=hedef, izinli_kok=kok)
        self.kuyruk = OnayKuyrugu(klasor=hedef, izinli_kok=kok)
        self.durum_yolu = self.kuyruk.klasor / "state.json"
        self.durum = yukle_veya_varsayilan(self.durum_yolu)

    # -- Baglam kurma --------------------------------------------------------

    def baglam(self, soru: str) -> str:
        """
        Modele verilecek sistem metnini kurar:
        sabit talimat + onaylanmis bilgiler + hatirlanan konusmalar + durum.
        """
        parcalar = [SISTEM_METNI]

        onaylanmis = self.kuyruk.hafiza()
        if onaylanmis:
            satirlar = "\n".join(f"- {k['metin']}" for k in onaylanmis)
            parcalar.append("Onaylanmis kalici bilgiler:\n" + satirlar)

        hatirlanan = self.hafiza.baglam_metni(soru)
        if hatirlanan:
            parcalar.append(hatirlanan)

        parcalar.append("Su anki durumun: " + self.durum.ozet())
        return "\n\n".join(parcalar)

    # -- Sohbet --------------------------------------------------------------

    def konus(self, girdi: str) -> str:
        """Bir mesaji bastan sona isler ve cevabi dondurur."""
        self.hafiza.ekle(KULLANICI, girdi)
        cevap = self.llm.cevapla(girdi, sistem=self.baglam(girdi))
        self.hafiza.ekle(CEKIRDEK, cevap.metin)

        aday = aday_oner(girdi)
        if aday:
            kayit = self.kuyruk.ekle(aday, kaynak="konusma")
            if kayit.durum == "bekliyor":
                return (
                    f"{cevap.metin}\n"
                    f"   (not: [{kayit.no}] numarali aday onay kuyruguna kondu, "
                    f"HENUZ ogrenmedim. /listele ile bakabilirsin.)"
                )
        return cevap.metin

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

        if ad in ("onayla", "reddet"):
            if not arg:
                return f"Kullanim: /{ad} <no>"
            try:
                no = int(arg[0])
            except ValueError:
                return f"'{arg[0]}' bir numara degil."
            try:
                if ad == "onayla":
                    kayit = self.kuyruk.onayla(no)
                    return f"Ogrenildi (artik kalici): {kayit['metin']}"
                aday = self.kuyruk.reddet(no, sebep=" ".join(arg[1:]))
                return f"Silindi, hafizaya girmedi: {aday.metin}"
            except KeyError as hata:
                return f"Hata: {hata}"

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
  /listele               onay bekleyen adaylar
  /onayla <no>           adayi hafizaya al
  /reddet <no>           adayi sil
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
    argv = list(sys.argv[1:] if argv is None else argv)
    model_adi = "mock"
    if "--model" in argv:
        yer = argv.index("--model")
        if yer + 1 < len(argv):
            model_adi = argv[yer + 1]

    try:
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

    c = Cekirdek(llm=llm)

    # Uyanma: hafizayi yukle, kisa bir satir yaz, sonra sessizce bekle.
    bekleyen = len(c.kuyruk.bekleyenler())
    yazdir(
        f"Cekirdek uyandi. model: {model_adi} | "
        f"konusma: {c.hafiza.sayi()} mesaj | "
        f"kalici bilgi: {len(c.kuyruk.hafiza())} | "
        f"onay bekleyen: {bekleyen}"
    )
    yazdir("Yardim icin /yardim, cikmak icin /cik yaz.\n")

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
            yazdir("cekirdek> " + c.konus(satir))
        yazdir("")


if __name__ == "__main__":
    raise SystemExit(main())
