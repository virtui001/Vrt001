"""
core/approval.py -- ONAY KUYRUGU

BU DOSYA PROJENIN EN ONEMLI TASARIM KARARIDIR (CLAUDE.md Faz 1, madde 3).

KURAL TEK CUMLE:
    Sistem bir sey ogrenmek istediginde onu DOGRUDAN hafizaya yazamaz.
    Once "aday" olarak kuyruga koyar. Sen onaylarsan hafizaya gecer,
    reddedersen silinir. Onaylanmayan hicbir sey hafizaya giremez.

NEDEN?
Cunku kendi kendine ogrenen bir sistem, yanlis bir seyi ogrendiginde onu
sonsuza kadar dogru sanar. Arada bir insan olmazsa hata birikir ve sistem
sessizce bozulur. Bu kuyruk, o insanin durdugu yerdir.

UC DOSYA VAR (hepsi ./workspace/ icinde):
    onay_kuyrugu.json  -> bekleyen adaylar (henuz hafiza DEGIL)
    hafiza.json        -> ONAYLANMIS bilgiler (kalici hafiza)
    onay_gecmisi.json  -> ne zaman neyi onayladin/reddettin (denetim kaydi)

TERMINAL KOMUTLARI:
    python -m core.approval listele
    python -m core.approval onayla 3          (ya da: onayla 1 4 7 / onayla 1-18)
    python -m core.approval reddet 4
    python -m core.approval ekle "Kullanicinin kedisinin adi Pamuk"
    python -m core.approval tohumla           (proje kurallarini kuyruga koyar)
    python -m core.approval hafiza
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from core.guvenlik import PROJE_KOKU, WORKSPACE, guvenli_klasor
from core.metin import sadelestir

# Cekirdek'in kendisi hakkinda bilmesi gereken kurallar.
# 'tohumla' komutu bunlari kuyruga koyar -- hafizaya DEGIL.
KURALLAR_DOSYASI = PROJE_KOKU / "bilgi" / "proje_kurallari.json"

# Aday durumlari
BEKLIYOR = "bekliyor"
ONAYLANDI = "onaylandi"
REDDEDILDI = "reddedildi"


def _simdi() -> str:
    """Su anki zamani standart (ISO 8601, UTC) metin olarak dondurur."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Aday:
    """
    Kuyruktaki tek bir ogrenme adayi.

    no      : degismeyen sira numarasi. 'onayla 3' derken bu numarayi yazarsin.
              Silme/onaylama sonrasi numaralar KAYMAZ; yanlislikla baskasini
              onaylama riski olmasin diye.
    metin   : ogrenilmek istenen bilgi.
    kaynak  : bu bilgi nereden geldi (konusma, kamera, dosya...). Denetim icin.
    """

    no: int
    metin: str
    kaynak: str = "bilinmiyor"
    olusturma: str = ""
    durum: str = BEKLIYOR
    karar_zamani: str | None = None
    not_: str = ""

    def satir(self) -> str:
        """Terminalde tek satirlik gosterim."""
        return f"[{self.no:>3}] {self.metin}   (kaynak: {self.kaynak})"


class OnayKuyrugu:
    """
    Onay kuyrugunun tamami. Butun dosya okuma/yazma isi burada.

    Kullanim:
        k = OnayKuyrugu()
        k.ekle("Kullanici sabahlari cay iciyor", kaynak="konusma")
        print(k.listele())
        k.onayla(1)          # -> artik hafizada
        k.reddet(2)          # -> silindi, hafizaya girmedi
        print(k.hafiza())
    """

    def __init__(self, klasor: str | Path | None = None, izinli_kok: str | Path | None = None) -> None:
        """
        klasor     : dosyalarin yazilacagi yer. Varsayilan ./workspace/
        izinli_kok : yazmaya izin verilen ust sinir. Varsayilan ./workspace/
                     (Testlerde gecici bir klasor verilebilir; ama gercek
                      kullanimda workspace disina cikmak MUMKUN DEGIL.)
        """
        # Guvenlik kontrolu core/guvenlik.py'de; workspace disina cikilamaz.
        # WORKSPACE'i burada okuyoruz ki testler gecici klasorle degistirebilsin.
        kok = izinli_kok if izinli_kok is not None else WORKSPACE
        self.klasor = guvenli_klasor(klasor if klasor is not None else kok, kok)

        self.kuyruk_dosyasi = self.klasor / "onay_kuyrugu.json"
        self.hafiza_dosyasi = self.klasor / "hafiza.json"
        self.gecmis_dosyasi = self.klasor / "onay_gecmisi.json"

    # -- Ic yardimcilar ------------------------------------------------------

    def _oku(self, dosya: Path) -> list[dict]:
        """Bir JSON listesini okur. Dosya yoksa bos liste doner."""
        if not dosya.exists():
            return []
        try:
            veri = json.loads(dosya.read_text(encoding="utf-8"))
        except json.JSONDecodeError as hata:
            raise ValueError(
                f"{dosya} bozuk görünüyor (gecerli JSON degil): {hata}\n"
                "Dosyayi elle acip duzeltebilir ya da silip bastan baslayabilirsin."
            ) from hata
        if not isinstance(veri, list):
            raise ValueError(f"{dosya} bir liste icermeli, {type(veri).__name__} bulundu.")
        return veri

    def _yaz(self, dosya: Path, veri: list[dict]) -> None:
        """
        JSON listesini diske yazar. Once gecici dosyaya yazip sonra ismini
        degistiriyoruz ki yarim yazilmis bozuk dosya olusmasin.
        """
        gecici = dosya.with_suffix(dosya.suffix + ".tmp")
        gecici.write_text(
            json.dumps(veri, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        gecici.replace(dosya)

    def _gecmise_yaz(self, olay: str, aday: Aday) -> None:
        """Denetim kaydi: kim ne zaman neyi onayladi/reddetti."""
        kayit = self._oku(self.gecmis_dosyasi)
        kayit.append({"olay": olay, "zaman": _simdi(), "aday": asdict(aday)})
        self._yaz(self.gecmis_dosyasi, kayit)

    def _adaylar(self) -> list[Aday]:
        return [Aday(**k) for k in self._oku(self.kuyruk_dosyasi)]

    def _adaylari_kaydet(self, adaylar: list[Aday]) -> None:
        self._yaz(self.kuyruk_dosyasi, [asdict(a) for a in adaylar])

    # -- Genel arayuz --------------------------------------------------------

    def ekle(self, metin: str, kaynak: str = "bilinmiyor") -> Aday:
        """
        Kuyruga yeni bir aday koyar. HAFIZAYA YAZMAZ.

        Ayni metin zaten bekliyorsa ya da zaten onaylanmissa tekrar eklenmez;
        mevcut kayit geri dondurulur. Kuyruk ayni seyle dolup sismesin diye.
        """
        metin = (metin or "").strip()
        if not metin:
            raise ValueError("Bos bir aday eklenemez.")

        adaylar = self._adaylar()

        for a in adaylar:
            if a.durum == BEKLIYOR and sadelestir(a.metin) == sadelestir(metin):
                return a  # zaten kuyrukta

        for h in self.hafiza():
            if sadelestir(h["metin"]) == sadelestir(metin):
                # Zaten onaylanmis; yeniden onaya sunmanin anlami yok.
                return Aday(
                    no=h.get("no", 0), metin=h["metin"], kaynak=h.get("kaynak", ""),
                    olusturma=h.get("olusturma", ""), durum=ONAYLANDI,
                    karar_zamani=h.get("onay_zamani"),
                )

        yeni = Aday(
            no=self._sonraki_no(adaylar),
            metin=metin,
            kaynak=kaynak,
            olusturma=_simdi(),
            durum=BEKLIYOR,
        )
        adaylar.append(yeni)
        self._adaylari_kaydet(adaylar)
        return yeni

    def _sonraki_no(self, adaylar: list[Aday]) -> int:
        """
        Bir sonraki numara: hem kuyrukta hem hafizada kullanilmis en buyuk
        numaranin bir fazlasi. Numaralar asla geri donusturulmez, cunku
        "onayla 3" komutu her zaman ayni seyi kastetmeli.
        """
        kullanilmis = [a.no for a in adaylar]
        kullanilmis += [h.get("no", 0) for h in self.hafiza()]
        kullanilmis += [
            k.get("aday", {}).get("no", 0) for k in self._oku(self.gecmis_dosyasi)
        ]
        return (max(kullanilmis) + 1) if kullanilmis else 1

    def bekleyenler(self) -> list[Aday]:
        """Karar bekleyen adaylar (numara sirasinda)."""
        return sorted(
            [a for a in self._adaylar() if a.durum == BEKLIYOR], key=lambda a: a.no
        )

    def listele(self) -> str:
        """Bekleyen adaylari terminalde gosterilecek metin olarak dondurur."""
        bekleyen = self.bekleyenler()
        if not bekleyen:
            return "Onay bekleyen bir sey yok. Hafizaya hicbir sey eklenmedi."

        satirlar = [f"Onay bekleyen {len(bekleyen)} aday:", ""]
        satirlar += [a.satir() for a in bekleyen]
        satirlar += [
            "",
            "Onaylamak icin : python -m core.approval onayla <no>",
            "Reddetmek icin : python -m core.approval reddet <no>",
        ]
        return "\n".join(satirlar)

    def bul(self, no: int) -> Aday:
        """Numaraya gore bekleyen adayi bulur; yoksa acik hata verir."""
        for a in self._adaylar():
            if a.no == no:
                if a.durum != BEKLIYOR:
                    raise KeyError(f"{no} numarali aday zaten '{a.durum}' durumunda.")
                return a
        raise KeyError(
            f"{no} numarali bekleyen aday yok. 'listele' ile mevcut numaralara bak."
        )

    def onayla(self, no: int) -> dict:
        """
        Adayi hafizaya alir. Hafizaya yazmanin TEK yolu burasidir.
        Baska hicbir fonksiyon hafiza.json'a yazmaz.
        """
        aday = self.bul(no)
        aday.durum = ONAYLANDI
        aday.karar_zamani = _simdi()

        hafiza = self.hafiza()
        hafiza.append(
            {
                "no": aday.no,
                "metin": aday.metin,
                "kaynak": aday.kaynak,
                "olusturma": aday.olusturma,
                "onay_zamani": aday.karar_zamani,
            }
        )
        self._yaz(self.hafiza_dosyasi, hafiza)

        # Onaylanan aday kuyruktan cikar (artik hafizada).
        self._adaylari_kaydet([a for a in self._adaylar() if a.no != no])
        self._gecmise_yaz(ONAYLANDI, aday)
        return hafiza[-1]

    def reddet(self, no: int, sebep: str = "") -> Aday:
        """
        Adayi siler. Hafizaya GECMEZ. Sadece denetim kaydinda izi kalir
        ("neyi reddettim" sorusunu sonradan cevaplayabilelim diye).
        """
        aday = self.bul(no)
        aday.durum = REDDEDILDI
        aday.karar_zamani = _simdi()
        aday.not_ = sebep

        self._adaylari_kaydet([a for a in self._adaylar() if a.no != no])
        self._gecmise_yaz(REDDEDILDI, aday)
        return aday

    def tohumla(self, dosya: str | Path | None = None) -> list[Aday]:
        """
        bilgi/proje_kurallari.json icindeki kurallari KUYRUGA koyar.

        DIKKAT: hafizaya koymaz. Projenin kendi kurallari bile onaysiz iceri
        giremez -- kural herkese esit uygulanir, yoksa kural degildir.

        Zaten kuyrukta ya da hafizada olanlar tekrar eklenmez, bu yuzden
        komutu iki kez calistirmak zararsizdir.
        """
        dosya = Path(dosya) if dosya else KURALLAR_DOSYASI
        if not dosya.exists():
            raise ValueError(f"Kural dosyasi bulunamadi: {dosya}")

        try:
            veri = json.loads(dosya.read_text(encoding="utf-8"))
        except json.JSONDecodeError as hata:
            raise ValueError(f"{dosya} gecerli bir JSON degil: {hata}") from hata

        # Once kuyrukta hali hazirda hangi numaralar var, onu not ediyoruz.
        # ekle() zaten var olan bir adayi geri donduruyor; onu "yeni eklendi"
        # diye raporlarsak ikinci calistirmada 18 kural eklenmis gibi gorunur.
        oncekiler = {a.no for a in self._adaylar()}

        yeniler = []
        for kural in veri.get("kurallar", []):
            metin = (kural.get("metin") or "").strip()
            if not metin:
                continue
            aday = self.ekle(metin, kaynak="proje_kurallari")
            if aday.durum == BEKLIYOR and aday.no not in oncekiler:
                yeniler.append(aday)
        return yeniler

    def hafiza(self) -> list[dict]:
        """Onaylanmis (kalici) bilgilerin listesi."""
        return self._oku(self.hafiza_dosyasi)

    def gecmis(self) -> list[dict]:
        """Onay/red kararlarinin denetim kaydi."""
        return self._oku(self.gecmis_dosyasi)


# -- Terminal komutlari ------------------------------------------------------


YARDIM = """Onay kuyrugu komutlari:

  python -m core.approval listele              Bekleyen adaylari gosterir
  python -m core.approval onayla <no...>       Adaylari hafizaya alir
  python -m core.approval reddet <no...>       Adaylari siler
  python -m core.approval ekle "<metin>"       Yeni aday ekler
  python -m core.approval tohumla              Proje kurallarini kuyruga koyar
  python -m core.approval hafiza               Onaylanmis bilgileri gosterir

Numara yazarken:
  onayla 3            tek aday
  onayla 1 4 7        birden fazla aday
  onayla 1-12         araliktaki adaylar

"onayla hepsi" diye bir sey YOK ve olmayacak. Neyi onayladigini her zaman
numarayla soylemen gerekiyor -- listeye bakmadan onaylamak, onay olmaz."""


def main(argv: list[str] | None = None) -> int:
    """
    Terminal girisi. Basarili ise 0, hatali ise 1 dondurur.
    (0 = her sey yolunda, bu Unix geleneğidir; testler de bunu kontrol eder.)
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(YARDIM)
        return 1

    komut = argv[0].lower()
    kuyruk = OnayKuyrugu()

    try:
        if komut == "listele":
            print(kuyruk.listele())

        elif komut == "ekle":
            if len(argv) < 2:
                print("Eksik: eklenecek metni tirnak icinde yaz.")
                return 1
            aday = kuyruk.ekle(" ".join(argv[1:]), kaynak="terminal")
            print(f"Kuyruga eklendi (henuz hafizada DEGIL): {aday.satir()}")

        elif komut == "tohumla":
            yeniler = kuyruk.tohumla()
            if not yeniler:
                print("Eklenecek yeni kural yok (hepsi zaten kuyrukta ya da hafizada).")
            else:
                print(f"{len(yeniler)} proje kurali onay kuyruguna kondu.")
                print("Hicbiri HENUZ ogrenilmedi. Once oku, sonra onayla:\n")
                for a in yeniler:
                    print(f"  [{a.no:>3}] {a.metin}")
                ilk, son = yeniler[0].no, yeniler[-1].no
                print(f"\nHepsini kabul ediyorsan: python -m core.approval onayla {ilk}-{son}")

        elif komut == "onayla":
            numaralar = numaralari_oku(argv)
            for no in numaralar:
                kayit = kuyruk.onayla(no)
                print(f"Onaylandi ve hafizaya alindi: [{no}] {kayit['metin'][:70]}")
            if len(numaralar) > 1:
                print(f"\nToplam {len(numaralar)} bilgi hafizaya alindi.")

        elif komut == "reddet":
            # Sebep yazilabilsin diye: sadece ilk arguman numara/aralik sayilir,
            # gerisi sebep metnidir. Toplu red icin 'reddet 1-5' yeterli.
            numaralar = numaralari_oku(argv[:2])
            sebep = " ".join(argv[2:])
            for no in numaralar:
                aday = kuyruk.reddet(no, sebep)
                print(f"Reddedildi, hafizaya GIRMEDI: [{no}] {aday.metin[:70]}")

        elif komut == "hafiza":
            kayitlar = kuyruk.hafiza()
            if not kayitlar:
                print("Hafiza bos. (Onaylanan hicbir sey yok.)")
            else:
                print(f"Hafizada {len(kayitlar)} onaylanmis bilgi:")
                for k in kayitlar:
                    print(f"  [{k['no']:>3}] {k['metin']}")

        else:
            print(f"Bilinmeyen komut: {komut}\n")
            print(YARDIM)
            return 1

    except (KeyError, ValueError, PermissionError) as hata:
        # Hatayi Turkce ve tek satir gosteriyoruz; yigin izi (traceback) degil.
        print(f"Hata: {hata}")
        return 1

    return 0


def numaralari_oku(argv: list[str]) -> list[int]:
    """
    Komut satirindaki numaralari okur. Uc bicim destekleniyor:
        onayla 3          -> [3]
        onayla 1 4 7      -> [1, 4, 7]
        onayla 1-5        -> [1, 2, 3, 4, 5]

    Sonuc kucukten buyuge sirali ve tekrarsizdir.
    """
    if len(argv) < 2:
        raise ValueError("Numara eksik. Ornek: python -m core.approval onayla 3")

    numaralar: set[int] = set()
    for parca in argv[1:]:
        if "-" in parca[1:]:  # "1-5" aralik; bastaki eksiyi (negatif) sayma
            bas, _, son = parca.partition("-")
            try:
                bas_no, son_no = int(bas), int(son)
            except ValueError:
                raise ValueError(
                    f"'{parca}' gecerli bir aralik degil. Ornek: onayla 1-5"
                ) from None
            if son_no < bas_no:
                raise ValueError(f"'{parca}' tersten yazilmis. Ornek: onayla 1-5")
            numaralar.update(range(bas_no, son_no + 1))
        else:
            try:
                numaralar.add(int(parca))
            except ValueError:
                raise ValueError(
                    f"'{parca}' bir numara degil. Ornek: onayla 3 ya da onayla 1-5"
                ) from None

    return sorted(numaralar)


if __name__ == "__main__":
    raise SystemExit(main())
