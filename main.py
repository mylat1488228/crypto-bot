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
BOT_TOKEN = 'ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН' 
bot = telebot.TeleBot(BOT_TOKEN)

# Словарь тикеров (Yahoo Finance формат)
# Формат для фиата: Валюта=X (обычно это курс к USD)
# Формат для крипты: ТИКЕР-USD
TICKERS = {
    '🇺🇸 USD (Доллар)': 'DX-Y.NYB', # Индекс доллара (примерно) или просто USDT для расчетов
    '🇪🇺 EUR (Евро)': 'EURUSD=X',   # Курс Евро к Доллару
    '🇨🇳 CNY (Юань)': 'CNY=X',      # Юань к Доллару (обратный курс)
    '🇦🇪 AED (Дирхам)': 'AED=X',
    '🇹🇯 TJS (Сомони)': 'TJS=X',    # Может работать нестабильно, если данных мало, но тикер верный
    '🇺🇿 UZS (Сум)': 'UZS=X',
    '🇷🇺 RUB (Рубль)': 'RUB=X',
    '₿ BTC (Биткоин)': 'BTC-USD',
    '💎 ETH (Эфир)': 'ETH-USD',
    '💎 TON (Тонкоин)': 'TON11419-USD',
    '💵 USDT (Тезер)': 'USDT-USD'
}

# Хранилище данных пользователей
users_db = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_price(ticker):
    try:
        data = yf.Ticker(ticker)
        history = data.history(period='1d')
        if not history.empty:
            return history['Close'].iloc[-1]
    except Exception as e:
        print(f"Ошибка цены {ticker}: {e}")
    return None

def get_chart(ticker, period, interval):
    try:
        data = yf.Ticker(ticker)
        df = data.history(period=period, interval=interval)
        if df.empty: return None
        
        plt.figure(figsize=(10, 5))
        plt.plot(df.index, df['Close'], label=ticker, color='blue')
        plt.title(f'График {ticker} за {period}')
        plt.xlabel('Дата')
        plt.ylabel('Цена')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        return buf
    except:
        return None

# --- ИИ АНАЛИЗ (RSI) ---
def analyze_market(ticker):
    try:
        # Берем данные за 20 дней для расчета RSI
        data = yf.Ticker(ticker)
        df = data.history(period="1mo", interval="1d")
        
        if len(df) < 14:
            return "Недостаточно данных для анализа."
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]
        
        # Логика "ИИ"
        signal = ""
        explanation = ""
        
        if current_rsi < 30:
            signal = "🟢 ПОКУПАТЬ (Сильный сигнал)"
            explanation = "Актив перепродан. Цена упала слишком низко, ожидается отскок вверх."
        elif current_rsi > 70:
            signal = "🔴 ПРОДАВАТЬ (Сильный сигнал)"
            explanation = "Актив перекуплен. Цена слишком высока, возможна коррекция вниз."
        elif 30 <= current_rsi < 45:
            signal = "🟢 Возможно к покупке (Слабый сигнал)"
            explanation = "Цена находится в нижней зоне, можно присмотреться к покупке."
        elif 55 < current_rsi <= 70:
            signal = "🔴 Возможно к продаже (Слабый сигнал)"
            explanation = "Цена растет, но риск коррекции увеличивается."
        else:
            signal = "🟡 ДЕРЖАТЬ / ЖДАТЬ"
            explanation = "Рынок в равновесии. Явного тренда нет, лучше подождать."
            
        return f"🤖 **Анализ для {ticker}:**\n\n📊 **RSI Индекс:** {current_rsi:.1f}\n💡 **Сигнал:** {signal}\n\n📝 **Пояснение:** {explanation}"
    except Exception as e:
        return f"Ошибка анализа: {e}"

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🧮 Калькулятор")
    btn2 = types.KeyboardButton("📈 Графики")
    btn3 = types.KeyboardButton("🤖 ИИ Анализ")
    btn4 = types.KeyboardButton("⭐ Мой список")
    markup.add(btn1, btn2, btn3, btn4)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    uid = message.chat.id
    if uid not in users_db:
        users_db[uid] = {'watchlist': [], 'calc_state': {}, 'last_prices': {}}
    bot.send_message(uid, "Привет! Я бот для работы с Фиатом и Криптой.\nЯ умею считать комиссии, строить графики и анализировать рынок.", reply_markup=main_menu())

# --- 1. КАЛЬКУЛЯТОР ---
@bot.message_handler(func=lambda message: message.text == "🧮 Калькулятор")
def calc_start(message):
    # Для простоты: обмен выбранной валюты в USD (базовый расчет)
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, ticker in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"sel_calc_{ticker}"))
    bot.send_message(message.chat.id, "Выберите валюту, которую хотите обменять/продать:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sel_calc_'))
def calc_currency_selected(call):
    ticker = call.data.replace('sel_calc_', '')
    users_db[call.message.chat.id]['calc_state'] = {'ticker': ticker}
    msg = bot.edit_message_text(f"Выбрано: {ticker}.\nВведите сумму сделки:", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(msg, get_amount)

def get_amount(message):
    try:
        amount = float(message.text)
        users_db[message.chat.id]['calc_state']['amount'] = amount
        msg = bot.send_message(message.chat.id, "Введите комиссию в процентах (например 1 или 0.5):")
        bot.register_next_step_handler(msg, get_fee)
    except ValueError:
        bot.send_message(message.chat.id, "Нужно ввести число.", reply_markup=main_menu())

def get_fee(message):
    try:
        fee_percent = float(message.text)
        data = users_db[message.chat.id]['calc_state']
        ticker = data['ticker']
        amount = data['amount']
        
        price = get_price(ticker)
        if price is None:
            bot.send_message(message.chat.id, "Не удалось узнать актуальный курс.", reply_markup=main_menu())
            return

        total_dirty = amount * price # Примерная стоимость в USD или базе
        fee_val = total_dirty * (fee_percent / 100)
        total_clean = total_dirty - fee_val
        
        text = f"💰 **Результат сделки:**\n"
        text += f"Валюта: {ticker}\n"
        text += f"Текущий курс: {price:.4f}\n"
        text += f"Общая сумма: {total_dirty:.2f}\n"
        text += f"Комиссия ({fee_percent}%): -{fee_val:.2f}\n"
        text += f"💵 **Вы получите (чистыми):** {total_clean:.2f}"
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())
    except ValueError:
        bot.send_message(message.chat.id, "Ошибка ввода.", reply_markup=main_menu())

# --- 2. ГРАФИКИ ---
@bot.message_handler(func=lambda message: message.text == "📈 Графики")
def charts_start(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, ticker in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"chart_tic_{ticker}"))
    bot.send_message(message.chat.id, "Выберите валюту для графика:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('chart_tic_'))
def chart_period(call):
    ticker = call.data.replace('chart_tic_', '')
    users_db[call.message.chat.id]['chart_ticker'] = ticker
    
    periods = {'30 дней': '1mo', '15 дней': '15d', '7 дней': '5d', '3 дня': '3d', '1 день': '1d', '12 часов': '12h'}
    markup = types.InlineKeyboardMarkup(row_width=3)
    for txt, val in periods.items():
        markup.add(types.InlineKeyboardButton(txt, callback_data=f"chart_per_{val}"))
    
    bot.edit_message_text("Выберите период:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('chart_per_'))
def chart_send(call):
    p_raw = call.data.replace('chart_per_', '')
    ticker = users_db[call.message.chat.id].get('chart_ticker')
    
    bot.answer_callback_query(call.id, "Рисую график...")
    interval = '1h' if p_raw in ['1d', '12h', '3d'] else '1d'
    if p_raw == '12h': interval = '30m'
    
    photo = get_chart(ticker, p_raw, interval)
    if photo:
        bot.send_photo(call.message.chat.id, photo, caption=f"График {ticker} ({p_raw})")
    else:
        bot.send_message(call.message.chat.id, "Нет данных для графика.")

# --- 3. ИИ АНАЛИЗ ---
@bot.message_handler(func=lambda message: message.text == "🤖 ИИ Анализ")
def ai_start(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, ticker in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"ai_sel_{ticker}"))
    bot.send_message(message.chat.id, "Какой актив должен проанализировать ИИ?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ai_sel_'))
def ai_process(call):
    ticker = call.data.replace('ai_sel_', '')
    bot.answer_callback_query(call.id, "ИИ анализирует рынок...")
    
    report = analyze_market(ticker)
    bot.send_message(call.message.chat.id, report, parse_mode="Markdown")

# --- 4. ОТЧЕТЫ И АЛЕРТЫ ---
@bot.message_handler(func=lambda message: message.text == "⭐ Мой список")
def watchlist_menu(message):
    uid = message.chat.id
    wl = users_db.get(uid, {}).get('watchlist', [])
    text = f"Сейчас в отслеживании: {', '.join(wl) if wl else 'Ничего'}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Добавить", callback_data="wl_add"),
               types.InlineKeyboardButton("➖ Очистить", callback_data="wl_clear"))
    bot.send_message(uid, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "wl_add")
def wl_add_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, ticker in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"wl_save_{ticker}"))
    bot.edit_message_text("Выберите валюту:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("wl_save_"))
def wl_save_tic(call):
    ticker = call.data.replace("wl_save_", "")
    uid = call.message.chat.id
    if uid not in users_db: users_db[uid] = {'watchlist': [], 'last_prices': {}}
    
    if ticker not in users_db[uid]['watchlist']:
        users_db[uid]['watchlist'].append(ticker)
        users_db[uid]['last_prices'][ticker] = get_price(ticker)
    
    bot.send_message(uid, f"✅ {ticker} добавлен в отчеты.", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "wl_clear")
def wl_clear_all(call):
    users_db[call.message.chat.id]['watchlist'] = []
    bot.send_message(call.message.chat.id, "Список очищен.", reply_markup=main_menu())

# --- ФОНОВЫЕ ЗАДАЧИ ---
def job_checker():
    # Проверка скачков (3%)
    for uid, data in users_db.items():
        for ticker in data.get('watchlist', []):
            cur = get_price(ticker)
            old = data['last_prices'].get(ticker)
            if cur and old:
                change = ((cur - old) / old) * 100
                if abs(change) >= 3:
                    emoji = "🚀" if change > 0 else "🔻"
                    try:
                        bot.send_message(uid, f"⚠️ {ticker} {emoji}\nИзменение цены: {change:.2f}%!\nЦена: {cur}")
                        data['last_prices'][ticker] = cur
                    except: pass

def job_report():
    # Ежечасный отчет
    for uid, data in users_db.items():
        wl = data.get('watchlist', [])
        if not wl: continue
        msg = "🕐 **Часовой отчет:**\n"
        for ticker in wl:
            cur = get_price(ticker)
            old = data['last_prices'].get(ticker)
            if cur and old:
                change = ((cur - old) / old) * 100
                status = "Рост 📈" if change > 0 else "Падение 📉"
                if abs(change) < 0.1: status = "На месте 💤"
                msg += f"{ticker}: {cur:.2f} ({status} {change:.2f}%)\n"
                data['last_prices'][ticker] = cur
        try:
            bot.send_message(uid, msg, parse_mode="Markdown")
        except: pass

schedule.every(10).minutes.do(job_checker)
schedule.every(1).hours.do(job_report)

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

t = threading.Thread(target=run_schedule)
t.daemon = True
t.start()

print("Бот запущен с новыми валютами и ИИ...")
if __name__ == '__main__':
    bot.infinity_polling()
        amount = float(message.text)
        users_db[message.chat.id]['calc_state']['amount'] = amount
        msg = bot.send_message(message.chat.id, "Введите процент комиссии биржи/обменника (например, 0.5 или 3):")
        bot.register_next_step_handler(msg, get_fee)
    except ValueError:
        bot.send_message(message.chat.id, "Это не число. Попробуйте снова через меню.", reply_markup=main_menu())

def get_fee(message):
    try:
        fee_percent = float(message.text)
        data = users_db[message.chat.id]['calc_state']
        ticker = data['ticker']
        amount = data['amount']
        
        price = get_price(ticker)
        if price is None:
            bot.send_message(message.chat.id, "Не удалось получить курс.", reply_markup=main_menu())
            return

        # Логика расчета
        total_value = amount * price
        fee_value = total_value * (fee_percent / 100)
        final_value = total_value - fee_value
        
        text = f"🧮 **Расчет сделки:**\n"
        text += f"Курс: {price:.2f}\n"
        text += f"Сумма: {amount}\n"
        text += f"Комиссия ({fee_percent}%): -{fee_value:.2f}\n"
        text += f"📉 **Вы получите на руки:** {final_value:.2f}"
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())
        
    except ValueError:
        bot.send_message(message.chat.id, "Ошибка ввода числа.", reply_markup=main_menu())

# --- 2. ГРАФИКИ ---
@bot.message_handler(func=lambda message: message.text == "📈 Графики")
def charts_start(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, ticker in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"chart_tic_{ticker}"))
    bot.send_message(message.chat.id, "Выберите валюту для графика:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('chart_tic_'))
def chart_period_select(call):
    ticker = call.data.replace('chart_tic_', '')
    users_db[call.message.chat.id]['chart_ticker'] = ticker
    
    # Кнопки времени
    periods = {
        '30 дней': '30d', '15 дней': '15d', '7 дней': '7d', '3 дня': '5d', # yfinance 3d глючит иногда, берем 5
        '1 день': '1d', '12 часов': '12h', '6 часов': '6h', '3 часа': '3h'
    } # Для часов нужно подбирать интервалы
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    for txt, val in periods.items():
        markup.add(types.InlineKeyboardButton(txt, callback_data=f"chart_per_{val}"))
    
    bot.edit_message_text("За какой период нужен график?", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('chart_per_'))
def send_chart_img(call):
    period_raw = call.data.replace('chart_per_', '')
    ticker = users_db[call.message.chat.id].get('chart_ticker')
    
    bot.answer_callback_query(call.id, "Генерирую график...")
    
    # Настройка интервалов для yfinance
    interval = '1d'
    period = period_raw
    
    if period_raw in ['12h', '6h', '3h']:
        period = '1d' # Запрашиваем день, обрежем графиком или оставим как есть детально
        interval = '5m' if period_raw == '3h' else '15m'
        if period_raw == '12h': interval = '30m'
        
    # Генерируем фото
    photo = get_chart(ticker, period, interval)
    if photo:
        bot.send_photo(call.message.chat.id, photo, caption=f"График {ticker} ({period_raw})")
    else:
        bot.send_message(call.message.chat.id, "Ошибка получения данных графика.")

# --- 3. СПИСОК ОТСЛЕЖИВАНИЯ И ФОНОВЫЕ ЗАДАЧИ ---
@bot.message_handler(func=lambda message: message.text == "⭐ Мой список (Отчеты)")
def watchlist_menu(message):
    uid = message.chat.id
    watchlist = users_db.get(uid, {}).get('watchlist', [])
    
    text = "Ваш список отслеживания:\n" + (", ".join(watchlist) if watchlist else "Пусто")
    text += "\n\nБот будет присылать отчет каждый час и оповещать, если цена изменится более чем на 3%."
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Добавить валюту", callback_data="wl_add"))
    markup.add(types.InlineKeyboardButton("➖ Очистить список", callback_data="wl_clear"))
    
    bot.send_message(uid, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "wl_add")
def wl_add(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, ticker in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"wl_save_{ticker}"))
    bot.edit_message_text("Что добавить в отслеживание?", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("wl_save_"))
def wl_save(call):
    ticker = call.data.replace("wl_save_", "")
    uid = call.message.chat.id
    if uid not in users_db: users_db[uid] = {'watchlist': [], 'calc_state': {}, 'last_prices': {}}
    
    if ticker not in users_db[uid]['watchlist']:
        users_db[uid]['watchlist'].append(ticker)
        # Запоминаем текущую цену для отслеживания
        price = get_price(ticker)
        users_db[uid]['last_prices'][ticker] = price
    
    bot.send_message(uid, f"Добавлено: {ticker}", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "wl_clear")
def wl_clear(call):
    uid = call.message.chat.id
    if uid in users_db:
        users_db[uid]['watchlist'] = []
        users_db[uid]['last_prices'] = {}
    bot.send_message(uid, "Список очищен.", reply_markup=main_menu())

# --- ФОНОВЫЙ ПОТОК (ПРОВЕРКА ЦЕН) ---
def background_checker():
    # Эта функция работает вечно в отдельном потоке
    while True:
        schedule.run_pending()
        time.sleep(1)

def check_alerts_job():
    # Проверка каждые 5-10 минут на резкие скачки (3%)
    print("Проверка алертов...")
    for uid, data in users_db.items():
        watchlist = data.get('watchlist', [])
        last_prices = data.get('last_prices', {})
        
        for ticker in watchlist:
            current_price = get_price(ticker)
            old_price = last_prices.get(ticker)
            
            if current_price and old_price:
                change = ((current_price - old_price) / old_price) * 100
                
                # Если изменение больше 3% (в плюс или минус)
                if abs(change) >= 3:
                    emoji = "🚀" if change > 0 else "🔻"
                    try:
                        bot.send_message(uid, f"⚠️ **АЛЕРТ!** {emoji}\n{ticker} изменился на {change:.2f}%\nБыло: {old_price}\nСтало: {current_price}", parse_mode="Markdown")
                        # Обновляем цену, чтобы не спамить
                        users_db[uid]['last_prices'][ticker] = current_price
                    except:
                        pass

def hourly_report_job():
    # Отчет каждый час
    print("Отправка почасового отчета...")
    for uid, data in users_db.items():
        watchlist = data.get('watchlist', [])
        if not watchlist: continue
        
        report = "🕐 **Почасовой отчет:**\n"
        for ticker in watchlist:
            current_price = get_price(ticker)
            old_price = data['last_prices'].get(ticker)
            
            if current_price and old_price:
                change = ((current_price - old_price) / old_price) * 100
                if abs(change) < 0.01:
                    status = "Стоит на месте 💤"
                elif change > 0:
                    status = f"Выросла на {change:.2f}% 📈"
                else:
                    status = f"Упала на {abs(change):.2f}% 📉"
                
                report += f"- {ticker}: {current_price:.2f} ({status})\n"
                
                # Обновляем "старую" цену на текущую для следующего часа
                users_db[uid]['last_prices'][ticker] = current_price
        
        try:
            bot.send_message(uid, report, parse_mode="Markdown")
        except:
            pass

# Планировщик задач
schedule.every(10).minutes.do(check_alerts_job) # Проверка скачков каждые 10 мин
schedule.every(1).hours.do(hourly_report_job)   # Отчет каждый час

# Запуск потока планировщика
thread = threading.Thread(target=background_checker)
thread.daemon = True
thread.start()

# --- ЗАПУСК БОТА ---
print("Бот запущен...")
if __name__ == '__main__':

    bot.infinity_polling()

