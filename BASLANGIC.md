# BAŞLANGIÇ — sıfırdan, adım adım

Bu belge hiç yazılım bilmeyen biri için yazıldı. Komut ezberlemeyeceksin.
Sırayla git, **her adımın sonunda "ne görmelisin" yazıyor**. Onu görmüyorsan
dur ve o adımı bana getir.

Toplam süre: yaklaşık 30 dakika (çoğu indirme beklemesi).

---

## ADIM 1 — Ollama (yapay zekanın kendisi)

Bu, bilgisayarında çalışacak yapay zeka programı.

1. Tarayıcında şuraya git: **https://ollama.com/download**
2. **"Download for Windows"** düğmesine bas.
3. İnen dosyaya çift tıkla, **Install** de. Bitmesini bekle.

**Ne görmelisin:** Sağ altta, saatin yanında küçük bir lama ikonu belirir.

---

## ADIM 2 — Yapay zeka modelini indir

Ollama boş bir kutu; içine "beyin" indirmemiz lazım. Senin ekran kartın
(RTX 3070, 8 GB) için doğru boyut seçildi.

1. **Windows tuşuna** bas, **`cmd`** yaz, **Enter**'a bas. Siyah bir pencere açılır.
2. Şunu yaz ve Enter'a bas:

   ```
   ollama pull llama3.1:8b
   ```

3. Yüzde ilerleyen bir çubuk göreceksin. **Yaklaşık 4.7 GB**, internetine göre
   5–20 dakika sürer. Bitmesini bekle.
4. Bittiğinde bir de bunu yaz:

   ```
   ollama pull nomic-embed-text
   ```

   Bu küçük (275 MB), hızlı biter. Hatırlama işini yapan parça.

**Ne görmelisin:** Her ikisinin sonunda `success` yazısı.

Bu pencereyi şimdi kapatabilirsin.

---

## ADIM 3 — Python (projenin çalışması için gerekli)

1. Tarayıcında şuraya git: **https://www.python.org/downloads/**
2. Sarı **"Download Python 3.x"** düğmesine bas.
3. İnen dosyaya çift tıkla.
4. **ÇOK ÖNEMLİ:** Açılan ilk ekranın **en altında** bir kutu var:

   > ☐ Add python.exe to PATH

   **BU KUTUYU İŞARETLE.** İşaretlemezsen sonraki adım çalışmaz ve sebebini
   anlamak zor olur. En sık yapılan hata budur.

5. Sonra **"Install Now"**a bas, bitmesini bekle.

**Ne görmelisin:** "Setup was successful" yazısı.

---

## ADIM 4 — Projeyi indir

En kolay yol, klasörü zip olarak indirmek:

1. Tarayıcında şuraya git:
   **https://github.com/virtui001/Vrt001/tree/claude/phase-1-model-independent-hgrix4**
2. Sağ üstteki yeşil **"Code"** düğmesine bas.
3. Açılan menüden **"Download ZIP"**e bas.
4. İnen zip dosyasını bul (genelde *İndirilenler* klasöründe).
5. Üstüne **sağ tıkla** → **"Tümünü ayıkla"** (Extract All) → **Ayıkla**.
6. Ayıklanan klasörü **Masaüstü**ne taşı ve adını `Cekirdek` yap.

**Ne görmelisin:** Masaüstünde `Cekirdek` adlı bir klasör. İçini açtığında
`1-KUR.bat` ve `2-BASLAT.bat` dosyalarını görüyorsun.

> **Not:** Bu yöntemle güncelleme almak için zip'i yeniden indirmen gerekir.
> Sürekli güncelleme alacaksan **GitHub Desktop** daha rahat — ama şimdilik
> zip yeterli, onu sonra kurarız.

---

## ADIM 5 — Kur

`Cekirdek` klasöründe:

1. **`1-KUR.bat`** dosyasına **çift tıkla**.
2. Siyah bir pencere açılır, birkaç satır yazar.

**Ne görmelisin:**

```
[1/3] Python bulundu: 3.x.x
[2/3] Calisma ortami olusturuluyor...
[3/3] Gerekli paketler kuruluyor...

  KURULUM BITTI
```

**"Windows bilgisayarınızı korudu" uyarısı çıkarsa:** *Ek bilgi* → *Yine de
çalıştır*. (Windows, internetten inen her `.bat` dosyasına bunu sorar.)

**"[HATA] Python bulunamadi" yazıyorsa:** 3. adımda o kutuyu işaretlememişsin.
Python'u kaldırıp baştan kur, bu sefer **"Add python.exe to PATH"** kutusunu
işaretle.

Pencereyi kapat.

---

## ADIM 6 — Çalıştır

1. **`2-BASLAT.bat`** dosyasına **çift tıkla**.
2. Siyah pencere açılır ve **tarayıcın kendiliğinden açılır**.

**Ne görmelisin:** Koyu renkli bir sayfa, üstünde **Çekirdek** yazıyor ve
şu sekmeler var: Sohbet · Onay Kuyruğu · Hafıza · Durum · Teşhis

Açılmazsa tarayıcına elle şunu yaz: **http://localhost:8000**

> Siyah pencereyi **kapatma** — o kapanınca program da kapanır.
> Program bitince kapatmak için o pencereyi kapatman yeterli.

---

## ADIM 7 — İlk denemen

Artık komut yok, sadece tıklama.

**a) Konuş.** Sohbet sekmesinde bir şey yaz, Enter'a bas. Cevap gelir.
İlk cevap 10–30 saniye sürebilir (model ilk kez yükleniyor), sonrakiler hızlanır.

**b) Bir şey öğret.** Şunu yaz:

> Benim kedimin adı Pamuk

Cevabın altında sarı bir not çıkacak: *"onay kuyruğuna kondu — henüz ÖĞRENMEDİM"*.
İşte projenin kalbi bu: sen onaylamadan hiçbir şey öğrenilmiyor.

**c) Onayla.** **Onay Kuyruğu** sekmesine geç. Kedinin adını göreceksin.
Kutucuğunu işaretle, **"Seçilenleri öğren"**e bas.

**d) Kontrol et.** **Hafıza** sekmesine geç. Artık orada.

**e) Kuralları yükle.** Onay Kuyruğu sekmesinde en alttaki
**"Proje kurallarını kuyruğa koy"** düğmesine bas. 18 kural gelir.
Hepsini seçip **"Seçilenleri öğren"**e bas. Artık Çekirdek kendi kurallarını
biliyor.

---

## Bir şey ters giderse

**Teşhis** sekmesine geç, **"Yeniden kontrol et"**e bas. Her şeyin durumunu
gösterir ve ne yapman gerektiğini yazar.

Çözemezsen: o ekrandaki yazının **tamamını** kopyalayıp bana getir.
Tahmin yürütmemize gerek kalmaz.

**"sahte model" rozeti görüyorsan:** Ollama çalışmıyor demektir. Cevaplar
anlamsız gelir. Windows tuşu → `cmd` → `ollama serve` yaz, sonra
`2-BASLAT.bat`'ı tekrar çalıştır.
