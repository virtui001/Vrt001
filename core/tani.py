"""
core/tani.py -- TESHIS KOMUTU

    python -m core.tani

NE ISE YARAR?
Bir sey calismadiginda "muhtemelen sudur" diye tahmin yurutmek yerine
tek komutla her seyin durumunu gosterir: Python surumu, Ollama ayakta mi,
hangi modeller kurulu, hafizada ne var, sirada ne yapman gerekiyor.

Bir sorunla karsilasirsan once bunu calistir, ciktisini kopyala. Ekrandaki
tablo, hatanin nerede oldugunu genelde tek bakista soyler.

TASARIM KURALI: Bu komut HICBIR SEYI BOZMAZ. Sadece bakar, rapor eder.
Dosya yazmaz, model indirmez, ayar degistirmez. Guvenle calistirilabilir.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from core.guvenlik import PROJE_KOKU, WORKSPACE
from core.terminal import utf8_cikti

# Ekranda gorulecek isaretler. Bilerek ASCII: eski Windows terminallerinde
# emoji ya da ozel karakterler bozuk gorunuyor.
TAMAM = "[ok]"
UYARI = "[!!]"
YOK = "[--]"

# Faz 0 icin beklenen modeller.
SOHBET_MODELI = "llama3.1:8b"
GOMME_MODELI = "nomic-embed-text"


def _satir(isaret: str, baslik: str, ayrinti: str = "") -> str:
    metin = f"  {isaret} {baslik}"
    if ayrinti:
        metin += f": {ayrinti}"
    return metin


def python_kontrol() -> tuple[list[str], list[str]]:
    """Python surumu 3.11+ mi?"""
    satirlar, sorunlar = [], []
    surum = sys.version_info
    metin = f"{surum.major}.{surum.minor}.{surum.micro}"
    if (surum.major, surum.minor) >= (3, 11):
        satirlar.append(_satir(TAMAM, "Python surumu", metin))
    else:
        satirlar.append(_satir(UYARI, "Python surumu", f"{metin} (3.11+ gerekli)"))
        sorunlar.append(
            "Python surumun eski. python.org'dan 3.11 ya da ustunu kur, "
            "kurulumda 'Add python.exe to PATH' kutusunu isaretle."
        )

    satirlar.append(
        _satir(TAMAM, "Isletim sistemi", f"{platform.system()} {platform.release()}")
    )
    satirlar.append(_satir(TAMAM, "Cikti kodlamasi", str(sys.stdout.encoding)))
    return satirlar, sorunlar


def proje_kontrol() -> tuple[list[str], list[str]]:
    """Dogru klasorde miyiz, workspace yazilabilir mi, pytest kurulu mu?"""
    satirlar, sorunlar = [], []

    if (PROJE_KOKU / "CLAUDE.md").exists():
        satirlar.append(_satir(TAMAM, "Proje klasoru", str(PROJE_KOKU)))
    else:
        satirlar.append(_satir(UYARI, "Proje klasoru", "CLAUDE.md bulunamadi"))
        sorunlar.append("Yanlis klasorde olabilirsin. 'cd Vrt001' yazip tekrar dene.")

    # workspace gercekten yazilabiliyor mu? Deneme dosyasi yazip hemen siliyoruz.
    try:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        deneme = WORKSPACE / ".tani_deneme"
        deneme.write_text("deneme", encoding="utf-8")
        deneme.unlink()
        satirlar.append(_satir(TAMAM, "workspace yazilabilir", str(WORKSPACE)))
    except OSError as hata:
        satirlar.append(_satir(UYARI, "workspace yazilamiyor", str(hata)))
        sorunlar.append(
            "workspace klasorune yazilamiyor. Klasor izinlerini kontrol et ya da "
            "projeyi Belgeler gibi yazilabilir bir yere tasi."
        )

    try:
        import pytest  # noqa: F401

        satirlar.append(_satir(TAMAM, "pytest kurulu", ""))
    except ImportError:
        satirlar.append(_satir(YOK, "pytest kurulu degil", ""))
        # Tavsiye isletim sistemine gore degisir; yanlis komut vermek,
        # komut vermemekten kotudur.
        etkinlestir = (
            ".venv\\Scripts\\activate"
            if platform.system() == "Windows"
            else "source .venv/bin/activate"
        )
        sorunlar.append(
            f"Sanal ortam etkin olmayabilir. '{etkinlestir}' yazip "
            "'pip install -r requirements.txt' calistir."
        )

    return satirlar, sorunlar


def ollama_kontrol(sunucu: str | None = None) -> tuple[list[str], list[str]]:
    """Ollama ayakta mi, hangi modeller kurulu?"""
    from core.ollama_baglanti import VARSAYILAN_SUNUCU, OllamaHatasi, modeller

    sunucu = sunucu or VARSAYILAN_SUNUCU
    satirlar, sorunlar = [], []

    try:
        kurulu = modeller(sunucu, zaman_asimi_sn=5.0)
    except OllamaHatasi:
        satirlar.append(_satir(YOK, "Ollama sunucusu", f"ulasilamadi ({sunucu})"))
        sorunlar.append(
            "Ollama calismiyor. Once 'ollama --version' ile kurulu mu diye bak, "
            "kuruluysa 'ollama serve' yaz ya da bilgisayari yeniden baslat."
        )
        return satirlar, sorunlar

    satirlar.append(_satir(TAMAM, "Ollama sunucusu", sunucu))

    if not kurulu:
        satirlar.append(_satir(YOK, "Kurulu model", "hic yok"))
        sorunlar.append(f"Model indirilmemis: 'ollama pull {SOHBET_MODELI}'")
        return satirlar, sorunlar

    satirlar.append(_satir(TAMAM, "Kurulu modeller", ", ".join(sorted(kurulu))))

    # Isim karsilastirmasi hosgorulu: "nomic-embed-text:latest" de sayilir.
    def _var_mi(aranan: str) -> bool:
        return any(ad.split(":")[0] == aranan.split(":")[0] for ad in kurulu)

    if _var_mi(SOHBET_MODELI):
        satirlar.append(_satir(TAMAM, "Sohbet modeli", SOHBET_MODELI))
    else:
        satirlar.append(_satir(UYARI, "Sohbet modeli", f"{SOHBET_MODELI} yok"))
        sorunlar.append(
            f"Sohbet modeli eksik: 'ollama pull {SOHBET_MODELI}' "
            "(ya da kurulu baska bir modeli --ollama-model ile kullan)"
        )

    if _var_mi(GOMME_MODELI):
        satirlar.append(_satir(TAMAM, "Gomme modeli", GOMME_MODELI))
    else:
        satirlar.append(_satir(UYARI, "Gomme modeli", f"{GOMME_MODELI} yok"))
        sorunlar.append(
            f"Gomme modeli eksik: 'ollama pull {GOMME_MODELI}'. Program yine "
            "calisir ama arama anlamsal degil, kelime benzerligiyle yapilir."
        )

    return satirlar, sorunlar


def hafiza_kontrol() -> tuple[list[str], list[str]]:
    """Hafizada ne var? (Sorun degil, durum bilgisi.)"""
    satirlar, sorunlar = [], []
    try:
        from core.approval import OnayKuyrugu
        from core.memory import Hafiza

        kuyruk = OnayKuyrugu()
        hafiza = Hafiza()

        kalici = len(kuyruk.hafiza())
        bekleyen = len(kuyruk.bekleyenler())
        mesaj = hafiza.sayi()

        satirlar.append(_satir(TAMAM, "Konusma gunlugu", f"{mesaj} mesaj"))
        satirlar.append(_satir(TAMAM, "Kalici bilgi", f"{kalici} adet"))
        satirlar.append(_satir(TAMAM, "Onay bekleyen", f"{bekleyen} aday"))

        if kalici == 0:
            sorunlar.append(
                "Kalici hafiza bos. Proje kurallarini yuklemek icin: "
                "'python -m core.approval tohumla', sonra listeye bakip onayla."
            )
        if bekleyen:
            sorunlar.append(
                f"{bekleyen} aday karar bekliyor: 'python -m core.approval listele'"
            )
    except Exception as hata:  # tani komutu asla cokmemeli
        satirlar.append(_satir(UYARI, "Hafiza okunamadi", str(hata)[:80]))
        sorunlar.append(
            "Hafiza dosyalari bozuk olabilir. workspace/ icindeki .json "
            "dosyalarini silip bastan baslayabilirsin (kayitlar kaybolur)."
        )
    return satirlar, sorunlar


def eval_kontrol() -> tuple[list[str], list[str]]:
    """Son eval puani kayitli mi?"""
    satirlar: list[str] = []
    try:
        from evals.puanla import SON_PUAN_DOSYASI, son_puani_oku

        son = son_puani_oku(SON_PUAN_DOSYASI)
        if son:
            satirlar.append(
                _satir(
                    TAMAM,
                    "Son eval puani",
                    f"{son['gecen']}/{son['toplam']} ({son['model']}, {son['zaman'][:10]})",
                )
            )
        else:
            satirlar.append(_satir(YOK, "Son eval puani", "henuz olculmedi"))
    except Exception as hata:
        satirlar.append(_satir(UYARI, "Eval durumu okunamadi", str(hata)[:80]))
    return satirlar, []


def rapor(sunucu: str | None = None) -> tuple[str, bool]:
    """
    Tum kontrolleri calistirir. Doner: (rapor metni, her sey yolunda mi).
    """
    bolumler = [
        ("ORTAM", python_kontrol()),
        ("PROJE", proje_kontrol()),
        ("OLLAMA", ollama_kontrol(sunucu)),
        ("HAFIZA", hafiza_kontrol()),
        ("OLCUM", eval_kontrol()),
    ]

    metin = ["=" * 64, "CEKIRDEK TESHIS RAPORU", "=" * 64]
    tum_sorunlar: list[str] = []

    for baslik, (satirlar, sorunlar) in bolumler:
        metin.append(f"\n{baslik}")
        metin.extend(satirlar)
        tum_sorunlar.extend(sorunlar)

    metin.append("\n" + "=" * 64)
    if not tum_sorunlar:
        metin.append("Her sey yolunda. Sirada: python cekirdek.py --model ollama")
    else:
        metin.append(f"YAPILACAKLAR ({len(tum_sorunlar)}):")
        for i, sorun in enumerate(tum_sorunlar, 1):
            metin.append(f"  {i}. {sorun}")
    metin.append("=" * 64)

    return "\n".join(metin), not tum_sorunlar


def main(argv: list[str] | None = None) -> int:
    utf8_cikti()
    argv = list(sys.argv[1:] if argv is None else argv)

    sunucu = None
    if "--sunucu" in argv:
        yer = argv.index("--sunucu")
        if yer + 1 < len(argv):
            sunucu = argv[yer + 1]

    metin, temiz = rapor(sunucu)
    print(metin)
    # Cikis kodu 0: her sey yolunda. 1: yapilacak bir sey var.
    # (Hata degil -- "su su eksik" demenin makine tarafindaki karsiligi.)
    return 0 if temiz else 1


if __name__ == "__main__":
    raise SystemExit(main())
