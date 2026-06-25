@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
set WHISPER_MODEL_SIZE=small
set WHISPER_DEVICE=cpu
set WHISPER_COMPUTE_TYPE=int8
set REALTIME_INTERVAL=1.6
set STREAM_PORT=7861
python streaming_server.py
