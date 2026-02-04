from aiogram.fsm.state import State, StatesGroup

class ProjectState(StatesGroup):
    name = State()
    type = State()
    limit_turnover = State()
    limit_expenses = State()

class ReportState(StatesGroup):
    select_project = State()
    turnover = State()
    expenses = State() # Упростим ввод расходов до одной суммы для теста, или используй полную цепочку

class CalcState(StatesGroup):
    select_currency_1 = State()
    select_currency_2 = State()
    amount = State()
    fee = State()

class TripleCalcState(StatesGroup):
    curr_1 = State()
    curr_2 = State()
    curr_3 = State()
    amount = State()
    fee = State()
