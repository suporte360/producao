@echo off
title Totem Serralheria
:: Tenta Edge primeiro (vem no Windows 10/11), depois Chrome
set URL=http://192.168.1.14:5003

:: Verifica se Edge existe
where msedge >nul 2>&1
if %errorlevel%==0 (
    start msedge.exe --kiosk "%URL%" --edge-kiosk-type=fullscreen --no-first-run
    exit /b
)

:: Verifica se Chrome existe
where chrome >nul 2>&1
if %errorlevel%==0 (
    start chrome.exe --kiosk "%URL%" --incognito --no-first-run
    exit /b
)

:: Se nao achou nenhum, abre no navegador padrao
start "" "%URL%"
echo Navegador compativel nao encontrado. Abriu no navegador padrao.
timeout /t 3