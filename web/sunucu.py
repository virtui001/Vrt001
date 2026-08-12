"""
web/sunucu.py -- GORSEL ARAYUZ (WEB SUNUCUSU)

    python -m web.sunucu

Calistirinca tarayicinda acilan bir sayfa verir: http://localhost:8000
Terminal komutu ezberlemene gerek kalmaz, her sey dugmelerle.

GUVENLIK: Sunucu SADECE kendi bilgisayarina acilir (127.0.0.1). Ayni agdaki
baska bir cihaz bile goremez, internetten hic goremez. Bu bilincli bir tercih:
icinde kisisel hafizan var.

NEDEN YENI BIR KUTUPHANE KURMADIK?
CLAUDE.md'de "FastAPI" yaziyor ama kurmadik. Python'un kendi icinde bir web
sunucusu var (http.server) ve tek sayfalik bir arayuz icin fazlasiyla yeterli.
Bir bagimlilik eksik = kurulumda ters gidecek bir sey eksik. Arayuz buyurse
FastAPI'ye geceriz, o zaman sebebi de olur.
"""

from __future__ import annotations

import json
import sys
import time
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJE_KOKU = Path(__file__).resolve().parent.parent
if str(PROJE_KOKU) not in sys.path:
    sys.path.insert(0, str(PROJE_KOKU))

from cekirdek import Cekirdek, aday_oner  # noqa: E402
from core.llm import llm_olustur  # noqa: E402
from core.memory import CEKIRDEK, KULLANICI, OllamaGomucu  # noqa: E402
from core.ollama_baglanti import VARSAYILAN_SUNUCU  # noqa: E402
from core.terminal import utf8_cikti  # noqa: E402
from models.state import Durum, kaydet as durum_kaydet  # noqa: E402

SAYFA_DOSYASI = Path(__file__).resolve().parent / "sayfa.html"

# Sunucunun kullanacagi Cekirdek. main() icinde kuruluyor.
_cekirdek: Cekirdek | None = None
_kilit = threading.Lock()  # ayni anda iki istek hafizayi bozmasin
_model_adi = "mock"
_ollama_sunucusu = VARSAYILAN_SUNUCU


def cekirdek_al() -> Cekirdek:
    global _cekirdek
    if _cekirdek is None:
        _cekirdek = Cekirdek(llm=llm_olustur("mock"))
    return _cekirdek


class Islemci(BaseHTTPRequestHandler):
    """Tarayicidan gelen istekleri karsilar."""

    def log_message(self, *_):
        # Python'un kendi istek kaydini kapatiyoruz; onun yerine asagida
        # kendi kisa kaydimizi basiyoruz (bkz. _kayit).
        pass

    def _kayit(self, metin: str) -> None:
        """
        Siyah pencereye tek satirlik bilgi basar.

        NEDEN? Arayuz "dusunuyor..." derken arkada ne oldugunu gorebilmek
        icin. Ilk surumde butun kayitlari kapatmistim ve bir sey takildiginda
        hicbir ipucu kalmiyordu -- bu bir hataydi.
        """
        print(metin, flush=True)

    # -- Yardimcilar ---------------------------------------------------------

    def _json_yaz(self, veri, kod: int = 200):
        govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)

    def _html_yaz(self, metin: str):
        govde = metin.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)

    def _govde_oku(self) -> dict:
        uzunluk = int(self.headers.get("Content-Length", 0))
        if not uzunluk:
            return {}
        try:
            return json.loads(self.rfile.read(uzunluk))
        except json.JSONDecodeError:
            return {}

    # -- GET -----------------------------------------------------------------

    def do_GET(self):
        yol = urlparse(self.path).path
        sorgu = parse_qs(urlparse(self.path).query)

        if yol in ("/", "/index.html"):
            self._html_yaz(SAYFA_DOSYASI.read_text(encoding="utf-8"))
            return

        try:
            if yol == "/api/durum":
                self._json_yaz(self._durum_ozeti())
            elif yol == "/api/kuyruk":
                c = cekirdek_al()
                self._json_yaz(
                    [
                        {"no": a.no, "metin": a.metin, "kaynak": a.kaynak}
                        for a in c.kuyruk.bekleyenler()
                    ]
                )
            elif yol == "/api/hafiza":
                c = cekirdek_al()
                self._json_yaz(
                    [{"no": k["no"], "metin": k["metin"], "kaynak": k.get("kaynak", "")}
                     for k in c.kuyruk.hafiza()]
                )
            elif yol == "/api/gecmis":
                c = cekirdek_al()
                kac = int(sorgu.get("n", ["30"])[0])
                self._json_yaz(
                    [
                        {"rol": m.rol, "metin": m.metin, "zaman": m.zaman}
                        for m in c.hafiza.son(kac)
                    ]
                )
            elif yol == "/api/tani":
                from core.tani import rapor

                metin, temiz = rapor(_ollama_sunucusu if _model_adi == "ollama" else None)
                self._json_yaz({"metin": metin, "temiz": temiz})
            else:
                self._json_yaz({"hata": "Bilinmeyen adres"}, 404)
        except Exception as hata:  # arayuz asla beyaz ekran vermesin
            self._json_yaz({"hata": str(hata)}, 500)

    # -- POST ----------------------------------------------------------------

    def do_POST(self):
        yol = urlparse(self.path).path
        govde = self._govde_oku()

        try:
            with _kilit:  # ayni anda iki islem hafizayi bozmasin
                if yol == "/api/konus":
                    self._json_yaz(self._konus(govde.get("metin", "")))
                elif yol == "/api/karar":
                    self._json_yaz(self._karar(govde))
                elif yol == "/api/ogren":
                    c = cekirdek_al()
                    metin = (govde.get("metin") or "").strip()
                    if not metin:
                        self._json_yaz({"hata": "Bos metin"}, 400)
                        return
                    aday = c.kuyruk.ekle(metin, kaynak="arayuz")
                    self._json_yaz({"no": aday.no, "metin": aday.metin})
                elif yol == "/api/tohumla":
                    c = cekirdek_al()
                    yeniler = c.kuyruk.tohumla()
                    self._json_yaz({"eklenen": len(yeniler)})
                elif yol == "/api/durum":
                    self._json_yaz(self._durum_ayarla(govde))
                else:
                    self._json_yaz({"hata": "Bilinmeyen adres"}, 404)
        except Exception as hata:
            self._kayit(f"!! HATA: {hata}")
            self._json_yaz({"hata": str(hata)}, 500)

    # -- Islemler ------------------------------------------------------------

    def _durum_ozeti(self) -> dict:
        c = cekirdek_al()
        return {
            "durum": c.durum.sozluge_cevir(),
            "model": {
                "ad": _model_adi,
                "hazir": c.llm.hazir_mi(),
                "gercek": _model_adi != "mock",
            },
            "sayilar": {
                "mesaj": c.hafiza.sayi(),
                "kalici": len(c.kuyruk.hafiza()),
                "bekleyen": len(c.kuyruk.bekleyenler()),
            },
            "gomucu": c.hafiza.gomucu.ad,
        }

    def _konus(self, metin: str) -> dict:
        """
        Sohbet. Isin kendisini Cekirdek.konus() yapiyor -- burada sadece
        siyah pencereye ilerleme yaziyoruz. Mantigi burada tekrar yazmak
        (once oyleydi) iki yerde ayri ayri bozulmaya yol aciyordu.
        """
        metin = (metin or "").strip()
        if not metin:
            return {"hata": "Bos mesaj"}

        self._kayit(f"> soru alindi: {metin[:60]}")
        basla = time.perf_counter()

        sonuc = cekirdek_al().konus(metin)

        self._kayit(
            f"< cevap geldi ({time.perf_counter() - basla:.1f} sn)"
            + (f" | aday [{sonuc['aday']['no']}] kuyruga kondu" if sonuc.get("aday") else "")
        )
        return sonuc

    def _karar(self, govde: dict) -> dict:
        c = cekirdek_al()
        numaralar = govde.get("numaralar") or []
        karar = govde.get("karar")
        if karar not in ("onayla", "reddet"):
            return {"hata": "karar 'onayla' ya da 'reddet' olmali"}

        yapilanlar, hatalar = [], []
        for no in numaralar:
            try:
                if karar == "onayla":
                    kayit = c.kuyruk.onayla(int(no))
                    yapilanlar.append(kayit["metin"])
                else:
                    aday = c.kuyruk.reddet(int(no))
                    yapilanlar.append(aday.metin)
            except (KeyError, ValueError) as hata:
                hatalar.append(str(hata))
        return {"karar": karar, "adet": len(yapilanlar), "hatalar": hatalar}

    def _durum_ayarla(self, govde: dict) -> dict:
        c = cekirdek_al()
        alan = govde.get("alan")
        deger = govde.get("deger")
        if alan not in Durum.alan_adlari():
            return {"hata": f"Bilinmeyen alan: {alan}"}
        try:
            c.durum = c.durum.ayarla(**{alan: int(deger)})
        except (ValueError, TypeError) as hata:
            return {"hata": str(hata)}
        durum_kaydet(c.durum, c.durum_yolu)
        return c.durum.sozluge_cevir()


def main(argv: list[str] | None = None) -> int:
    global _cekirdek, _model_adi, _ollama_sunucusu

    utf8_cikti()
    argv = list(sys.argv[1:] if argv is None else argv)

    def _secenek(ad: str, varsayilan: str) -> str:
        if ad in argv:
            yer = argv.index(ad)
            if yer + 1 < len(argv):
                return argv[yer + 1]
        return varsayilan

    _model_adi = _secenek("--model", "ollama")
    _ollama_sunucusu = _secenek("--sunucu", VARSAYILAN_SUNUCU)
    ollama_modeli = _secenek("--ollama-model", "")
    kapi = int(_secenek("--kapi", "8000"))
    tarayici_ac = "--tarayici-acma" not in argv

    # Modeli hazirla. Ollama yoksa sessizce mock'a dusmuyoruz -- soyluyoruz.
    if _model_adi == "ollama":
        ayarlar = {"sunucu": _ollama_sunucusu}
        if ollama_modeli:
            ayarlar["model"] = ollama_modeli
        llm = llm_olustur("ollama", **ayarlar)
        if not llm.hazir_mi():
            print("UYARI: Ollama bulunamadi, sahte modelle aciliyor.")
            print("       Cevaplar anlamsiz olacak. Duzeltmek icin: ollama serve")
            llm = llm_olustur("mock")
            _model_adi = "mock"
    else:
        llm = llm_olustur(_model_adi)

    gomucu = None
    if _model_adi == "ollama":
        aday = OllamaGomucu(sunucu=_ollama_sunucusu)
        if aday.hazir_mi():
            gomucu = aday

    _cekirdek = Cekirdek(llm=llm, gomucu=gomucu)

    # 127.0.0.1: sadece bu bilgisayar. "0.0.0.0" yazsaydik agdaki herkes gorurdu.
    servis = ThreadingHTTPServer(("127.0.0.1", kapi), Islemci)
    adres = f"http://localhost:{kapi}"

    print("=" * 56)
    print("  CEKIRDEK ARAYUZU ACILDI")
    print("=" * 56)
    print(f"  Tarayicida ac: {adres}")
    print(f"  Model        : {_model_adi}")
    print("  Kapatmak icin: bu pencerede Ctrl+C")
    print("=" * 56)

    if tarayici_ac:
        threading.Timer(1.0, lambda: webbrowser.open(adres)).start()

    try:
        servis.serve_forever()
    except KeyboardInterrupt:
        print("\nArayuz kapatildi.")
    finally:
        servis.shutdown()
        servis.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
