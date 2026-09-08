@echo off
chcp 65001 >nul
title Gerar o Cardapio.exe
cd /d "%~dp0"

echo.
echo ============================================================
echo    Gerando o Cardapio.exe
echo ============================================================
echo.

rem ── acha o Python (instalado como "python" ou pelo lancador "py") ──
set PY=python
%PY% --version >nul 2>&1
if not errorlevel 1 goto tem_python
set PY=py
%PY% --version >nul 2>&1
if not errorlevel 1 goto tem_python
goto sem_python

:tem_python
for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo Usando %%v
echo.

echo [1 de 3] Instalando o que o programa precisa...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt pyinstaller
if errorlevel 1 goto erro_pip
echo       ok
echo.

set ICONE=
if exist icone.ico set ICONE=--icon icone.ico

echo [2 de 3] Empacotando. Isso demora alguns minutos - pode ir tomar um cafe.
echo.
%PY% -m PyInstaller --noconfirm --onefile --windowed --name Cardapio %ICONE% ^
    --exclude-module tkinter --exclude-module matplotlib ^
    --exclude-module numpy --exclude-module pandas ^
    cardapio.py
if errorlevel 1 goto erro_build
echo.

if not exist "dist\Cardapio.exe" goto erro_build

echo [3 de 3] Pronto!
echo.
echo    O programa esta aqui:
echo    %cd%\dist\Cardapio.exe
echo.
echo ------------------------------------------------------------
echo    ANTES DE USAR, FACA ASSIM:
echo.
echo    1. Crie uma pasta so dele, por exemplo  C:\Cardapio
echo    2. Copie o Cardapio.exe para dentro dela
echo    3. Clique com o botao direito no Cardapio.exe e escolha
echo       "Enviar para - Area de trabalho (criar atalho)"
echo.
echo    Os seus dados (cardapio.db e config.json) sao criados na
echo    MESMA pasta do Cardapio.exe. Nao ponha o programa dentro
echo    de "Arquivos de Programas": o Windows nao deixa gravar la.
echo ------------------------------------------------------------
echo.
pause
exit /b 0

:sem_python
echo.
echo    NAO ENCONTREI O PYTHON NESTE COMPUTADOR.
echo.
echo    Baixe em  https://www.python.org/downloads/
echo    e, na primeira tela do instalador, MARQUE a opcao
echo    "Add Python to PATH" antes de clicar em Install.
echo.
echo    Depois de instalar, feche esta janela e rode este
echo    arquivo de novo.
echo.
pause
exit /b 1

:erro_pip
echo.
echo    NAO CONSEGUI BAIXAR O QUE E PRECISO.
echo    Verifique se o computador esta conectado a internet.
echo.
pause
exit /b 1

:erro_build
echo.
echo    A GERACAO FALHOU. A mensagem do erro esta acima.
echo    Copie o texto e mande para quem cuida do programa.
echo.
pause
exit /b 1
