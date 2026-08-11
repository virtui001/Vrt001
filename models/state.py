"""
models/state.py -- DURUM VEKTORU SEMASI

NE ISE YARAR?
Sistemin "o anki ic hali"ni tutan tek bir veri yapisi. Alti alan var ve
hepsi 0-100 arasi tam sayi:

    aclik      0 = tok            100 = cok ac
    yorgunluk  0 = dinc           100 = bitkin
    temizlik   0 = kirli          100 = tertemiz
    yalnizlik  0 = cevresi kalabalik / ilgi gormus   100 = cok yalniz
    korku      0 = sakin          100 = dehsete dusmus
    guven      0 = hic guvenmiyor 100 = tam guveniyor

DIKKAT: Alanlarin yonu ayni degil. "temizlik" ve "guven" yuksekken IYI,
digerleri yuksekken KOTU. Bu bilerek boyle; ileride oyun tarafinda
"aclik > 70 ise su secenek acilir" gibi kurallar yazacagiz.

NEDEN AYRI VE BAGIMSIZ BIR DOSYA?
CLAUDE.md'deki plana gore bu sema hem Faz 4'teki oyun motorunda hem de
Faz 3'teki robotta kullanilacak. Bu yuzden dosya hicbir seye bagimli degil:
ne modele, ne veritabanina, ne oyun motoruna. Sadece Python'un kendi
kutuphanelerini (dataclasses, json, pathlib) kullanir. Boylece Unity/Godot
tarafina da, Raspberry Pi'ye de aynen tasinabilir.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, fields
from pathlib import Path

# Semanin surumu. Ileride yeni bir alan eklersek (ornegin "agri") bu sayiyi
# artiririz ve eski state.json dosyalarini nasil cevirecegimizi bilirz.
SEMA_SURUMU = 1

# Tum alanlar bu araligin icinde olmak zorunda.
EN_AZ = 0
EN_COK = 100


@dataclass
class Durum:
    """Durum vektoru. Alanlarin varsayilan degerleri 'sakin bir baslangic'tir."""

    aclik: int = 20
    yorgunluk: int = 20
    temizlik: int = 80
    yalnizlik: int = 30
    korku: int = 10
    guven: int = 50

    # -- Yardimcilar ---------------------------------------------------------

    @staticmethod
    def alan_adlari() -> list[str]:
        """Alan isimlerini sirali liste olarak dondurur. Testler ve UI icin."""
        return [f.name for f in fields(Durum)]

    def sozluge_cevir(self) -> dict[str, int]:
        """Durum -> normal Python sozlugu. JSON'a yazmadan once kullanilir."""
        return asdict(self)

    @classmethod
    def sozlukten_olustur(cls, veri: dict) -> "Durum":
        """
        Sozluk -> Durum. Bilinmeyen anahtarlar hata verir (sessizce yutmayiz),
        eksik anahtarlar varsayilan degerini alir.
        """
        if not isinstance(veri, dict):
            raise TypeError(f"Sozluk bekleniyordu, {type(veri).__name__} geldi.")

        bilinen = set(cls.alan_adlari())
        # "_sema_surumu" gibi bas alt cizgili alanlar meta bilgidir, alan degil.
        fazlalik = {k for k in veri if not k.startswith("_")} - bilinen
        if fazlalik:
            raise ValueError(
                "Bilinmeyen alan(lar): " + ", ".join(sorted(fazlalik))
                + ". Beklenen alanlar: " + ", ".join(sorted(bilinen))
            )

        temiz = {k: v for k, v in veri.items() if k in bilinen}
        durum = cls(**temiz)
        durum.dogrula_veya_hata()
        return durum

    # -- Dogrulama -----------------------------------------------------------

    def hatalari_bul(self) -> list[str]:
        """
        Sorunlari Turkce cumleler halinde liste olarak dondurur.
        Bos liste = her sey yolunda. Hata FIRLATMAZ; sadece rapor eder.
        Arayuzde "sunlar yanlis" diye gostermek icin bu kullanilir.
        """
        hatalar: list[str] = []
        for ad in self.alan_adlari():
            deger = getattr(self, ad)
            # bool, Python'da int sayilir ama biz istemiyoruz: True/False durum degeri degil.
            if isinstance(deger, bool) or not isinstance(deger, int):
                hatalar.append(
                    f"'{ad}' tam sayi olmali, ama {type(deger).__name__} geldi ({deger!r})."
                )
                continue
            if deger < EN_AZ or deger > EN_COK:
                hatalar.append(
                    f"'{ad}' {EN_AZ}-{EN_COK} arasinda olmali, ama {deger} verildi."
                )
        return hatalar

    def gecerli_mi(self) -> bool:
        """Kisa cevap: durum gecerli mi?"""
        return not self.hatalari_bul()

    def dogrula_veya_hata(self) -> "Durum":
        """
        Gecerliyse kendini dondurur, degilse ValueError firlatir.
        Kaydetmeden once cagirilir ki bozuk veri diske yazilmasin.
        """
        hatalar = self.hatalari_bul()
        if hatalar:
            raise ValueError("Durum vektoru gecersiz:\n- " + "\n- ".join(hatalar))
        return self

    # -- Degistirme ----------------------------------------------------------

    def degistir(self, **farklar: int) -> "Durum":
        """
        Alanlari GORECELI olarak degistirir ve YENI bir Durum dondurur.
        Ornek: durum.degistir(aclik=+15, yorgunluk=-5)

        Sonuc otomatik olarak 0-100 arasina kirpilir, yani 95 + 20 = 100 olur,
        eksiye dusmez. Boylece "sinir asildi" hatasi ile ugrasmayiz.
        Orijinal nesne degismez (bu bilincli bir tercih: eski hali elde kalir,
        istersek geri donebiliriz).
        """
        bilinen = set(self.alan_adlari())
        fazlalik = set(farklar) - bilinen
        if fazlalik:
            raise ValueError("Bilinmeyen alan(lar): " + ", ".join(sorted(fazlalik)))

        yeni = self.sozluge_cevir()
        for ad, fark in farklar.items():
            if isinstance(fark, bool) or not isinstance(fark, int):
                raise TypeError(f"'{ad}' icin verilen degisim tam sayi olmali.")
            yeni[ad] = _sinirla(yeni[ad] + fark)
        return Durum(**yeni)

    def ayarla(self, **degerler: int) -> "Durum":
        """
        Alanlari MUTLAK degerle ayarlar ve yeni bir Durum dondurur.
        Ornek: durum.ayarla(aclik=0)   -> aclik dogrudan 0 olur.
        Burada kirpma YOK: 0-100 disi bir deger verirsen hata alirsin,
        cunku bu genelde bir yazim hatasidir.
        """
        bilinen = set(self.alan_adlari())
        fazlalik = set(degerler) - bilinen
        if fazlalik:
            raise ValueError("Bilinmeyen alan(lar): " + ", ".join(sorted(fazlalik)))

        yeni = self.sozluge_cevir()
        yeni.update(degerler)
        return Durum(**yeni).dogrula_veya_hata()

    def ozet(self) -> str:
        """Insan okusun diye tek satirlik ozet. Terminalde gostermek icin."""
        return " | ".join(f"{ad}={getattr(self, ad)}" for ad in self.alan_adlari())


def _sinirla(deger: int) -> int:
    """Bir sayiyi 0-100 arasina kirpar. 120 -> 100, -5 -> 0."""
    return max(EN_AZ, min(EN_COK, deger))


# -- Diske yazma / diskten okuma --------------------------------------------


def kaydet(durum: Durum, yol: str | Path) -> Path:
    """
    Durumu JSON dosyasina yazar.

    Iki onemli detay:
    1) Once dogrulanir. Bozuk durum diske YAZILMAZ.
    2) Once gecici bir dosyaya yazilir, sonra ismi degistirilir ("atomik yazma").
       Boylece yazma sirasinda elektrik giderse elimizde yarim/bozuk bir
       state.json kalmaz; ya eski dosya ya yeni dosya olur.
    """
    durum.dogrula_veya_hata()

    yol = Path(yol)
    yol.parent.mkdir(parents=True, exist_ok=True)

    veri = {"_sema_surumu": SEMA_SURUMU}
    veri.update(durum.sozluge_cevir())

    gecici = yol.with_suffix(yol.suffix + ".tmp")
    gecici.write_text(
        json.dumps(veri, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    gecici.replace(yol)
    return yol


def yukle(yol: str | Path) -> Durum:
    """
    JSON dosyasindan Durum okur. Dosya yoksa FileNotFoundError,
    bozuksa acik Turkce mesajli ValueError firlatir.
    """
    yol = Path(yol)
    if not yol.exists():
        raise FileNotFoundError(f"Durum dosyasi bulunamadi: {yol}")

    ham = yol.read_text(encoding="utf-8")
    try:
        veri = json.loads(ham)
    except json.JSONDecodeError as hata:
        raise ValueError(f"{yol} gecerli bir JSON degil: {hata}") from hata

    surum = veri.get("_sema_surumu", SEMA_SURUMU) if isinstance(veri, dict) else None
    if surum is not None and surum > SEMA_SURUMU:
        raise ValueError(
            f"{yol} dosyasi sema surumu {surum} ile yazilmis, "
            f"bu kod en fazla {SEMA_SURUMU} biliyor. Kodu guncelle."
        )

    return Durum.sozlukten_olustur(veri)


def yukle_veya_varsayilan(yol: str | Path) -> Durum:
    """
    Dosya varsa okur, yoksa varsayilan durumu dondurur.
    Ilk calistirmada patlamamak icin pratik bir kisayol.
    """
    try:
        return yukle(yol)
    except FileNotFoundError:
        return Durum()


if __name__ == "__main__":
    # Dosyayi dogrudan calistirinca kucuk bir gosterim yapar:
    #     python -m models.state
    d = Durum()
    print("Varsayilan durum :", d.ozet())
    print("Yemek yedi       :", d.degistir(aclik=-20, yorgunluk=+5).ozet())
    print("Gecerli mi       :", d.gecerli_mi())
