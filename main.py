import telebot
from telebot import types
import yfinance as yf
import matplotlib
matplotlib.use('Agg') # Обязательно для сервера
import matplotlib.pyplot as plt
import io
import threading
import time
import schedule
import pandas as pd
import numpy as np
import random # Для "живых" ответов

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

# Фразы для "ИИ"
AI_GREETINGS = [
    "Привет, брат! Чем помочь? Спроси 'Что купить' или 'Как пользоваться'.",
    "Салам! Я на связи. Хочешь узнать, куда рынок движется?",
    "Приветствую! Я твой финансовый помощник. Задавай вопросы."
]

# --- СИСТЕМНЫЕ ФУНКЦИИ ---
def get_user_data(uid):
    if uid not in users_db:
        users_db[uid] = {'watchlist': [], 'calc': {}, 'triple': {}, 'chart_cur': None, 'last_prices': {}, 'mode': 'menu'}
    return users_db[uid]

def get_price(ticker):
    try:
        data = yf.Ticker(ticker)
        history = data.history(period='2d')
        if not history.empty:
            return history['Close'].iloc[-1]
    except: pass
    return None

def convert_to_usd(amount, ticker, price):
    if ticker in REVERSE_PAIRS: return amount / price
    else: return amount * price

def convert_from_usd(usd_amount, ticker, price):
    if ticker in REVERSE_PAIRS: return usd_amount * price
    else: return usd_amount / price

# --- ФУНКЦИЯ "МОЗГ" (СКАНИРОВАНИЕ РЫНКА) ---
def scan_market_for_advice():
    best_buy = None
    best_sell = None
    lowest_rsi = 100
    highest_rsi = 0

    # Проходимся по всем тикерам
    for name, ticker in TICKERS.items():
        try:
            data = yf.Ticker(ticker).history(period="1mo")
            if len(data) > 14:
                delta = data['Close'].diff()
                up = delta.clip(lower=0)
                down = -1 * delta.clip(upper=0)
                ema_up = up.ewm(com=13, adjust=False).mean()
                ema_down = down.ewm(com=13, adjust=False).mean()
                rs = ema_up / ema_down
                rsi = 100 - (100 / (1 + rs)).iloc[-1]

                if rsi < lowest_rsi:
                    lowest_rsi = rsi
                    best_buy = (name, rsi)
                
                if rsi > highest_rsi:
                    highest_rsi = rsi
                    best_sell = (name, rsi)
        except: continue

    return best_buy, best_sell

# --- МЕНЮ ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🧮 Калькулятор (1 шаг)"), types.KeyboardButton("🔀 Тройной обмен (2 шага)"))
    markup.add(types.KeyboardButton("📈 Графики"), types.KeyboardButton("⭐ Мой список"))
    markup.add(types.KeyboardButton("💬 AI Помощник (Чат)"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    get_user_data(message.chat.id)['mode'] = 'menu'
    bot.send_message(message.chat.id, "Бот готов к работе.", reply_markup=main_menu())

# =======================
# AI ЧАТ ПОМОЩНИК
# =======================
@bot.message_handler(func=lambda message: message.text == "💬 AI Помощник (Чат)")
def ai_chat_mode(message):
    get_user_data(message.chat.id)['mode'] = 'chat'
    greeting = random.choice(AI_GREETINGS)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("Что купить/продать сейчас?"), types.KeyboardButton("Как работает бот?"))
    markup.add(types.KeyboardButton("🔙 В главное меню"))
    bot.send_message(message.chat.id, greeting, reply_markup=markup)

@bot.message_handler(func=lambda message: get_user_data(message.chat.id).get('mode') == 'chat')
def ai_chat_response(message):
    text = message.text.lower()
    uid = message.chat.id

    if message.text == "🔙 В главное меню":
        get_user_data(uid)['mode'] = 'menu'
        bot.send_message(uid, "Выход в меню.", reply_markup=main_menu())
        return

    # 1. СОВЕТ ПО РЫНКУ
    if "купить" in text or "продать" in text or "выгодно" in text:
        bot.send_message(uid, "⏳ Брат, дай секунду, просканирую весь рынок...")
        buy, sell = scan_market_for_advice()
        
        response = ""
        # Логика совета
        if buy and buy[1] < 35:
            response += f"🚀 **Слушай, сейчас выгодно взять:** {buy[0]}.\nУ неё RSI {buy[1]:.1f} (очень дешево), скоро должен быть отскок вверх!\n\n"
        else:
            response += "🤔 По покупкам сейчас ничего супер-выгодного нет, рынок перегрет.\n\n"
            
        if sell and sell[1] > 65:
            response += f"📉 **А вот продать стоит:** {sell[0]}.\nRSI {sell[1]:.1f} (дорого), скорее всего цена упадет."
        else:
            response += "💎 По продажам сигналов нет, можно держать то, что есть."
            
        bot.send_message(uid, response, parse_mode="Markdown")
        return

    # 2. ПОМОЩЬ ПО БОТУ
    if "как" in text or "помоги" in text or "работает" in text or "бот" in text:
        help_text = (
            "🤖 **Я твой проводник. Вот что я умею:**\n\n"
            "1. **Калькулятор:** Считает простой обмен (например, USDT -> RUB) с учетом комиссии.\n"
            "2. **Тройной обмен:** Для арбитража. Считает цепочку (USDT -> TON -> RUB).\n"
            "3. **Графики:** Показывает картинку с ценой за 30 дней, 7 дней или даже 3 часа.\n"
            "4. **Мой список:** Добавь туда валюты, и я буду каждый час писать тебе отчет о ценах.\n"
            "5. **ИИ Чат:** Это здесь! Спрашивай меня про рынок."
        )
        bot.send_message(uid, help_text, parse_mode="Markdown")
        return

    # 3. ПРОСТО ОБЩЕНИЕ
    if "привет" in text or "салам" in text:
        bot.send_message(uid, "Салам! Спрашивай, не стесняйся.")
    else:
        bot.send_message(uid, "Брат, я пока понимаю только вопросы про 'Купить', 'Продать' или 'Как работает'. Нажми на кнопки внизу.")

# =======================
# ОСТАЛЬНЫЕ ФУНКЦИИ
# =======================

# ТРОЙНОЙ ОБМЕН
@bot.message_handler(func=lambda message: message.text == "🔀 Тройной обмен (2 шага)")
def triple_start(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    for name, ticker in TICKERS.items(): markup.add(types.InlineKeyboardButton(name, callback_data=f"tr_1_{ticker}"))
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
    msg = bot.edit_message_text(f"⛓ Цепь: {chain.get('start')} ➡️ {chain.get('mid')} ➡️ {t}\n\nВведите сумму:", uid, call.message.message_id)
    bot.register_next_step_handler(msg, triple_calc_go)

def triple_calc_go(message):
    try:
        amt = float(message.text)
        get_user_data(message.chat.id)['triple']['amount'] = amt
        msg = bot.send_message(message.chat.id, "Введите комиссию %:")
        bot.register_next_step_handler(msg, triple_final)
    except:
        bot.send_message(message.chat.id, "Нужно число.", reply_markup=main_menu())

def triple_final(message):
    try:
        fee = float(message.text)
        data = get_user_data(message.chat.id)['triple']
        if not all(k in data for k in ['start', 'mid', 'end', 'amount']):
            bot.send_message(message.chat.id, "Данные устарели.", reply_markup=main_menu())
            return
        t1, t2, t3, amt = data['start'], data['mid'], data['end'], data['amount']
        p1, p2, p3 = get_price(t1), get_price(t2), get_price(t3)
        if not p1 or not p2 or not p3:
            bot.send_message(message.chat.id, "Ошибка курса.", reply_markup=main_menu())
            return
        usd1 = convert_to_usd(amt, t1, p1)
        usd1_clean = usd1 - (usd1 * fee/100)
        res2 = convert_from_usd(usd1_clean, t2, p2)
        usd2 = convert_to_usd(res2, t2, p2)
        usd2_clean = usd2 - (usd2 * fee/100)
        final = convert_from_usd(usd2_clean, t3, p3)
        text = f"🔀 **Результат:**\n1. {amt} {t1} ➡️ {res2:.4f} {t2}\n2. {res2:.4f} {t2} ➡️ **{final:.2f} {t3}**\n\n✅ **ИТОГ:** {final:.2f} {t3}"
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}", reply_markup=main_menu())

# ОБЫЧНЫЙ КАЛЬКУЛЯТОР
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
    except: pass

# ГРАФИКИ
@bot.message_handler(func=lambda message: message.text == "📈 Графики")
def charts(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    for n, t in TICKERS.items(): markup.add(types.InlineKeyboardButton(n, callback_data=f"ch_sel_{t}"))
    bot.send_message(message.chat.id, "Выберите валюту:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ch_sel_'))
def charts_timeframe(call):
    ticker = call.data.replace('ch_sel_', '')
    get_user_data(call.message.chat.id)['chart_cur'] = ticker
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("30 Дней", callback_data="time_30d"),
        types.InlineKeyboardButton("15 Дней", callback_data="time_15d"),
        types.InlineKeyboardButton("7 Дней", callback_data="time_7d"),
        types.InlineKeyboardButton("3 Дня", callback_data="time_3d"),
        types.InlineKeyboardButton("1 День", callback_data="time_1d"),
        types.InlineKeyboardButton("12 Часов", callback_data="time_12h"),
        types.InlineKeyboardButton("6 Часов", callback_data="time_6h"),
        types.InlineKeyboardButton("3 Часа", callback_data="time_3h")
    )
    bot.edit_message_text(f"Валюта: {ticker}\nВыберите период:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('time_'))
def charts_generate(call):
    time_code = call.data.replace('time_', '')
    ticker = get_user_data(call.message.chat.id).get('chart_cur')
    if not ticker:
        bot.send_message(call.message.chat.id, "Ошибка.", reply_markup=main_menu())
        return
    bot.answer_callback_query(call.id, "Рисую график...")
    period = '1mo'
    interval = '1d'
    if time_code == '30d': period, interval = '1mo', '1d'
    elif time_code == '15d': period, interval = '1mo', '1d'
    elif time_code == '7d': period, interval = '5d', '60m'
    elif time_code == '3d': period, interval = '5d', '60m'
    elif time_code == '1d': period, interval = '1d', '30m'
    elif time_code == '12h': period, interval = '1d', '15m'
    elif time_code == '6h': period, interval = '1d', '5m'
    elif time_code == '3h': period, interval = '1d', '5m'

    try:
        data = yf.Ticker(ticker).history(period=period, interval=interval)
        if not data.empty:
            plt.figure(figsize=(10,5))
            plt.plot(data.index, data['Close'], label=f"{ticker}")
            plt.title(f"{ticker} ({time_code})")
            plt.grid(True)
            plt.legend()
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            bot.send_photo(call.message.chat.id, buf)
            plt.close()
        else: bot.send_message(call.message.chat.id, "Нет данных.")
    except Exception as e: bot.send_message(call.message.chat.id, f"Ошибка: {e}")

# СПИСОК
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
    bot.edit_message_text("Выберите:", call.message.chat.id, call.message.message_id, reply_markup=m)

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

# ФОНОВЫЕ ЗАДАЧИ
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
    except: pass

schedule.every(10).minutes.do(job)
threading.Thread(target=run_sch, daemon=True).start()

if __name__ == '__main__':
    bot.infinity_polling()
