"""
core/llm.py -- MODEL ARAYUZU

NE ISE YARAR?
Projenin geri kalani "hangi yapay zeka modelini kullaniyoruz" sorusunu
BILMEMELI. Sadece su sozu bilir:

    "Elimde bir LLM var. Ona metin veririm, bana metin dondurur."

Bu dosya iste o sozu tanimlar (LLM sinifi) ve iki farkli uygulamasini verir:

  1) MockLLM   -> Sahte model. Gercek bir yapay zeka yok, sabit/kayitli
                  cevaplar dondurur. Bilgisayar/GPU olmadan test yapabilmek icin.
  2) OllamaLLM -> Gercek yerel model. Bilgisayarindaki Ollama'ya baglanir.
                  Calismasi icin Ollama'nin acik ve modelin inmis olmasi gerek;
                  degilse hazir_mi() False doner ve sistem mock'a duser.

NEDEN BOYLE?
Yarin Ollama'dan LM Studio'ya veya llama.cpp'ye gecersek, projenin geri kalaninda
TEK SATIR degismeyecek. Sadece bu dosyaya yeni bir sinif eklenecek.
Buna "bagimliligi tersine cevirme" denir; sade hali bu kadar.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from core.metin import sadelestir
from core.ollama_baglanti import (
    VARSAYILAN_SUNUCU,
    OllamaHatasi,
    istek,
    model_var_mi,
)


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
    def cevapla(
        self,
        istem: str,
        sistem: str | None = None,
        gecmis: list[dict] | None = None,
    ) -> Cevap:
        """
        istem  : kullanicinin su anki sorusu.
        sistem : modele karakter/kural veren gizli talimat (istege bagli).
        gecmis : onceki konusma sirasi. [{"rol": "kullanici"|"cekirdek",
                 "metin": ...}, ...] En eskiden yeniye sirali.

        Doner  : Cevap nesnesi.

        GECMIS NEDEN VAR?
        Ilk surumde yoktu ve model her mesaji sifirdan goruyordu. Kullanici
        kendini anlatiyor, hemen ardindan "benimle ilgili ne biliyorsun?"
        diye soruyor ve model "sen ne is yapiyorsun?" diye cevap veriyordu --
        cunku bir onceki mesaji hic gormemisti. Sohbetin sohbet olmasi icin
        onceki siralar da gonderilmek zorunda.
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

    def cevapla(
        self,
        istem: str,
        sistem: str | None = None,
        gecmis: list[dict] | None = None,
    ) -> Cevap:
        self.gecmis.append({"istem": istem, "sistem": sistem, "sohbet": gecmis or []})

        anahtar = sadelestir(istem)
        for soru, cevap in self.cevaplar.items():
            if sadelestir(soru) == anahtar:
                return Cevap(metin=cevap, model_adi=self.ad)

        return Cevap(metin=self.sabit_cevap, model_adi=self.ad)

    def hazir_mi(self) -> bool:
        return True


class OllamaLLM(LLM):
    """
    GERCEK YEREL MODEL -- bilgisayarindaki Ollama'ya baglanir.

    Varsayilan model 'llama3.1:8b': RTX 3070'in 8 GB hafizasina sigan en
    buyuk siniftan. 14B sinifi 8 GB'a SIGMAZ, yarisi RAM'e taşar ve cok
    yavaslar. (Model secimi neden boyle: docs/faz0-kurulum.md)

    Kullanmadan once:
        ollama serve                 (arka planda calissin)
        ollama pull llama3.1:8b      (modeli indir, ~4.7 GB)

    Not: Bu kod gercek bir Ollama sunucusuna karsi degil, onun cevap seklini
    taklit eden sahte bir sunucuya karsi test edildi (tests/test_ollama.py).
    Bilgisayarinda ilk calistirdiginda beklenmedik bir sey cikarsa hata
    mesajini bana getir.
    """

    ad = "ollama"

    def __init__(
        self,
        model: str = "llama3.1:8b",
        sunucu: str = VARSAYILAN_SUNUCU,
        sicaklik: float = 0.7,
        zaman_asimi_sn: float = 180.0,
        azami_parca: int = 400,
    ) -> None:
        self.model = model
        self.sunucu = sunucu
        self.sicaklik = sicaklik
        # Ilk cevap modelin VRAM'e yuklenmesini bekler; bu tek seferlik ve
        # yavastir. 180 saniye onun icin.
        self.zaman_asimi_sn = zaman_asimi_sn
        # Cevabin en fazla kac parca (token) olacagi. Sinirsiz birakinca
        # kucuk modeller bazen sayfalarca yaziyor ve arayuz asili gorunuyor.
        # 400 parca ~ yarim sayfa; sohbet icin fazlasiyla yeterli.
        self.azami_parca = azami_parca

    def cevapla(
        self,
        istem: str,
        sistem: str | None = None,
        gecmis: list[dict] | None = None,
    ) -> Cevap:
        mesajlar = []
        if sistem:
            mesajlar.append({"role": "system", "content": sistem})

        # Onceki siralar. Bizim "cekirdek" dedigimize Ollama "assistant" diyor.
        for eski in gecmis or []:
            rol = "assistant" if eski.get("rol") == "cekirdek" else "user"
            metin = (eski.get("metin") or "").strip()
            if metin:
                mesajlar.append({"role": rol, "content": metin})

        mesajlar.append({"role": "user", "content": istem})

        basla = time.perf_counter()
        veri = istek(
            "/api/chat",
            {
                "model": self.model,
                "messages": mesajlar,
                "stream": False,  # cevabi parca parca degil, tek seferde al
                "options": {
                    "temperature": self.sicaklik,
                    "num_predict": self.azami_parca,
                },
            },
            self.sunucu,
            self.zaman_asimi_sn,
        )
        sure = time.perf_counter() - basla

        metin = (veri.get("message") or {}).get("content", "")
        if not metin:
            raise OllamaHatasi(
                f"Model bos cevap dondurdu. Gelen veri: {str(veri)[:200]}"
            )

        # Olcum bilgileri: kac parca uretti, saniyede kac parca.
        # CLAUDE.md Faz 2 kurali "olcmeden bir ust kademeye cikilmaz" -- olcum
        # aliskanligini bugunden kuruyoruz.
        uretilen = veri.get("eval_count", 0)
        return Cevap(
            metin=metin.strip(),
            model_adi=self.model,
            sure_sn=round(sure, 2),
            ek_bilgi={
                "uretilen_parca": uretilen,
                "parca_hiz": round(uretilen / sure, 1) if sure > 0 else 0.0,
            },
        )

    def hazir_mi(self) -> bool:
        """Ollama calisiyor ve model kurulu mu? Ulasilamazsa False."""
        return model_var_mi(self.model, self.sunucu, zaman_asimi_sn=5.0)


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


if __name__ == "__main__":
    # python -m core.llm
    m = llm_olustur("mock", cevaplar={"2+2 kac eder": "4"})
    print("mock hazir mi :", m.hazir_mi())
    print("2+2 kac eder  :", m.cevapla("2+2 kac eder"))
    print("baska bir soru:", m.cevapla("Hava nasil?"))

    o = llm_olustur("ollama")
    print("ollama hazir mi:", o.hazir_mi(), "(iskelet oldugu icin False)")
