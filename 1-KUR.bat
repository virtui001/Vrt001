@echo off
chcp 65001 >nul
title Cekirdek - Kurulum
cd /d "%~dp0"

echo ============================================================
echo   CEKIRDEK - KURULUM
echo ============================================================
echo.
echo Bu dosya bir kez calistirilir. Birkac dakika surebilir.
echo.

REM --- Python var mi? ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi.
    echo.
    echo Yapman gereken:
    echo   1. https://www.python.org/downloads/ adresine git
    echo   2. Sari "Download Python" dugmesine bas, dosyayi calistir
    echo   3. ILK EKRANDA "Add python.exe to PATH" KUTUSUNU ISARETLE
    echo      ^(bu kutu isaretlenmezse bu hata tekrar cikar^)
    echo   4. Install'a bas, bitince bu dosyaya tekrar cift tikla
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set SURUM=%%v
echo [1/3] Python bulundu: %SURUM%

REM --- Sanal ortam ---
if exist ".venv\Scripts\python.exe" (
    echo [2/3] Calisma ortami zaten var, atlaniyor.
) else (
    echo [2/3] Calisma ortami olusturuluyor...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo [HATA] Calisma ortami olusturulamadi.
        echo Python surumun cok eski olabilir. 3.11 ya da ustu gerekiyor.
        echo.
        pause
        exit /b 1
    )
)

REM --- Paketler ---
echo [3/3] Gerekli paketler kuruluyor...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo.
    echo [HATA] Paketler kurulamadi. Internet baglantini kontrol et.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   KURULUM BITTI
echo ============================================================
echo.
echo Simdi "2-BASLAT.bat" dosyasina cift tikla.
echo.
pause
