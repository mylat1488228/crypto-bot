import telebot
from telebot import types
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import threading
import time
import schedule
import pandas as pd
import numpy as np
import random
from datetime import datetime

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = 'ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН' 
MAIN_ADMIN = 'SIavyanln' # Твой ник без @ (чувствителен к регистру!)

bot = telebot.TeleBot(BOT_TOKEN)

# --- СПИСОК ВАЛЮТ ---
TICKERS = {
    '💵 USDT (Тезер)': 'USDT-USD',
    '🇺🇸 USD (Доллар)': 'DX-Y.NYB',
    '₿ BTC (Биткоин)': 'BTC-USD',
    '💎 ETH (Эфир)': 'ETH-USD',
    '💎 TON (Тонкоин)': 'TON11419-USD',
    '🇪🇺 EUR (Евро)': 'EURUSD=X',
    '🇷🇺 RUB (Рубль)': 'RUB=X',
    '🇰🇬 KGS (Сом)': 'KGS=X',
    '🇨🇳 CNY (Юань)': 'CNY=X',
    '🇦🇪 AED (Дирхам)': 'AED=X',
    '🇹🇯 TJS (Сомони)': 'TJS=X',
    '🇺🇿 UZS (Сум)': 'UZS=X'
}

REVERSE_PAIRS = ['RUB=X', 'KGS=X', 'CNY=X', 'AED=X', 'TJS=X', 'UZS=X']

# --- ДАННЫЕ ---
users_db = {}
global_logs = []
username_map = {}
banned_users = set()
moderators = set()

# --- СИСТЕМНЫЕ ФУНКЦИИ ---
def log_action(uid, username, action):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uname = username if username else "NoName"
    entry = f"[{timestamp}] @{uname} ({uid}): {action}"
    global_logs.append(entry)
    if len(global_logs) > 100: global_logs.pop(0)
    if uid in users_db: users_db[uid]['logs'].append(entry)

def get_user_data(message):
    uid = message.chat.id
    uname = message.from_user.username
    if uname: username_map[uname] = uid
    if uid not in users_db:
        users_db[uid] = {
            'watchlist': [], 'calc': {}, 'triple': {}, 
            'chart_cur': None, 'last_prices': {}, 'mode': 'menu',
            'logs': [], 'tutorial_passed': False
        }
    return users_db[uid]

def get_safe_price(ticker):
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period='2d')
        if not hist.empty: return hist['Close'].iloc[-1]
    except: pass
    return None

def convert_to_usd(amount, ticker, price):
    if ticker in REVERSE_PAIRS: return amount / price
    else: return amount * price

def convert_from_usd(usd_amount, ticker, price):
    if ticker in REVERSE_PAIRS: return usd_amount * price
    else: return usd_amount / price

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🧮 Калькулятор"), types.KeyboardButton("🔀 Тройной обмен"))
    markup.add(types.KeyboardButton("📈 Графики"), types.KeyboardButton("⭐ Мой список"))
    markup.add(types.KeyboardButton("💬 AI Помощник (Чат)"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    uid = message.chat.id
    if uid in banned_users: return
    data = get_user_data(message)
    log_action(uid, message.from_user.username, "Запуск бота")
    
    if not data['tutorial_passed']:
        # ОБУЧЕНИЕ НОВИЧКА ИИ-Ассистентом
        bot.send_message(uid, f"🤖 Привет, @{message.from_user.username}! Я твой финансовый ИИ-ассистент.")
        time.sleep(1)
        bot.send_message(uid, "Давай я быстро покажу, что я умею:\n\n"
                              "1. **Калькулятор** — Считает обмен с комиссией.\n"
                              "2. **Тройной обмен** — Это для арбитража (например USDT->TON->KGS).\n"
                              "3. **AI Помощник** — Это чат со мной. Спроси меня 'Что купить?', и я проанализирую рынок.\n"
                              "4. **Список** — Добавь валюту, и я буду следить за ее ценой каждый час.")
        time.sleep(2)
        data['tutorial_passed'] = True
        bot.send_message(uid, "Теперь ты готов! Начинаем?", reply_markup=main_menu())
    else:
        data['mode'] = 'menu'
        bot.send_message(uid, "С возвращением! Я готов к работе.", reply_markup=main_menu())

# =======================
# КОНСОЛЬ АДМИНА (Исправленная)
# =======================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    uid = message.chat.id
    uname = message.from_user.username
    
    is_main = (uname == MAIN_ADMIN)
    is_mod = (uid in moderators)

    if not (is_main or is_mod): return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📜 Логи (ВСЕ)", callback_data="adm_logs_all"),
               types.InlineKeyboardButton("👤 Логи (User)", callback_data="adm_logs_user"))
    
    title = "🛡 **ПАНЕЛЬ МОДЕРАТОРА**"
    if is_main:
        title = "🔒 **ПАНЕЛЬ АДМИНИСТРАТОРА**"
        markup.add(types.InlineKeyboardButton("🚫 Бан/Разбан", callback_data="adm_ban"),
                   types.InlineKeyboardButton("👮 Добавить Модера", callback_data="adm_add_mod"),
                   types.InlineKeyboardButton("🗑 Снять Модера", callback_data="adm_del_mod"),
                   types.InlineKeyboardButton("📋 Списки", callback_data="adm_lists"))

    bot.send_message(uid, title, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_actions(call):
    uid = call.message.chat.id
    uname = call.from_user.username
    action = call.data
    
    is_main = (uname == MAIN_ADMIN)
    
    if action == "adm_logs_all":
        logs = "\n".join(global_logs[-15:]) or "Пусто."
        bot.send_message(uid, f"📜 Логи:\n{logs}")
    elif action == "adm_logs_user":
        msg = bot.send_message(uid, "Введите @username:")
        bot.register_next_step_handler(msg, show_user_logs)
    
    # Только для главного
    elif is_main:
        if action == "adm_ban":
            msg = bot.send_message(uid, "Введите @username для бана:")
            bot.register_next_step_handler(msg, ban_logic)
        elif action == "adm_add_mod":
            msg = bot.send_message(uid, "Введите @username модера:")
            bot.register_next_step_handler(msg, add_mod)
        elif action == "adm_del_mod":
            msg = bot.send_message(uid, "Введите @username:")
            bot.register_next_step_handler(msg, del_mod)
        elif action == "adm_lists":
            bot.send_message(uid, f"Banned: {banned_users}\nMods: {moderators}")
    else:
        bot.answer_callback_query(call.id, "Нет прав.")

# Логика админки
def show_user_logs(message):
    t = message.text.replace('@', '')
    tid = username_map.get(t)
    if tid and tid in users_db: bot.send_message(message.chat.id, "\n".join(users_db[tid]['logs'][-15:]))
    else: bot.send_message(message.chat.id, "Не найден.")

def ban_logic(message):
    t = message.text.replace('@', '')
    tid = username_map.get(t)
    if tid:
        if tid in banned_users: banned_users.remove(tid); bot.send_message(message.chat.id, "Разбанен.")
        else: banned_users.add(tid); bot.send_message(message.chat.id, "Забанен.")
    else: bot.send_message(message.chat.id, "ID не найден.")

def add_mod(message):
    t = message.text.replace('@', '')
    tid = username_map.get(t)
    if tid: moderators.add(tid); bot.send_message(message.chat.id, "Модер добавлен.")
    else: bot.send_message(message.chat.id, "Не найден.")

def del_mod(message):
    t = message.text.replace('@', '')
    tid = username_map.get(t)
    if tid in moderators: moderators.remove(tid); bot.send_message(message.chat.id, "Модер снят.")

# =======================
# РАЗГОВОРНЫЙ ИИ (CHAT MODE)
# =======================
@bot.message_handler(func=lambda message: message.text == "💬 AI Помощник (Чат)")
def ai_enter(message):
    if message.chat.id in banned_users: return
    get_user_data(message)['mode'] = 'chat'
    log_action(message.chat.id, message.from_user.username, "Вошел в AI Чат")
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Что купить?", "Что продать?")
    markup.add("🔙 Главное меню")
    
    bot.send_message(message.chat.id, "🤖 Режим чата активирован!\n\nТы можешь спросить:\n- *Что купить сейчас?*\n- *Как дела?*\n- *Какая погода?*\n- *Как работает бот?*\n\nИли просто пообщаться.", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: get_user_data(message).get('mode') == 'chat')
def ai_conversation(message):
    uid = message.chat.id
    if uid in banned_users: return
    text = message.text.lower()
    
    # ВЫХОД
    if message.text == "🔙 Главное меню":
        get_user_data(message)['mode'] = 'menu'
        bot.send_message(uid, "Выход в меню.", reply_markup=main_menu())
        return

    # 1. ФИНАНСОВЫЙ СКАНЕР (УМНЫЙ)
    if "купить" in text or "продать" in text or "вложить" in text or "выгодно" in text:
        bot.send_message(uid, "🧐 Секунду, сканирую рынок (RSI индикаторы)...")
        
        # Реальный скан
        best_buy, best_sell = None, None
        low_rsi, high_rsi = 100, 0
        
        for name, ticker in TICKERS.items():
            try:
                data = yf.Ticker(ticker).history(period="1mo")
                if len(data) > 10:
                    delta = data['Close'].diff()
                    u, d = delta.clip(lower=0), -1 * delta.clip(upper=0)
                    rs = u.ewm(com=13, adjust=False).mean() / d.ewm(com=13, adjust=False).mean()
                    rsi = 100 - (100 / (1 + rs)).iloc[-1]
                    
                    if rsi < low_rsi: low_rsi, best_buy = rsi, name
                    if rsi > high_rsi: high_rsi, best_sell = rsi, name
            except: continue
        
        response = ""
        # Логика ответов
        if best_buy and low_rsi < 40:
            response += f"🚀 **Брат, обрати внимание на {best_buy}.**\nRSI {low_rsi:.1f} (Перепродана). Хороший момент для входа.\n\n"
        else:
            response += "📉 Для покупки сейчас всё дороговато. Лучше подождать.\n\n"
            
        if best_sell and high_rsi > 60:
            response += f"💰 **Если держишь {best_sell}, можно фиксировать прибыль.**\nRSI {high_rsi:.1f} (Перекуплена)."
        else:
            response += "🛡 Для продажи сигналов нет. HODL (Держи)!"
            
        bot.send_message(uid, response, parse_mode="Markdown")
        return

    # 2. РАЗГОВОРНАЯ ЧАСТЬ (БОЛТАЛКА)
    if "привет" in text or "салам" in text or "здравствуй" in text:
        answers = ["Салам! Готов делать деньги?", "Приветствую! Смотрим графики?", "Привет! Я на связи 24/7."]
        bot.send_message(uid, random.choice(answers))
        return
        
    if "как дела" in text or "как жизнь" in text:
        bot.send_message(uid, "У меня всё стабильно, как курс USDT. А у тебя как? Профит есть?")
        return
        
    if "погода" in text:
        bot.send_message(uid, "Я облачный бот, у меня всегда облачно ☁️. Но если серьезно — посмотри в окно, я же графики анализирую, а не метеорологию!")
        return
        
    if "кто ты" in text or "что ты" in text:
        bot.send_message(uid, "Я — твой карманный финансовый аналитик. Умею считать арбитраж, следить за ценами и давать советы. И я никогда не сплю.")
        return
        
    if "как пользоваться" in text or "помоги" in text:
        bot.send_message(uid, "Всё просто:\n1. Нажми 'Назад в меню'.\n2. 'Калькулятор' чтобы посчитать обмен.\n3. 'Мой список' чтобы следить за криптой.\nЕсли что — спрашивай!")
        return

    # 3. ЕСЛИ НЕ ПОНЯЛ
    bot.send_message(uid, "Слушай, я не ChatGPT, я финансовый бот. Спроси меня 'Что купить', 'Как дела' или просто нажми кнопки.", parse_mode="Markdown")


# =======================
# ФУНКЦИИ БОТА (КАЛЬКУЛЯТОРЫ И ТД)
# =======================
@bot.message_handler(func=lambda message: message.text == "🧮 Калькулятор")
def calc(message):
    if message.chat.id in banned_users: return
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"sc_1_{t}"))
    bot.send_message(message.chat.id, "Что меняем?", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sc_1_'))
def sc_2(call):
    get_user_data(call.message)['calc'] = {'start': call.data.replace('sc_1_', '')}
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"sc_2_{t}"))
    bot.edit_message_text("На что?", call.message.chat.id, call.message.message_id, reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sc_2_'))
def sc_3(call):
    get_user_data(call.message)['calc']['end'] = call.data.replace('sc_2_', '')
    msg = bot.edit_message_text("Сумма:", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(msg, sc_4)

def sc_4(message):
    try:
        get_user_data(message)['calc']['amount'] = float(message.text)
        msg = bot.send_message(message.chat.id, "Комиссия %:")
        bot.register_next_step_handler(msg, sc_5)
    except: pass

def sc_5(message):
    try:
        fee = float(message.text)
        d = get_user_data(message)['calc']
        p1, p2 = get_safe_price(d['start']), get_safe_price(d['end'])
        if p1 and p2:
            u = convert_to_usd(d['amount'], d['start'], p1)
            res = convert_from_usd(u-(u*fee/100), d['end'], p2)
            bot.send_message(message.chat.id, f"Итог: {res:.2f} {d['end']}", reply_markup=main_menu())
            log_action(message.chat.id, message.from_user.username, "Калькулятор")
    except: pass

@bot.message_handler(func=lambda message: message.text == "🔀 Тройной обмен")
def tr(message):
    if message.chat.id in banned_users: return
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"tr_1_{t}"))
    bot.send_message(message.chat.id, "1. Старт:", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_1_'))
def tr_2(call):
    get_user_data(call.message)['triple'] = {'start': call.data.replace('tr_1_', '')}
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"tr_2_{t}"))
    bot.edit_message_text("2. Центр:", call.message.chat.id, call.message.message_id, reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_2_'))
def tr_3(call):
    get_user_data(call.message)['triple']['mid'] = call.data.replace('tr_2_', '')
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"tr_3_{t}"))
    bot.edit_message_text("3. Финиш:", call.message.chat.id, call.message.message_id, reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_3_'))
def tr_4(call):
    get_user_data(call.message)['triple']['end'] = call.data.replace('tr_3_', '')
    msg = bot.edit_message_text("Сумма:", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(msg, tr_5)

def tr_5(message):
    try:
        get_user_data(message)['triple']['amount'] = float(message.text)
        msg = bot.send_message(message.chat.id, "Комиссия %:")
        bot.register_next_step_handler(msg, tr_6)
    except: pass

def tr_6(message):
    try:
        fee = float(message.text)
        d = get_user_data(message)['triple']
        p1, p2, p3 = get_safe_price(d['start']), get_safe_price(d['mid']), get_safe_price(d['end'])
        if p1 and p2 and p3:
            u1 = convert_to_usd(d['amount'], d['start'], p1)
            u2 = convert_to_usd(convert_from_usd(u1*(1-fee/100), d['mid'], p2), d['mid'], p2)
            res = convert_from_usd(u2*(1-fee/100), d['end'], p3)
            bot.send_message(message.chat.id, f"Итог: {res:.2f} {d['end']}", reply_markup=main_menu())
            log_action(message.chat.id, message.from_user.username, "Тройной обмен")
    except: pass

@bot.message_handler(func=lambda message: message.text == "📈 Графики")
def chart(message):
    if message.chat.id in banned_users: return
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"ch_{t}"))
    bot.send_message(message.chat.id, "Валюта:", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ch_'))
def ch_2(call):
    get_user_data(call.message)['chart_cur'] = call.data.replace('ch_', '')
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("30 дней", callback_data="tm_30d"), types.InlineKeyboardButton("1 день", callback_data="tm_1d"))
    bot.edit_message_text("Период:", call.message.chat.id, call.message.message_id, reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tm_'))
def ch_3(call):
    tm = call.data.replace('tm_', '')
    t = get_user_data(call.message)['chart_cur']
    bot.answer_callback_query(call.id, "Рисую...")
    p, i = ('1mo', '1d') if tm == '30d' else ('1d', '30m')
    try:
        d = yf.Ticker(t).history(period=p, interval=i)
        if not d.empty:
            plt.figure(figsize=(10,5))
            plt.plot(d.index, d['Close'])
            plt.title(f"{t} ({tm})")
            plt.grid(True)
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            bot.send_photo(call.message.chat.id, buf)
            plt.close()
    except: pass

@bot.message_handler(func=lambda message: message.text == "⭐ Мой список")
def wl(message):
    if message.chat.id in banned_users: return
    wl = get_user_data(message).get('watchlist', [])
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("➕ Добавить", callback_data="wla"), types.InlineKeyboardButton("➖ Очистить", callback_data="wlc"))
    bot.send_message(message.chat.id, f"Список: {wl}", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data == "wla")
def wla(call):
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"wls_{t}"))
    bot.edit_message_text("Выбери:", call.message.chat.id, call.message.message_id, reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('wls_'))
def wls(call):
    t = call.data.replace('wls_', '')
    d = get_user_data(call.message)
    if t not in d['watchlist']: 
        d['watchlist'].append(t)
        d['last_prices'][t] = get_safe_price(t)
    bot.send_message(call.message.chat.id, "Добавлено!", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "wlc")
def wlc(call):
    get_user_data(call.message)['watchlist'] = []
    bot.send_message(call.message.chat.id, "Очищено.", reply_markup=main_menu())

def run_bg():
    while True:
        schedule.run_pending()
        time.sleep(1)

def job():
    for u, d in users_db.items():
        if u in banned_users: continue
        for t in d.get('watchlist', []):
            np = get_safe_price(t)
            op = d['last_prices'].get(t)
            if np and op and abs((np-op)/op*100) >= 3:
                bot.send_message(u, f"⚠️ Скачок {t}!")
                d['last_prices'][t] = np

schedule.every(10).minutes.do(job)
threading.Thread(target=run_bg, daemon=True).start()

if __name__ == '__main__':
    bot.infinity_polling()
