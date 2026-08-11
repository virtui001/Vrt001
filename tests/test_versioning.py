"""
tests/test_versioning.py -- Surum yonetimi ve geri alma testleri

Her test kendi GECICI git deposunda calisir. Gercek proje deposuna
kesinlikle dokunulmaz -- yoksa test calistirmak isini bozabilirdi.
"""

import subprocess

import pytest

from core import versioning
from core.versioning import (
    GitHatasi,
    depo_mu,
    dal,
    geri_al,
    surum_kaydet,
    surum_var_mi,
    surumler,
    temiz_mi,
)


@pytest.fixture
def depo(tmp_path):
    """Icinde tek dosya ve tek commit olan gecici bir git deposu."""
    subprocess.run(["git", "init", "-q", "-b", "ana", str(tmp_path)], check=True)
    (tmp_path / "dosya.txt").write_text("ilk hal\n", encoding="utf-8")
    versioning._git("add", "-A", depo=tmp_path)
    versioning._git("commit", "-m", "ilk commit", depo=tmp_path)
    return tmp_path


# -- Temel sorular -----------------------------------------------------------


def test_depo_mu(depo, tmp_path):
    assert depo_mu(depo)


def test_git_olmayan_klasor(tmp_path):
    bos = tmp_path / "bos"
    bos.mkdir()
    assert not depo_mu(bos)


def test_temiz_mi(depo):
    assert temiz_mi(depo)
    (depo / "dosya.txt").write_text("degisti\n", encoding="utf-8")
    assert not temiz_mi(depo)


def test_dal_adi(depo):
    assert dal(depo) == "ana"


def test_gecersiz_git_komutu_turkce_hata_verir(depo):
    with pytest.raises(GitHatasi, match="basarisiz"):
        versioning._git("boyle-bir-komut-yok", depo=depo)


# -- Surum kaydetme ----------------------------------------------------------


def test_kaydet_commit_ve_etiket_olusturur(depo):
    (depo / "dosya.txt").write_text("ikinci hal\n", encoding="utf-8")
    sonuc = surum_kaydet("ikinci hal yazildi", etiket="v0.1.0", depo=depo)
    assert sonuc["commit"]
    assert surum_var_mi("v0.1.0", depo)


def test_kaydet_etiketsiz_de_calisir(depo):
    (depo / "dosya.txt").write_text("degisti\n", encoding="utf-8")
    sonuc = surum_kaydet("etiketsiz kayit", depo=depo)
    assert sonuc["etiket"] is None
    assert surumler(depo) == []


def test_bos_mesaj_reddedilir(depo):
    with pytest.raises(ValueError, match="bos olamaz"):
        surum_kaydet("   ", depo=depo)


def test_degisiklik_yokken_kaydedilmez(depo):
    with pytest.raises(GitHatasi, match="degisiklik yok"):
        surum_kaydet("bos kayit", depo=depo)


def test_ayni_etiket_iki_kez_kullanilamaz(depo):
    (depo / "a.txt").write_text("a\n", encoding="utf-8")
    surum_kaydet("bir", etiket="v0.1.0", depo=depo)
    (depo / "b.txt").write_text("b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="zaten var"):
        surum_kaydet("iki", etiket="v0.1.0", depo=depo)


def test_surumler_yeniden_eskiye_sirali(depo):
    for i in (1, 2, 3):
        (depo / f"{i}.txt").write_text(f"{i}\n", encoding="utf-8")
        surum_kaydet(f"surum {i}", etiket=f"v0.{i}.0", depo=depo)
    etiketler = [s["etiket"] for s in surumler(depo)]
    assert etiketler[0] == "v0.3.0"
    assert set(etiketler) == {"v0.1.0", "v0.2.0", "v0.3.0"}


def test_surum_kaydinda_mesaj_saklanir(depo):
    (depo / "a.txt").write_text("a\n", encoding="utf-8")
    surum_kaydet("anlamli bir mesaj", etiket="v1.0.0", depo=depo)
    assert surumler(depo)[0]["mesaj"] == "anlamli bir mesaj"


# -- Geri alma ---------------------------------------------------------------


def test_geri_al_varsayilan_olarak_dosyaya_dokunmaz(depo):
    """En onemli guvenlik tercihi: --uygula yazmadan hicbir sey degismez."""
    (depo / "dosya.txt").write_text("iyi hal\n", encoding="utf-8")
    surum_kaydet("ilk surum", etiket="v0.1.0", depo=depo)
    (depo / "dosya.txt").write_text("bozuk hal\n", encoding="utf-8")
    surum_kaydet("bozuk degisiklik", depo=depo)

    sonuc = geri_al("v0.1.0", depo=depo)

    assert sonuc["uygulandi"] is False
    assert (depo / "dosya.txt").read_text(encoding="utf-8") == "bozuk hal\n"
    assert "--uygula" in sonuc["ozet"]


def test_geri_al_uygulayinca_eski_hale_doner(depo):
    (depo / "dosya.txt").write_text("iyi hal\n", encoding="utf-8")
    surum_kaydet("iyi hal", etiket="v0.1.0", depo=depo)
    (depo / "dosya.txt").write_text("bozuk hal\n", encoding="utf-8")
    surum_kaydet("bozuk degisiklik", depo=depo)

    sonuc = geri_al("v0.1.0", depo=depo, uygula=True)

    assert sonuc["uygulandi"] is True
    assert (depo / "dosya.txt").read_text(encoding="utf-8") == "iyi hal\n"


def test_geri_alma_gecmisi_silmez(depo):
    """
    'git revert' kullaniyoruz: eski commit'ler duruyor, ustune yeni bir
    commit ekleniyor. Boylece geri almayi da geri alabilirsin.
    """
    (depo / "dosya.txt").write_text("iyi\n", encoding="utf-8")
    surum_kaydet("iyi", etiket="v0.1.0", depo=depo)
    (depo / "dosya.txt").write_text("bozuk\n", encoding="utf-8")
    surum_kaydet("bozuk", depo=depo)

    onceki_sayi = int(versioning._git("rev-list", "--count", "HEAD", depo=depo))
    geri_al("v0.1.0", depo=depo, uygula=True)
    sonraki_sayi = int(versioning._git("rev-list", "--count", "HEAD", depo=depo))

    assert sonraki_sayi == onceki_sayi + 1
    assert surum_var_mi("v0.1.0", depo)  # etiket de duruyor


def test_olmayan_surum_mevcutlari_soyler(depo):
    (depo / "a.txt").write_text("a\n", encoding="utf-8")
    surum_kaydet("bir", etiket="v0.1.0", depo=depo)
    with pytest.raises(ValueError, match="v0.1.0"):
        geri_al("v9.9.9", depo=depo)


def test_zaten_o_surumdeyken_bilgi_verir(depo):
    (depo / "a.txt").write_text("a\n", encoding="utf-8")
    surum_kaydet("surum", etiket="v0.2.0", depo=depo)
    sonuc = geri_al("v0.2.0", depo=depo)
    assert sonuc["uygulandi"] is False
    assert "geri alacak bir sey yok" in sonuc["ozet"]


def test_kirli_calisma_alaninda_geri_alinmaz(depo):
    """Kaydedilmemis isin ustune yazmayiz."""
    (depo / "dosya.txt").write_text("iyi\n", encoding="utf-8")
    surum_kaydet("iyi", etiket="v0.1.0", depo=depo)
    (depo / "dosya.txt").write_text("bozuk\n", encoding="utf-8")
    surum_kaydet("bozuk", depo=depo)
    (depo / "dosya.txt").write_text("kaydedilmemis is\n", encoding="utf-8")

    with pytest.raises(GitHatasi, match="Kaydedilmemis"):
        geri_al("v0.1.0", depo=depo, uygula=True)


# -- Terminal komutlari ------------------------------------------------------


@pytest.fixture
def terminal(depo, monkeypatch):
    """main() fonksiyonunu gecici depo uzerinde calistirir."""
    monkeypatch.setattr(versioning, "PROJE_KOKU", depo)
    return versioning.main


def test_komut_listele_bos(terminal, capsys):
    assert terminal(["listele"]) == 0
    assert "Henuz kayitli surum yok" in capsys.readouterr().out


def test_komut_kaydet_ve_listele(terminal, depo, capsys):
    (depo / "a.txt").write_text("a\n", encoding="utf-8")
    assert terminal(["kaydet", "yeni is", "--etiket", "v0.1.0", "--eval-atla"]) == 0
    assert "Kaydedildi" in capsys.readouterr().out

    assert terminal(["listele"]) == 0
    assert "v0.1.0" in capsys.readouterr().out


def test_komut_kaydet_eval_calistirir(terminal, depo, capsys):
    """
    'Hicbir degisiklik eval'den gecmeden kalici olmaz' kurali:
    kaydet komutu once eval'i calistirir.
    """
    (depo / "a.txt").write_text("a\n", encoding="utf-8")
    assert terminal(["kaydet", "eval ile"]) == 0
    assert "Eval: 30/30" in capsys.readouterr().out


def test_komut_kaydet_mesajsiz(terminal, capsys):
    assert terminal(["kaydet"]) == 1
    assert "Eksik" in capsys.readouterr().out


def test_komut_geri_al_surum_yok(terminal, capsys):
    assert terminal(["geri_al", "v9.9.9"]) == 1
    assert "Hata:" in capsys.readouterr().out


def test_komut_geri_al_hedefsiz(terminal, capsys):
    assert terminal(["geri_al"]) == 1
    assert "Eksik" in capsys.readouterr().out


def test_bilinmeyen_komut(terminal, capsys):
    assert terminal(["zipzip"]) == 1
    assert "Bilinmeyen komut" in capsys.readouterr().out


def test_komutsuz_yardim_gosterir(terminal, capsys):
    assert terminal([]) == 1
    assert "geri_al" in capsys.readouterr().out
