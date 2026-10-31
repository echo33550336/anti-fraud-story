FROM python:3.11-slim

WORKDIR /app

# 零依赖：不安装任何第三方包
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

ENV HOST=0.0.0.0 \
    PORT=10000 \
    ALLOW_PUBLIC=1 \
    PYTHONUNBUFFERED=1

EXPOSE 10000

WORKDIR /app/backend

# 同一个进程同时提供 /api/story/* 和前端页面 /
CMD ["python", "app.py"]
