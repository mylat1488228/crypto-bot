import telebot
from telebot import types
import yfinance as yf
import matplotlib.pyplot as plt
import io
import threading
import time
import schedule
import os

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = '8212929038:AAFdctXociA1FcnaxKW7N0wbfc6SdFbJ1v0' 
bot = telebot.TeleBot(BOT_TOKEN)

# Словарь тикеров (можно расширять)
TICKERS = {
    'USD (Доллар)': 'RUB=X', # USD к RUB
    'EUR (Евро)': 'EURRUB=X',
    'BTC (Биткоин)': 'BTC-USD',
    'ETH (Эфир)': 'ETH-USD',
    'TON (Тонкоин)': 'TON11419-USD',
    'USDT (Тезер)': 'USDT-USD'
}

# Хранилище данных пользователей (в памяти)
# Структура: user_id: {'watchlist': [], 'calc_state': {}, 'last_prices': {}}
users_db = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_price(ticker):
    try:
        data = yf.Ticker(ticker)
        # Берем последнюю доступную цену
        history = data.history(period='1d')
        if not history.empty:
            return history['Close'].iloc[-1]
    except Exception as e:
        print(f"Ошибка получения цены {ticker}: {e}")
    return None

def get_chart(ticker, period, interval):
    try:
        data = yf.Ticker(ticker)
        df = data.history(period=period, interval=interval)
        
        plt.figure(figsize=(10, 5))
        plt.plot(df.index, df['Close'], label=ticker)
        plt.title(f'График {ticker} за {period}')
        plt.xlabel('Дата')
        plt.ylabel('Цена')
        plt.grid(True)
        plt.legend()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        return buf
    except:
        return None

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🧮 Калькулятор")
    btn2 = types.KeyboardButton("📈 Графики")
    btn3 = types.KeyboardButton("⭐ Мой список (Отчеты)")
    markup.add(btn1, btn2, btn3)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    uid = message.chat.id
    if uid not in users_db:
        users_db[uid] = {'watchlist': [], 'calc_state': {}, 'last_prices': {}}
    bot.send_message(uid, "Привет! Я твой финансовый бот.\nЯ работаю 24/7. Выбери действие:", reply_markup=main_menu())

# --- 1. КАЛЬКУЛЯТОР ---
@bot.message_handler(func=lambda message: message.text == "🧮 Калькулятор")
def calc_start(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    # Упрощенная схема: Валюта -> Валюта (через USD или прямые пары для простоты примера используем продажу в USD/RUB)
    # Для примера сделаем конвертер в USD/RUB с учетом комиссии
    markup.add(
        types.InlineKeyboardButton("Продать Крипту (в USD)", callback_data="calc_crypto_usd"),
        types.InlineKeyboardButton("Купить Крипту (за USD)", callback_data="calc_usd_crypto"),
        types.InlineKeyboardButton("USD -> RUB", callback_data="calc_usd_rub"),
        types.InlineKeyboardButton("RUB -> USD", callback_data="calc_rub_usd")
    )
    bot.send_message(message.chat.id, "Выберите тип обмена:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('calc_'))
def calc_callback(call):
    mode = call.data
    users_db[call.message.chat.id]['calc_state'] = {'mode': mode}
    
    # Выбор валюты
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, ticker in TICKERS.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"sel_cur_{ticker}"))
    
    bot.edit_message_text("Выберите валюту/крипту:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sel_cur_'))
def cur_callback(call):
    ticker = call.data.replace('sel_cur_', '')
    users_db[call.message.chat.id]['calc_state']['ticker'] = ticker
    
    msg = bot.edit_message_text("Введите сумму для обмена (только число):", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(msg, get_amount)

def get_amount(message):
    try:
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
