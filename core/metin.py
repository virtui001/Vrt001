"""
core/metin.py -- Metin sadelestirme yardimcilari

NE ISE YARAR?
"Açlık" ile "aclik", "  Merhaba   DÜNYA " ile "merhaba dunya" karsilastirmalarda
ayni sayilsin diye metinleri standart hale getirir.

NEDEN AYRI DOSYA?
Ayni islev uc yerde birden lazim oluyordu (onay kuyrugu, model, puanlayici,
hafiza). Ucunde de ayri ayri yazmak yerine tek yere koyduk. Tek yerde
duzeltince her yer duzeliyor.
"""

from __future__ import annotations

# Turkce harfleri sade karsiliklarina cevirir. Tabletten yazarken Turkce
# klavye olmayabilir; "aclik" yazan da "açlık" yazan da ayni sonucu almali.
_HARF_TABLOSU = str.maketrans(
    {
        "ı": "i", "İ": "i", "I": "i",
        "ç": "c", "Ç": "c",
        "ş": "s", "Ş": "s",
        "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u",
        "ö": "o", "Ö": "o",
        "â": "a", "î": "i", "û": "u",
    }
)


def sadelestir(metin: str) -> str:
    """
    Kucuk harfe cevirir ve fazla bosluklari tek boslugla degistirir.
    Turkce harfler KORUNUR.
        '  Merhaba   DUNYA ' -> 'merhaba dunya'
    """
    return " ".join((metin or "").lower().split())


def turkcesiz(metin: str) -> str:
    """
    sadelestir()'in yaptigini yapar, ustune Turkce harfleri de sadelestirir.
        'Açlık   YÜKSEK' -> 'aclik yuksek'
    """
    return " ".join((metin or "").translate(_HARF_TABLOSU).lower().split())


def kelimeler(metin: str) -> list[str]:
    """
    Metni kelimelere ayirir. Noktalama isaretleri atilir.
        'Kedinin adi Pamuk!' -> ['kedinin', 'adi', 'pamuk']
    """
    temiz = "".join(h if h.isalnum() else " " for h in turkcesiz(metin))
    return temiz.split()
