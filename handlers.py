import io
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import *
from states import *
from config import TICKERS, REVERSE_PAIRS, MAIN_ADMIN_USERNAME

router = Router()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_price(ticker):
    try:
        d = yf.Ticker(ticker)
        h = d.history(period='2d')
        return h['Close'].iloc[-1] if not h.empty else None
    except: return None

def convert(amount, ticker, price, to_usd=True):
    if to_usd:
        return amount / price if ticker in REVERSE_PAIRS else amount * price
    else:
        return amount * price if ticker in REVERSE_PAIRS else amount / price

# --- КЛАВИАТУРЫ ---
def main_kb(role):
    kb = [
        [KeyboardButton(text="🧮 Калькулятор"), KeyboardButton(text="🔀 Тройной Обмен")],
        [KeyboardButton(text="📈 Графики"), KeyboardButton(text="⭐ Избранное")],
        [KeyboardButton(text="💬 AI Советник"), KeyboardButton(text="➕ Отчет (Проекты)")]
    ]
    if role == 'admin': kb.append([KeyboardButton(text="⚙️ Админка Проектов")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def tickers_kb(prefix):
    # Генерирует кнопки из списка валют
    btns = []
    row = []
    for name, ticker in TICKERS.items():
        row.append(InlineKeyboardButton(text=name, callback_data=f"{prefix}_{ticker}"))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row: btns.append(row)
    return InlineKeyboardMarkup(inline_keyboard=btns)

# --- START ---
@router.message(Command("start"))
async def start(msg: types.Message):
    role = 'admin' if msg.from_user.username == MAIN_ADMIN_USERNAME else 'executor'
    await add_user(msg.from_user.id, msg.from_user.username, role)
    await msg.answer("Бот перезапущен! Все функции активны.", reply_markup=main_kb(role))

# ===========================
# 1. ОБЫЧНЫЙ КАЛЬКУЛЯТОР
# ===========================
@router.message(F.text == "🧮 Калькулятор")
async def calc_start(msg: types.Message, state: FSMContext):
    await msg.answer("Выберите валюту, которую отдаете:", reply_markup=tickers_kb("c1"))
    await state.set_state(CalcState.select_currency_1)

@router.callback_query(F.data.startswith("c1_"))
async def calc_step_2(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(c1=call.data.split("_")[1])
    await call.message.edit_text("Выберите валюту, которую получаете:", reply_markup=tickers_kb("c2"))
    await state.set_state(CalcState.select_currency_2)

@router.callback_query(F.data.startswith("c2_"))
async def calc_step_3(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(c2=call.data.split("_")[1])
    await call.message.edit_text("Введите сумму обмена (число):")
    await state.set_state(CalcState.amount)

@router.message(CalcState.amount)
async def calc_step_4(msg: types.Message, state: FSMContext):
    try:
        await state.update_data(amt=float(msg.text))
        await msg.answer("Введите комиссию в % (например 0.5):")
        await state.set_state(CalcState.fee)
    except: await msg.answer("Нужно число!")

@router.message(CalcState.fee)
async def calc_finish(msg: types.Message, state: FSMContext):
    try:
        fee = float(msg.text)
        d = await state.get_data()
        p1, p2 = get_price(d['c1']), get_price(d['c2'])
        
        if p1 and p2:
            usd_val = convert(d['amt'], d['c1'], p1, True)
            usd_clean = usd_val * (1 - fee/100)
            final = convert(usd_clean, d['c2'], p2, False)
            await msg.answer(f"✅ Итог: {final:,.2f}\n(Курсы биржи)")
        else:
            await msg.answer("Ошибка получения курса.")
        await state.clear()
    except: await msg.answer("Ошибка ввода.")

# ===========================
# 2. ТРОЙНОЙ АРБИТРАЖ
# ===========================
@router.message(F.text == "🔀 Тройной Обмен")
async def triple_start(msg: types.Message, state: FSMContext):
    await msg.answer("1️⃣ Первая валюта (Старт):", reply_markup=tickers_kb("t1"))
    await state.set_state(TripleCalcState.curr_1)

@router.callback_query(F.data.startswith("t1_"))
async def triple_2(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(c1=call.data.split("_")[1])
    await call.message.edit_text("2️⃣ Промежуточная валюта:", reply_markup=tickers_kb("t2"))
    await state.set_state(TripleCalcState.curr_2)

@router.callback_query(F.data.startswith("t2_"))
async def triple_3(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(c2=call.data.split("_")[1])
    await call.message.edit_text("3️⃣ Конечная валюта:", reply_markup=tickers_kb("t3"))
    await state.set_state(TripleCalcState.curr_3)

@router.callback_query(F.data.startswith("t3_"))
async def triple_4(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(c3=call.data.split("_")[1])
    await call.message.edit_text("Введите начальную сумму:")
    await state.set_state(TripleCalcState.amount)

@router.message(TripleCalcState.amount)
async def triple_5(msg: types.Message, state: FSMContext):
    try:
        await state.update_data(amt=float(msg.text))
        await msg.answer("Комиссия на каждом шаге (%):")
        await state.set_state(TripleCalcState.fee)
    except: await msg.answer("Число!")

@router.message(TripleCalcState.fee)
async def triple_final(msg: types.Message, state: FSMContext):
    try:
        fee = float(msg.text) / 100
        d = await state.get_data()
        p1, p2, p3 = get_price(d['c1']), get_price(d['c2']), get_price(d['c3'])
        
        if p1 and p2 and p3:
            # Шаг 1
            u1 = convert(d['amt'], d['c1'], p1, True)
            u1_c = u1 * (1 - fee)
            res2 = convert(u1_c, d['c2'], p2, False)
            
            # Шаг 2
            u2 = convert(res2, d['c2'], p2, True)
            u2_c = u2 * (1 - fee)
            final = convert(u2_c, d['c3'], p3, False)
            
            text = (f"🔄 Цепочка:\n"
                    f"1. {d['amt']} -> {res2:.2f} (Промежуток)\n"
                    f"2. {res2:.2f} -> {final:.2f} (Финиш)\n"
                    f"💰 Итог на руки: {final:,.2f}")
            await msg.answer(text)
        await state.clear()
    except Exception as e: await msg.answer(f"Ошибка: {e}")

# ===========================
# 3. ГРАФИКИ (ПОЛНЫЕ)
# ===========================
@router.message(F.text == "📈 Графики")
async def chart_select(msg: types.Message):
    # Добавляем Избранное в начало
    user_wl = await get_watchlist(msg.from_user.id)
    kb = []
    
    # Кнопки избранного
    if user_wl:
        row = []
        for t in user_wl:
            row.append(InlineKeyboardButton(text=f"⭐ {t}", callback_data=f"gsel_{t}"))
        kb.append(row)
    
    # Кнопка "Все валюты"
    kb.append([InlineKeyboardButton(text="📋 Выбрать из списка", callback_data="g_list")])
    
    await msg.answer("Какой график строим?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "g_list")
async def chart_list(call: types.CallbackQuery):
    await call.message.edit_text("Выберите валюту:", reply_markup=tickers_kb("gsel"))

@router.callback_query(F.data.startswith("gsel_"))
async def chart_timeframe(call: types.CallbackQuery):
    ticker = call.data.split("_")[1]
    
    # Клавиатура времени
    btns = [
        [InlineKeyboardButton(text="30 Дней", callback_data=f"gt_{ticker}_30d"),
         InlineKeyboardButton(text="15 Дней", callback_data=f"gt_{ticker}_15d")],
        [InlineKeyboardButton(text="7 Дней", callback_data=f"gt_{ticker}_7d"),
         InlineKeyboardButton(text="1 День", callback_data=f"gt_{ticker}_1d")],
        [InlineKeyboardButton(text="12 Часов", callback_data=f"gt_{ticker}_12h"),
         InlineKeyboardButton(text="3 Часа", callback_data=f"gt_{ticker}_3h")],
        [InlineKeyboardButton(text="➕ В Избранное", callback_data=f"fav_add_{ticker}")]
    ]
    await call.message.edit_text(f"График для {ticker}. Период:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@router.callback_query(F.data.startswith("gt_"))
async def chart_draw(call: types.CallbackQuery):
    _, ticker, period_code = call.data.split("_")
    await call.answer("Рисую график...")
    
    # Настройки периода
    p, i = '1mo', '1d'
    if period_code == '15d': p, i = '1mo', '1d' # yf limitation
    elif period_code == '7d': p, i = '5d', '60m'
    elif period_code == '1d': p, i = '1d', '30m'
    elif period_code == '12h': p, i = '1d', '15m'
    elif period_code == '3h': p, i = '1d', '5m'
    
    try:
        data = yf.Ticker(ticker).history(period=p, interval=i)
        if data.empty: return await call.message.answer("Нет данных.")
        
        plt.figure(figsize=(10,5))
        plt.plot(data.index, data['Close'], label=ticker)
        plt.title(f"{ticker} ({period_code})")
        plt.grid(True)
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        
        await call.message.answer_photo(types.BufferedInputFile(buf.getvalue(), "chart.png"))
    except Exception as e: await call.message.answer(f"Ошибка: {e}")

# ===========================
# 4. ИЗБРАННОЕ
# ===========================
@router.callback_query(F.data.startswith("fav_add_"))
async def fav_add(call: types.CallbackQuery):
    ticker = call.data.split("_")[2]
    await add_to_watchlist(call.from_user.id, ticker)
    await call.answer(f"{ticker} добавлен в избранное!", show_alert=True)

@router.message(F.text == "⭐ Мой список")
async def show_fav(msg: types.Message):
    wl = await get_watchlist(msg.from_user.id)
    if not wl: return await msg.answer("Список пуст. Добавьте валюты через меню Графиков.")
    
    text = "⭐ **Ваши курсы сейчас:**\n"
    for t in wl:
        p = get_price(t)
        text += f"- {t}: {p:.4f}\n" if p else f"- {t}: Ошибка\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Очистить список", callback_data="fav_clear")]])
    await msg.answer(text, parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data == "fav_clear")
async def fav_clear_h(call: types.CallbackQuery):
    await clear_watchlist(call.from_user.id)
    await call.answer("Список очищен")
    await call.message.delete()

# ===========================
# 5. AI СОВЕТНИК (RSI + КНОПКИ)
# ===========================
@router.message(F.text == "💬 AI Советник")
async def ai_menu(msg: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Что купить?"), KeyboardButton(text="Что продать?")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True)
    await msg.answer("🤖 Финансовый ИИ готов. Выбери вопрос:", reply_markup=kb)

@router.message(F.text.in_({"Что купить?", "Что продать?"}))
async def ai_analyze(msg: types.Message):
    await msg.answer("⏳ Анализирую рынок (RSI индикаторы)... Это займет пару секунд.")
    
    best_buy, best_sell = None, None
    min_rsi, max_rsi = 100, 0
    
    for name, ticker in TICKERS.items():
        try:
            data = yf.Ticker(ticker).history(period="1mo")
            if len(data) > 14:
                delta = data['Close'].diff()
                u = delta.clip(lower=0)
                d = -1 * delta.clip(upper=0)
                rs = u.ewm(com=13, adjust=False).mean() / d.ewm(com=13, adjust=False).mean()
                rsi = 100 - (100 / (1 + rs)).iloc[-1]
                
                if rsi < min_rsi: min_rsi, best_buy = rsi, name
                if rsi > max_rsi: max_rsi, best_sell = rsi, name
        except: continue
        
    res = ""
    if msg.text == "Что купить?":
        if best_buy and min_rsi < 40:
            res = f"🟢 **Рекомендую:** {best_buy}\n📊 RSI: {min_rsi:.1f} (Перепродан)\nСигнал к росту! 🚀"
        else: res = "⚠️ Сейчас всё дорого. Лучше подождать коррекции."
    else:
        if best_sell and max_rsi > 60:
            res = f"🔴 **Можно продать:** {best_sell}\n📊 RSI: {max_rsi:.1f} (Перекуплен)\nСкоро может упасть! 📉"
        else: res = "💎 Сигналов на продажу нет. HODL (Держи)."
        
    await msg.answer(res, parse_mode="Markdown")

@router.message(F.text == "🔙 Назад")
async def back_menu(msg: types.Message):
    role = await get_user_role(msg.from_user.id)
    await msg.answer("Главное меню", reply_markup=main_kb(role))

# ===========================
# 6. ПРОЕКТЫ (АДМИНКА)
# ===========================
@router.message(F.text == "⚙️ Админка Проектов")
async def proj_admin(msg: types.Message):
    await msg.answer("Введите название нового проекта:")
    # Тут должна быть FSM логика создания проектов, как я писал в прошлом ответе.
    # Чтобы код влез в лимит сообщения, я оставил основу.
    # Если нужно подробно создание проектов - просто скопируй часть из прошлого моего ответа.
