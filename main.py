import telebot
from telebot import types
import yfinance as yf

# --- ВАЖНЫЙ ФИКС ДЛЯ СЕРВЕРА ---
import matplotlib
matplotlib.use('Agg') # Это заставляет графики работать без монитора
import matplotlib.pyplot as plt
# -------------------------------

import io
import threading
import time
import schedule
import pandas as pd
import numpy as np

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = '8212929038:AAFdctXociA1FcnaxKW7N0wbfc6SdFbJ1v0' 
bot = telebot.TeleBot(BOT_TOKEN)

TICKERS = {
    '💵 USDT (Тезер)': 'USDT-USD',
    '🇺🇸 USD (Доллар)': 'DX-Y.NYB',
    '₿ BTC (Биткоин)': 'BTC-USD',
    '💎 ETH (Эфир)': 'ETH-USD',
    '💎 TON (Тонкоин)': 'TON11419-USD',
    '🇪🇺 EUR (Евро)': 'EURUSD=X',
    '🇷🇺 RUB (Рубль)': 'RUB=X',
    '🇨🇳 CNY (Юань)': 'CNY=X',
    '🇦🇪 AED (Дирхам)': 'AED=X',
    '🇹🇯 TJS (Сомони)': 'TJS=X',
    '🇺🇿 UZS (Сум)': 'UZS=X'
}

REVERSE_PAIRS = ['RUB=X', 'CNY=X', 'AED=X', 'TJS=X', 'UZS=X']
users_db = {}

# --- ФУНКЦИИ ---
def get_user_data(uid):
    if uid not in users_db:
        users_db[uid] = {'watchlist': [], 'calc': {}, 'triple': {}, 'last_prices': {}}
    return users_db[uid]

def get_price(ticker):
    try:
        data = yf.Ticker(ticker)
        history = data.history(period='2d')
        if not history.empty:
            return history['Close'].iloc[-1]
    except:
        pass
    return None

def convert_to_usd(amount, ticker, price):
    if ticker in REVERSE_PAIRS: return amount / price
    else: return amount * price

def convert_from_usd(usd_amount, ticker, price):
    if ticker in REVERSE_PAIRS: return usd_amount * price
    else: return usd_amount / price

# --- МЕНЮ ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🧮 Калькулятор (1 шаг)"), types.KeyboardButton("🔀 Тройной обмен (2 шага)"))
    markup.add(types.KeyboardButton("📈 Графики"), types.KeyboardButton("🤖 ИИ Анализ"))
    markup.add(types.KeyboardButton("⭐ Мой список"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    get_user_data(message.chat.id)
    bot.send_message(message.chat.id, "Бот готов к работе (Server Fix Applied).", reply_markup=main_menu())

# --- ТРОЙНОЙ ОБМЕН ---
@bot.message_handler(func=lambda message: message.text == "🔀 Тройной обмен (2 шага)")
def triple_start(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, ticker in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"tr_1_{ticker}"))
    bot.send_message(message.chat.id, "1️⃣ Что отдаем?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_1_'))
def triple_step_2(call):
    uid = call.message.chat.id
    t = call.data.replace('tr_1_', '')
    get_user_data(uid)['triple'] = {'start': t}
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, tk in TICKERS.items(): markup.add(types.InlineKeyboardButton(name, callback_data=f"tr_2_{tk}"))
    bot.edit_message_text(f"Начало: {t}\n2️⃣ Промежуточная:", uid, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_2_'))
def triple_step_3(call):
    uid = call.message.chat.id
    t = call.data.replace('tr_2_', '')
    get_user_data(uid)['triple']['mid'] = t
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, tk in TICKERS.items(): markup.add(types.InlineKeyboardButton(name, callback_data=f"tr_3_{tk}"))
    bot.edit_message_text(f"Цепь: ...-> {t} ->...\n3️⃣ Конец:", uid, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_3_'))
def triple_step_amt(call):
    uid = call.message.chat.id
    t = call.data.replace('tr_3_', '')
    get_user_data(uid)['triple']['end'] = t
    chain = get_user_data(uid)['triple']
    msg = bot.edit_message_text(f"Цепь: {chain.get('start')} -> {chain.get('mid')} -> {t}\nВведите сумму:", uid, call.message.message_id)
    bot.register_next_step_handler(msg, triple_calc_go)

def triple_calc_go(message):
    try:
        amt = float(message.text)
        get_user_data(message.chat.id)['triple']['amount'] = amt
        msg = bot.send_message(message.chat.id, "Введите комиссию %:")
        bot.register_next_step_handler(msg, triple_final)
    except: bot.send_message(message.chat.id, "Ошибка ввода числа.", reply_markup=main_menu())

def triple_final(message):
    try:
        fee = float(message.text)
        data = get_user_data(message.chat.id)['triple']
        t1, t2, t3, amt = data['start'], data['mid'], data['end'], data['amount']
        
        p1, p2, p3 = get_price(t1), get_price(t2), get_price(t3)
        if not p1 or not p2 or not p3:
            bot.send_message(message.chat.id, "Ошибка курса.", reply_markup=main_menu())
            return

        # 1 step
        usd1 = convert_to_usd(amt, t1, p1)
        usd1_clean = usd1 - (usd1 * fee/100)
        res2 = convert_from_usd(usd1_clean, t2, p2)
        # 2 step
        usd2 = convert_to_usd(res2, t2, p2)
        usd2_clean = usd2 - (usd2 * fee/100)
        final = convert_from_usd(usd2_clean, t3, p3)

        text = f"🔀 **Результат:**\n{amt} {t1} ➡️ {res2:.4f} {t2}\n⬇️\n**{final:.2f} {t3}**"
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e: bot.send_message(message.chat.id, f"Ошибка: {e}", reply_markup=main_menu())

# --- ОБЫЧНЫЙ КАЛЬКУЛЯТОР ---
@bot.message_handler(func=lambda message: message.text == "🧮 Калькулятор (1 шаг)")
def s_calc(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): markup.add(types.InlineKeyboardButton(n, callback_data=f"sc_1_{t}"))
    bot.send_message(message.chat.id, "Что меняем?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sc_1_'))
def s_calc_2(call):
    t = call.data.replace('sc_1_', '')
    get_user_data(call.message.chat.id)['calc'] = {'start': t}
    markup = types.InlineKeyboardMarkup(row_width=3)
    for n, tk in TICKERS.items(): markup.add(types.InlineKeyboardButton(n, callback_data=f"sc_2_{tk}"))
    bot.edit_message_text("На что?", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sc_2_'))
def s_calc_3(call):
    t = call.data.replace('sc_2_', '')
    get_user_data(call.message.chat.id)['calc']['end'] = t
    msg = bot.edit_message_text("Сумма:", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(msg, s_calc_4)

def s_calc_4(message):
    try:
        amt = float(message.text)
        get_user_data(message.chat.id)['calc']['amount'] = amt
        msg = bot.send_message(message.chat.id, "Комиссия %:")
        bot.register_next_step_handler(msg, s_calc_5)
    except: pass

def s_calc_5(message):
    try:
        fee = float(message.text)
        d = get_user_data(message.chat.id)['calc']
        t1, t2, amt = d['start'], d['end'], d['amount']
        p1, p2 = get_price(t1), get_price(t2)
        if p1 and p2:
            u = convert_to_usd(amt, t1, p1)
            u_cl = u - (u*fee/100)
            res = convert_from_usd(u_cl, t2, p2)
            bot.send_message(message.chat.id, f"Итог: {res:.2f} {t2}", reply_markup=main_menu())
    except: pass

# --- ИИ И ГРАФИКИ ---
@bot.message_handler(func=lambda message: message.text == "📈 Графики")
def charts(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): markup.add(types.InlineKeyboardButton(n, callback_data=f"ch_{t}"))
    bot.send_message(message.chat.id, "Валюта:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ch_'))
def charts_2(call):
    t = call.data.replace('ch_', '')
    bot.answer_callback_query(call.id, "Генерирую...")
    try:
        data = yf.Ticker(t).history(period="1mo")
        if not data.empty:
            plt.figure(figsize=(10,5))
            plt.plot(data.index, data['Close'])
            plt.title(t)
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            bot.send_photo(call.message.chat.id, buf)
            plt.close()
        else: bot.send_message(call.message.chat.id, "Нет данных")
    except Exception as e: bot.send_message(call.message.chat.id, f"Ошибка: {e}")

@bot.message_handler(func=lambda message: message.text == "🤖 ИИ Анализ")
def ai_start(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): markup.add(types.InlineKeyboardButton(n, callback_data=f"ai_{t}"))
    bot.send_message(message.chat.id, "Валюта:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ai_'))
def ai_run(call):
    t = call.data.replace('ai_', '')
    bot.answer_callback_query(call.id, "Анализ...")
    try:
        data = yf.Ticker(t).history(period="1mo")
        if len(data) > 10:
            delta = data['Close'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=13, adjust=False).mean()
            ema_down = down.ewm(com=13, adjust=False).mean()
            rs = ema_up / ema_down
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            sig = "🟢 ПОКУПАТЬ" if rsi < 30 else "🔴 ПРОДАВАТЬ" if rsi > 70 else "🟡 ЖДАТЬ"
            bot.send_message(call.message.chat.id, f"Анализ {t}:\nRSI: {rsi:.1f}\nСовет: {sig}", parse_mode="Markdown")
        else: bot.send_message(call.message.chat.id, "Мало данных")
    except: bot.send_message(call.message.chat.id, "Ошибка")

# --- СПИСОК ---
@bot.message_handler(func=lambda message: message.text == "⭐ Мой список")
def wl(message):
    wl = get_user_data(message.chat.id).get('watchlist', [])
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
    d = get_user_data(call.message.chat.id)
    if t not in d['watchlist']:
        d['watchlist'].append(t)
        d['last_prices'][t] = get_price(t)
    bot.send_message(call.message.chat.id, "Добавлено!", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "wlc")
def wlc(call):
    get_user_data(call.message.chat.id)['watchlist'] = []
    bot.send_message(call.message.chat.id, "Очищено.", reply_markup=main_menu())

# --- ЗАПУСК ---
def run_sch():
    while True:
        schedule.run_pending()
        time.sleep(1)

def job():
    try:
        for u, d in users_db.items():
            for t in d.get('watchlist', []):
                np = get_price(t)
                op = d['last_prices'].get(t)
                if np and op and abs((np-op)/op*100) >= 3:
                    bot.send_message(u, f"⚠️ Скачок {t}!")
                    d['last_prices'][t] = np
    except: pass

schedule.every(10).minutes.do(job)
threading.Thread(target=run_sch, daemon=True).start()

if __name__ == '__main__':
    bot.infinity_polling()
