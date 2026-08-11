"""
core/ollama_baglanti.py -- OLLAMA SUNUCUSUYLA KONUSMA

NE ISE YARAR?
Ollama, bilgisayarinda arka planda calisan bir program. Ona internet
tarayicisinin site actigi gibi istek gonderiyoruz: "su modele sunu sor",
"su metnin gommesini cikar". Bu dosya o istekleri gonderen tek yer.

NEDEN YENI BIR KUTUPHANE KURMADIK?
Ollama'nin resmi bir Python paketi var (`pip install ollama`) ama kurmadik.
Cunku yaptigi is duz bir HTTP istegi ve bunu Python zaten kendi icinde
yapabiliyor (urllib). CLAUDE.md kurali: yeni bagimlilik eklemeden once neden
gerektigini acikla. Burada gerekmiyor -- 40 satir kod, sifir bagimlilik,
kurulumda bir sey ters gitme ihtimali daha az.

HATA MESAJLARI
Bir sey ters giderse "ConnectionRefusedError" gibi bir sey degil, ne yapman
gerektigini soyleyen Turkce bir cumle gorursun. Hata okumak ogrenilecek bir
sey; okunmasi kolay olsun diye ugrastik.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

VARSAYILAN_SUNUCU = "http://localhost:11434"

# Ollama HER ZAMAN kendi bilgisayarinda calisir. Bu yuzden isteklerimizin
# vekil sunucudan (proxy) gecmesini istemiyoruz: VPN, kurumsal ag ya da bir
# indirme programi ayarladiysa, localhost istegi de oraya yonlenir ve sebebi
# anlasilmaz sekilde patlar. Bos ProxyHandler "hicbir vekil kullanma" demek.
_ACICI = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class OllamaHatasi(Exception):
    """Ollama ile ilgili her sorun. Mesaji Turkce ve ne yapilacagini soyler."""


def istek(
    yol: str,
    govde: dict | None = None,
    sunucu: str = VARSAYILAN_SUNUCU,
    zaman_asimi_sn: float = 120.0,
) -> dict:
    """
    Ollama sunucusuna bir istek gonderir ve cevabi sozluk olarak dondurur.

    yol   : "/api/chat" gibi adres parcasi
    govde : gonderilecek veri (None ise GET istegi olur)
    """
    adres = sunucu.rstrip("/") + yol

    if govde is None:
        talep = urllib.request.Request(adres, method="GET")
    else:
        talep = urllib.request.Request(
            adres,
            data=json.dumps(govde).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

    try:
        with _ACICI.open(talep, timeout=zaman_asimi_sn) as cevap:
            ham = cevap.read().decode("utf-8")
    except urllib.error.HTTPError as hata:
        ayrinti = ""
        try:
            ayrinti = hata.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        if hata.code == 404:
            raise OllamaHatasi(
                f"Ollama '{yol}' istegini bulamadi (404). Genelde sebebi: model "
                f"henuz indirilmemis. Terminalde 'ollama list' ile bak, "
                f"eksikse 'ollama pull <model adi>' ile indir.\n{ayrinti}"
            ) from hata
        raise OllamaHatasi(
            f"Ollama hata dondurdu (kod {hata.code}): {ayrinti}"
        ) from hata
    except urllib.error.URLError as hata:
        raise OllamaHatasi(
            f"Ollama sunucusuna ulasilamadi ({sunucu}).\n"
            "Kontrol listesi:\n"
            "  1. Ollama kurulu mu?         -> ollama --version\n"
            "  2. Arka planda calisiyor mu? -> ollama serve\n"
            "  3. Adres dogru mu?           -> varsayilan http://localhost:11434\n"
            f"Teknik ayrinti: {hata.reason}"
        ) from hata
    except TimeoutError as hata:
        raise OllamaHatasi(
            f"Ollama {zaman_asimi_sn} saniyede cevap vermedi. Model ilk kez "
            "yukleniyorsa uzun surebilir; tekrar dene. Surekli oluyorsa model "
            "ekran kartina sigmiyor olabilir (daha kucuk model dene)."
        ) from hata

    try:
        return json.loads(ham)
    except json.JSONDecodeError as hata:
        raise OllamaHatasi(
            f"Ollama'dan anlasilmayan cevap geldi: {ham[:200]}"
        ) from hata


def modeller(sunucu: str = VARSAYILAN_SUNUCU, zaman_asimi_sn: float = 5.0) -> list[str]:
    """Sunucuda kurulu model isimlerini dondurur. Ulasilamazsa OllamaHatasi."""
    veri = istek("/api/tags", None, sunucu, zaman_asimi_sn)
    return [m.get("name", "") for m in veri.get("models", [])]


def model_var_mi(
    model: str, sunucu: str = VARSAYILAN_SUNUCU, zaman_asimi_sn: float = 5.0
) -> bool:
    """
    Model kurulu mu? Sunucuya ulasilamazsa False doner (hata firlatmaz),
    cunku bu fonksiyon "hazir misin" sorusunu cevaplamak icin kullaniliyor.

    Isim karsilastirmasi hosgorulu: "llama3.1" yazarsan "llama3.1:latest"
    ya da "llama3.1:8b" de kabul edilir.
    """
    try:
        kurulu = modeller(sunucu, zaman_asimi_sn)
    except OllamaHatasi:
        return False

    istenen = (model or "").strip()
    for ad in kurulu:
        if ad == istenen:
            return True
        if ad.split(":")[0] == istenen.split(":")[0] and ":" not in istenen:
            return True
    return False
