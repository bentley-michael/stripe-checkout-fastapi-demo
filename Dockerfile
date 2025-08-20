
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt requirements-weasy.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-weasy.txt &&     apt-get update && apt-get install -y --no-install-recommends       libpango-1.0-0 libcairo2 libgdk-pixbuf2.0-0 fonts-dejavu &&     rm -rf /var/lib/apt/lists/*

COPY . .
ENV PORT=8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
