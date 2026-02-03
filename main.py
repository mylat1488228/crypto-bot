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

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = 'ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН' 
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
    bot.send_message(message.chat.id, "Бот готов к работе.", reply_markup=main_menu())

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

@bot.callback_query_handler(func=lambda call: 
