@echo off
cd /d "%~dp0"
python -m streamlit run Painel.py --server.showEmailPrompt=false
