import os
import asyncio
import threading
import sqlite3
import random
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, List

import discord
from discord import app_commands
from discord.ext import commands
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Validate required environment variables
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is required.")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required.")

# Gemini model list, ordered by preference
GEMINI_MODELS: List[str] = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

# ==============================================================================
# WEB SERVER (Health Check for deployment platforms)
# ==============================================================================
class HealthHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to keep the bot alive on platforms like Render/Heroku."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Megumi Fushiguro Discord Bot is running online!")

    def log_message(self, format, *args):
        # Suppress default HTTP server logs
        pass


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Web server started on port {port}")
    server.serve_forever()


# Start web server in a background thread
threading.Thread(target=run_web_server, daemon=True).start()

# ==============================================================================
# GEMINI AI CLIENT
# ==============================================================================
# Initialize the Gemini client
gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def _call_gemini_sync(
    model_name: str,
    contents: str,
    system_instruction: str,
    temperature: float,
) -> str:
    """
    Synchronous wrapper to call Gemini API.
    This runs in a thread to avoid blocking the async event loop.
    """
    response = gemini_client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        ),
    )
    if response and response.text:
        return response.text
    return "Bố trận... Bát Ngát Kiếm Ma Ha La... (Triệu hồi Mahoraga, Megumi im lặng)"


async def ask_gemini(
    contents: str,
    system_instruction: str,
    temperature: float = 0.85,
) -> str:
    """
    Asynchronously calls Gemini with automatic fallback across multiple models.
    Retries each model up to 2 times before moving to the next.
    """
    last_error: Optional[Exception] = None

    for model_name in GEMINI_MODELS:
        for attempt in range(1, 3):  # 2 attempts per model
            try:
                print(f"[Gemini] Trying model: {model_name} (attempt {attempt})")
                result = await asyncio.to_thread(
                    _call_gemini_sync,
                    model_name,
                    contents,
                    system_instruction,
                    temperature,
                )
                return result

            except Exception as e:
                last_error = e
                error_str = str(e).upper()
                print(f"[Gemini] Model {model_name} failed (attempt {attempt}): {str(e)[:200]}")

                # If it's a safety/filter issue, return a themed response immediately
                if "SAFETY" in error_str or "FINISH_REASON" in error_str:
                    return (
                        "Bố trận... Bát Ngát Kiếm Ma Ha La! "
                        "(Mahoraga được triệu hồi, Megumi im lặng phó mặc cho thức thần!)"
                    )

                # If rate-limited, wait before retrying
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s
                    print(f"[Gemini] Rate limited. Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue  # Retry same model

                # For other errors, break to try the next model
                break

    # All models failed
    print(f"[Gemini] All models failed. Last error: {last_error}")
    return (
        "Hmm... Mahoraga đang gặp vấn đề với kết nối. "
        "Megumi sẽ thử lại sau!"
    )


# ==============================================================================
# DISCORD BOT SETUP
# ==============================================================================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# System instruction for the AI persona
MEGUMI_SYSTEM_PROMPT = (
    "You are Megumi Fushiguro from Jujutsu Kaisen. "
    "You speak in a calm, slightly reserved manner. "
    "You occasionally reference jujutsu techniques and shikigami. "
    "Keep responses concise and in-character."
)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.tree.command(name="ask", description="Ask Megumi anything!")
@app_commands.describe(question="What do you want to ask Megumi?")
async def ask_command(interaction: discord.Interaction, question: str):
    """Slash command to interact with the Gemini-powered Megumi persona."""
    await interaction.response.defer()  # Give us time to think

    response = await ask_gemini(
        contents=question,
        system_instruction=MEGUMI_SYSTEM_PROMPT,
        temperature=0.85,
    )

    # Discord has a 2000 character limit per message
    if len(response) > 2000:
        response = response[:1997] + "..."

    await interaction.followup.send(response)


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    print("Starting Megumi Fushiguro Bot...")
    bot.run(DISCORD_TOKEN)