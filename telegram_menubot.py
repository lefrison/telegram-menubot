import os
import logging
import tempfile
from pydub import AudioSegment
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI

# -----------------------------
# Setup
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Environment vars
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# -----------------------------
# Helper functions
# -----------------------------

async def transcribe_audio(file_path: str) -> str:
    """Transcribe an audio file using Whisper (OpenAI)."""
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript.text


async def generate_menus(prompt_text: str) -> str:
    """Send user prompt to ChatGPT and return the answer."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Je bent een behulpzame kookassistent die weekmenu's maakt op basis van aanbiedingen."},
                {"role": "user", "content": prompt_text}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Fout bij aanroepen ChatGPT: {e}")
        return "Er ging iets mis bij het genereren van de menu's."


# -----------------------------
# Telegram handlers
# -----------------------------

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ontvang spraakbericht, transcribeer en genereer weekmenu."""
    try:
        user = update.effective_user.first_name
        voice = update.message.voice

        logger.info(f"Ontvangen spraakbericht van {user}")

        # Download voice file
        file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as f:
            await file.download_to_drive(f.name)
            ogg_path = f.name

        # Converteer naar WAV (Whisper werkt beter met .wav)
        wav_path = ogg_path.replace(".ogg", ".wav")
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")

        # Transcribeer
        await update.message.reply_text("Momentje, ik luister even naar je bericht… 🎧")
        text = await transcribe_audio(wav_path)
        logger.info(f"Transcriptie: {text}")

        # Maak prompt
        prompt = (
            f"De gebruiker zei: '{text}'. "
            "Gebruik dit als context om weekmenu's te maken op basis van de huidige aanbiedingen. "
            "Reken voor 3 volwassen personen, geef voor elk menu ook een korte bereiding."
        )

        # Genereer antwoord
        await update.message.reply_text("Dank je! Ik stel de menu’s samen… 🍽️")
        answer = await generate_menus(prompt)

        # Verstuur antwoord
        await update.message.reply_text(answer)

        # Ruim tijdelijke bestanden op
        os.remove(ogg_path)
        os.remove(wav_path)

    except Exception as e:
        logger.error(f"Fout in voice handler: {e}")
        await update.message.reply_text("Er ging iets mis bij het verwerken van je bericht 😞")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verwerk tekstberichten (zelfde logica als spraak)."""
    user_input = update.message.text
    logger.info(f"Tekstbericht ontvangen: {user_input}")

    prompt = (
        f"De gebruiker zei: '{user_input}'. "
        "Gebruik dit als context om weekmenu's te maken op basis van de huidige aanbiedingen. "
        "Reken voor 3 volwassen personen, geef voor elk menu ook een korte bereiding."
    )

    await update.message.reply_text("Momentje, ik stel de menu’s samen… 🍽️")
    answer = await generate_menus(prompt)
    await update.message.reply_text(answer)


# -----------------------------
# Main
# -----------------------------

def main():
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        raise ValueError("TELEGRAM_TOKEN en OPENAI_API_KEY moeten als environment variables gezet zijn.")

    logger.info("Bot wordt gestart...")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


if __name__ == "__main__":
    main()
