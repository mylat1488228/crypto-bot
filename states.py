from aiogram.fsm.state import State, StatesGroup

class ProjectState(StatesGroup):
    name = State()
    type = State()
    limit_turnover = State()
    limit_expenses = State()

class ReportState(StatesGroup):
    select_project = State()
    turnover = State()
    cost_materials = State()
    cost_commissions = State()
    cost_payouts = State()
    cost_ads = State()
    cost_services = State()
    confirm = State()

class CalcState(StatesGroup):
    waiting_for_input = State()
