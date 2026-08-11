"""
core/versioning.py -- SURUM YONETIMI VE GERI ALMA

CLAUDE.md Faz 1, madde 5:
    "Her kalici degisiklik commit + tag. Puan duserse geri_al komutu."

Bu dosya git'i senin yerine, guvenli ve dar bir kapidan kullanir. Amac:
git ogrenmek zorunda kalmadan "kaydet" ve "geri al" diyebilmen.

UC KOMUT:
    python -m core.versioning listele
    python -m core.versioning kaydet "ne degisti" --etiket v0.1.1
    python -m core.versioning geri_al v0.1.0            (once dener, yazmaz)
    python -m core.versioning geri_al v0.1.0 --uygula   (gercekten yapar)

GUVENLIK TERCIHLERI (bilerek boyle):
  * geri_al VARSAYILAN OLARAK HICBIR SEY YAPMAZ. Once "su su degisecek" der.
    Gercekten yapmasi icin --uygula yazman gerekir. Yanlislikla is kaybetme.
  * Gecmis ASLA silinmez/yeniden yazilmaz. Geri alma islemi 'git revert' ile
    YENI bir commit olusturur. Boylece "geri aldigimi da geri alabilirim".
  * kaydet komutu once eval'i calistirir. Puan esigin altindaysa commit ATMAZ.
    ("Hicbir degisiklik eval'den gecmeden kalici olmaz.")
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJE_KOKU = Path(__file__).resolve().parent.parent

# Commit atarken kullanilacak kimlik. Bilgisayarinda git ayarli degilse bile
# calissin diye her komutta acikca veriliyor.
GIT_ADI = "Cekirdek"
GIT_EPOSTA = "cekirdek@yerel"


class GitHatasi(Exception):
    """Git komutu basarisiz oldugunda firlatilir. Mesaji Turkce ve okunur."""


def _git(*argumanlar: str, depo: str | Path | None = None, hata_ver: bool = True) -> str:
    """
    Bir git komutu calistirir ve ciktisini metin olarak dondurur.

    hata_ver=False dersen basarisizlikta hata firlatmaz, bos metin doner.
    (Ornegin "bu klasor git deposu mu" diye bakarken kullaniyoruz.)
    """
    depo = Path(depo) if depo is not None else PROJE_KOKU
    komut = [
        "git",
        "-C", str(depo),
        "-c", f"user.name={GIT_ADI}",
        "-c", f"user.email={GIT_EPOSTA}",
        *argumanlar,
    ]
    sonuc = subprocess.run(komut, capture_output=True, text=True)
    if sonuc.returncode != 0:
        if not hata_ver:
            return ""
        raise GitHatasi(
            f"git {' '.join(argumanlar)} basarisiz oldu:\n"
            f"{(sonuc.stderr or sonuc.stdout).strip()}"
        )
    return sonuc.stdout.strip()


def depo_mu(depo: str | Path | None = None) -> bool:
    """Bu klasor bir git deposu mu?"""
    return _git("rev-parse", "--git-dir", depo=depo, hata_ver=False) != ""


def temiz_mi(depo: str | Path | None = None) -> bool:
    """
    Kaydedilmemis degisiklik var mi? Temizse True.
    Geri alma islemi oncesi sart: ustune yazilacak is olmasin.
    """
    return _git("status", "--porcelain", depo=depo) == ""


def dal(depo: str | Path | None = None) -> str:
    """Su an hangi daldayiz?"""
    return _git("rev-parse", "--abbrev-ref", "HEAD", depo=depo)


def surumler(depo: str | Path | None = None) -> list[dict]:
    """
    Kayitli surumleri (etiketleri) yeniden eskiye dogru dondurur.
    Her biri: {"etiket": ..., "tarih": ..., "mesaj": ...}
    """
    # Iki sirama olcutu var. Git'te SON yazilan olcut birincildir:
    #   birincil : -creatordate  -> yeni surum once
    #   ikincil  : -v:refname    -> ayni saniyede olusturulan etiketler icin
    #              surum numarasina gore (v0.10.0 > v0.9.0 dogru anlasilir)
    # Tek basina creatordate yeterli degil: saniye hassasiyetinde oldugu icin
    # pes pese olusturulan etiketlerin sirasi rastgele kaliyordu.
    cikti = _git(
        "tag", "--sort=-v:refname", "--sort=-creatordate",
        "--format=%(refname:short)\t%(creatordate:short)\t%(contents:subject)",
        depo=depo,
    )
    surum_listesi = []
    for satir in cikti.splitlines():
        if not satir.strip():
            continue
        parcalar = satir.split("\t")
        surum_listesi.append(
            {
                "etiket": parcalar[0],
                "tarih": parcalar[1] if len(parcalar) > 1 else "",
                "mesaj": parcalar[2] if len(parcalar) > 2 else "",
            }
        )
    return surum_listesi


def surum_var_mi(etiket: str, depo: str | Path | None = None) -> bool:
    return any(s["etiket"] == etiket for s in surumler(depo))


def surum_kaydet(
    mesaj: str, etiket: str | None = None, depo: str | Path | None = None
) -> dict:
    """
    Degisiklikleri commit'ler ve istege bagli olarak etiketler.
    Doner: {"commit": kisa_kimlik, "etiket": ...}
    """
    if not (mesaj or "").strip():
        raise ValueError("Commit mesaji bos olamaz. Ne degistigini bir cumleyle yaz.")

    if not depo_mu(depo):
        raise GitHatasi("Burasi bir git deposu degil.")

    if temiz_mi(depo):
        raise GitHatasi("Kaydedilecek bir degisiklik yok (calisma alani temiz).")

    if etiket and surum_var_mi(etiket, depo):
        raise ValueError(f"'{etiket}' etiketi zaten var. Baska bir isim sec.")

    _git("add", "-A", depo=depo)
    _git("commit", "-m", mesaj, depo=depo)
    kimlik = _git("rev-parse", "--short", "HEAD", depo=depo)

    if etiket:
        _git("tag", "-a", etiket, "-m", mesaj, depo=depo)

    return {"commit": kimlik, "etiket": etiket, "mesaj": mesaj}


def geri_al(etiket: str, depo: str | Path | None = None, uygula: bool = False) -> dict:
    """
    Depoyu, verilen etiketteki haline dondurur.

    uygula=False (varsayilan): HICBIR SEY YAPMAZ. Sadece "su dosyalar
        degisecek" ozetini dondurur. Once buna bakarsin.
    uygula=True: 'git revert' ile YENI bir commit olusturur. Eski commit'ler
        silinmez; istersen bu geri almayi da geri alabilirsin.

    Doner: {"uygulandi": bool, "ozet": ..., "commit": ...}
    """
    if not depo_mu(depo):
        raise GitHatasi("Burasi bir git deposu degil.")

    if not surum_var_mi(etiket, depo):
        mevcut = ", ".join(s["etiket"] for s in surumler(depo)) or "(hic yok)"
        raise ValueError(f"'{etiket}' diye bir surum yok. Mevcut surumler: {mevcut}")

    ozet = _git("diff", "--stat", f"{etiket}..HEAD", depo=depo)

    if not ozet:
        return {
            "uygulandi": False,
            "ozet": f"Zaten '{etiket}' surumundeki haldesin, geri alacak bir sey yok.",
            "commit": None,
        }

    if not uygula:
        return {
            "uygulandi": False,
            "ozet": (
                f"'{etiket}' surumune donulurse degisecekler:\n{ozet}\n\n"
                f"Gercekten yapmak icin: python -m core.versioning geri_al {etiket} --uygula"
            ),
            "commit": None,
        }

    if not temiz_mi(depo):
        raise GitHatasi(
            "Kaydedilmemis degisiklikler var. Geri almadan once ya kaydet "
            "(python -m core.versioning kaydet \"...\") ya da vazgec."
        )

    # --no-commit: once tum degisiklikleri hazirla, sonra tek commit at.
    # Boylece geri alma islemi gecmiste tek ve anlasilir bir adim olur.
    _git("revert", "--no-commit", f"{etiket}..HEAD", depo=depo)
    _git("commit", "-m", f"geri_al: {etiket} surumune donuldu", depo=depo)
    kimlik = _git("rev-parse", "--short", "HEAD", depo=depo)

    return {
        "uygulandi": True,
        "ozet": f"'{etiket}' surumune donuldu. Yeni commit: {kimlik}",
        "commit": kimlik,
    }


# -- Terminal komutlari ------------------------------------------------------

YARDIM = """Surum yonetimi komutlari:

  python -m core.versioning listele
      Kayitli surumleri (etiketleri) gosterir.

  python -m core.versioning kaydet "ne degisti" [--etiket v0.1.1] [--eval-atla]
      Once eval'i calistirir; puan dusukse commit ATMAZ.
      Sonra degisiklikleri commit'ler ve etiketler.

  python -m core.versioning geri_al v0.1.0 [--uygula]
      --uygula yazmazsan sadece ne olacagini gosterir, dosyalara dokunmaz.
"""


def _eval_gecti_mi(esik: int) -> bool:
    """
    Eval'i calistirir. Puan esigin altindaysa False doner.
    Ice aktarma fonksiyonun icinde: core katmani evals'e bagimli olmasin,
    sadece terminal komutu kullanirken yuklensin.
    """
    from evals.puanla import calistir, eval_setini_yukle
    from core.llm import llm_olustur

    sorular = eval_setini_yukle()
    anahtar = {s["soru"]: s["ornek_cevap"] for s in sorular}
    rapor = calistir(llm_olustur("mock", cevaplar=anahtar), sorular)

    print(f"Eval: {rapor['gecen']}/{rapor['toplam']} (esik: {esik})")
    return rapor["gecen"] >= esik


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(YARDIM)
        return 1

    komut = argv[0].lower()

    try:
        if komut == "listele":
            kayitlar = surumler()
            if not kayitlar:
                print("Henuz kayitli surum yok.")
                print("Ilk surumu olusturmak icin: "
                      'python -m core.versioning kaydet "ilk surum" --etiket v0.1.0')
            else:
                print(f"Kayitli {len(kayitlar)} surum (yeniden eskiye):\n")
                for s in kayitlar:
                    print(f"  {s['etiket']:<16} {s['tarih']}  {s['mesaj']}")

        elif komut == "kaydet":
            if len(argv) < 2 or argv[1].startswith("--"):
                print("Eksik: ne degistigini tirnak icinde yaz.")
                return 1
            mesaj = argv[1]
            etiket = None
            if "--etiket" in argv:
                yer = argv.index("--etiket")
                if yer + 1 >= len(argv):
                    print("--etiket yazdin ama etiket ismi vermedin.")
                    return 1
                etiket = argv[yer + 1]

            if "--eval-atla" not in argv:
                if not _eval_gecti_mi(esik=30):
                    print("\nEval esigi saglanmadi. Commit ATILMADI.")
                    print("Once puani duzelt, ya da bilerek atliyorsan --eval-atla yaz.")
                    return 1

            sonuc = surum_kaydet(mesaj, etiket)
            etiket_yazi = f", etiket: {sonuc['etiket']}" if sonuc["etiket"] else ""
            print(f"Kaydedildi. commit: {sonuc['commit']}{etiket_yazi}")

        elif komut == "geri_al":
            if len(argv) < 2:
                print("Eksik: hangi surume donulecek? Ornek: geri_al v0.1.0")
                return 1
            sonuc = geri_al(argv[1], uygula="--uygula" in argv)
            print(sonuc["ozet"])

        else:
            print(f"Bilinmeyen komut: {komut}\n")
            print(YARDIM)
            return 1

    except (GitHatasi, ValueError) as hata:
        print(f"Hata: {hata}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
