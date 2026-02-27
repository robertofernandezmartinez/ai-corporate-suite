import telebot
import requests
import os
from anthropic import Anthropic
from dotenv import load_dotenv
from supabase import create_client
from collections import Counter

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_URL = "http://0.0.0.0:8000"

bot = telebot.TeleBot(BOT_TOKEN)
claude = Anthropic(api_key=ANTHROPIC_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase_context():
    """Get aggregated stats from all 3 systems"""
    context = {}
    
    # SmartPort
    try:
        total = supabase.table('smartport_alerts').select('*', count='exact').execute()
        critical = supabase.table('smartport_alerts').select('*', count='exact').eq('risk_level', 'CRITICAL').execute()
        warning = supabase.table('smartport_alerts').select('*', count='exact').eq('risk_level', 'WARNING').execute()
        normal = supabase.table('smartport_alerts').select('*', count='exact').eq('risk_level', 'NORMAL').execute()
        context['smartport'] = {
            'total': total.count,
            'critical': critical.count,
            'warning': warning.count,
            'normal': normal.count
        }
    except Exception as e:
        context['smartport'] = {'error': str(e)}
    
    # NASA
    try:
        total = supabase.table('nasa_rul_predictions').select('*', count='exact').execute()
        critical = supabase.table('nasa_rul_predictions').select('*', count='exact').eq('rul_category', 'CRITICAL').execute()
        warning = supabase.table('nasa_rul_predictions').select('*', count='exact').eq('rul_category', 'WARNING').execute()
        normal = supabase.table('nasa_rul_predictions').select('*', count='exact').eq('rul_category', 'NORMAL').execute()
        context['nasa'] = {
            'total': total.count,
            'critical': critical.count,
            'warning': warning.count,
            'normal': normal.count,
        }
    except Exception as e:
        context['nasa'] = {'error': str(e)}
    
    # Stockout
    try:
        total = supabase.table('stockout_predictions').select('*', count='exact').execute()
        high = supabase.table('stockout_predictions').select('*', count='exact').eq('risk_level', 'HIGH').execute()
        medium = supabase.table('stockout_predictions').select('*', count='exact').eq('risk_level', 'MEDIUM').execute()
        low = supabase.table('stockout_predictions').select('*', count='exact').eq('risk_level', 'LOW').execute()
        context['stockout'] = {
            'total': total.count,
            'high': high.count,
            'medium': medium.count,
            'low': low.count
        }
    except Exception as e:
        context['stockout'] = {'error': str(e)}
    
    return context

def ask_claude(user_message, context):
    sp = context.get('smartport', {})
    nasa = context.get('nasa', {})
    st = context.get('stockout', {})

    system_prompt = f"""You are an AI assistant for an industrial AI Corporate Suite.
Here is the EXACT current data from 3 systems:

SMARTPORT (vessel delay risk):
- Total predictions: {sp.get('total', 0):,}
- CRITICAL (immediate action): {sp.get('critical', 0):,}
- WARNING (monitor): {sp.get('warning', 0):,}
- NORMAL (routine): {sp.get('normal', 0):,}

NASA RUL (engine remaining useful life):
- Total predictions: {nasa.get('total', 0):,}
- CRITICAL (less than 50 cycles left): {nasa.get('critical', 0):,}
- WARNING (50-100 cycles left): {nasa.get('warning', 0):,}
- NORMAL (more than 100 cycles left): {nasa.get('normal', 0):,}

STOCKOUT RISK (inventory):
- Total predictions: {st.get('total', 0):,}
- HIGH risk (likely stockout): {st.get('high', 0):,}
- MEDIUM risk: {st.get('medium', 0):,}
- LOW risk: {st.get('low', 0):,}

Use ONLY these exact numbers. Do not confuse total with critical.
Answer concisely. Use emojis. Reply in the same language as the user."""

    response = claude.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    return response.content[0].text

@bot.message_handler(commands=['start', 'help'])
def start(message):
    bot.reply_to(message, """
🤖 *AI Corporate Suite Bot*

Hola! Soy tu asistente de IA industrial.

Puedo responder preguntas sobre:
📦 *SmartPort* - Riesgos de delay en puertos
🔧 *NASA RUL* - Vida útil restante de motores  
🏪 *Stockout* - Riesgo de rotura de stock

¡Pregúntame lo que quieras en lenguaje natural!
""", parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status(message):
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code == 200:
            context = get_supabase_context()
            sp = context.get('smartport', {})
            nasa = context.get('nasa', {})
            st = context.get('stockout', {})
            bot.reply_to(message, f"""
✅ *API Online - All 3 models ready*

🚢 *SmartPort:* {sp.get('total', 0):,} predictions
└ 🔴 Critical: {sp.get('critical', 0):,}
└ 🟡 Warning: {sp.get('warning', 0):,}
└ 🟢 Normal: {sp.get('normal', 0):,}

🔧 *NASA RUL:* {nasa.get('total', 0):,} predictions
└ 🔴 Critical: {nasa.get('critical', 0):,}
└ 🟡 Warning: {nasa.get('warning', 0):,}
└ 🟢 Normal: {nasa.get('normal', 0):,}

📦 *Stockout:* {st.get('total', 0):,} predictions
└ 🔴 High: {st.get('high', 0):,}
└ 🟡 Medium: {st.get('medium', 0):,}
└ 🟢 Low: {st.get('low', 0):,}
""", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ API Offline")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        context = get_supabase_context()
        response = ask_claude(message.text, context)
        bot.reply_to(message, response)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🤖 AI Corporate Suite Bot started...")
    bot.infinity_polling()
