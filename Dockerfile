FROM python:3.10-slim

# Установка зависимостей системы
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

# Копирование файлов
COPY requirements.txt .
COPY ryanair_price_tracker.py .

# Установка Python-зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Создание директории для данных
RUN mkdir -p /app/data/price_plots

# Запуск скрипта
CMD ["python", "ryanair_price_tracker.py"]