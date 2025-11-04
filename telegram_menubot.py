"""
Telegram MenuPlanner Bot (Ready-to-Deploy, Dynamisch Aantal Menu's)
-----------------------------------------------------------------

Features:
- Spraak naar tekst via OpenAI Whisper
- Menu's genereren via ChatGPT
- Dynamisch aantal menu's gebaseerd op gebruikersinput
- Geschikt voor gezin van 2 volwassenen + 2 kinderen
- Klaar voor Render.com Free Tier

Dependencies (requirements.txt):
- python-telegram-bot==20.5
- requests
- python-dotenv
- openai
- pydub
- ffmpeg geïnstalleerd (Linux: sudo apt install ffmpeg, Mac: brew install ffmpeg)

Environment variables:
- TELEGRAM_TOKEN = <je Telegram bot token>
- OPENAI_API_KEY = <je OpenAI API key>
"""

import os
import logging
import tempfile
import re
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from pydub import AudioSegment
import openai

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Zet TELEGRAM_TOKEN en OPENAI_API_KEY in je omgevingsvariabelen")

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Convert OGG to WAV
def convert_ogg_to_wav(input_path):
    audio = AudioSegment.from_ogg(input_path)
    output_path = input_path.replace('.ogg', '.wav')
    audio.export(output_path, format="wav")
    return output_path

# Transcribe audio via OpenAI Whisper
def transcribe_audio(filepath):
    wav_path = convert_ogg_to_wav(filepath)
    with open(wav_path, 'rb') as f:
        transcript = openai.Audio.transcriptions.create(model="whisper-1", file=f)
    return transcript.text

# Extract number of menus from user input
def extract_number_of_menus(text):
    match = re.search(r'\b(\d+)\b', text)
    if match:
        return int(match.group(1))
    return 3  # standaard als geen getal gevonden wordt

# Generate menus via ChatGPT with dynamic number
def call_openai_chat_dynamic(prompt_text):
    num_menus = extract_number_of_menus(prompt_text)
    system_msg = (
        f"Je bent een slimme weekmenu-planner. Gebruik de huidige aanbiedingen op "
        f"https://www.jumbo.com/acties/weekaanbiedingen om {num_menus} menu's samen te stellen "
        f"voor een gezin van 2 volwassenen en 2 kinderen (ongeveer 3 volwassen porties). "
        f"Geef per menu: naam, boodschappenlijst met hoeveelheden en geschatte prijzen, en een korte bereidingswijze."
    )
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt_text}
        ],
        temperature=0.4,
        max_tokens=1000
    )
    return response.choices[0].message.content

# Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hallo! Stuur me een spraakbericht met je verzoek, bijvoorbeeld: 'Geef mij 3 weekmenu's voor mijn gezin op basis van de aanbiedingen van deze week.'"
    )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = msg.from_user
    logger.info("Received voice from %s (%s)", user.full_name, user.id)

    voice = msg.voice
    if not voice:
        await msg.reply_text("Geen audio gevonden in het bericht.")
        return

    # Download OGG bestand
    file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
        temp_path = tf.name
        await file.download_to_drive(custom_path=temp_path)

    await msg.reply_text("Audio ontvangen, ik transcribeer het nu...")

    try:
        transcript = transcribe_audio(temp_path)
        logger.info("Transcriptie: %s", transcript)
        await msg.reply_text(f"Transcriptie:\n{transcript}\n\nIk ga nu menu's samenstellen...")

        response_text = call_openai_chat_dynamic(transcript)

        # Stuur terug, splitsen als te lang
        if len(response_text) > 3500:
            with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as out:
                out.write(response_text)
                out.flush()
                await msg.reply_document(document=InputFile(out.name), filename="menu_planner_output.txt")
        else:
            await msg.reply_text(response_text)

    except Exception as e:
        logger.exception("Fout tijdens verwerking: %s", e)
        await msg.reply_text("Er is iets misgegaan tijdens de verwerking. Controleer de logs.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text("Oké, ik maak de menu's — even geduld...")
    try:
        response_text = call_openai_chat_dynamic(text)
        await update.message.reply_text(response_text)
    except Exception as e:
        logger.exception("Chat call failed: %s", e)
        await update.message.reply_text("Kon de menu's niet genereren — zie logs.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    logger.info("Bot gestart...")
    app.run_polling()

if __name__ == '__main__':
    main()
