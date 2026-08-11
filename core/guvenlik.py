"""
core/guvenlik.py -- YAZMA SINIRI

CLAUDE.md'deki pazarlik disi kural:
    "Sistem yalnizca ./workspace/ klasorune yazabilir."

Bu kuralin TEK uygulandigi yer burasi. Dosyaya yazan her modul (onay kuyrugu,
hafiza, ileride kamera kayitlari) klasorunu buradan alir. Tek yerde olmasinin
sebebi: kurali guclendirmek ya da duzeltmek gerekirse tek dosya degisir,
unutulan bir kose kalmaz.
"""

from __future__ import annotations

from pathlib import Path

# Bu dosya core/ icinde; bir ust klasor proje koku.
PROJE_KOKU = Path(__file__).resolve().parent.parent
WORKSPACE = PROJE_KOKU / "workspace"


def icinde_mi(yol: Path, kok: Path) -> bool:
    """
    yol, kok klasorunun icinde mi? (kokun kendisi de kabul edilir)

    Once .resolve() ile gercek yol bulunur; boylece '../../etc' gibi
    yukari cikma denemeleri de yakalanir.
    """
    try:
        Path(yol).resolve().relative_to(Path(kok).resolve())
        return True
    except ValueError:
        return False


def guvenli_klasor(klasor: str | Path | None, izinli_kok: str | Path | None) -> Path:
    """
    Yazilacak klasoru dogrular ve olusturur.

    klasor     : yazilmak istenen yer (None ise izinli_kok'un kendisi)
    izinli_kok : yazmaya izin verilen ust sinir (None ise ./workspace/)

    Klasor izinli kokun disindaysa PermissionError firlatir. Testlerde
    izinli_kok olarak gecici bir klasor verilebilir; gercek kullanimda
    varsayilan her zaman ./workspace/ olur.
    """
    kok = Path(izinli_kok) if izinli_kok is not None else WORKSPACE
    kok = kok.resolve()
    kok.mkdir(parents=True, exist_ok=True)

    hedef = (Path(klasor) if klasor is not None else kok).resolve()

    if not icinde_mi(hedef, kok):
        raise PermissionError(
            f"Yazma reddedildi. Sistem yalnizca {kok} klasorune yazabilir, "
            f"ama {hedef} istendi."
        )

    hedef.mkdir(parents=True, exist_ok=True)
    return hedef
