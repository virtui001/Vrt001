# FAZ 0 — KURULUM (RTX 3070 / i5-12400F icin)

Bu belge senin donanimina gore yazildi. Adimlari sirayla yap, **bir adim
bitmeden digerine gecme**. Her adimda "ne gormelisin" yaziyor; goremezsen dur.

---

## 0. Donanim ozeti ve model karari

| | |
|---|---|
| Ekran karti | RTX 3070 — **8 GB VRAM** |
| Islemci | i5-12400F (6 cekirdek; "F" = dahili ekran karti yok) |

**Karar: 8B sinifi model.** Sebebi hesap:

| Model sinifi | Diskteki boyut (4 bit) | 8 GB'a sigar mi |
|---|---|---|
| 8B | ~4.7 GB | **Evet**, ustune ~3 GB bosluk kalir |
| 14B | ~8.5 GB | Hayir — yarisi RAM'e taşar, 5-10 kat yavaslar |

Ek detay: 12400**F**'in dahili ekran karti olmadigi icin monitorun 3070'e
takili. Windows masaustu tek basina 0.5-1 GB VRAM kullanir. Bu 8B'yi etkilemez
ama 14B'yi busbutun imkansiz kilar.

CLAUDE.md'deki "8-16 GB VRAM → 8B/14B" araliginin **alt ucundasin**.

---

## 1. Ollama kurulumu

1. <https://ollama.com/download> adresinden Windows surumunu indir, kur.
2. Terminali ac (Windows tusu → "PowerShell" yaz → Enter).
3. Kurulumu dogrula:

```powershell
ollama --version
```

**Ne gormelisin:** `ollama version 0.x.x` gibi bir satir.
**Goremezsen:** kurulum tamamlanmamis ya da terminali yeniden acman gerekiyor.

---

## 2. Modelleri indir

Iki model lazim: biri konusmak, digeri hatirlamak icin.

```powershell
ollama pull llama3.1:8b          # sohbet modeli, ~4.7 GB
ollama pull nomic-embed-text     # gomme modeli, ~275 MB
```

**Ne gormelisin:** yuzde ilerleyen bir indirme cubugu, sonunda `success`.

**Turkce'si zayif gelirse** alternatifler (birini indir, kiyasla):

```powershell
ollama pull qwen2.5:7b
ollama pull gemma2:9b
```

Hangisinin daha iyi oldugunu **tahmin etmeyeceksin, olceceksin** — 5. adimda.

Model isimleri zamanla degisebilir; guncel liste <https://ollama.com/library>.

---

## 3. Ollama calisiyor mu

```powershell
ollama list
```

**Ne gormelisin:** indirdigin modellerin listesi.
**Bos gorunuyorsa:** indirme tamamlanmamis, 2. adima don.

Windows'ta Ollama kurulunca arka planda kendi baslar. Baslamadiysa:

```powershell
ollama serve
```

Bu komut terminali mesgul eder — **kapatma**, yeni bir terminal ac.

---

## 4. Projeyi indir ve kur

```powershell
git clone https://github.com/virtui001/Vrt001.git
cd Vrt001
git checkout claude/phase-1-model-independent-hgrix4

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Ne gormelisin:** satir basinda `(.venv)` yazisi ve `pytest` kurulumu.

Once her sey yerinde mi, onu dogrula:

```powershell
pytest -q
```

**Ne gormelisin:** `259 passed`. Bir tanesi bile kirmizi yanarsa bana getir.

---

## 5. Hangi model daha iyi — olcerek sec

Elinde 30 soruluk bir sinav var. Model olmadan yazildi, tam da bunun icin.

```powershell
python -m evals.puanla --model ollama --ollama-model llama3.1:8b
python -m evals.puanla --model ollama --ollama-model qwen2.5:7b
python -m evals.puanla --model ollama --ollama-model gemma2:9b
```

Ayni 30 soru, ayni puanlama. Hangisi yuksek puan aliyorsa onu kullaniriz.
Cikan raporda kategori kirilimi de var: bir model hafiza sorularinda iyi
digeri genel sorularda iyi olabilir.

Sohbet ederken de ayni secenek gecerli:

```powershell
python cekirdek.py --model ollama --ollama-model qwen2.5:7b
```

**BEKLENTIYI BASTAN SOYLEYEYIM:** ilk denemede puan dusuk cikacak, muhtemelen
30 uzerinden 12-18. Bu modelin kotu oldugu anlamina GELMEZ. Sebebi su: sinavdaki
"onay", "guvenlik" ve "durum" sorulari bu projenin kendi kurallarini soruyor
(orn. "sistem yeni bir bilgi ogrenmek istediginde ne yapar?"). Model bu
kurallari bilemez, cunku ona soylemedik.

Cozumu var ve zaten elimizde: bu kurallari **onay kuyrugundan gecirip kalici
hafizaya koyacagiz**, boylece her soruda modele baglam olarak gidecekler.
Bunu birlikte yapacagiz — ilk puani aldiktan sonra bana getir.

Yani ilk olcum "modelin ham hali", ikinci olcum "sistemin hali" olacak.
Arasindaki fark, kurdugumuz hafizanin ne ise yaradigini gosterecek.

---

## 6. Konus

```powershell
python cekirdek.py --model ollama
```

**Ne gormelisin:**

```
Cekirdek uyandi. model: ollama | konusma: 0 mesaj | kalici bilgi: 0 | onay bekleyen: 0
Yardim icin /yardim, cikmak icin /cik yaz.

sen>
```

Bir sey yaz, cevap gelsin. Sonra sunu dene:

```
sen> Benim kedimin adi Pamuk
sen> /listele
sen> /onayla 1
sen> /hafiza
```

Kedinin adi ancak sen `/onayla` dedikten sonra ogrenilir. Onay kuyrugu boyle
calisiyor.

---

## Bir sey ters giderse

Program artik anlasilir hata mesajlari veriyor. En sik gorulecekler:

**"Ollama sunucusuna ulasilamadi"**
→ Ollama kapali. `ollama serve` calistir ya da bilgisayari yeniden baslat.

**"Ollama ... bulamadi (404) ... ollama pull"**
→ Model indirilmemis. `ollama list` ile bak, eksigi `ollama pull` ile indir.

**"Ollama 120 saniyede cevap vermedi"**
→ Model ilk yuklemede yavas olabilir, tekrar dene. Surekli oluyorsa model
ekran kartina sigmiyordur — daha kucuk bir model dene.

**Cevaplar cok yavas geliyor (saniyede birkac kelime)**
→ Model VRAM'e sigmamis, RAM'den calisiyor. `ollama ps` yaz; `100% GPU`
gormuyorsan sorun budur. Daha kucuk model ya da daha kisa baglam gerekir.

Hangisi olursa olsun: **hata mesajinin tamamini** kopyala ve bana getir.
Tahmin yurutmek yerine mesaji okuyacagiz.

---

## Bittiginde

Faz 0'in "bitti tanimi": terminalden yerel modele soru sorulup cevap aliniyor
ve her sey git'te. 6. adim calistiysa bitmistir.

Sonrasi: 5. adimdaki iki olcumu alip Faz 1'in eksigini kapatmak — projenin
kendi kurallarini onay kuyrugundan gecirip kalici hafizaya koymak.
