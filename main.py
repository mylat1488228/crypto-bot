import telebot
from telebot import types
import yfinance as yf
import matplotlib.pyplot as plt
import io
import threading
import time
import schedule
import pandas as pd
import numpy as np

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = '8212929038:AAFdctXociA1FcnaxKW7N0wbfc6SdFbJ1v0' 
bot = telebot.TeleBot(BOT_TOKEN)

# Тикеры валют
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

# Обратные пары (где курс показывает кол-во валюты за 1 доллар)
REVERSE_PAIRS = ['RUB=X', 'CNY=X', 'AED=X', 'TJS=X', 'UZS=X']

# Хранилище (в памяти)
users_db = {}

# --- БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ДАННЫХ ---
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
    if ticker in REVERSE_PAIRS:
        return amount / price
    else:
        return amount * price

def convert_from_usd(usd_amount, ticker, price):
    if ticker in REVERSE_PAIRS:
        return usd_amount * price
    else:
        return usd_amount / price

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🧮 Калькулятор (1 шаг)"), types.KeyboardButton("🔀 Тройной обмен (2 шага)"))
    markup.add(types.KeyboardButton("📈 Графики"), types.KeyboardButton("🤖 ИИ Анализ"))
    markup.add(types.KeyboardButton("⭐ Мой список"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    get_user_data(message.chat.id)
    bot.send_message(message.chat.id, "Привет! Бот перезапущен и готов к работе.", reply_markup=main_menu())

# =======================
# ТРОЙНОЙ ОБМЕН (ARBITRAGE)
# =======================
@bot.message_handler(func=lambda message: message.text == "🔀 Тройной обмен (2 шага)")
def triple_start(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, ticker in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"tr_1_{ticker}"))
    bot.send_message(message.chat.id, "1️⃣ Что отдаем? (Начало)", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_1_'))
def triple_step_2(call):
    uid = call.message.chat.id
    user_data = get_user_data(uid)
    
    ticker = call.data.replace('tr_1_', '')
    user_data['triple'] = {'start': ticker}
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, t in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"tr_2_{t}"))
    
    bot.edit_message_text(f"Начало: {ticker}\n2️⃣ Промежуточная валюта:", uid, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_2_'))
def triple_step_3(call):
    uid = call.message.chat.id
    user_data = get_user_data(uid)
    
    if 'triple' not in user_data or 'start' not in user_data['triple']:
        bot.send_message(uid, "Ошибка сессии. Начните заново.", reply_markup=main_menu())
        return

    ticker = call.data.replace('tr_2_', '')
    user_data['triple']['mid'] = ticker
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, t in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"tr_3_{t}"))
    
    bot.edit_message_text(f"Цепочка: ... -> {ticker} -> ...\n3️⃣ Что получаем в конце?", uid, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_3_'))
def triple_step_amount(call):
    uid = call.message.chat.id
    user_data = get_user_data(uid)
    
    ticker = call.data.replace('tr_3_', '')
    if 'triple' not in user_data: 
        bot.send_message(uid, "Ошибка данных.", reply_markup=main_menu())
        return
        
    user_data['triple']['end'] = ticker
    chain = user_data['triple']
    
    msg = bot.edit_message_text(f"⛓ Цепь: {chain.get('start')} ➡️ {chain.get('mid')} ➡️ {ticker}\n\nВведите сумму (число):", uid, call.message.message_id)
    bot.register_next_step_handler(msg, triple_get_amount)

def triple_get_amount(message):
    try:
        # Вот здесь у тебя была ошибка отступа. Теперь исправлено.
        amount = float(message.text)
        get_user_data(message.chat.id)['triple']['amount'] = amount
        msg = bot.send_message(message.chat.id, "Введите % комиссии (снимается дважды):")
        bot.register_next_step_handler(msg, triple_calc_final)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Это не число. Попробуйте заново через меню.", reply_markup=main_menu())

def triple_calc_final(message):
    try:
        fee = float(message.text)
        user_data = get_user_data(message.chat.id)
        data = user_data.get('triple', {})
        
        if not all(k in data for k in ['start', 'mid', 'end', 'amount']):
            bot.send_message(message.chat.id, "Данные устарели. Начните заново.", reply_markup=main_menu())
            return
        
        t1, t2, t3 = data['start'], data['mid'], data['end']
        amount = data['amount']
        
        msg = bot.send_message(message.chat.id, "⏳ Считаю курсы...")
        
        p1 = get_price(t1)
        p2 = get_price(t2)
        p3 = get_price(t3)
        
        if p1 is None or p2 is None or p3 is None:
            bot.send_message(message.chat.id, "❌ Не удалось получить курс одной из валют. Попробуйте позже.", reply_markup=main_menu())
            return

        # Расчет
        val_usd_1 = convert_to_usd(amount, t1, p1)
        fee_val_1 = val_usd_1 * (fee / 100)
        val_usd_1_clean = val_usd_1 - fee_val_1
        amount_2 = convert_from_usd(val_usd_1_clean, t2, p2)
        
        val_usd_2 = convert_to_usd(amount_2, t2, p2)
        fee_val_2 = val_usd_2 * (fee / 100)
        val_usd_2_clean = val_usd_2 - fee_val_2
        final_amount = convert_from_usd(val_usd_2_clean, t3, p3)
        
        bot.delete_message(message.chat.id, msg.message_id)
        
        res = f"🔀 **Результат Тройного Обмена:**\n"
        res += f"1. {amount} {t1} ➡️ {amount_2:.4f} {t2}\n"
        res += f"   *(Комиссия: -{fee_val_1:.2f} USD)*\n"
        res += f"2. {amount_2:.4f} {t2} ➡️ **{final_amount:.2f} {t3}**\n"
        res += f"   *(Комиссия: -{fee_val_2:.2f} USD)*\n\n"
        res += f"✅ **ИТОГ:** {final_amount:.2f} {t3}"
        
        bot.send_message(message.chat.id, res, parse_mode="Markdown", reply_markup=main_menu())
        
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка расчета: {e}", reply_markup=main_menu())

# =======================
# ОБЫЧНЫЙ КАЛЬКУЛЯТОР
# =======================
@bot.message_handler(func=lambda message: message.text == "🧮 Калькулятор (1 шаг)")
def simple_calc_start(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, ticker in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"sc_1_{ticker}"))
    bot.send_message(message.chat.id, "Что меняем?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sc_1_'))
def simple_calc_step2(call):
    ticker = call.data.replace('sc_1_', '')
    get_user_data(call.message.chat.id)['calc'] = {'start': ticker}
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, t in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"sc_2_{t}"))
    bot.edit_message_text("На что меняем?", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sc_2_'))
def simple_calc_amt(call):
    ticker = call.data.replace('sc_2_', '')
    get_user_data(call.message.chat.id)['calc']['end'] = ticker
    msg = bot.edit_message_text("Введите сумму:", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(msg, simple_get_amt)

def simple_get_amt(message):
    try:
        amount = float(message.text)
        get_user_data(message.chat.id)['calc']['amount'] = amount
        msg = bot.send_message(message.chat.id, "Комиссия (%):")
        bot.register_next_step_handler(msg, simple_do_calc)
    except:
        bot.send_message(message.chat.id, "Нужно число.", reply_markup=main_menu())

def simple_do_calc(message):
    try:
        fee = float(message.text)
        d = get_user_data(message.chat.id).get('calc', {})
        if 'start' not in d:
            bot.send_message(message.chat.id, "Данные устарели.", reply_markup=main_menu())
            return

        t1, t2, amt = d['start'], d['end'], d['amount']
        p1, p2 = get_price(t1), get_price(t2)
        
        if p1 and p2:
            usd_val = convert_to_usd(amt, t1, p1)
            clean_usd = usd_val - (usd_val * fee/100)
            final = convert_from_usd(clean_usd, t2, p2)
            bot.send_message(message.chat.id, f"🧮 {amt} {t1} ➡️ {final:.2f} {t2}\n(Комиссия {fee}%)", reply_markup=main_menu())
        else:
            bot.send_message(message.chat.id, "Ошибка получения курса.", reply_markup=main_menu())
    except: pass

# =======================
# ОСТАЛЬНОЕ (ГРАФИКИ, ИИ)
# =======================
@bot.message_handler(func=lambda message: message.text == "🤖 ИИ Анализ")
def ai_start(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, ticker in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"ai_{ticker}"))
    bot.send_message(message.chat.id, "Что анализировать?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ai_'))
def ai_run(call):
    t = call.data.replace('ai_', '')
    bot.answer_callback_query(call.id, "Думаю...")
    try:
        data = yf.Ticker(t).history(period="1mo")
        if len(data) > 14:
            rsi = 50 
            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi_val = 100 
