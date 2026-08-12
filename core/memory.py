"""
core/memory.py -- KONUSMA HAFIZASI VE GERI CAGIRMA

CLAUDE.md Faz 1, madde 1 ve 2:
    "Her mesaj zaman damgali kaydedilir, gomme (embedding) cikarilir,
     vektor veritabanina yazilir."
    "Yeni soruda ilgili gecmis parcalar bulunup baglama eklenir."

ONEMLI AYRIM -- karistirilmasin:

    KONUSMA GUNLUGU (bu dosya)      ->  ham kayit. Otomatik tutulur.
                                        "Ne konustuk" sorusunu cevaplar.
                                        Bir seyin dogru oldugunu IDDIA ETMEZ.

    KALICI BILGI (core/approval.py) ->  ogrenilmis bilgi. SADECE senin
                                        onayinla girer. "Bu boyledir" der.

Yani konusma gunlugu bir ses kayit cihazidir, hafiza degil. Sistem gunluge
bakip "dun sunu konustuk" diyebilir; ama "kedinin adi Pamuk'tur" diye
ogrenmesi icin senin onayin gerekir. Onay kuyrugu bu yuzden bozulmuyor.

GOMME (EMBEDDING) NEDIR?
Bir cumleyi sayi dizisine cevirmektir. Iki cumlenin sayi dizileri birbirine
benziyorsa cumleler de benziyordur. Boylece "kedimin adi neydi" diye
sorulunca icinde kedi gecen eski mesajlar bulunabilir.

SU AN MODEL YOK, PEKI NASIL CALISIYOR?
BasitGomucu ile. Kelimeleri ve harf parcalarini sayarak vektor uretir.
DURUSTCE SOYLEYELIM: bu ANLAM anlamaz, KELIME BENZERLIGI yakalar.
"kedi" ile "pisi" ayni sayilmaz. Gercek anlamsal arama icin bilgisayara
gecince OllamaGomucu doldurulacak; o zaman bu dosyada baska hicbir sey
degismeyecek, sadece gomucu degisecek.

DOSYA: workspace/konusma_gunlugu.json
"""

from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path

from core.guvenlik import WORKSPACE, guvenli_klasor
from core.metin import kelimeler
from core.ollama_baglanti import (
    VARSAYILAN_SUNUCU,
    OllamaHatasi,
    istek,
    model_var_mi,
)

# Konusmadaki roller
KULLANICI = "kullanici"
CEKIRDEK = "cekirdek"
GECERLI_ROLLER = (KULLANICI, CEKIRDEK)


def _simdi() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- Gomme (embedding) uretenler ---------------------------------------------


class Gomucu(ABC):
    """
    Metni sayi dizisine ceviren seyin sozlesmesi.
    LLM arayuzundeki mantigin aynisi: hafiza hangi gomucuyu kullandigini bilmez.
    """

    ad: str = "gomucu"
    boyut: int = 0

    @abstractmethod
    def gom(self, metin: str) -> list[float]:
        """Metni sabit uzunlukta bir sayi listesine cevirir."""
        raise NotImplementedError

    def hazir_mi(self) -> bool:
        return True


class BasitGomucu(Gomucu):
    """
    MODEL GEREKTIRMEYEN gomucu. Tabletten bile calisir.

    Nasil calisir (uc adim):
      1. Metin kelimelere ayrilir: "Kedinin adi Pamuk" -> [kedinin, adi, pamuk]
      2. Her kelimeden ayrica 4 harflik parcalar cikarilir: kedinin -> kedi,
         edin, dini, inin. Turkce eklerle buyuyen bir dil oldugu icin bu sart:
         "kedi", "kedinin", "kedim" boylece birbirine yakin cikar.
      3. Her parca sabit bir kovaya atilir ve sayilir; sonuc normalize edilir.

    Kova numarasi icin Python'un kendi hash() fonksiyonu KULLANILMAZ; o her
    calistirmada farkli sonuc verir ve diske yazilmis vektorler bozulurdu.
    Onun yerine blake2b kullaniyoruz: her zaman ayni sonucu verir.
    """

    ad = "basit"

    # Kac kova? Az kova = farkli kelimeler ayni kovaya duser ("carpisma") ve
    # alakasiz mesajlar benzer gorunur. Ornek cumlelerle olctuk:
    #    256 kova  -> alakasiz sorguda 0.20'ye kadar sahte benzerlik
    #   1024 kova  -> 0.10
    #   4096 kova  -> 0.09'un altinda  (secilen)
    # Vektorun neredeyse tamami sifir oldugu ve diske seyrek yazildigi icin
    # (asagidaki seyreklestir fonksiyonu) 4096 kova yer olarak bedavaya geliyor.
    def __init__(self, boyut: int = 4096) -> None:
        if boyut < 8:
            raise ValueError("Boyut en az 8 olmali.")
        self.boyut = boyut

    def gom(self, metin: str) -> list[float]:
        vektor = [0.0] * self.boyut
        for parca in self._parcalar(metin):
            vektor[self._kova(parca)] += 1.0

        # Uzunlugu 1'e normalize ediyoruz. Boylece uzun mesajlar sirf uzun
        # olduklari icin daha "benzer" cikmiyor.
        uzunluk = math.sqrt(sum(d * d for d in vektor))
        if uzunluk == 0:
            return vektor
        return [d / uzunluk for d in vektor]

    def _parcalar(self, metin: str):
        """
        Bir metinden kova anahtarlarini uretir.

        Kelimenin kendisi ve 4 harflik parcalari AYNI havuza atilir. Bu onemli:
        "kedi" diye arayinca "kedimin" icindeki 'kedi' parcasiyla eslessin diye.
        Ayri havuzlara koyarsak Turkce'de ekli hicbir kelime bulunamaz.
        """
        for kelime in kelimeler(metin):
            yield kelime
            if len(kelime) > 4:
                for i in range(len(kelime) - 3):
                    yield kelime[i : i + 4]

    def _kova(self, parca: str) -> int:
        ozet = hashlib.blake2b(parca.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(ozet, "big") % self.boyut


class OllamaGomucu(Gomucu):
    """
    GERCEK ANLAMSAL GOMUCU -- Ollama'daki gomme modelini kullanir.

    BasitGomucu'dan farki: bu ANLAMA bakar. "gidiyordum" ile "gidecegim"in
    ayni fiil oldugunu, "kedi" ile "pisi"nin yakin oldugunu bilir. BasitGomucu
    bunlari bilemez cunku sadece harfleri sayar.

    Kullanmadan once:
        ollama pull nomic-embed-text     (~275 MB, kucuk ve hizli)

    Vektor boyutu ilk istekte sunucudan ogrenilir; elle yazmiyoruz ki model
    degisirse (ornegin mxbai-embed-large) kod kendini ayarlasin.
    """

    ad = "ollama"

    def __init__(
        self,
        model: str = "nomic-embed-text",
        sunucu: str = VARSAYILAN_SUNUCU,
        zaman_asimi_sn: float = 60.0,
    ) -> None:
        self.model = model
        self.sunucu = sunucu
        self.zaman_asimi_sn = zaman_asimi_sn
        self.boyut = 0  # ilk gom() cagrisinda dolar
        self._adres = ""  # hangi gomme adresi calisiyor (ilk istekte bulunur)

    def gom(self, metin: str) -> list[float]:
        vektor = self._gomme_iste(metin or "")
        if not vektor:
            raise OllamaHatasi(
                "Gomme modeli bos cevap dondurdu. Model dogru mu? "
                f"('ollama pull {self.model}' ile indirilmis olmali)"
            )

        if self.boyut and len(vektor) != self.boyut:
            raise OllamaHatasi(
                f"Vektor boyu degisti ({self.boyut} -> {len(vektor)}). "
                "Model degistiyse eski kayitlar bu modelle uyusmaz."
            )
        self.boyut = len(vektor)

        # Uzunlugu 1'e getiriyoruz. benzerlik() fonksiyonu vektorlerin
        # normalize oldugunu varsayiyor; BasitGomucu ile ayni kurala uyalim.
        uzunluk = math.sqrt(sum(d * d for d in vektor))
        if uzunluk == 0:
            return vektor
        return [d / uzunluk for d in vektor]

    def _gomme_iste(self, metin: str) -> list[float]:
        """
        Ollama'dan gomme ister.

        NEDEN IKI ADRES DENIYORUZ?
        Ollama'nin gomme adresi surum icinde degisti:
            eski: /api/embeddings  {"prompt": ...} -> {"embedding": [...]}
            yeni: /api/embed       {"input": ...}  -> {"embeddings": [[...]]}
        Hangi surumun kurulu oldugunu bilmiyoruz ve kullaniciya "once surumunu
        kontrol et" demek istemiyoruz. Once yeni adresi deniyoruz, o yoksa
        eskisine dusuyoruz. Bulunani hatirliyoruz ki her seferinde iki istek
        atmayalim.
        """
        if self._adres != "/api/embeddings":
            try:
                veri = istek(
                    "/api/embed",
                    {"model": self.model, "input": metin},
                    self.sunucu,
                    self.zaman_asimi_sn,
                )
                kume = veri.get("embeddings") or []
                if kume:
                    self._adres = "/api/embed"
                    return list(kume[0])
            except OllamaHatasi:
                # Bu surumde yeni adres yok; eskisini deneyecegiz.
                pass

        veri = istek(
            "/api/embeddings",
            {"model": self.model, "prompt": metin},
            self.sunucu,
            self.zaman_asimi_sn,
        )
        self._adres = "/api/embeddings"
        return list(veri.get("embedding") or [])

    def hazir_mi(self) -> bool:
        return model_var_mi(self.model, self.sunucu, zaman_asimi_sn=5.0)


def seyreklestir(vektor: list[float]) -> dict[str, float]:
    """
    Yogun vektoru seyrek hale getirir: sadece sifir OLMAYAN degerleri saklar.

    Neden? BasitGomucu 4096 kova kullaniyor ama bir cumle bunlarin ancak
    15-20 tanesini doldurur. Hepsini diske yazmak mesaj basina ~80 KB eder;
    sadece dolu olanlari yazmak ~1 KB. Ayni bilgi, 80 kat az yer.

    JSON anahtarlari metin olmak zorunda oldugu icin kova numarasi metne cevrilir.
    """
    return {str(i): d for i, d in enumerate(vektor) if d != 0.0}


def yogunlastir(seyrek: dict[str, float], boyut: int) -> list[float]:
    """seyreklestir()'in tersi: seyrek sozlukten yogun vektore doner."""
    vektor = [0.0] * boyut
    for anahtar, deger in seyrek.items():
        yer = int(anahtar)
        if 0 <= yer < boyut:
            vektor[yer] = deger
    return vektor


def benzerlik(a: list[float], b: list[float]) -> float:
    """
    Iki vektorun ne kadar benzedigi ("kosinus benzerligi").
    1.0 = ayni yone bakiyor (cok benzer), 0.0 = alakasiz.
    Vektorler zaten normalize oldugu icin carpimlarinin toplami yeterli.
    """
    if len(a) != len(b):
        raise ValueError(f"Vektor boylari farkli: {len(a)} ve {len(b)}")
    return sum(x * y for x, y in zip(a, b))


# -- Mesaj ve hafiza ---------------------------------------------------------


@dataclass
class Mesaj:
    """Konusma gunlugundeki tek bir satir."""

    no: int
    rol: str
    metin: str
    zaman: str
    gomucu: str = ""
    boyut: int = 0
    # Gomme seyrek saklanir: {"kova numarasi": deger}. Bkz. seyreklestir().
    gomme: dict[str, float] = field(default_factory=dict)

    def satir(self) -> str:
        kisa_zaman = self.zaman[:16].replace("T", " ")
        kim = "Sen" if self.rol == KULLANICI else "Cekirdek"
        return f"[{kisa_zaman}] {kim}: {self.metin}"


class Hafiza:
    """
    Konusma gunlugu + geri cagirma.

    Kullanim:
        h = Hafiza()
        h.ekle(KULLANICI, "Kedimin adi Pamuk")
        h.ekle(CEKIRDEK, "Not aldim.")
        for mesaj, puan in h.hatirla("kedimin adi neydi"):
            print(puan, mesaj.metin)
    """

    def __init__(
        self,
        klasor: str | Path | None = None,
        izinli_kok: str | Path | None = None,
        gomucu: Gomucu | None = None,
    ) -> None:
        kok = izinli_kok if izinli_kok is not None else WORKSPACE
        self.klasor = guvenli_klasor(klasor if klasor is not None else kok, kok)
        self.dosya = self.klasor / "konusma_gunlugu.json"
        self.gomucu = gomucu or BasitGomucu()

    # -- Dosya islemleri -----------------------------------------------------

    def _oku(self) -> list[dict]:
        if not self.dosya.exists():
            return []
        try:
            veri = json.loads(self.dosya.read_text(encoding="utf-8"))
        except json.JSONDecodeError as hata:
            raise ValueError(
                f"{self.dosya} bozuk (gecerli JSON degil): {hata}"
            ) from hata
        if not isinstance(veri, list):
            raise ValueError(f"{self.dosya} bir liste icermeli.")
        return veri

    def _yaz(self, veri: list[dict]) -> None:
        gecici = self.dosya.with_suffix(self.dosya.suffix + ".tmp")
        gecici.write_text(
            json.dumps(veri, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        gecici.replace(self.dosya)

    # -- Genel arayuz --------------------------------------------------------

    def ekle(self, rol: str, metin: str) -> Mesaj:
        """
        Konusmaya yeni bir mesaj yazar: zaman damgasi + gomme ile birlikte.
        Bu KALICI BILGI DEGILDIR; sadece "sunu konustuk" kaydidir.
        """
        if rol not in GECERLI_ROLLER:
            raise ValueError(
                f"Bilinmeyen rol: {rol!r}. Secenekler: {', '.join(GECERLI_ROLLER)}"
            )
        metin = (metin or "").strip()
        if not metin:
            raise ValueError("Bos mesaj kaydedilemez.")

        ham = self._oku()

        # Once gommeyi hesapla, SONRA boyutu oku. Ters sirada olursa sorun cikar:
        # OllamaGomucu vektor boyunu ilk istekten sonra ogreniyor, once sorarsak
        # 0 yazilir ve her aramada gereksiz yere yeniden hesaplanir.
        vektor = self.gomucu.gom(metin)
        mesaj = Mesaj(
            no=(max((k["no"] for k in ham), default=0) + 1),
            rol=rol,
            metin=metin,
            zaman=_simdi(),
            gomucu=self.gomucu.ad,
            boyut=len(vektor),
            gomme=seyreklestir(vektor),
        )
        ham.append(asdict(mesaj))
        self._yaz(ham)
        return mesaj

    def tumu(self) -> list[Mesaj]:
        """Tum mesajlar, eskiden yeniye."""
        return [Mesaj(**k) for k in self._oku()]

    def son(self, kac: int = 10) -> list[Mesaj]:
        """Son N mesaj (eskiden yeniye sirali)."""
        if kac <= 0:
            return []
        return self.tumu()[-kac:]

    def sayi(self) -> int:
        return len(self._oku())

    def hatirla(
        self, soru: str, kac: int = 3, esik: float = 0.10
    ) -> list[tuple[Mesaj, float]]:
        """
        Soruya en cok benzeyen gecmis mesajlari bulur.

        kac  : en fazla kac sonuc
        esik : bu benzerligin altindakiler elenir. Alakasiz seyleri baglama
               eklemek modeli yaniltir; bos donmek daha iyidir.
               0.10 secildi cunku olctugumuzde gercek eslesmeler 0.17 ve
               uzerinde, carpisma kaynakli sahte benzerlikler ise 0.09'un
               altinda kaldi. Esik tam aradaki bosluga konuldu.

        Doner: [(mesaj, benzerlik_puani), ...] en benzerden baslayarak.
        """
        if not (soru or "").strip():
            return []

        soru_vektoru = self.gomucu.gom(soru)
        sonuclar: list[tuple[Mesaj, float]] = []

        for mesaj in self.tumu():
            # Gomucu degistiyse (ornegin Ollama'ya gecildiyse) diskteki eski
            # vektor gecersizdir; o mesajin gommesini anlik yeniden hesapliyoruz.
            if mesaj.gomucu == self.gomucu.ad and mesaj.boyut == self.gomucu.boyut:
                vektor = yogunlastir(mesaj.gomme, mesaj.boyut)
            else:
                vektor = self.gomucu.gom(mesaj.metin)
            puan = benzerlik(soru_vektoru, vektor)
            if puan >= esik:
                sonuclar.append((mesaj, puan))

        # En benzer once; esitlik olursa yeni mesaj once gelsin.
        sonuclar.sort(key=lambda ikili: (ikili[1], ikili[0].no), reverse=True)
        return sonuclar[:kac]

    def baglam_metni(self, soru: str, kac: int = 3) -> str:
        """
        Geri cagrilan mesajlari, modele verilecek duz metne cevirir.
        Hicbir sey bulunamazsa BOS METIN doner -- uydurma baglam eklemeyiz.
        """
        bulunanlar = self.hatirla(soru, kac=kac)
        if not bulunanlar:
            return ""
        satirlar = [f"- {m.satir()}" for m, _ in bulunanlar]
        return "Gecmis konusmalardan hatirladiklarin:\n" + "\n".join(satirlar)

    def temizle(self) -> int:
        """
        Konusma gunlugunu siler. Kac mesaj silindigini dondurur.
        Kalici hafizaya (hafiza.json) DOKUNMAZ.
        """
        adet = self.sayi()
        if self.dosya.exists():
            self.dosya.unlink()
        return adet


if __name__ == "__main__":
    # python -m core.memory  -> gecici bir ornekle calisir, diske yazmaz
    import tempfile

    with tempfile.TemporaryDirectory() as gecici:
        h = Hafiza(klasor=gecici, izinli_kok=gecici)
        h.ekle(KULLANICI, "Kedimin adi Pamuk, tekir bir kedi.")
        h.ekle(CEKIRDEK, "Anladim, not aldim.")
        h.ekle(KULLANICI, "Yarin Ankara'ya gidecegim.")

        print("Toplam mesaj:", h.sayi(), "\n")
        for soru in ["kedimin adi neydi", "nereye gidiyorum"]:
            print(f"Soru: {soru}")
            for mesaj, puan in h.hatirla(soru):
                print(f"   {puan:.2f}  {mesaj.metin}")
            print()
