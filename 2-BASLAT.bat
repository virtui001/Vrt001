@echo off
chcp 65001 >nul
title Cekirdek - Calisiyor
cd /d "%~dp0"

echo ============================================================
echo   CEKIRDEK BASLATILIYOR
echo ============================================================
echo.

REM --- Kurulum yapilmis mi? ---
if not exist ".venv\Scripts\python.exe" (
    echo [HATA] Once kurulum yapilmali.
    echo.
    echo "1-KUR.bat" dosyasina cift tikla, bitince buraya don.
    echo.
    pause
    exit /b 1
)

REM --- Ollama ayakta mi? Sadece bilgi amacli, engellemiyoruz. ---
ollama list >nul 2>&1
if errorlevel 1 (
    echo [UYARI] Ollama calismiyor gibi gorunuyor.
    echo         Arayuz yine acilacak ama cevaplar anlamsiz olacak.
    echo         Duzeltmek icin: yeni bir pencere acip "ollama serve" yaz.
    echo.
)

echo Tarayici birazdan kendiliginden acilacak.
echo Acilmazsa tarayicina sunu yaz:  http://localhost:8000
echo.
echo Kapatmak icin: BU PENCEREYI KAPAT.
echo.

".venv\Scripts\python.exe" -m web.sunucu --model ollama

echo.
echo Cekirdek kapandi.
pause
