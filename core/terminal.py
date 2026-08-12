"""
core/terminal.py -- TERMINAL CIKTISINI GUVENLI HALE GETIRME

SORUN (Windows'a ozel):
Python, ekrana yazi basarken isletim sisteminin "kod sayfasi"ni kullanir.
Windows'ta bu genelde cp1254 ya da cp437'dir ve Turkce harflerin hepsini
tanimaz. Ciktiyi bir dosyaya yonlendirirsen (`> kayit.txt`) ya da eski bir
terminal kullaniyorsan, "Benim adım Ali" gibi bir metni basmaya calisirken
program soyle cokebilir:

    UnicodeEncodeError: 'charmap' codec can't encode character '\\u0131'

Bu, kullanicinin yazdigi metni geri gosterirken oluyor -- yani tam da
programin ise yaramasi gereken anda.

COZUM:
Program baslar baslamaz ciktiyi UTF-8'e sabitliyoruz. errors="replace"
diyoruz ki cok eski bir terminalde bile cokmek yerine, tanimadigi harfin
yerine soru isareti koyup devam etsin. Yazi biraz bozuk gorunur ama program
calismaya devam eder -- cokmekten iyidir.

Linux ve macOS'ta zaten UTF-8 kullanildigi icin bu fonksiyon orada bir sey
degistirmez, zararsizca gecer.
"""

from __future__ import annotations

import sys


def utf8_cikti() -> bool:
    """
    Ekrana yazmayi UTF-8'e sabitler. Basarili olduysa True doner.

    Her main() fonksiyonunun ilk satirinda cagirilir. Cagirmayi unutmak
    Windows'ta programi coktururdu, bu yuzden bir test bunu kontrol ediyor.
    """
    tamam = True
    for akis in (sys.stdout, sys.stderr):
        # reconfigure Python 3.7+ ile geldi. Testlerde stdout bazen sahte bir
        # nesneyle degistirilir ve onda bu metot olmaz; o durumda sessizce gec.
        if hasattr(akis, "reconfigure"):
            try:
                akis.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                # Cok nadir: akis yeniden yapilandirilamiyor. Program yine de
                # calissin; en fazla bazi harfler bozuk gorunur.
                tamam = False
    return tamam
