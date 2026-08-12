"""
tests/test_terminal.py -- Windows'ta Turkce karakter cokmesi

Bu dosya tek bir seyi koruyor: kullanicinin yazdigi Turkce metin ekrana
basilirken program cokmemeli.

Neden onemli? Windows'ta ciktinin kodlamasi cogu zaman UTF-8 degildir.
"Benim adım Ali" gibi bir metni geri gosterirken program soyle cokebilir:

    UnicodeEncodeError: 'charmap' codec can't encode character '\\u0131'

Yani tam da programin ise yaramasi gereken anda. Cozum: her giris noktasi
basinda utf8_cikti() cagriliyor. Buradaki testler o cagrinin unutulmadigini
dogruluyor.
"""

import io
import sys

import pytest

from core.terminal import utf8_cikti


def test_utf8_cikti_calisir():
    assert utf8_cikti() is True


def test_reconfigure_olmayan_akista_cokmez(monkeypatch):
    """
    Testlerde ve bazi ortamlarda stdout sahte bir nesneyle degistirilir ve
    onda reconfigure metodu olmaz. Program bu durumda cokmemeli.
    """

    class SahteAkis:
        def write(self, _):
            pass

    monkeypatch.setattr(sys, "stdout", SahteAkis())
    monkeypatch.setattr(sys, "stderr", SahteAkis())
    assert utf8_cikti() is True  # sessizce gecti


def test_turkce_metin_dar_kodlamada_cokmez():
    """
    Windows'un dar kod sayfasini taklit ediyoruz (cp1252 Turkce harfleri
    tanimaz). errors='replace' sayesinde program cokmek yerine devam etmeli.
    """
    ham = io.BytesIO()
    akis = io.TextIOWrapper(ham, encoding="cp1252")

    # Once duzeltmeden: cokuyor mu? (sorunun gercek oldugunu gosterir)
    with pytest.raises(UnicodeEncodeError):
        akis.write("Benim adım Ali, kedim Pamuk")
        akis.flush()

    # Simdi utf8_cikti()'nin yaptigini yapiyoruz:
    akis2 = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    akis2.reconfigure(encoding="utf-8", errors="replace")
    akis2.write("Benim adım Ali, kedim Pamuk")
    akis2.flush()  # cokmedi


# -- Giris noktalari cagriyi unutmamis mi? -----------------------------------


@pytest.mark.parametrize(
    "dosya",
    ["cekirdek.py", "core/approval.py", "core/versioning.py", "evals/puanla.py"],
)
def test_her_giris_noktasi_utf8_cagiriyor(dosya):
    """
    Yeni bir komut eklerken bu cagriyi unutmak kolay; unutulursa hata
    sadece Windows'ta ve sadece Turkce harf basilinca ortaya cikar --
    yani bulmasi en zor turden. Bu test onu burada yakalar.
    """
    from pathlib import Path

    kaynak = (Path(__file__).resolve().parent.parent / dosya).read_text(encoding="utf-8")
    assert "utf8_cikti()" in kaynak, f"{dosya} icinde utf8_cikti() cagrisi yok"
