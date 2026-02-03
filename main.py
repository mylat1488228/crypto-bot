import telebot
from telebot import types
import yfinance as yf
import matplotlib
matplotlib.use('Agg') # Фикс для сервера
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
MAIN_ADMIN = 'SIavyanln' # Юзернейм главного админа БЕЗ @ (чувствителен к регистру)

bot = telebot.TeleBot(BOT_TOKEN)

# --- ВАЛЮТЫ ---
TICKERS = {
    '💵 USDT (Тезер)': 'USDT-USD',
    '🇺🇸 USD (Доллар)': 'DX-Y.NYB',
    '₿ BTC (Биткоин)': 'BTC-USD',
    '💎 ETH (Эфир)': 'ETH-USD',
    '💎 TON (Тонкоин)': 'TON11419-USD',
    '🇪🇺 EUR (Евро)': 'EURUSD=X',
    '🇷🇺 RUB (Рубль)': 'RUB=X',
    '🇰🇬 KGS (Сом)': 'KGS=X',  # Новая валюта
    '🇨🇳 CNY (Юань)': 'CNY=X',
    '🇦🇪 AED (Дирхам)': 'AED=X',
    '🇹🇯 TJS (Сомони)': 'TJS=X',
    '🇺🇿 UZS (Сум)': 'UZS=X'
}

# Валюты, курс которых "Х единиц за 1 доллар"
REVERSE_PAIRS = ['RUB=X', 'KGS=X', 'CNY=X', 'AED=X', 'TJS=X', 'UZS=X']

# --- БАЗЫ ДАННЫХ (RAM) ---
users_db = {}       # Данные юзеров
global_logs = []    # Общий лог действий
username_map = {}   # Связь username -> chat_id (для бана по нику)
banned_users = set()
moderators = set()

# --- СИСТЕМНЫЕ ФУНКЦИИ ---

def log_action(uid, username, action):
    # Записываем действие в лог
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uname = username if username else "NoName"
    entry = f"[{timestamp}] @{uname} ({uid}): {action}"
    
    # Сохраняем в общий лог (храним последние 100)
    global_logs.append(entry)
    if len(global_logs) > 100: global_logs.pop(0)
    
    # Сохраняем в личный лог юзера
    if uid in users_db:
        users_db[uid]['logs'].append(entry)

def get_user_data(message):
    uid = message.chat.id
    uname = message.from_user.username
    
    # Сохраняем маппинг ника для админки
    if uname:
        username_map[uname] = uid
    
    if uid not in users_db:
        # Новый пользователь
        users_db[uid] = {
            'watchlist': [], 'calc': {}, 'triple': {}, 
            'chart_cur': None, 'last_prices': {}, 'mode': 'menu',
            'logs': [], 'tutorial_passed': False
        }
    return users_db[uid]

def is_admin(username):
    return username == MAIN_ADMIN

def is_mod(username, uid):
    return username == MAIN_ADMIN or uid in moderators

def get_price(ticker):
    try:
        data = yf.Ticker(ticker).history(period='2d')
        if not history.empty: return history['Close'].iloc[-1]
        # Fallback fetch
        return data['Close'].iloc[-1]
    except: return None
    
# Обновленная функция цены с защитой
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

# --- МЕНЮ И СТАРТ ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🧮 Калькулятор"), types.KeyboardButton("🔀 Тройной обмен"))
    markup.add(types.KeyboardButton("📈 Графики"), types.KeyboardButton("⭐ Мой список"))
    markup.add(types.KeyboardButton("💬 AI Помощник"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    uid = message.chat.id
    if uid in banned_users: return # Игнор забаненных
    
    data = get_user_data(message)
    log_action(uid, message.from_user.username, "Запустил бота (/start)")
    
    if not data['tutorial_passed']:
        # ОБУЧЕНИЕ НОВИЧКА
        bot.send_message(uid, f"👋 Привет, @{message.from_user.username}!\nЯ вижу ты тут впервые. Давай я быстро научу тебя пользоваться мной.")
        time.sleep(1)
        bot.send_message(uid, "🧮 **Калькулятор** — Считает честный обмен с учетом комиссии биржи.")
        time.sleep(1)
        bot.send_message(uid, "📈 **Графики** — Покажу историю цены любой валюты (от 30 дней до 3 часов).")
        time.sleep(1)
        bot.send_message(uid, "🔀 **Арбитраж** — Посчитаю сложную сделку (например, USDT -> TON -> KGS).")
        time.sleep(1)
        bot.send_message(uid, "💬 **AI** — Можешь спросить меня 'Что купить?', и я проанализирую рынок. Или просто спроси про погоду (я пошучу).")
        time.sleep(1)
        data['tutorial_passed'] = True
        bot.send_message(uid, "Теперь ты готов! Выбирай действие:", reply_markup=main_menu())
    else:
        data['mode'] = 'menu'
        bot.send_message(uid, "С возвращением! Работаем.", reply_markup=main_menu())

# =======================
# КОНСОЛЬ АДМИНИСТРАТОРА (Для @SIavyanln)
# =======================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.username != MAIN_ADMIN:
        return # Игнорируем чужаков

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📜 Логи (ВСЕ)", callback_data="adm_logs_all"),
        types.InlineKeyboardButton("👤 Логи (User)", callback_data="adm_logs_user"),
        types.InlineKeyboardButton("🚫 Бан/Разбан", callback_data="adm_ban"),
        types.InlineKeyboardButton("👮 Добавить Модера", callback_data="adm_add_mod"),
        types.InlineKeyboardButton("🗑 Удалить Модера", callback_data="adm_del_mod"),
        types.InlineKeyboardButton("📋 Список банов", callback_data="adm_list_ban")
    )
    bot.send_message(message.chat.id, "🔒 **АДМИН КОНСОЛЬ** 🔒\nПривет, Создатель. Что делаем?", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_actions(call):
    if call.from_user.username != MAIN_ADMIN: return
    
    action = call.data
    
    if action == "adm_logs_all":
        # Показать последние 15 логов
        logs_text = "\n".join(global_logs[-15:])
        if not logs_text: logs_text = "Логов нет."
        bot.send_message(call.message.chat.id, f"📜 **Последние события:**\n\n{logs_text}", parse_mode="HTML")
        
    elif action == "adm_logs_user":
        msg = bot.send_message(call.message.chat.id, "Введите @username пользователя для просмотра логов:")
        bot.register_next_step_handler(msg, show_user_logs)
        
    elif action == "adm_ban":
        msg = bot.send_message(call.message.chat.id, "Введите @username для БАНА (или разбана):")
        bot.register_next_step_handler(msg, ban_user_logic)
        
    elif action == "adm_add_mod":
        msg = bot.send_message(call.message.chat.id, "Введите @username нового модератора:")
        bot.register_next_step_handler(msg, add_mod_logic)
        
    elif action == "adm_list_ban":
        text = f"Забанены ID: {banned_users}"
        bot.send_message(call.message.chat.id, text)

# Логика админских функций
def show_user_logs(message):
    target = message.text.replace('@', '')
    tid = username_map.get(target)
    if tid and tid in users_db:
        logs = "\n".join(users_db[tid]['logs'][-15:])
        bot.send_message(message.chat.id, f"Логи {target}:\n{logs}")
    else:
        bot.send_message(message.chat.id, "Пользователь не найден или не пользовался ботом.")

def ban_user_logic(message):
    target = message.text.replace('@', '')
    tid = username_map.get(target)
    if tid:
        if tid in banned_users:
            banned_users.remove(tid)
            bot.send_message(message.chat.id, f"✅ Пользователь @{target} разбанен.")
        else:
            banned_users.add(tid)
            bot.send_message(message.chat.id, f"🚫 Пользователь @{target} ЗАБАНЕН.")
    else:
        bot.send_message(message.chat.id, "Не могу найти ID этого юзера. Пусть он сначала запустит бота.")

def add_mod_logic(message):
    target = message.text.replace('@', '')
    tid = username_map.get(target)
    if tid:
        moderators.add(tid)
        bot.send_message(message.chat.id, f"👮 @{target} теперь Модератор (видит логи, но не банит).")
    else:
        bot.send_message(message.chat.id, "Юзер не найден.")

# =======================
# AI ЧАТ (РАСШИРЕННЫЙ)
# =======================
@bot.message_handler(func=lambda message: message.text == "💬 AI Помощник")
def ai_chat_mode(message):
    uid = message.chat.id
    if uid in banned_users: return
    get_user_data(message)['mode'] = 'chat'
    log_action(uid, message.from_user.username, "Вошел в AI чат")
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Что купить?", "Что продать?", "Погода")
    markup.add("🔙 Меню")
    bot.send_message(uid, "🤖 Я готов. Спрашивай про рынок, валюты или просто о жизни.", reply_markup=markup)

@bot.message_handler(func=lambda message: get_user_data(message).get('mode') == 'chat')
def ai_logic(message):
    uid = message.chat.id
    if uid in banned_users: return
    text = message.text.lower()
    
    if message.text == "🔙 Меню":
        get_user_data(message)['mode'] = 'menu'
        bot.send_message(uid, "Меню:", reply_markup=main_menu())
        return

    # 1. БАЗОВЫЕ ВОПРОСЫ (Эмуляция умного бота)
    if "погода" in text:
        responses = [
            "🌦 Я живу на сервере, тут всегда +25 и сухо. А у тебя советую глянуть в окно!",
            "У меня нет глаз, но судя по графикам, на рынке сегодня шторм! 📉",
            "Зачем тебе погода? Главное, чтобы Биткоин рос! 🚀"
        ]
        bot.send_message(uid, random.choice(responses))
        return
        
    if "привет" in text or "как дела" in text:
        bot.send_message(uid, "Дела отлично, считаю проценты. Ты как? Готов заработать?")
        return

    # 2. ФИНАНСОВЫЙ АНАЛИЗ
    if "купить" in text or "продать" in text:
        bot.send_message(uid, "🧠 Сканирую 12 пар валют...")
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
            
        msg = ""
        if best_buy and low_rsi < 40:
            msg += f"🟢 **Советую купить:** {best_buy} (RSI {low_rsi:.1f} - дешево).\n"
        else: msg += "🟢 Покупок с хорошей скидкой пока нет.\n"
        
        if best_sell and high_rsi > 60:
            msg += f"🔴 **Советую продать:** {best_sell} (RSI {high_rsi:.1f} - дорого)."
        else: msg += "🔴 Продавать пока рано, держи."
        
        bot.send_message(uid, msg, parse_mode="Markdown")
    else:
        bot.send_message(uid, "Я не совсем понял. Спроси 'Что купить' или 'Погода'.")

# =======================
# ФУНКЦИОНАЛ (Калькуляторы, Графики)
# =======================
@bot.message_handler(func=lambda message: message.text == "🧮 Калькулятор")
def s_calc(message):
    if message.chat.id in banned_users: return
    log_action(message.chat.id, message.from_user.username, "Открыл Калькулятор")
    markup = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): markup.add(types.InlineKeyboardButton(n, callback_data=f"sc_1_{t}"))
    bot.send_message(message.chat.id, "Что меняем?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sc_1_'))
def sc_2(call):
    get_user_data(call.message)['calc'] = {'start': call.data.replace('sc_1_', '')}
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"sc_2_{t}"))
    bot.edit_message_text("На что меняем?", call.message.chat.id, call.message.message_id, reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sc_2_'))
def sc_3(call):
    get_user_data(call.message)['calc']['end'] = call.data.replace('sc_2_', '')
    msg = bot.edit_message_text("Введите сумму:", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(msg, sc_4)

def sc_4(message):
    try:
        amt = float(message.text)
        get_user_data(message)['calc']['amount'] = amt
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
            final = convert_from_usd(u - (u*fee/100), d['end'], p2)
            bot.send_message(message.chat.id, f"Итог: {final:.2f} {d['end']}", reply_markup=main_menu())
            log_action(message.chat.id, message.from_user.username, f"Посчитал {d['amount']} {d['start']} -> {d['end']}")
    except: pass

@bot.message_handler(func=lambda message: message.text == "🔀 Тройной обмен")
def tr_start(message):
    if message.chat.id in banned_users: return
    log_action(message.chat.id, message.from_user.username, "Открыл Тройной обмен")
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"tr_1_{t}"))
    bot.send_message(message.chat.id, "1. Что отдаем?", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_1_'))
def tr_2(call):
    get_user_data(call.message)['triple'] = {'start': call.data.replace('tr_1_', '')}
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"tr_2_{t}"))
    bot.edit_message_text("2. Промежуточная:", call.message.chat.id, call.message.message_id, reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_2_'))
def tr_3(call):
    get_user_data(call.message)['triple']['mid'] = call.data.replace('tr_2_', '')
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"tr_3_{t}"))
    bot.edit_message_text("3. Конец:", call.message.chat.id, call.message.message_id, reply_markup=m)

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
            res2 = convert_from_usd(u1 - (u1*fee/100), d['mid'], p2)
            u2 = convert_to_usd(res2, d['mid'], p2)
            fin = convert_from_usd(u2 - (u2*fee/100), d['end'], p3)
            bot.send_message(message.chat.id, f"Итог: {fin:.2f} {d['end']}", reply_markup=main_menu())
            log_action(message.chat.id, message.from_user.username, "Сделал тройной расчет")
    except: pass

@bot.message_handler(func=lambda message: message.text == "📈 Графики")
def charts(message):
    if message.chat.id in banned_users: return
    log_action(message.chat.id, message.from_user.username, "Смотрит графики")
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"ch_{t}"))
    bot.send_message(message.chat.id, "Валюта:", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ch_'))
def ch_2(call):
    get_user_data(call.message)['chart_cur'] = call.data.replace('ch_', '')
    m = types.InlineKeyboardMarkup(row_width=3)
    m.add(types.InlineKeyboardButton("30 дней", callback_data="tm_30d"), types.InlineKeyboardButton("7 дней", callback_data="tm_7d"), types.InlineKeyboardButton("1 день", callback_data="tm_1d"))
    bot.edit_message_text("Период:", call.message.chat.id, call.message.message_id, reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tm_'))
def ch_3(call):
    tm = call.data.replace('tm_', '')
    t = get_user_data(call.message)['chart_cur']
    bot.answer_callback_query(call.id, "Генерирую...")
    
    p, i = '1mo', '1d'
    if tm == '7d': p, i = '5d', '60m'
    if tm == '1d': p, i = '1d', '15m'
    
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

# --- СПИСОК ---
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
    log_action(call.message.chat.id, call.from_user.username, f"Добавил {t} в список")

@bot.callback_query_handler(func=lambda call: call.data == "wlc")
def wlc(call):
    get_user_data(call.message)['watchlist'] = []
    bot.send_message(call.message.chat.id, "Очищено.", reply_markup=main_menu())

# --- ФОНОВЫЕ ЗАДАЧИ ---
def run_bg():
    while True:
        schedule.run_pending()
        time.sleep(1)

def job_check():
    for u, d in users_db.items():
        if u in banned_users: continue
        for t in d.get('watchlist', []):
            np = get_safe_price(t)
            op = d['last_prices'].get(t)
            if np and op and abs((np-op)/op*100) >= 3:
                bot.send_message(u, f"⚠️ Скачок {t}!")
                d['last_prices'][t] = np

schedule.every(10).minutes.do(job_check)
threading.Thread(target=run_bg, daemon=True).start()

if __name__ == '__main__':
    bot.infinity_polling()
