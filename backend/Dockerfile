FROM python:3.13-slim
ENV ENVIRONMENT=production PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer libreoffice-calc libreoffice-impress tesseract-ocr poppler-utils fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home --uid 10001 esign
USER esign
CMD ["sh", "-c", "uvicorn ${APP_MODULE:-main}:app --host 0.0.0.0 --port ${PORT:-8080}"]
