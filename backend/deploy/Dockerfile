FROM python:3.11-slim

WORKDIR /app

# 零依赖：无需 pip install
COPY app.py /app/app.py
COPY game /app/game

ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "app.py"]
