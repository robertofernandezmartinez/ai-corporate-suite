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

# Environment Variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
# This variable name must match exactly the one used in create_client below
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

BOT_BUILD = "BUILD 1760 - STABLE ROOT"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN")

# Initialize Clients
# We use the variable names defined above to avoid NameError
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

supabase = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
else:
    logger.warning("Supabase credentials missing. Database features will be disabled.")

claude = Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

logger.info("Telegram bot initialized | build=%s", BOT_BUILD)
logger.info("Claude enabled: %s", bool(claude))


# =========================
# 2. DATA HELPERS
# =========================
def get_supabase_context() -> Dict[str, Any]:
    """
    Fetch real-time summary from the 3 platform pillars.
    """
    context = {
        "smartport": {"total": 0, "critical": 0},
        "nasa": {"total": 0, "critical": 0},
        "stockout": {"total": 0, "high": 0},
    }

    if not supabase:
        return context

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
        f"📊 *EXECUTIVE SYSTEM REPORT*",
        f"_Build: {BOT_BUILD}_",
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
# 3. SECURITY & AUTH
# =========================
def is_authorized(chat_id: int) -> bool:
    """Check if the sender is the authorized user."""
    return str(chat_id) == str(TELEGRAM_CHAT_ID)


# =========================
# 4. CLAUDE CALL
# =========================
def ask_claude(user_text: str) -> str:
    if not claude:
        raise RuntimeError("ANTHROPIC_API_KEY missing or Claude client not initialized")

    context = get_supabase_context()

    system_prompt = f"""
You are the AI Corporate Assistant for an industrial AI platform.

Current platform data:
- SmartPort: {context['smartport']}
- NASA RUL: {context['nasa']}
- Stockout: {context['stockout']}

Rules:
1. Reply in the same language as the user.
2. Be concise, executive, and operational.
3. Use Markdown only when useful.
4. If there are CRITICAL or HIGH risks, highlight them clearly.
5. Focus on actionable interpretation, not generic theory.
"""

    response = claude.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
    )

    text_blocks = [block.text for block in response.content if hasattr(block, "text")]
    return "\n".join(text_blocks).strip()


# =========================
# 5. TELEGRAM HANDLERS
# =========================
@bot.message_handler(commands=["start", "help"])
def welcome(message):
    if not is_authorized(message.chat.id):
        bot.reply_to(message, "❌ Unauthorized access.")
        return

    welcome_text = (
        f"✨ *AI Corporate Suite v2.0* ✨\n"
        f"_Build: {BOT_BUILD}_\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Hello. I am your *Industrial Intelligence Assistant*.\n\n"
        "🚀 *Available Commands*\n"
        "• `/status` - Full system overview\n"
        "• `/id` - Show your Telegram Chat ID\n"
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=["id"])
def get_id(message):
    bot.reply_to(message, f"Your Chat ID: `{message.chat.id}`")


@bot.message_handler(commands=["status"])
def status_report(message):
    if not is_authorized(message.chat.id):
        bot.reply_to(message, "❌ Unauthorized access.")
        return

    try:
        report = build_status_report()
        bot.reply_to(message, report)
    except Exception as exc:
        logger.exception("Status report failed")
        bot.reply_to(message, f"❌ Status error: `{str(exc)}`")


@bot.message_handler(func=lambda message: bool(message.text and not message.text.startswith("/")))
def handle_ai(message):
    if not is_authorized(message.chat.id):
        return

    bot.send_chat_action(message.chat.id, "typing")
    try:
        reply_text = ask_claude(message.text)
        bot.reply_to(message, reply_text)
    except Exception as exc:
        logger.exception("Claude response failed")
        bot.reply_to(message, f"❌ Claude error:\n`{str(exc)}`")


# =========================
# EXTRA: PUSH NOTIFICATIONS
# =========================
def send_push_alert(engine_name: str, risk_level: str, details: str):
    """
    Sends a proactive alert to the admin when a CRITICAL risk is detected.
    """
    if not BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Push failed: Missing Token or Chat ID")
        return

    emoji = "🔴" if risk_level == "CRITICAL" else "⚠️"
    message = (
        f"{emoji} *INDUSTRIAL RISK ALERT*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔹 *Engine:* {engine_name.upper()}\n"
        f"🔹 *Level:* {risk_level}\n"
        f"🔹 *Details:* {details}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 _Action required via Dashboard_"
    )
    
    try:
        # Re-using the existing bot instance
        bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode="Markdown")
        logger.info(f"✅ Push Alert sent for {engine_name}")
    except Exception as e:
        logger.error(f"❌ Failed to send Push: {e}")


# =========================
# 6. LOCAL RUN
# =========================
if __name__ == "__main__":
    logger.info("🚀 Starting local bot polling...")
    bot.infinity_polling(skip_pending=True)