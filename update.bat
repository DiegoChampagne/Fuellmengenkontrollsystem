@echo off
rem Holt die neueste Version von GitHub und installiert bei Bedarf neue Pakete.
rem Voraussetzung: Ordner wurde mit "git clone" angelegt, Git ist installiert,
rem Internetzugang vorhanden.
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
    echo Git ist nicht installiert - bitte von git-scm.com installieren.
    pause & exit /b 1
)
if not exist ".git" (
    echo Dieser Ordner ist kein Git-Klon - Update nicht moeglich.
    echo Einmalig: git clone ^<Repository-URL^> und config.json/Datenbank dorthin kopieren.
    pause & exit /b 1
)

for /f %%i in ('git rev-parse HEAD') do set VORHER=%%i

git pull --ff-only
if errorlevel 1 (
    echo.
    echo Update fehlgeschlagen. Moegliche Ursachen: kein Internet oder von Hand
    echo geaenderte Programmdateien ^(mit "git status" pruefen^).
    pause & exit /b 1
)

for /f %%i in ('git rev-parse HEAD') do set NACHHER=%%i
if "%VORHER%"=="%NACHHER%" (
    echo Bereits auf dem neuesten Stand.
    pause & exit /b 0
)

echo Aktualisiert.
git diff --quiet %VORHER% %NACHHER% -- requirements.txt
if errorlevel 1 (
    echo Pakete haben sich geaendert - installiere...
    if exist venv\Scripts\python.exe (
        venv\Scripts\python.exe -m pip install -r requirements.txt
    ) else (
        python -m pip install -r requirements.txt
    )
)
echo Fertig.
pause
