import telebot
from telebot import types
import yfinance as yf
import matplotlib
matplotlib.use('Agg') # Обязательно для работы на сервере без экрана
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

# Список валют и их тикеров на Yahoo Finance
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

# Список валют, которые котируются как "Кол-во за 1 доллар"
# Например, RUB=X значит "92 рубля за 1 доллар"
REVERSE_PAIRS = ['RUB=X', 'CNY=X', 'AED=X', 'TJS=X', 'UZS=X']

# База данных в оперативной памяти
users_db = {}

# --- СИСТЕМНЫЕ ФУНКЦИИ ---

def get_user_data(uid):
    # Создает ячейку памяти для пользователя, если её нет (защита от краша)
    if uid not in users_db:
        users_db[uid] = {'watchlist': [], 'calc': {}, 'triple': {}, 'last_prices': {}}
    return users_db[uid]

def get_price(ticker):
    try:
        data = yf.Ticker(ticker)
        # Берем историю за 2 дня, так как в выходные биржи могут стоять
        history = data.history(period='2d')
        if not history.empty:
            return history['Close'].iloc[-1]
    except:
        pass
    return None

def convert_to_usd(amount, ticker, price):
    # Перевод любой валюты В ДОЛЛАРЫ
    if ticker in REVERSE_PAIRS:
        return amount / price # 9000 руб / 90 = 100 баксов
    else:
        return amount * price # 2 битка * 60000 = 120000 баксов

def convert_from_usd(usd_amount, ticker, price):
    # Перевод ИЗ ДОЛЛАРОВ в целевую валюту
    if ticker in REVERSE_PAIRS:
        return usd_amount * price # 100 баксов * 90 = 9000 руб
    else:
        return usd_amount / price # 120000 баксов / 60000 = 2 битка

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
    t = call.data.replace('tr_1_', '')
    get_user_data(uid)['triple'] = {'start': t}
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, tk in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"tr_2_{tk}"))
    bot.edit_message_text(f"Начало: {t}\n2️⃣ Промежуточная валюта:", uid, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_2_'))
def triple_step_3(call):
    uid = call.message.chat.id
    t = call.data.replace('tr_2_', '')
    get_user_data(uid)['triple']['mid'] = t
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, tk in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"tr_3_{tk}"))
    bot.edit_message_text(f"Цепь: ...-> {t} ->...\n3️⃣ Что получаем в конце?", uid, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_3_'))
def triple_step_amt(call):
    uid = call.message.chat.id
    t = call.data.replace('tr_3_', '')
    get_user_data(uid)['triple']['end'] = t
    
    chain = get_user_data(uid)['triple']
    msg = bot.edit_message_text(f"⛓ Цепь: {chain.get('start')} ➡️ {chain.get('mid')} ➡️ {t}\n\nВведите сумму (число):", uid, call.message.message_id)
    bot.register_next_step_handler(msg, triple_calc_go)

def triple_calc_go(message):
    try:
        amt = float(message.text)
        get_user_data(message.chat.id)['triple']['amount'] = amt
        msg = bot.send_message(message.chat.id, "Введите комиссию % (снимается дважды):")
        bot.register_next_step_handler(msg, triple_final)
    except:
        bot.send_message(message.chat.id, "Нужно ввести число.", reply_markup=main_menu())

def triple_final(message):
    try:
        fee = float(message.text)
        data = get_user_data(message.chat.id)['triple']
        
        # Проверяем, есть ли все данные
        if not all(k in data for k in ['start', 'mid', 'end', 'amount']):
            bot.send_message(message.chat.id, "Данные устарели. Начните заново.", reply_markup=main_menu())
            return

        t1, t2, t3, amt = data['start'], data['mid'], data['end'], data['amount']
        
        # Получаем курсы
        p1, p2, p3 = get_price(t1), get_price(t2), get_price(t3)
        
        if not p1 or not p2 or not p3:
            bot.send_message(message.chat.id, "Ошибка получения курса биржи.", reply_markup=main_menu())
            return

        # Шаг 1: Валюта 1 -> Валюта 2
        usd1 = convert_to_usd(amt, t1, p1)
        usd1_clean = usd1 - (usd1 * fee/100)
        res2 = convert_from_usd(usd1_clean, t2, p2)
        
        # Шаг 2: Валюта 2 -> Валюта 3
        usd2 = convert_to_usd(res2, t2, p2)
        usd2_clean = usd2 - (usd2 * fee/100)
        final = convert_from_usd(usd2_clean, t3, p3)

        text = f"🔀 **Результат:**\n1. {amt} {t1} ➡️ {res2:.4f} {t2}\n2. {res2:.4f} {t2} ➡️ **{final:.2f} {t3}**\n\n✅ **ИТОГ:** {final:.2f} {t3}"
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())
        
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}", reply_markup=main_menu())

# =======================
# ОБЫЧНЫЙ КАЛЬКУЛЯТОР
# =======================
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
    bot.edit_message_text("На что меняем?", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sc_2_'))
def s_calc_3(call):
    t = call.data.replace('sc_2_', '')
    get_user_data(call.message.chat.id)['calc']['end'] = t
    msg = bot.edit_message_text("Введите сумму:", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(msg, s_calc_4)

def s_calc_4(message):
    try:
        amt = float(message.text)
        get_user_data(message.chat.id)['calc']['amount'] = amt
        msg = bot.send_message(message.chat.id, "Комиссия %:")
        bot.register_next_step_handler(msg, s_calc_5)
    except:
        bot.send_message(message.chat.id, "Нужно число.", reply_markup=main_menu())

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
            bot.send_message(message.chat.id, f"🧮 Итог: {amt} {t1} ➡️ {res:.2f} {t2}", reply_markup=main_menu())
        else:
             bot.send_message(message.chat.id, "Ошибка курса.", reply_markup=main_menu())
    except:
        pass

# =======================
# ГРАФИКИ
# =======================
@bot.message_handler(func=lambda message: message.text == "📈 Графики")
def charts(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): markup.add(types.InlineKeyboardButton(n, callback_data=f"ch_{t}"))
    bot.send_message(message.chat.id, "Выберите валюту:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ch_'))
def charts_2(call):
    t = call.data.replace('ch_', '')
    bot.answer_callback_query(call.id, "Генерирую график...")
    try:
        data = yf.Ticker(t).history(period="1mo")
        if not data.empty:
            plt.figure(figsize=(10,5))
            plt.plot(data.index, data['Close'])
            plt.title(t)
            plt.grid(True)
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            bot.send_photo(call.message.chat.id, buf)
            plt.close()
        else:
            bot.send_message(call.message.chat.id, "Нет данных для графика.")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Ошибка графика: {e}")

# =======================
# ИИ АНАЛИЗ (RSI)
# =======================
@bot.message_handler(func=lambda message: message.text == "🤖 ИИ Анализ")
def ai_start(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): markup.add(types.InlineKeyboardButton(n, callback_data=f"ai_{t}"))
    bot.send_message(message.chat.id, "Что анализировать?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ai_'))
def ai_run(call):
    t = call.data.replace('ai_', '')
    bot.answer_callback_query(call.id, "ИИ думает...")
    try:
        data = yf.Ticker(t).history(period="1mo")
        if len(data) > 14:
            # Расчет RSI
            delta = data['Close'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=13, adjust=False).mean()
            ema_down = down.ewm(com=13, adjust=False).mean()
            rs = ema_up / ema_down
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            sig = "🟢 ПОКУПАТЬ" if rsi < 30 else "🔴 ПРОДАВАТЬ" if rsi > 70 else "🟡 ЖДАТЬ"
            bot.send_message(call.message.chat.id, f"🤖 Анализ {t}:\n\n📊 RSI: {rsi:.1f}\n💡 Совет: {sig}", parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, "Мало данных для анализа.")
    except:
        bot.send_message(call.message.chat.id, "Ошибка при анализе.")

# =======================
# МОЙ СПИСОК (WATCHLIST)
# =======================
@bot.message_handler(func=lambda message: message.text == "⭐ Мой список")
def wl(message):
    wl = get_user_data(message.chat.id).get('watchlist', [])
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("➕ Добавить", callback_data="wla"), types.InlineKeyboardButton("➖ Очистить", callback_data="wlc"))
    text = ", ".join(wl) if wl else "Пусто"
    bot.send_message(message.chat.id, f"Ваш список: {text}", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data == "wla")
def wla(call):
    m = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): m.add(types.InlineKeyboardButton(n, callback_data=f"wls_{t}"))
    bot.edit_message_text("Выберите валюту:", call.message.chat.id, call.message.message_id, reply_markup=m)

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
    bot.send_message(call.message.chat.id, "Список очищен.", reply_markup=main_menu())

# --- ФОНОВЫЕ ЗАДАЧИ (БЕЗ КРАШЕЙ) ---
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
                    bot.send_message(u, f"⚠️ ВНИМАНИЕ! {t} резко изменился!")
                    d['last_prices'][t] = np
    except:
        pass

schedule.every(10).minutes.do(job)
threading.Thread(target=run_sch, daemon=True).start()

# --- ЗАПУСК ---
if __name__ == '__main__':
    bot.infinity_polling()

