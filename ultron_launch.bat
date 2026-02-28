@echo off
cd /d "c:\arkon alive"
call ".\.venv\Scripts\activate.bat"
pip install transformers==4.49.0
python "main_clone.py"
pause