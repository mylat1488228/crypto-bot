import io
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
from datetime import datetime
from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from database import *
from states import *
from config import TICKERS, REVERSE_PAIRS, MAIN_ADMIN_USERNAME

router = Router()
global_logs = [] # Логи в оперативной памяти (последние 100 действий)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def log_action(user, action):
    t = datetime.now().strftime("%H:%M")
    entry = f"[{t}] @{user.username} ({user.id}): {action}"
    global_logs.append(entry)
    if len(global_logs) > 50: global_logs.pop(0)

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
async def start(msg: types.Message, state: FSMContext):
    await state.clear()
    role = 'admin' if msg.from_user.username == MAIN_ADMIN_USERNAME else 'executor'
    await add_user(msg.from_user.id, msg.from_user.username, role)
    log_action(msg.from_user, "Запустил бота")
    await msg.answer("Бот готов! Выбери действие:", reply_markup=main_kb(role))

# ===========================
# 0. АДМИН КОНСОЛЬ (ВЕРНУЛ)
# ===========================
@router.message(Command("admin"))
async def admin_panel(msg: types.Message):
    if msg.from_user.username != MAIN_ADMIN_USERNAME:
        return await msg.answer("⛔ Доступ запрещен.")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Логи (50)", callback_data="adm_logs"),
         InlineKeyboardButton(text="👥 Пользователи", callback_data="adm_users")]
    ])
    await msg.answer("🔒 **Админ Консоль**", parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data == "adm_logs")
async def show_logs(call: types.CallbackQuery):
    if not global_logs: return await call.answer("Логов пока нет", show_alert=True)
    text = "\n".join(global_logs[-15:]) # Показываем последние 15
    await call.message.answer(f"📜 **Последние действия:**\n\n{text}", parse_mode="Markdown")
    await call.answer()

@router.callback_query(F.data == "adm_users")
async def show_users(call: types.CallbackQuery):
    users = await get_all_users_list() # Функция из database.py
    if not users: return await call.answer("Пусто")
    
    text = f"👥 **Всего пользователей: {len(users)}**\n\n"
    for u in users:
        text += f"- @{u['username']} (ID: {u['user_id']}) | {u['role']}\n"
    
    if len(text) > 4000: text = text[:4000] + "..."
    await call.message.answer(text)
    await call.answer()

# ===========================
# 1. АДМИНКА ПРОЕКТОВ
# ===========================
@router.message(F.text == "⚙️ Админка Проектов")
async def proj_start(msg: types.Message, state: FSMContext):
    role = await get_user_role(msg.from_user.id)
    if role != 'admin': return await msg.answer("Доступ запрещен.")
    
    await msg.answer("Введите название проекта:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ProjectState.name)

@router.message(StateFilter(ProjectState.name))
async def proj_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="карта"), KeyboardButton(text="сим")],
        [KeyboardButton(text="проект"), KeyboardButton(text="другое")]
    ], resize_keyboard=True)
    await msg.answer("Выберите тип проекта:", reply_markup=kb)
    await state.set_state(ProjectState.type)

@router.message(StateFilter(ProjectState.type))
async def proj_type(msg: types.Message, state: FSMContext):
    if msg.text not in ['карта', 'сим', 'проект', 'другое']: return await msg.answer("Нажми кнопку!")
    await state.update_data(type=msg.text)
    await msg.answer("Лимит расходов (число, или 0):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ProjectState.limit_expenses)

@router.message(StateFilter(ProjectState.limit_expenses))
async def proj_finish(msg: types.Message, state: FSMContext):
    try:
        limit = float(msg.text)
        data = await state.get_data()
        await create_project(data['name'], data['type'], 0, limit)
        role = await get_user_role(msg.from_user.id)
        await msg.answer(f"✅ Проект '{data['name']}' создан!", reply_markup=main_kb(role))
        await state.clear()
        log_action(msg.from_user, f"Создал проект {data['name']}")
    except: await msg.answer("Это не число.")

# ===========================
# 2. ОТЧЕТЫ (ИСПОЛНИТЕЛИ)
# ===========================
@router.message(F.text == "➕ Отчет (Проекты)")
async def rep_start(msg: types.Message, state: FSMContext):
    projects = await get_projects()
    if not projects: return await msg.answer("Нет проектов.")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=p['name'], callback_data=f"rep_{p['id']}")] for p in projects
    ])
    await msg.answer("Выберите проект:", reply_markup=kb)
    await state.set_state(ReportState.select_project)

@router.callback_query(StateFilter(ReportState.select_project), F.data.startswith("rep_"))
async def rep_sel(call: types.CallbackQuery, state: FSMContext):
    pid = int(call.data.split("_")[1])
    await state.update_data(pid=pid)
    await call.message.edit_text("Введи ОБОРОТ (число):")
    await state.set_state(ReportState.turnover)

@router.message(StateFilter(ReportState.turnover))
async def rep_turn(msg: types.Message, state: FSMContext):
    try:
        await state.update_data(turnover=float(msg.text))
        await msg.answer("Введи РАСХОДЫ (число):")
        await state.set_state(ReportState.expenses)
    except: await msg.answer("Число!")

@router.message(StateFilter(ReportState.expenses))
async def rep_fin(msg: types.Message, state: FSMContext):
    try:
        exp = float(msg.text)
        d = await state.get_data()
        profit = d['turnover'] - exp
        roi = (profit / exp * 100) if exp > 0 else 0
        margin = (profit / d['turnover'] * 100) if d['turnover'] > 0 else 0
        
        await add_report((msg.from_user.id, d['pid'], d['turnover'], exp, profit, roi, margin))
        role = await get_user_role(msg.from_user.id)
        await msg.answer(f"✅ Отчет принят!\nПрибыль: {profit}", reply_markup=main_kb(role))
        log_action(msg.from_user, f"Сдал отчет. Прибыль: {profit}")
        await state.clear()
    except: await msg.answer("Число!")

# ===========================
# 3. КАЛЬКУЛЯТОР
# ===========================
@router.message(F.text == "🧮 Калькулятор")
async def calc_start(msg: types.Message, state: FSMContext):
    await msg.answer("Что отдаем?", reply_markup=tickers_kb("c1"))
    await state.set_state(CalcState.select_currency_1)

@router.callback_query(StateFilter(CalcState.select_currency_1), F.data.startswith("c1_"))
async def calc_2(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(c1=call.data.split("_")[1])
    await call.message.edit_text("Что получаем?", reply_markup=tickers_kb("c2"))
    await state.set_state(CalcState.select_currency_2)

@router.callback_query(StateFilter(CalcState.select_currency_2), F.data.startswith("c2_"))
async def calc_3(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(c2=call.data.split("_")[1])
    await call.message.edit_text("Сумма?")
    await state.set_state(CalcState.amount)

@router.message(StateFilter(CalcState.amount))
async def calc_4(msg: types.Message, state: FSMContext):
    try:
        await state.update_data(amt=float(msg.text))
        await msg.answer("Комиссия %:")
        await state.set_state(CalcState.fee)
    except: await msg.answer("Число!")

@router.message(StateFilter(CalcState.fee))
async def calc_5(msg: types.Message, state: FSMContext):
    try:
        fee = float(msg.text)
        d = await state.get_data()
        p1, p2 = get_price(d['c1']), get_price(d['c2'])
        if p1 and p2:
            u = convert(d['amt'], d['c1'], p1, True)
            fin = convert(u*(1-fee/100), d['c2'], p2, False)
            await msg.answer(f"Итог: {fin:,.2f}")
        else: await msg.answer("Ошибка курса.")
        await state.clear()
    except: pass

# ===========================
# 4. ТРОЙНОЙ ОБМЕН
# ===========================
@router.message(F.text == "🔀 Тройной Обмен")
async def triple_start(msg: types.Message, state: FSMContext):
    await msg.answer("1. Старт:", reply_markup=tickers_kb("t1"))
    await state.set_state(TripleCalcState.curr_1)

@router.callback_query(StateFilter(TripleCalcState.curr_1), F.data.startswith("t1_"))
async def triple_2(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(c1=call.data.split("_")[1])
    await call.message.edit_text("2. Центр:", reply_markup=tickers_kb("t2"))
    await state.set_state(TripleCalcState.curr_2)

@router.callback_query(StateFilter(TripleCalcState.curr_2), F.data.startswith("t2_"))
async def triple_3(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(c2=call.data.split("_")[1])
    await call.message.edit_text("3. Финиш:", reply_markup=tickers_kb("t3"))
    await state.set_state(TripleCalcState.curr_3)

@router.callback_query(StateFilter(TripleCalcState.curr_3), F.data.startswith("t3_"))
async def triple_4(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(c3=call.data.split("_")[1])
    await call.message.edit_text("Сумма:")
    await state.set_state(TripleCalcState.amount)

@router.message(StateFilter(TripleCalcState.amount))
async def triple_5(msg: types.Message, state: FSMContext):
    try:
        await state.update_data(amt=float(msg.text))
        await msg.answer("Комиссия %:")
        await state.set_state(TripleCalcState.fee)
    except: await msg.answer("Число!")

@router.message(StateFilter(TripleCalcState.fee))
async def triple_6(msg: types.Message, state: FSMContext):
    try:
        fee = float(msg.text)/100
        d = await state.get_data()
        p1, p2, p3 = get_price(d['c1']), get_price(d['c2']), get_price(d['c3'])
        if p1 and p2 and p3:
            u1 = convert(d['amt'], d['c1'], p1, True)
            u2 = convert(convert(u1*(1-fee), d['c2'], p2, False), d['c2'], p2, True)
            fin = convert(u2*(1-fee), d['c3'], p3, False)
            await msg.answer(f"Итог: {fin:,.2f}")
        await state.clear()
    except: pass

# ===========================
# 5. ГРАФИКИ
# ===========================
@router.message(F.text == "📈 Графики")
async def charts(msg: types.Message):
    user_wl = await get_watchlist(msg.from_user.id)
    kb = []
    if user_wl:
        row = [InlineKeyboardButton(text=f"⭐ {t}", callback_data=f"gsel_{t}") for t in user_wl]
        kb.append(row)
    kb.append([InlineKeyboardButton(text="📋 Список валют", callback_data="g_list")])
    await msg.answer("Выбери:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "g_list")
async def chart_list(call: types.CallbackQuery):
    await call.message.edit_text("Валюта:", reply_markup=tickers_kb("gsel"))

@router.callback_query(F.data.startswith("gsel_"))
async def chart_tf(call: types.CallbackQuery):
    t = call.data.split("_")[1]
    kb = [
        [InlineKeyboardButton(text="30д", callback_data=f"gt_{t}_30d"), InlineKeyboardButton(text="7д", callback_data=f"gt_{t}_7d")],
        [InlineKeyboardButton(text="1д", callback_data=f"gt_{t}_1d"), InlineKeyboardButton(text="3ч", callback_data=f"gt_{t}_3h")],
        [InlineKeyboardButton(text="➕ В Избранное", callback_data=f"fav_add_{t}")]
    ]
    await call.message.edit_text(f"Период для {t}:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("gt_"))
async def chart_draw(call: types.CallbackQuery):
    _, t, p = call.data.split("_")
    await call.answer("Рисую...")
    per, inter = '1mo', '1d'
    if p == '7d': per, inter = '5d', '60m'
    elif p == '1d': per, inter = '1d', '30m'
    elif p == '3h': per, inter = '1d', '5m'
    try:
        d = yf.Ticker(t).history(period=per, interval=inter)
        plt.figure()
        plt.plot(d.index, d['Close'])
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        await call.message.answer_photo(types.BufferedInputFile(buf.getvalue(), "chart.png"))
    except: await call.message.answer("Ошибка")

# ===========================
# 6. ОСТАЛЬНОЕ
# ===========================
@router.callback_query(F.data.startswith("fav_add_"))
async def fav_add(call: types.CallbackQuery):
    await add_to_watchlist(call.from_user.id, call.data.split("_")[2])
    await call.answer("Добавлено!")

@router.message(F.text == "⭐ Мой список")
async def wl(msg: types.Message):
    wl = await get_watchlist(msg.from_user.id)
    if not wl: return await msg.answer("Пусто.")
    t = "⭐ **Курсы:**\n"
    for ticker in wl:
        p = get_price(ticker)
        t += f"{ticker}: {p}\n" if p else f"{ticker}: Err\n"
    await msg.answer(t, parse_mode="Markdown")

@router.message(F.text == "💬 AI Советник")
async def ai(msg: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Что купить?"), KeyboardButton(text="Что продать?")]], resize_keyboard=True)
    await msg.answer("Спрашивай:", reply_markup=kb)

@router.message()
async def echo(msg: types.Message):
    if "купить" in msg.text.lower(): await msg.answer("Анализ...")
    else: await msg.answer("Используй меню.")
