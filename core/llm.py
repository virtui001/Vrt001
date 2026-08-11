"""
core/llm.py -- MODEL ARAYUZU

NE ISE YARAR?
Projenin geri kalani "hangi yapay zeka modelini kullaniyoruz" sorusunu
BILMEMELI. Sadece su sozu bilir:

    "Elimde bir LLM var. Ona metin veririm, bana metin dondurur."

Bu dosya iste o sozu tanimlar (LLM sinifi) ve iki farkli uygulamasini verir:

  1) MockLLM   -> Sahte model. Gercek bir yapay zeka yok, sabit/kayitli
                  cevaplar dondurur. Bilgisayar/GPU olmadan test yapabilmek icin.
  2) OllamaLLM -> Gercek yerel model. SU AN ISKELET. Bilgisayara gecince
                  icini dolduracagiz. Iskelet olmasi kasitli: arayuz bugunden
                  sabitlensin, sonra sadece bir metodun ici yazilsin.

NEDEN BOYLE?
Yarin Ollama'dan LM Studio'ya veya llama.cpp'ye gecersek, projenin geri kalaninda
TEK SATIR degismeyecek. Sadece bu dosyaya yeni bir sinif eklenecek.
Buna "bagimliligi tersine cevirme" denir; sade hali bu kadar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Cevap:
    """
    Modelden donen sonuc. Sadece duz metin degil, cunku ileride
    "hangi model, kac saniye surdu" gibi seyleri de olcecegiz
    (CLAUDE.md Faz 2: 'olcmeden bir ust kademeye cikilmaz').
    """

    metin: str
    model_adi: str = "bilinmiyor"
    sure_sn: float = 0.0
    ek_bilgi: dict = field(default_factory=dict)

    def __str__(self) -> str:  # print(cevap) dendiginde metni gosterir
        return self.metin


class LLM(ABC):
    """
    Tum modellerin uymak zorunda oldugu sozlesme (interface).

    ABC = Abstract Base Class. Bu siniftan dogrudan nesne uretilemez;
    sadece miras alinip @abstractmethod isaretli metotlar doldurulabilir.
    Yani "cevapla" metodunu yazmayi unutan bir model sinifi Python
    tarafindan daha ilk kullanimda reddedilir.
    """

    ad: str = "llm"

    @abstractmethod
    def cevapla(self, istem: str, sistem: str | None = None) -> Cevap:
        """
        istem  : kullanicinin sorusu / verilen gorev metni.
        sistem : modele karakter/kural veren gizli talimat (istege bagli).
        Doner  : Cevap nesnesi.
        """
        raise NotImplementedError

    def hazir_mi(self) -> bool:
        """
        Model su an kullanilabilir mi? (Ollama calisiyor mu, model inmis mi...)
        Varsayilan cevap True; gercek modeller bunu kendine gore ezer.
        Bu sayede "once kontrol et, sonra sor" yazabiliriz.
        """
        return True

    def __repr__(self) -> str:
        return f"<{type(self).__name__} ad={self.ad!r}>"


class MockLLM(LLM):
    """
    SAHTE MODEL -- test icin.

    Iki modda calisir:
      * Sabit cevap: ne sorarsan sor ayni metni doner.
      * Kayitli cevaplar: 'cevaplar' sozlugune soru->cevap yazarsan,
        o sorular icin o cevaplari doner; digerlerinde sabit cevaba duser.

    Neden kayitli cevap? Cunku evals/ klasorundeki 30 soruluk testi
    modelsiz calistirabilelim ve puanlama betiginin dogru calistigini
    gorebilelim istiyoruz. Model YOKKEN de boru hattinin tamami test edilir.

    MockLLM asla internete cikmaz, asla dosya yazmaz, her zaman ayni sonucu
    verir (deterministik). Testin sarti budur.
    """

    ad = "mock"

    def __init__(
        self,
        sabit_cevap: str = "Bu bir test cevabidir.",
        cevaplar: dict[str, str] | None = None,
    ) -> None:
        self.sabit_cevap = sabit_cevap
        self.cevaplar = dict(cevaplar or {})
        # Kendisine sorulan her seyi saklar; testte "ne soruldu" diye bakariz.
        self.gecmis: list[dict[str, str | None]] = []

    def cevapla(self, istem: str, sistem: str | None = None) -> Cevap:
        self.gecmis.append({"istem": istem, "sistem": sistem})

        anahtar = _sadelestir(istem)
        for soru, cevap in self.cevaplar.items():
            if _sadelestir(soru) == anahtar:
                return Cevap(metin=cevap, model_adi=self.ad)

        return Cevap(metin=self.sabit_cevap, model_adi=self.ad)

    def hazir_mi(self) -> bool:
        return True


class OllamaLLM(LLM):
    """
    GERCEK YEREL MODEL -- SU AN ISKELET, CALISMAZ.

    Bilgisayara gecince yapilacaklar (tek tek):
      1. `pip install ollama` (requirements.txt'de yorum satirinda hazir duruyor).
      2. Terminalde `ollama serve` calisiyor mu kontrol et.
      3. Donanima uygun modeli indir. VRAM'e gore:
           8-16 GB VRAM -> 8B/14B sinifi
           24 GB VRAM   -> 30B MoE sinifi
         (CLAUDE.md kurali: donanim bilinmeden model secilmez.)
      4. Asagidaki `cevapla` metodunun icindeki NotImplementedError'i sil,
         yerine ollama cagrisini yaz. Baska HICBIR dosyaya dokunma.

    Metodu simdiden bos birakmamizin sebebi: arayuzun sekli bugun sabitlensin,
    yarin sadece ic kisim dolsun. Boylece bugun yazdigimiz testler yarin da gecerli.
    """

    ad = "ollama"

    def __init__(
        self,
        model: str = "llama3.1:8b",
        sunucu: str = "http://localhost:11434",
        sicaklik: float = 0.7,
        zaman_asimi_sn: float = 120.0,
    ) -> None:
        self.model = model
        self.sunucu = sunucu
        self.sicaklik = sicaklik
        self.zaman_asimi_sn = zaman_asimi_sn

    def cevapla(self, istem: str, sistem: str | None = None) -> Cevap:
        raise NotImplementedError(
            "OllamaLLM henuz doldurulmadi (Faz 1 - modelden bagimsiz kisim).\n"
            "Bilgisayara gecince: pip install ollama, ardindan bu metodun icine\n"
            "ollama.chat(...) cagrisini yaz. core/llm.py disinda degisiklik gerekmez."
        )

    def hazir_mi(self) -> bool:
        # Iskelet oldugu surece durusu net olsun: hazir degil.
        # Doldurulunca burasi sunucuya kucuk bir istek atip True/False donecek.
        return False


# -- Fabrika -----------------------------------------------------------------

# Kullanilabilir modellerin listesi. Yeni bir model eklemek =
# yukariya bir sinif yazip buraya bir satir eklemek. Baska hicbir yer degismez.
KAYITLI_MODELLER: dict[str, type[LLM]] = {
    "mock": MockLLM,
    "ollama": OllamaLLM,
}


def llm_olustur(ad: str = "mock", **ayarlar) -> LLM:
    """
    Isme gore model uretir. Cagiran taraf sadece "mock" ya da "ollama"
    yazar; hangi sinifin kullanildigini bilmesine gerek yoktur.

    Ornek:
        model = llm_olustur("mock")
        print(model.cevapla("Merhaba"))
    """
    anahtar = (ad or "").strip().lower()
    if anahtar not in KAYITLI_MODELLER:
        raise ValueError(
            f"Bilinmeyen model: {ad!r}. "
            f"Secenekler: {', '.join(sorted(KAYITLI_MODELLER))}"
        )
    return KAYITLI_MODELLER[anahtar](**ayarlar)


def _sadelestir(metin: str) -> str:
    """
    Karsilastirma icin metni sadelestirir: bastaki/sondaki bosluklar gider,
    harfler kucuk olur, ic bosluklar tekile iner.
    'Merhaba   DUNYA ' ile 'merhaba dunya' ayni sayilsin diye.
    """
    return " ".join(metin.lower().split())


if __name__ == "__main__":
    # python -m core.llm
    m = llm_olustur("mock", cevaplar={"2+2 kac eder": "4"})
    print("mock hazir mi :", m.hazir_mi())
    print("2+2 kac eder  :", m.cevapla("2+2 kac eder"))
    print("baska bir soru:", m.cevapla("Hava nasil?"))

    o = llm_olustur("ollama")
    print("ollama hazir mi:", o.hazir_mi(), "(iskelet oldugu icin False)")
