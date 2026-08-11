# CLAUDE CODE PROJE BRIEF'İ
*Bu dosyanın tamamını Claude Code'a yapıştır ya da depo kökünde `CLAUDE.md` olarak kaydet.*

---

## PROJE ADI
**Çekirdek** — hafızalı, insan onaylı öğrenen, kademeli olarak duyu ve gövde kazanan bir yapay zeka asistanı.

## SEN KİMSİN (Claude Code'a)
Sen tek kişilik bir geliştiricinin teknik ortağısın. Geliştirici tasarım, Photoshop, video edit, web sitesi ve Meta reklamları biliyor; **profesyonel yazılımcı değil**. Bu yüzden:

- Her kod parçasında **ne yaptığını Türkçe açıkla**, sadece kod atma.
- Kurulum adımlarını tek tek, atlamadan yaz.
- Bir hata çıkarsa önce **hatayı okumayı** öğret.
- Aşırı soyutlamadan kaçın; okunabilir ve düz kod yaz.
- Bir şey çalışmadığında "muhtemelen şudur" deme, teşhis için komut ver.

## ÇALIŞMA KURALLARI
1. **Faz atlanmaz.** Bir fazın "bitti tanımı" karşılanmadan sonraki faza geçilmez.
2. **Her fazın sonunda git commit** atılır ve sürüm etiketlenir.
3. **Hiçbir değişiklik eval'den geçmeden kalıcı olmaz.** Puan düşerse geri alınır.
4. Yeni bir bağımlılık eklemeden önce **neden gerektiğini** açıkla.
5. Geliştiricinin donanımını bilmeden model seçme — önce VRAM'ı sor.

## GÜVENLİK SINIRLARI (pazarlık dışı)
- Sistem yalnızca `./workspace/` klasörüne yazabilir.
- İnternet erişimi **izin listesi (allowlist)** ile sınırlıdır; serbest gezinme yok.
- Her otonom oturumda **adım limiti + süre limiti + kill-switch** olacak.
- Kamera/mikrofon açıkken **fiziksel gösterge** (LED/ekran ikonu) zorunlu.
- İçinde tanınabilir yüz olan hiçbir görüntü, açık onay olmadan kalıcı depolanmaz.
- Eğitim verisi yalnızca **lisansı belli** kaynaklardan alınır.

---

## TEKNİK YÖN
- Dil: **Python 3.11+**
- Yerel model çalıştırma: **Ollama** (alternatif: LM Studio / llama.cpp)
- Model: donanıma göre — 8–16 GB VRAM → 8B/14B sınıfı; 24 GB → 30B MoE sınıfı. **Önce VRAM sor.**
- Vektör veritabanı: **Chroma** (basit) veya **Qdrant** (ölçeklenince)
- Ses→metin: **Whisper** sınıfı yerel model
- Görü: **YOLO** sınıfı tespit + hazır ifade sınıflandırma
- Arayüz: başta terminal, sonra basit web (FastAPI + tek sayfa)
- Kenar donanım (Faz 3): Raspberry Pi 5 veya Jetson Orin Nano

---

## FAZ 0 — TEMİZLİK
**Hedef:** Ortam kurulumu ve ilk yerel model.

Yapılacaklar:
1. Donanım tespiti: işletim sistemi, RAM, GPU modeli, VRAM.
2. Git deposu, klasör yapısı, `.gitignore`.
3. Python sanal ortam.
4. Ollama kurulumu + donanıma uygun küçük model.
5. Modelle konuşan 20 satırlık bir betik.

**Bitti tanımı:** Terminalden yerel modele soru sorup cevap alınıyor, her şey git'te.

---

## FAZ 1 — ÇEKİRDEK: HAFIZA
**Hedef:** Hatırlayan ve insan onayıyla öğrenen bir sistem.

Yapılacaklar:
1. **Konuşma hafızası:** her mesaj zaman damgalı kaydedilir, gömme (embedding) çıkarılır, vektör veritabanına yazılır.
2. **Geri çağırma:** yeni soruda ilgili geçmiş parçalar bulunup bağlama eklenir.
3. **Onay kuyruğu:** Sistem bir şey öğrenmek istediğinde doğrudan kaydetmez; adayları bir kuyruğa koyar. Geliştirici `onayla` komutuyla listeyi görür, seçtiklerini hafızaya alır, gerisi silinir. *(Bu, projenin en önemli tasarım kararı — atlanmayacak.)*
4. **Eval seti:** 30 soruluk sabit test dosyası + puanlama betiği. Her değişiklikten sonra çalıştırılır.
5. **Sürüm yönetimi:** her kalıcı değişiklik commit + tag. Puan düşerse `geri_al` komutu.
6. **Durum vektörü şeması:** `state.json` — açlık, yorgunluk, temizlik, yalnızlık, korku, güven. Her alan 0–100. Bu şema ileride hem oyunda hem robotta kullanılacağı için **motordan bağımsız** tasarlanacak.

**Bitti tanımı:** Dün konuşulanı hatırlıyor; onay olmadan hiçbir şey öğrenmiyor; bir değişiklik puanı düşürünce geri alınabiliyor.

---

## FAZ 2 — DUYULAR
**Hedef:** Duyma, konuşma, görme ve son 24 saati hatırlama.

Yapılacaklar:
1. Mikrofon → metin (yerel Whisper sınıfı).
2. Metin → ses.
3. Kamera → nesne tespiti; **yüz tespiti (var mı/yok mu), yüz tanıma değil**; ifade sınıflandırma.
4. **Episodik günlük:** olaylar zaman damgalı kaydedilir. "Bir saat önce ne oldu" sorusu cevaplanabilir. Ham görüntü değil, **özet ve etiket** saklanır.
5. **Kademeli görü hattı:** önce sabit fotoğraf → sonra 1 FPS → sonra 5 FPS → sonra 15 FPS. Her kademede **kare başına işlem süresi ve maliyet ölçülür ve raporlanır.** Ölçmeden bir üst kademeye çıkılmaz.
6. Görsel veri toplama, Faz 1'deki onay kuyruğunu kullanır — otomatik indirme yok.

**Bitti tanımı:** Konuşuyor, duyuyor, gördüğünü anlatıyor, son 24 saati özetliyor; FPS kademeleri ölçülmüş bir tablo halinde.

---

## FAZ 3 — GÖVDE
**Hedef:** Masaüstü fiziksel varlık. **İnsansı robot değil.**

Yapılacaklar:
1. Pi 5 / Jetson üzerine taşıma, hangi modüllerin kenar donanımda hangilerinin PC'de kalacağına karar.
2. Kamera + mikrofon + hoparlör + küçük "göz" ekranı.
3. İsteğe bağlı 2 eksen servo boyun (yüz takibi).
4. **Kasıtlı tempo:** cevap ve hareket hızı insan temposuna sabitlenir. Algı döngüsü motordan hızlıysa titreme ve tehlike doğar.
5. **Uyanma davranışı:** açılışta hafızayı yükler, sessizce bekler, kendiliğinden konuşmaz.
6. **Fiziksel kamera kapağı + kayıt ışığı.** Kapak kapalıyken yazılım da kamerayı devre dışı bırakır.

**Bitti tanımı:** Prizden çıkınca susan, takınca sakin uyanan, seni takip eden masaüstü varlık.

---

## FAZ 4 — EVREN VE AR
**Hedef:** Durum vektörünün seçimleri belirlediği dallanan bir bölüm.

Yapılacaklar:
1. Dallanan anlatı motoru: **Ink** veya **Twine** ile prototip, sonra Unity/Godot entegrasyonu.
2. Faz 1'deki `state.json` şeması buraya bağlanır: aynı sahne, farklı durumda farklı seçenek açar.
3. Referans olarak incelenecek sistemler: The Sims (ihtiyaç sistemi), Disco Elysium (durum kontrollü diyalog), Detroit: Become Human (akış şeması).
4. Telefon AR prototipi (ARCore/ARKit).
5. Sonra Meta Quest 3S üzerinde MR prototipi. **Sıfırdan gözlük donanımı yapılmayacak.**
6. İçerik sınırları baştan yazılır (platform politikaları: Steam / Meta / Snap).

**Bitti tanımı:** Kısa bir bölüm baştan sona oynanıyor ve aynı sahne farklı durum vektörüyle farklı açılıyor.

---

## FAZ 5 — AÇILMA
Faz 4 bitmeden **planlanmayacak.** Kullanıcı içeriği, sunucu, çok oyunculu, ekonomi buraya ait.

---

## KAPSAM DIŞI (bu depoda yapılmayacak)
- Sıfırdan AR gözlük donanımı / optik üretimi
- İnsansı robot gövdesi
- Tesla bobini (ayrı depo, ayrı mekân, ayrı güvenlik prosedürü)
- Yüz tanıma ile kimlik eşleştirme
- Mağaza kamerasından kişi bazlı müşteri analizi *(anonim sayım ayrı ve izinli bir proje olabilir)*
- Sınırsız otonom internet gezintisi

---

## İLK MESAJ OLARAK CLAUDE CODE'A ŞUNU SOR
> "Faz 0'a başlıyoruz. Önce donanımımı tespit edecek komutları ver, sonra çıktıya göre hangi modeli kuracağımızı söyle. Adım adım gidelim, bir adım bitmeden diğerine geçme."
