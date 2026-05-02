FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY telegram_bot.py .
COPY payment.py .
COPY webhook.py .
COPY email_sender.py .
COPY check_notifications.py .
COPY faq.py .
COPY promos.py .
COPY analytics.py .
COPY rate_limiter.py .
COPY backup.py .
COPY category_stats.py .

CMD ["python", "main.py"]
