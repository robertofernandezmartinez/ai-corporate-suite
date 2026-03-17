import logging
import os
from typing import Dict, Any

import telebot
from anthropic import Anthropic
from dotenv import load_dotenv
from supabase import create_client


# =========================
# 1. CONFIG / SETUP
# =========================
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") # ID autorizado
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

BOT_BUILD = "BUILD 1745 - OPTIMIZED"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_URL else None
claude = Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

# =========================
# 2. SECURITY MIDDLEWARE
# =========================
def is_authorized(chat_id: int) -> bool:
    """Check if the user is the authorized admin."""
    return str(chat_id) == str(TELEGRAM_CHAT_ID)

# =========================
# 3. DATA HELPERS
# =========================
def get_supabase_context() -> Dict[str, Any]:
    context = {
        "smartport": {"total": 0, "critical": 0},
        "nasa": {"total": 0, "critical": 0},
        "stockout": {"total": 0, "high": 0},
    }
    if not supabase: return context

    try:
        # SmartPort
        sp = supabase.table("smartport_predictions").select("risk_level").execute()
        levels = [r.get("risk_level") for r in sp.data if r.get("risk_level")]
        context["smartport"] = {"total": len(levels), "critical": levels.count("CRITICAL")}

        # NASA
        ns = supabase.table("nasa_predictions").select("predicted_rul").execute()
        ruls = [r.get("predicted_rul") for r in ns.data if r.get("predicted_rul") is not None]
        context["nasa"] = {"total": len(ruls), "critical": len([r for r in ruls if r < 30])}

        # Stockout
        st = supabase.table("stockout_predictions").select("risk_level").execute()
        st_levels = [r.get("risk_level") for r in st.data if r.get("risk_level")]
        context["stockout"] = {"total": len(st_levels), "high": st_levels.count("HIGH") + st_levels.count("CRITICAL")}
    except Exception as exc:
        logger.warning("Context fetch failed: %s", exc)

    return context

def build_status_report() -> str:
    ctx = get_supabase_context()
    return (
        f"📊 *EXECUTIVE SYSTEM REPORT*\n"
        f"_Build: {BOT_BUILD}_\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🚢 *SMARTPORT*: `{ctx['smartport']['total']}` recs | {'🔴 ' + str(ctx['smartport']['critical']) if ctx['smartport']['critical'] > 0 else '🟢 OK'}\n"
        f"🔧 *NASA RUL*: `{ctx['nasa']['total']}` engines | {'🔴 ' + str(ctx['nasa']['critical']) if ctx['nasa']['critical'] > 0 else '🟢 OK'}\n"
        f"📦 *STOCKOUT*: `{ctx['stockout']['total']}` items | {'🔴 ' + str(ctx['stockout']['high']) if ctx['stockout']['high'] > 0 else '🟢 OK'}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💬 *AI Insights:* _Ask for details or priorities._"
    )

# =========================
# 4. ACTIONS & AI
# =========================
def ask_claude(user_text: str) -> str:
    if not claude: return "❌ Claude API not configured."
    context = get_supabase_context()
    
    system_prompt = f"You are an Industrial AI Assistant. Data: SmartPort:{context['smartport']}, NASA:{context['nasa']}, Stockout:{context['stockout']}. Reply in user's language. Be concise and executive."
    
    response = claude.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
    )
    return "\n".join([block.text for block in response.content if hasattr(block, 'text')]).strip()

# =========================
# 5. HANDLERS
# =========================
@bot.message_handler(commands=["id"])
def handle_id(message):
    bot.reply_to(message, f"Your chat_id is: `{message.chat.id}`")

@bot.message_handler(func=lambda m: True)
def main_handler(message):
    # Seguridad: Bloqueo de intrusos
    if not is_authorized(message.chat.id):
        bot.reply_to(message, "🚫 *Access Denied.* Restricted to authorized personnel only.")
        return

    # Comandos
    if message.text.startswith("/start") or message.text.startswith("/help"):
        bot.reply_to(message, f"✨ *AI Corporate Suite v2.0*\nCommands: `/status`, `/id`\nOr ask me anything about the data.")
    
    elif message.text.startswith("/status"):
        bot.reply_to(message, build_status_report())

    # Conversación con IA
    else:
        bot.send_chat_action(message.chat.id, "typing")
        try:
            reply = ask_claude(message.text)
            bot.reply_to(message, reply)
        except Exception as exc:
            bot.reply_to(message, "❌ *Claude Error*")

# =========================
# 6. RUN (LOCAL ONLY)
# =========================
if __name__ == "__main__":
    logger.info("🚀 Starting Bot Polling...")
    bot.infinity_polling(skip_pending=True)