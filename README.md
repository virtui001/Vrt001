# Cekirdek

Hafizali, **insan onayli ogrenen**, kademeli olarak duyu ve govde kazanan bir
yapay zeka asistani. Proje planinin tamami [`CLAUDE.md`](CLAUDE.md) dosyasinda.

Bu depo su an **Faz 1'in modelden bagimsiz kismini** icerir. Yani: burada calisan
hicbir sey bir yapay zeka modeline ihtiyac duymaz. Bilgisayara/GPU'ya gecince
sadece `OllamaLLM` sinifinin ici doldurulacak, geri kalan kod ayni kalacak.

## Klasor yapisi

```
Vrt001/
├── CLAUDE.md            # Proje brief'i - tum fazlarin plani
├── requirements.txt     # Python bagimliliklari (su an sadece pytest)
├── models/
│   └── state.py         # Durum vektoru semasi (aclik, yorgunluk, ...)
├── core/
│   ├── llm.py           # Model arayuzu: MockLLM + OllamaLLM
│   └── approval.py      # Onay kuyrugu - onaysiz hicbir sey hafizaya gecmez
├── evals/
│   ├── eval_seti.json   # 30 soruluk sabit test
│   └── puanla.py        # Puanlama betigi
├── tests/               # pytest testleri
└── workspace/           # Sistemin yazma izni olan TEK klasor (bos baslar)
```

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Calistirma

```bash
# Testler
pytest -v

# Onay kuyrugu (terminal komutlari)
python -m core.approval listele
python -m core.approval onayla 1
python -m core.approval reddet 2

# 30 soruluk eval, MockLLM ile (model gerekmez)
python -m evals.puanla --model mock
```

## Guvenlik sinirlari (pazarlik disi)

- Sistem yalnizca `./workspace/` klasorune yazabilir.
- Onay kuyrugundan gecmeyen hicbir bilgi kalici hafizaya yazilmaz.
- Internet erisimi izin listesi ile sinirlidir; serbest gezinme yoktur.
