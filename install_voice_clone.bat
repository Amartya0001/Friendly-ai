@echo off
chcp 65001 >nul
echo.
echo === Voice clone (Coqui TTS) ===
echo Yeh package Python 3.9 - 3.11 par hi chalta hai. Python 3.12 / 3.13 par pip fail hoga.
echo NOTE: Clone (XTTS) ke liye FFmpeg install + PATH me zaroori ho sakta hai.
echo.

where py >nul 2>&1
if errorlevel 1 (
  echo "py" launcher nahi mila. Python 3.11 install karo: https://www.python.org/downloads/
  pause
  exit /b 1
)

echo Python 3.11 se naya venv banaya ja raha hai: .venv-tts
py -3.11 -m venv .venv-tts
if errorlevel 1 (
  echo.
  echo FAIL: Python 3.11 install nahi hai. Pehle Python 3.11 install karo, phir dubara chalao.
  pause
  exit /b 1
)

call .venv-tts\Scripts\activate.bat
python -m pip install -U pip
python -m pip install -r "%~dp0requirements-voice-clone.txt"
if errorlevel 1 (
  echo.
  echo Install fail. Upar wala error padho.
  pause
  exit /b 1
)

echo.
echo Quick check:
python check_clone_env.py

echo.
echo Done. Streamlit is venv se chalao:
echo   .venv-tts\Scripts\activate
echo   streamlit run streamlit_app.py
echo.
pause
