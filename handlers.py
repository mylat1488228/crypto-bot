import asyncio
import io
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import *
from states import *
from config import TICKERS, MAIN_ADMIN_USERNAME

router = Router()

# --- КЛАВИАТУРЫ ---
def main_kb(role):
    kb = [
        [KeyboardButton(text="📄 Мои Проекты"), KeyboardButton(text="➕ Добавить отчет")],
        [KeyboardButton(text="🧮 Калькулятор"), KeyboardButton(text="📈 Графики Валют")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="💬 AI Помощник")]
    ]
    if role == 'admin':
        kb.append([KeyboardButton(text="⚙️ Создать Проект (Админ)")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- БАЗОВЫЕ КОМАНДЫ ---
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    role = 'admin' if message.from_user.username == MAIN_ADMIN_USERNAME else 'executor'
    await add_user(message.from_user.id, message.from_user.username, role)
    await message.answer(f"Привет, {message.from_user.first_name}! Я твой финансовый бот 2.0.\nРоль: {role}", 
                         reply_markup=main_kb(role))

# --- СОЗДАНИЕ ПРОЕКТА (Только Админ) ---
@router.message(F.text == "⚙️ Создать Проект (Админ)")
async def new_project_start(message: types.Message, state: FSMContext):
    role = await get_user_role(message.from_user.id)
    if role != 'admin':
        return await message.answer("Доступ запрещен.")
    await state.set_state(ProjectState.name)
    await message.answer("Введите название нового проекта:")

@router.message(ProjectState.name)
async def process_project_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ProjectState.type)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="карта"), KeyboardButton(text="сим")],
        [KeyboardButton(text="проект"), KeyboardButton(text="другое")]
    ], resize_keyboard=True)
    await message.answer("Выберите тип проекта:", reply_markup=kb)

@router.message(ProjectState.type)
async def process_project_type(message: types.Message, state: FSMContext):
    await state.update_data(type=message.text)
    await state.set_state(ProjectState.limit_turnover)
    await message.answer("Установите лимит Оборота (число, например 500000). Если нет - 0:", reply_markup=types.ReplyKeyboardRemove())

@router.message(ProjectState.limit_turnover)
async def process_limit_t(message: types.Message, state: FSMContext):
    try:
        val = float(message.text)
        await state.update_data(limit_t=val)
        await state.set_state(ProjectState.limit_expenses)
        await message.answer("Установите лимит Расходов (число):")
    except: await message.answer("Введите число!")

@router.message(ProjectState.limit_expenses)
async def process_limit_e(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        limit_e = float(message.text)
        await create_project(data['name'], data['type'], data['limit_t'], limit_e)
        role = await get_user_role(message.from_user.id)
        await message.answer(f"✅ Проект '{data['name']}' создан!", reply_markup=main_kb(role))
        await state.clear()
    except: await message.answer("Введите число!")

# --- ДОБАВЛЕНИЕ ОТЧЕТА (Вся математика тут) ---
@router.message(F.text == "➕ Добавить отчет")
async def add_report_start(message: types.Message, state: FSMContext):
    projects = await get_projects()
    if not projects:
        return await message.answer("Нет активных проектов.")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=p['name'], callback_data=f"sel_proj_{p['id']}")] for p in projects
    ])
    await message.answer("Выберите проект для отчета:", reply_markup=kb)
    await state.set_state(ReportState.select_project)

@router.callback_query(F.data.startswith("sel_proj_"))
async def report_proj_sel(callback: types.CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[2])
    await state.update_data(pid=pid)
    await state.set_state(ReportState.turnover)
    await callback.message.answer("💰 Введите ОБОРОТ (выручка):")
    await callback.answer()

@router.message(ReportState.turnover)
async def rep_turnover(message: types.Message, state: FSMContext):
    try:
        await state.update_data(turnover=float(message.text))
        await state.set_state(ReportState.cost_materials)
        await message.answer("📦 Расход на МАТЕРИАЛЫ:")
    except: await message.answer("Число!")

@router.message(ReportState.cost_materials)
async def rep_mat(message: types.Message, state: FSMContext):
    try:
        await state.update_data(mat=float(message.text))
        await state.set_state(ReportState.cost_commissions)
        await message.answer("💳 Расход на КОМИССИИ:")
    except: await message.answer("Число!")

@router.message(ReportState.cost_commissions)
async def rep_com(message: types.Message, state: FSMContext):
    try:
        await state.update_data(com=float(message.text))
        await state.set_state(ReportState.cost_payouts)
        await message.answer("👥 Расход на ВЫПЛАТЫ (проценты):")
    except: await message.answer("Число!")

@router.message(ReportState.cost_payouts)
async def rep_pay(message: types.Message, state: FSMContext):
    try:
        await state.update_data(pay=float(message.text))
        await state.set_state(ReportState.cost_ads)
        await message.answer("📢 Расход на РЕКЛАМУ:")
    except: await message.answer("Число!")

@router.message(ReportState.cost_ads)
async def rep_ads(message: types.Message, state: FSMContext):
    try:
        await state.update_data(ads=float(message.text))
        await state.set_state(ReportState.cost_services)
        await message.answer("🛠 Расход на СЕРВИСЫ/ПРОЧЕЕ:")
    except: await message.answer("Число!")

@router.message(ReportState.cost_services)
async def rep_finish(message: types.Message, state: FSMContext):
    try:
        serv = float(message.text)
        d = await state.get_data()
        
        # РАСЧЕТЫ
        total_exp = d['mat'] + d['com'] + d['pay'] + d['ads'] + serv
        net_profit = d['turnover'] - total_exp
        
        roi = (net_profit / total_exp * 100) if total_exp > 0 else 0
        margin = (net_profit / d['turnover'] * 100) if d['turnover'] > 0 else 0
        
        # Сохранение в БД
        report_data = (
            message.from_user.id, d['pid'], d['turnover'], 
            d['mat'], d['com'], d['pay'], d['ads'], serv,
            total_exp, net_profit, roi, margin
        )
        await add_report(report_data)
        
        # Проверка лимитов (упрощенно)
        projects = await get_projects()
        proj = next((p for p in projects if p['id'] == d['pid']), None)
        alert = ""
        if proj and proj['limit_expenses'] > 0 and total_exp > proj['limit_expenses']:
            alert = "\n⚠️ <b>ВНИМАНИЕ! Лимит расходов превышен!</b>"

        res = (
            f"✅ <b>Отчет принят!</b>\n\n"
            f"📈 Оборот: {d['turnover']:,.2f} ₽\n"
            f"💸 Общие расходы: {total_exp:,.2f} ₽\n"
            f"💵 <b>Чистая прибыль: {net_profit:,.2f} ₽</b>\n"
            f"📊 ROI: {roi:.1f}%\n"
            f"📉 Маржа: {margin:.1f}%"
            f"{alert}"
        )
        role = await get_user_role(message.from_user.id)
        await message.answer(res, parse_mode="HTML", reply_markup=main_kb(role))
        await state.clear()
        
    except Exception as e: await message.answer(f"Ошибка: {e}")

# --- СТАТИСТИКА И CSV ---
@router.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    data = await get_stats_data()
    if not data: return await message.answer("Пока нет отчетов.")
    
    df = pd.DataFrame([dict(row) for row in data])
    
    total_turnover = df['turnover'].sum()
    total_profit = df['net_profit'].sum()
    avg_roi = df['roi'].mean()
    
    # CSV
    csv_buf = io.StringIO()
    df.to_csv(csv_buf)
    csv_buf.seek(0)
    file = types.BufferedInputFile(csv_buf.getvalue().encode(), filename="stats.csv")
    
    text = (
        f"📊 <b>Общая статистика:</b>\n"
        f"Всего отчетов: {len(df)}\n"
        f"💰 Оборот: {total_turnover:,.0f}\n"
        f"🤑 Прибыль: {total_profit:,.0f}\n"
        f"📈 Средний ROI: {avg_roi:.1f}%"
    )
    await message.answer_document(file, caption=text, parse_mode="HTML")

# --- СТАРЫЕ ФУНКЦИИ (ГРАФИКИ) ---
@router.message(F.text == "📈 Графики Валют")
async def old_charts(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="USDT", callback_data="chart_USDT-USD"),
         InlineKeyboardButton(text="BTC", callback_data="chart_BTC-USD")]
    ])
    await message.answer("Выберите валюту:", reply_markup=kb)

@router.callback_query(F.data.startswith("chart_"))
async def send_chart(callback: types.CallbackQuery):
    ticker = callback.data.split("_")[1]
    try:
        data = yf.Ticker(ticker).history(period="1mo")
        plt.figure()
        plt.plot(data.index, data['Close'])
        plt.title(f"{ticker} (30 days)")
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        
        await callback.message.answer_photo(
            types.BufferedInputFile(buf.getvalue(), filename="chart.png")
        )
        await callback.answer()
    except: await callback.answer("Ошибка получения данных")

# --- AI ЧАТ (Эмуляция) ---
@router.message(F.text == "💬 AI Помощник")
async def ai_chat(message: types.Message):
    await message.answer("🤖 Привет! Спроси меня 'Что купить?' или 'Куда уходят деньги?'.")

@router.message(F.text.lower().contains("деньги"))
async def ai_analyze_money(message: types.Message):
    # Анализ самого большого расхода из БД
    data = await get_stats_data()
    if not data: return await message.answer("Нужны данные отчетов для анализа.")
    
    df = pd.DataFrame([dict(row) for row in data])
    expenses = {
        'Материалы': df['cost_materials'].sum(),
        'Комиссии': df['cost_commissions'].sum(),
        'Реклама': df['cost_ads'].sum()
    }
    max_cat = max(expenses, key=expenses.get)
    await message.answer(f"🧐 Анализ показал: больше всего денег уходит на <b>{max_cat}</b>.", parse_mode="HTML")

# --- КАЛЬКУЛЯТОР ---
@router.message(F.text == "🧮 Калькулятор")
async def simple_calc(message: types.Message):
    await message.answer("Введите выражение (например: 45000 - 13000 * 0.9)")

# Ловушка для текста (AI и Калькулятор)
@router.message()
async def text_handler(message: types.Message):
    # Простой калькулятор
    if any(x in message.text for x in "+-*/"):
        try:
            res = eval(message.text.replace(',', '.'))
            await message.answer(f"🧮 Результат: {res}")
            return
        except: pass
    
    # AI ответы
    if "привет" in message.text.lower():
        await message.answer("Салам! Готов работать?")
    elif "купить" in message.text.lower():
        await message.answer("Сейчас рынок нестабилен. Посмотри графики в меню.")
    else:
        await message.answer("Я не понял команду. Используйте кнопки меню.")
