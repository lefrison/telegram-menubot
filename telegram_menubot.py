import os
import logging
import tempfile
import re
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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# -----------------------------
# Helper functions
# -----------------------------

async def transcribe_audio(file_path: str) -> str:
    """Transcribe an audio file using Whisper."""
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript.text


async def generate_menus(prompt_text: str) -> str:
    """Send user prompt to ChatGPT and return the structured answer."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Je bent een behulpzame kookassistent. "
                    "Wanneer de gebruiker om menu's vraagt, geef ze in gestructureerde vorm terug: "
                    "Gebruik het volgende format:\n\n"
                    "MENU 1: [Titel]\n"
                    "Boodschappenlijst:\n"
                    "- item 1\n- item 2\n\n"
                    "Bereiding:\n"
                    "1. stap 1\n2. stap 2\n\n"
                    "MENU 2: ... enzovoort."
                )},
                {"role": "user", "content": prompt_text}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Fout bij aanroepen ChatGPT: {e}")
        return "Er ging iets mis bij het genereren van de menu's."


async def send_split_messages(update: Update, text: str):
    """
    Splits het antwoord in losse menu's en stuurt elk menu in aparte berichten:
      1. Titel
      2. Boodschappenlijst
      3. Bereiding
    """
    # Split op menu’s
    menus = re.split(r"(?=MENU\s*\d+:)", text, flags=re.IGNORECASE)
    for menu in menus:
        if not menu.strip():
            continue

        # Stuur menutitel
        titel_match = re.search(r"MENU\s*\d+:\s*(.+)", menu)
        if titel_match:
            await update.message.reply_text(f"🍽️ *{titel_match.group(0).strip()}*", parse_mode="Markdown")

        # Boodschappenlijst
        boodschappen_match = re.search(r"Boodschappenlijst:(.+?)(?:Bereiding:|$)", menu, re.S | re.I)
        if boodschappen_match:
            boodschappen = boodschappen_match.group(1).strip()
            await update.message.reply_text(f"🛒 *Boodschappenlijst:*\n{boodschappen}", parse_mode="Markdown")

        # Bereiding
        bereiding_match = re.search(r"Bereiding:(.+)", menu, re.S | re.I)
        if bereiding_match:
            bereiding = bereiding_match.group(1).strip()
            await update.message.reply_text(f"👩‍🍳 *Bereiding:*\n{bereiding}", parse_mode="Markdown")


# -----------------------------
# Telegram handlers
# -----------------------------

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verwerkt spraakberichten, transcribeert en genereert menu’s."""
    try:
        user = update.effective_user.first_name
        voice = update.message.voice
        logger.info(f"Ontvangen spraakbericht van {user}")

        # Download audio
        file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as f:
            await file.download_to_drive(f.name)
            ogg_path = f.name

        # Converteer naar WAV
        wav_path = ogg_path.replace(".ogg", ".wav")
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")

        await update.message.reply_text("Momentje, ik luister even naar je bericht… 🎧")
        text = await transcribe_audio(wav_path)
        logger.info(f"Transcriptie: {text}")

        prompt = (
            f"De gebruiker zei: '{text}'. "
            "Gebruik dit om weekmenu's te maken voor 3 volwassenen en 2 kinderen. "
            "Zorg dat elk menu een titel, boodschappenlijst en bereiding bevat."
        )

        await update.message.reply_text("Ik stel de menu’s samen, een momentje… 🍳")
        answer = await generate_menus(prompt)
        await send_split_messages(update, answer)

        os.remove(ogg_path)
        os.remove(wav_path)

    except Exception as e:
        logger.error(f"Fout in voice handler: {e}")
        await update.message.reply_text("Er ging iets mis bij het verwerken van je bericht 😞")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verwerkt tekstberichten."""
    user_input = update.message.text
    logger.info(f"Tekstbericht ontvangen: {user_input}")

    prompt = (
        f"De gebruiker zei: '{user_input}'. "
        "Gebruik dit om weekmenu's te maken voor 3 volwassenen en 2 kinderen. "
        "Zorg dat elk menu een titel, boodschappenlijst en bereiding bevat."
    )

    await update.message.reply_text("Ik stel de menu’s samen, een momentje… 🍳")
    answer = await generate_menus(prompt)
    await send_split_messages(update, answer)


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
