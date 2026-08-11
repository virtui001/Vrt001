# Cekirdek

Hafizali, **insan onayli ogrenen**, kademeli olarak duyu ve govde kazanan bir
yapay zeka asistani. Proje planinin tamami [`CLAUDE.md`](CLAUDE.md) dosyasinda.

Depo iki sekilde calisir:

* **Modelsiz** (varsayilan): sahte model ve kelime benzerligiyle. Her sey
  calisir, cevaplar anlamsizdir. Test ve gelistirme icin.
* **Gercek modelle**: bilgisayarinda Ollama varsa `--model ollama` ile.

Donanima gore model secimi ve adim adim kurulum:
[`docs/faz0-kurulum.md`](docs/faz0-kurulum.md).

## Klasor yapisi

```
Vrt001/
├── CLAUDE.md              # Proje brief'i - tum fazlarin plani
├── cekirdek.py            # TERMINAL ARAYUZU - buradan calistirilir
├── requirements.txt       # Bagimliliklar (su an sadece pytest)
├── models/
│   └── state.py           # Durum vektoru semasi (aclik, yorgunluk, ...)
├── core/
│   ├── guvenlik.py        # Yazma sinirir: sadece workspace/
│   ├── ollama_baglanti.py # Ollama sunucusuyla konusma (sifir bagimlilik)
│   ├── metin.py           # Metin sadelestirme (Turkce harflere duyarsiz)
│   ├── llm.py             # Model arayuzu: MockLLM + OllamaLLM
│   ├── memory.py          # Konusma gunlugu + geri cagirma
│   ├── approval.py        # Onay kuyrugu - onaysiz hicbir sey ogrenilmez
│   └── versioning.py      # Surum kaydetme ve geri_al
├── evals/
│   ├── eval_seti.json     # 30 soruluk sabit test
│   └── puanla.py          # Puanlama betigi
├── tests/                 # 261 pytest testi
└── workspace/             # Sistemin yazma izni olan TEK klasor (bos baslar)
```

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Calistirma

```bash
python cekirdek.py                 # modelsiz (sahte cevaplar)
python cekirdek.py --model ollama  # gercek model (Ollama kurulu olmali)
```

Acilista hafizasini yukler, tek satir bilgi yazar ve **sessizce bekler**.
`/` ile baslamayan her sey sohbettir; komutlar:

| Komut | Ne yapar |
|---|---|
| `/durum` | durum vektorunu gosterir |
| `/durum aclik 40` | bir alani ayarlar ve kaydeder |
| `/ogren <metin>` | onay kuyruguna aday ekler (**ogrenmez**) |
| `/listele` | onay bekleyen adaylar |
| `/onayla <no>` | adayi kalici hafizaya alir |
| `/reddet <no>` | adayi siler |
| `/hafiza` | onaylanmis kalici bilgiler |
| `/hatirla <soru>` | gecmis konusmalarda arar |
| `/gecmis [n]` | son n mesaj |
| `/cik` | cikis |

### Tek tek modulleri calistirma

```bash
# Onay kuyrugu
python -m core.approval listele
python -m core.approval onayla 1

# Surum yonetimi (once eval'i calistirir, puan dusukse commit atmaz)
python -m core.versioning listele
python -m core.versioning kaydet "ne degisti" --etiket v0.1.1
python -m core.versioning geri_al v0.1.0            # once ne olacagini gosterir
python -m core.versioning geri_al v0.1.0 --uygula   # gercekten yapar

# 30 soruluk eval
python -m evals.puanla                    # 0/30  - sabit cevap veren model
python -m evals.puanla --cevap-anahtari   # 30/30 - dogru cevaplari bilen model
python -m evals.puanla --model ollama --ollama-model qwen2.5:7b   # gercek model

# Testler
pytest -q
```

## Iki hafiza var, karistirmayin

| | Konusma gunlugu | Kalici hafiza |
|---|---|---|
| Dosya | `workspace/konusma_gunlugu.json` | `workspace/hafiza.json` |
| Nasil dolar | otomatik, her mesajda | **sadece senin onayinla** |
| Ne der | "sunu konustuk" | "bu boyledir" |
| Kod | `core/memory.py` | `core/approval.py` |

Konusma gunlugu bir ses kayit cihazidir; bir seyin dogru oldugunu iddia etmez.
Sistemin bir bilgiyi **ogrenmesi** icin onay kuyrugundan gecmesi gerekir.

## Bilinen sinir

Modelsiz calisirken gomme (embedding) uretimi `BasitGomucu` ile yapiliyor:
kelimeleri ve 4 harflik parcalari sayar. Bu **kelime benzerligi** yakalar,
**anlam** degil. "kedi" ile "kedimin" eslesir; "gidiyordum" ile "gidecegim"
eslesmez. Bu sinir `tests/test_memory.py` icinde acikca test edilmis durumda.

`ollama pull nomic-embed-text` ile `OllamaGomucu` devreye girer ve arama
anlamsal hale gelir. Gomme modeli yoksa program patlamaz, kelime benzerligine
duser ve bunu acilista soyler.

Ayrica: Ollama'ya baglanan kod gercek bir Ollama sunucusuna karsi degil, onun
cevap seklini taklit eden sahte bir sunucuya karsi test edildi
(`tests/test_ollama.py`). Bilgisayarda ilk calistirmada beklenmedik bir sey
cikabilir; hata mesajlari bunu anlatacak sekilde yazildi.

## Guvenlik sinirlari (pazarlik disi)

- Sistem yalnizca `./workspace/` klasorune yazabilir (`core/guvenlik.py`).
- Onay kuyrugundan gecmeyen hicbir bilgi kalici hafizaya yazilmaz.
- `geri_al` varsayilan olarak hicbir seye dokunmaz; `--uygula` gerekir.
- Geri alma gecmisi silmez; `git revert` ile yeni commit olusturur.
- Internet erisimi izin listesi ile sinirlidir; serbest gezinme yoktur.
