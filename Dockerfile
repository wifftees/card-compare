# syntax=docker/dockerfile:1.4
FROM python:3.13-slim

# # Установка системных зависимостей для Playwright (закомментировано)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    fonts-liberation \
    fonts-noto-color-emoji \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Сначала ставим тяжёлые зависимости отдельным слоем (редко меняются)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install supabase==2.27.1

# Установка Playwright браузеров (закомментировано)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install playwright==1.48.0
RUN playwright install firefox

# Остальные зависимости (меняются чаще)
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Копирование кода приложения (в самом конце)
COPY . .

# Создание директорий для storage
RUN mkdir -p storage/downloads

# Переменные окружения
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
