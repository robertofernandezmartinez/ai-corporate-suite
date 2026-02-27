import telebot
import requests
import os
from anthropic import Anthropic
from dotenv import load_dotenv
from supabase import create_client

# 1. SETUP
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_URL = os.getenv("SUITE_API_URL", "https://central-api-engine-production.up.railway.app")

bot = telebot.TeleBot(BOT_TOKEN)
claude = Anthropic(api_key=ANTHROPIC_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase_context():
    """Fetches real-time data from the 3 industrial pillars"""
    context = {}
    
    # --- SmartPort ---
    try:
        sp = supabase.table('smartport_predictions').select('risk_level').execute()
        lvls = [r['risk_level'] for r in sp.data]
        context['smartport'] = {'total': len(lvls), 'critical': lvls.count('CRITICAL')}
    except: context['smartport'] = {'total': 0, 'critical': 0}
    
    # --- NASA RUL ---
    try:
        ns = supabase.table('nasa_predictions').select('predicted_rul').execute()
        ruls = [r['predicted_rul'] for r in ns.data]
        context['nasa'] = {'total': len(ruls), 'critical': len([r for r in ruls if r < 30])}
    except: context['nasa'] = {'total': 0, 'critical': 0}
    
    # --- Stockout ---
    try:
        st = supabase.table('stockout_predictions').select('risk_level').execute()
        lvls = [r['risk_level'] for r in st.data]
        context['stockout'] = {'total': len(lvls), 'high': lvls.count('HIGH')}
    except: context['stockout'] = {'total': 0, 'high': 0}
        
    return context

# 2. VISUAL HANDLERS
@bot.message_handler(commands=['start', 'help'])
def welcome(message):
    welcome_text = (
        "✨ *AI Corporate Suite v2.0* ✨\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Hello! I am your **Industrial Intelligence Assistant**. "
        "I monitor your fleet's health in real-time.\n\n"
        "🚀 **Available Commands:**\n"
        "👉 `/status` - Full Fleet Overview\n"
        "👉 `/help` - Show this guide\n\n"
        "💡 *Tip:* You can ask me things like: \n"
        "_'Which engines need maintenance?'_ or \n"
        "_'Give me a summary of the port risk.'_"
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status_report(message):
    ctx = get_supabase_context()
    
    # Visual construction of the report
    report = [
        "📊 *EXECUTIVE SYSTEM REPORT*",
        "━━━━━━━━━━━━━━━━━━",
        f"🚢 *SMARTPORT LOGISTICS*",
        f"  ├ Total Records: `{ctx['smartport']['total']}`",
        f"  └ Critical Alerts: `{'🔴 ' + str(ctx['smartport']['critical']) if ctx['smartport']['critical'] > 0 else '🟢 None'}`",
        "",
        f"🔧 *NASA ENGINE RUL*",
        f"  ├ Engines Monitored: `{ctx['nasa']['total']}`",
        f"  └ Risk (<30 cycles): `{'🔴 ' + str(ctx['nasa']['critical']) if ctx['nasa']['critical'] > 0 else '🟢 Healthy'}`",
        "",
        f"📦 *INVENTORY STOCKOUT*",
        f"  ├ Items Analyzed: `{ctx['stockout']['total']}`",
        f"  └ High Risk: `{'🔴 ' + str(ctx['stockout']['high']) if ctx['stockout']['high'] > 0 else '🟢 Optimal'}`",
        "━━━━━━━━━━━━━━━━━━",
        "💬 *AI Insights:* _Ask me for a detailed analysis of these figures._"
    ]
    
    bot.reply_to(message, "\n".join(report), parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_ai(message):
    bot.send_chat_action(message.chat.id, 'typing')
    context = get_supabase_context()
    
    # Claude System Prompt with Visual Instructions
    system_prompt = f"""You are the AI Corporate Assistant. 
    Data: SmartPort({context['smartport']}), NASA({context['nasa']}), Stockout({context['stockout']}).
    
    RULES:
    1. Use Markdown for bold/italic text.
    2. Use professional Emojis (🚀, 📊, ⚠️, ✅).
    3. Be concise but insightful.
    4. If there are CRITICAL or HIGH risks, highlight them with 🚨.
    5. Always reply in the same language as the user."""

    response = claude.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=800,
        system=system_prompt,
        messages=[{"role": "user", "content": message.text}]
    )
    bot.reply_to(message, response.content[0].text, parse_mode='Markdown')

if __name__ == "__main__":
    print("🚀 Corporate Visual Bot is live...")
    bot.infinity_polling()