FROM python:3.12-slim

WORKDIR /app

# 先装依赖（利用 Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目
COPY . .

EXPOSE 8000

CMD ["python", "web_server.py"]
