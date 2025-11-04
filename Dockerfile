# basis
FROM python:3.11-slim

# systeem dependencies (ffmpeg + apt helpers)
RUN apt-get update && apt-get install -y ffmpeg gcc libpq-dev build-essential && rm -rf /var/lib/apt/lists/*

# werkdir
WORKDIR /app

# kopieer requirements en installeer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# kopieer rest van de app
COPY . .

# expose (niet strikt nodig voor polling bot, maar harmless)
EXPOSE 8080

# start command
CMD ["python", "telegram_menubot.py"]
