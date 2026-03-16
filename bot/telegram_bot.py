import logging
import os

import telebot
from anthropic import Anthropic
from dotenv import load_dotenv
from supabase import create_client


# =========================
# 1. CONFIG / SETUP
# =========================
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_URL = os.getenv(
    "SUITE_API_URL",
    "https://ai-corporate-suite-production.up.railway.app"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
claude = Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None


# =========================
# 2. DATA HELPERS
# =========================
def get_supabase_context() -> dict:
    """
    Fetch real-time summary from the 3 platform pillars.
    """
    context = {
        "smartport": {"total": 0, "critical": 0},
        "nasa": {"total": 0, "critical": 0},
        "stockout": {"total": 0, "high": 0},
    }

    # SmartPort
    try:
        sp = supabase.table("smartport_predictions").select("risk_level").execute()
        rows = sp.data or []
        levels = [r.get("risk_level") for r in rows if r.get("risk_level") is not None]
        context["smartport"] = {
            "total": len(levels),
            "critical": levels.count("CRITICAL"),
        }
    except Exception as exc:
        logger.warning("SmartPort context fetch failed: %s", exc)

    # NASA
    try:
        ns = supabase.table("nasa_predictions").select("predicted_rul").execute()
        rows = ns.data or []
        ruls = [r.get("predicted_rul") for r in rows if r.get("predicted_rul") is not None]
        context["nasa"] = {
            "total": len(ruls),
            "critical": len([r for r in ruls if r < 30]),
        }
    except Exception as exc:
        logger.warning("NASA context fetch failed: %s", exc)

    # Stockout
    try:
        st = supabase.table("stockout_predictions").select("risk_level").execute()
        rows = st.data or []
        levels = [r.get("risk_level") for r in rows if r.get("risk_level") is not None]
        context["stockout"] = {
            "total": len(levels),
            "high": levels.count("HIGH") + levels.count("CRITICAL"),
        }
    except Exception as exc:
        logger.warning("Stockout context fetch failed: %s", exc)

    return context


def build_status_report() -> str:
    ctx = get_supabase_context()

    report = [
        "📊 *EXECUTIVE SYSTEM REPORT*",
        "━━━━━━━━━━━━━━━━━━",
        "",
        "🚢 *SMARTPORT LOGISTICS*",
        f"• Total Records: `{ctx['smartport']['total']}`",
        f"• Critical Alerts: `{'🔴 ' + str(ctx['smartport']['critical']) if ctx['smartport']['critical'] > 0 else '🟢 None'}`",
        "",
        "🔧 *NASA ENGINE RUL*",
        f"• Engines Monitored: `{ctx['nasa']['total']}`",
        f"• Risk (<30 cycles): `{'🔴 ' + str(ctx['nasa']['critical']) if ctx['nasa']['critical'] > 0 else '🟢 Healthy'}`",
        "",
        "📦 *INVENTORY STOCKOUT*",
        f"• Items Analyzed: `{ctx['stockout']['total']}`",
        f"• High Risk: `{'🔴 ' + str(ctx['stockout']['high']) if ctx['stockout']['high'] > 0 else '🟢 Optimal'}`",
        "",
        "━━━━━━━━━━━━━━━━━━",
        "💬 *AI Insights:* _Ask me for a summary, risks, anomalies, or priorities._",
    ]

    return "\n".join(report)


# =========================
# 3. ALERT FUNCTION
# =========================
def send_push_alert(message: str) -> dict:
    """
    Send push alert to configured Telegram chat.
    Used by predictors when high-risk events are detected.
    """
    if not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_CHAT_ID is missing")
        return {"sent": 0, "error": "TELEGRAM_CHAT_ID missing"}

    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info("Telegram alert sent successfully")
        return {"sent": 1}
    except Exception as exc:
        logger.exception("Failed to send Telegram alert: %s", exc)
        return {"sent": 0, "error": str(exc)}


# =========================
# 4. TELEGRAM HANDLERS
# =========================
@bot.message_handler(commands=["start", "help"])
def welcome(message):
    welcome_text = (
        "✨ *AI Corporate Suite v2.0* ✨\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Hello. I am your *Industrial Intelligence Assistant*.\n\n"
        "🚀 *Available Commands*\n"
        "• `/status` - Full system overview\n"
        "• `/help` - Show this guide\n\n"
        "💡 *Examples*\n"
        "_Which engines need maintenance?_\n"
        "_Give me a summary of port risk._\n"
        "_What is the current inventory risk level?_"
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=["status"])
def status_report(message):
    try:
        report = build_status_report()
        bot.reply_to(message, report)
    except Exception as exc:
        logger.exception("Status report failed: %s", exc)
        bot.reply_to(
            message,
            "❌ Error generating status report. Please try again."
        )


@bot.message_handler(func=lambda message: bool(message.text and not message.text.startswith("/")))
def handle_ai(message):
    bot.send_chat_action(message.chat.id, "typing")

    if not claude:
        bot.reply_to(
            message,
            "⚠️ Claude is not configured right now. Available commands: `/status` and `/help`."
        )
        return

    try:
        context = get_supabase_context()

        system_prompt = f"""
You are the AI Corporate Assistant for an industrial AI platform.

Current platform data:
- SmartPort: {context['smartport']}
- NASA RUL: {context['nasa']}
- Stockout: {context['stockout']}

Rules:
1. Reply in the same language as the user.
2. Be concise, executive, and useful.
3. Use Markdown formatting when helpful.
4. If there are CRITICAL or HIGH risks, highlight them clearly.
5. Focus on operational implications, not generic theory.
"""

        response = claude.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=700,
            system=system_prompt,
            messages=[
                {"role": "user", "content": message.text}
            ],
        )

        reply_text = response.content[0].text.strip()
        bot.reply_to(message, reply_text)

    except Exception as exc:
        logger.exception("Claude response failed:")
        bot.reply_to(
            message,
            f"❌ Claude error: {str(exc)}"
        )


# =========================
# 5. LOCAL RUN
# =========================
if __name__ == "__main__":
    logger.info("🚀 AI Corporate Suite Telegram bot is live...")
    bot.infinity_polling(skip_pending=True)