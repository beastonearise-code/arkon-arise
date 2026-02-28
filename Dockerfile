# పైథాన్ పునాది (Stability కోసం 3.10 వాడుతున్నాం)
FROM python:3.10

# కంటైనర్ లోపల పని చేసే ప్రదేశం
WORKDIR /code

# నీ ప్రాజెక్ట్ ఫైల్స్ అన్నింటినీ కంటైనర్ లోకి కాపీ చేయడం
COPY . .

# లైబ్రరీలను ఇన్‌స్టాల్ చేయడం
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# ప్లేరైట్ (Playwright) బ్రౌజర్లను సెటప్ చేయడం (నీ బాట్ కి ఇది అవసరం)
RUN playwright install --with-deps chromium

# అల్ట్రాన్ (FastAPI + Bot) ని స్టార్ట్ చేసే కమాండ్
# హగ్గింగ్ ఫేస్ పోర్ట్ 7860 మీద రన్ అవుతుంది
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]