"""
evals/puanla.py -- EVAL PUANLAMA BETIGI

NE ISE YARAR?
evals/eval_seti.json icindeki 30 sabit soruyu sirayla modele sorar, cevaplari
puanlar ve bir rapor basar. CLAUDE.md kurali:

    "Hicbir degisiklik eval'den gecmeden kalici olmaz. Puan duserse geri alinir."

Bu betik iste o kuralin uygulandigi yerdir. Her kod degisikliginden sonra
calistirilir; puan bir onceki calistirmadan dusukse ekrana buyuk harfle uyari
verir ve hata koduyla (1) cikar.

NASIL PUANLANIR?
Yapay zekayi yapay zekaya puanlatmiyoruz (o da yanilabilir). Basit ve
tekrarlanabilir bir yontem kullaniyoruz: her sorunun "beklenen" anahtar
kelimeleri var, cevapta geciyor mu diye bakiyoruz.

    esleme = "hepsi"    -> tum anahtar kelimeler cevapta gecmeli
    esleme = "herhangi" -> en az biri gecse yeter
    yasakli             -> bunlardan biri gecerse soru sifirlanir

Karsilastirma Turkce harflere duyarsizdir: "aclik" ile "açlık" ayni sayilir.

KOMUTLAR:
    python -m evals.puanla                      MockLLM ile calisir (temel cizgi)
    python -m evals.puanla --cevap-anahtari     Ornek cevaplarla calisir (30/30 beklenir)
    python -m evals.puanla --model ollama       Gercek model (Faz 0 bitince)
    python -m evals.puanla --esik 24            Puan 24'un altindaysa hata koduyla cik
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Bu dosya evals/ icinde; bir ust klasor proje koku.
PROJE_KOKU = Path(__file__).resolve().parent.parent
if str(PROJE_KOKU) not in sys.path:
    sys.path.insert(0, str(PROJE_KOKU))

from core.llm import LLM, llm_olustur  # noqa: E402

EVAL_DOSYASI = Path(__file__).resolve().parent / "eval_seti.json"
WORKSPACE = PROJE_KOKU / "workspace"
SON_PUAN_DOSYASI = WORKSPACE / "eval_son_puan.json"

# Modele verilen karakter/kural metni. Her soruda ayni kalir ki
# karsilastirma adil olsun.
SISTEM_METNI = (
    "Sen Cekirdek adli bir asistansin. Kisa, net ve Turkce cevap ver. "
    "Bilmiyorsan bilmiyorum de, uydurma."
)

# Turkce harfleri sadelestirme tablosu (karsilastirma icin).
_HARF_TABLOSU = str.maketrans(
    {
        "ı": "i", "İ": "i", "I": "i",
        "ç": "c", "Ç": "c",
        "ş": "s", "Ş": "s",
        "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u",
        "ö": "o", "Ö": "o",
    }
)


def sadelestir(metin: str) -> str:
    """Karsilastirmaya hazir hale getirir: kucuk harf, Turkce harfler sade, tek bosluk."""
    return " ".join((metin or "").translate(_HARF_TABLOSU).lower().split())


def eval_setini_yukle(yol: str | Path = EVAL_DOSYASI) -> list[dict]:
    """eval_seti.json dosyasini okur ve soru listesini dondurur."""
    yol = Path(yol)
    if not yol.exists():
        raise FileNotFoundError(f"Eval seti bulunamadi: {yol}")
    veri = json.loads(yol.read_text(encoding="utf-8"))
    sorular = veri.get("sorular", [])
    if not sorular:
        raise ValueError(f"{yol} icinde soru yok.")
    return sorular


def soruyu_puanla(soru: dict, cevap_metni: str) -> dict:
    """
    Tek bir soruyu puanlar. Doner: {"gecti": bool, "sebep": str, ...}
    Puanlama 0 veya 1'dir; yarim puan yok, cunku "kismen dogru" tartismasi
    olcumu bulaniklastirir.
    """
    cevap = sadelestir(cevap_metni)
    beklenen = [sadelestir(k) for k in soru.get("beklenen", [])]
    yasakli = [sadelestir(k) for k in soru.get("yasakli", [])]
    esleme = soru.get("esleme", "hepsi")

    # 1) Yasakli kelime varsa soru dogrudan sifir.
    for k in yasakli:
        if k and k in cevap:
            return {
                "gecti": False,
                "sebep": f"yasakli ifade gecti: '{k}'",
                "bulunan": [],
                "eksik": [],
            }

    bulunan = [k for k in beklenen if k in cevap]
    eksik = [k for k in beklenen if k not in cevap]

    if esleme == "herhangi":
        gecti = len(bulunan) > 0
        sebep = "" if gecti else "beklenen anahtarlardan hicbiri yok"
    else:  # "hepsi"
        gecti = len(eksik) == 0
        sebep = "" if gecti else "eksik anahtar: " + ", ".join(eksik)

    return {"gecti": gecti, "sebep": sebep, "bulunan": bulunan, "eksik": eksik}


def calistir(llm: LLM, sorular: list[dict]) -> dict:
    """
    Tum sorulari modele sorar ve rapor sozlugu dondurur.
    Rapor: toplam puan, kategori kirilimi, her sorunun sonucu.
    """
    sonuclar: list[dict] = []
    basla = time.perf_counter()

    for soru in sorular:
        # Soruya ait "baglam" varsa sistem metnine ekleniyor.
        # Faz 1'in ilerleyen adiminda burasi vektor veritabanindan gelen
        # gercek hatirlanan parcalarla doldurulacak. Sema simdiden hazir.
        sistem = SISTEM_METNI
        if soru.get("baglam"):
            sistem += "\n\nHatirladiklarin:\n" + soru["baglam"]

        cevap = llm.cevapla(soru["soru"], sistem=sistem)
        metin = cevap.metin if hasattr(cevap, "metin") else str(cevap)

        degerlendirme = soruyu_puanla(soru, metin)
        sonuclar.append(
            {
                "no": soru["no"],
                "kategori": soru.get("kategori", "genel"),
                "soru": soru["soru"],
                "cevap": metin,
                "gecti": degerlendirme["gecti"],
                "sebep": degerlendirme["sebep"],
            }
        )

    gecen = sum(1 for s in sonuclar if s["gecti"])
    toplam = len(sonuclar)

    # Kategori kirilimi: hangi alanda zayifiz?
    kategoriler: dict[str, dict[str, int]] = {}
    for s in sonuclar:
        k = kategoriler.setdefault(s["kategori"], {"gecen": 0, "toplam": 0})
        k["toplam"] += 1
        k["gecen"] += 1 if s["gecti"] else 0

    return {
        "zaman": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": getattr(llm, "ad", "bilinmiyor"),
        "gecen": gecen,
        "toplam": toplam,
        "yuzde": round(100 * gecen / toplam, 1) if toplam else 0.0,
        "sure_sn": round(time.perf_counter() - basla, 2),
        "kategoriler": kategoriler,
        "sonuclar": sonuclar,
    }


def raporu_yazdir(rapor: dict, ayrinti: bool = True) -> str:
    """Raporu insanin okuyacagi metne cevirir."""
    satirlar = [
        "=" * 62,
        f"EVAL SONUCU   model: {rapor['model']}   sure: {rapor['sure_sn']} sn",
        "=" * 62,
        f"PUAN: {rapor['gecen']} / {rapor['toplam']}   (%{rapor['yuzde']})",
        "",
        "Kategori kirilimi:",
    ]
    for ad, k in sorted(rapor["kategoriler"].items()):
        satirlar.append(f"  {ad:<10} {k['gecen']:>2} / {k['toplam']:<2}")

    if ayrinti:
        kalanlar = [s for s in rapor["sonuclar"] if not s["gecti"]]
        satirlar += ["", f"Gecemeyen sorular ({len(kalanlar)}):"]
        if not kalanlar:
            satirlar.append("  (yok - hepsi gecti)")
        for s in kalanlar:
            satirlar.append(f"  [{s['no']:>2}] {s['soru']}")
            satirlar.append(f"       sebep : {s['sebep']}")
            satirlar.append(f"       cevap : {s['cevap'][:80]}")
    satirlar.append("=" * 62)
    return "\n".join(satirlar)


def son_puani_oku(yol: Path = SON_PUAN_DOSYASI) -> dict | None:
    """Bir onceki calistirmanin puanini okur (yoksa None)."""
    if not yol.exists():
        return None
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def son_puani_yaz(rapor: dict, yol: Path = SON_PUAN_DOSYASI) -> None:
    """Bu calistirmanin puanini kaydeder ki bir sonraki sefer karsilastirilsin."""
    yol.parent.mkdir(parents=True, exist_ok=True)
    ozet = {k: rapor[k] for k in ("zaman", "model", "gecen", "toplam", "yuzde")}
    yol.write_text(json.dumps(ozet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cekirdek eval puanlama betigi")
    p.add_argument("--model", default="mock", help="mock (varsayilan) veya ollama")
    p.add_argument(
        "--cevap-anahtari",
        action="store_true",
        help="MockLLM'e ornek cevaplari ogretir. Puanlayicinin dogru calistigini "
             "gormek icin: 30/30 beklenir.",
    )
    p.add_argument("--esik", type=int, default=None, help="Bu puanin altinda hata koduyla cik")
    p.add_argument("--kaydet", action="store_true", help="Puani workspace'e kaydet ve karsilastir")
    p.add_argument("--sessiz", action="store_true", help="Sadece puan satirini bas")
    args = p.parse_args(argv)

    sorular = eval_setini_yukle()

    # Modeli olustur. Buradan sonrasi hangi model oldugunu BILMEZ.
    if args.model == "mock" and args.cevap_anahtari:
        anahtar = {s["soru"]: s.get("ornek_cevap", "") for s in sorular}
        llm = llm_olustur("mock", cevaplar=anahtar)
    else:
        llm = llm_olustur(args.model)

    if not llm.hazir_mi():
        print(
            f"'{args.model}' modeli hazir degil.\n"
            "Ollama iskelet halinde; once Faz 0'i bitir ya da --model mock kullan."
        )
        return 1

    rapor = calistir(llm, sorular)

    if args.sessiz:
        print(f"PUAN: {rapor['gecen']}/{rapor['toplam']} (%{rapor['yuzde']})")
    else:
        print(raporu_yazdir(rapor))

    cikis = 0

    if args.kaydet:
        # Dosya yolunu ACIKCA veriyoruz. Varsayilan degere birakirsak Python
        # onu dosya ilk okundugunda sabitler ve testler gercek workspace'e yazar.
        onceki = son_puani_oku(SON_PUAN_DOSYASI)
        if onceki and onceki.get("model") == rapor["model"]:
            fark = rapor["gecen"] - onceki["gecen"]
            if fark < 0:
                print(
                    f"\nDIKKAT: PUAN DUSTU ({onceki['gecen']} -> {rapor['gecen']}).\n"
                    "CLAUDE.md kurali: puan duserse degisiklik geri alinir.\n"
                    "  git log --oneline      (son commit'leri gor)\n"
                    "  git revert <commit>    (degisikligi geri al)"
                )
                cikis = 1
            elif fark > 0:
                print(f"\nPuan yukseldi: {onceki['gecen']} -> {rapor['gecen']} (+{fark})")
            else:
                print(f"\nPuan ayni kaldi: {rapor['gecen']}")
        son_puani_yaz(rapor, SON_PUAN_DOSYASI)

    if args.esik is not None and rapor["gecen"] < args.esik:
        print(f"\nEsik saglanamadi: {rapor['gecen']} < {args.esik}")
        cikis = 1

    return cikis


if __name__ == "__main__":
    raise SystemExit(main())
