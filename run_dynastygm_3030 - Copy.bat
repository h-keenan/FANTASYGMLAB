@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
set DYNASTYGM_DEBUG_AUTH=true
python -m streamlit run app.py --server.port 3000
