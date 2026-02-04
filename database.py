import aiosqlite

DB_NAME = "finance_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Пользователи
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT DEFAULT 'executor' 
        )''')
        # Проекты
        await db.execute('''CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            limit_turnover REAL DEFAULT 0,
            limit_expenses REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # Отчеты
        await db.execute('''CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            project_id INTEGER,
            turnover REAL,
            total_expenses REAL,
            net_profit REAL,
            roi REAL,
            margin REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # ИЗБРАННОЕ (НОВОЕ)
        await db.execute('''CREATE TABLE IF NOT EXISTS watchlist (
            user_id INTEGER,
            ticker TEXT,
            UNIQUE(user_id, ticker)
        )''')
        await db.commit()

async def add_user(user_id, username, role='executor'):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username, role) VALUES (?, ?, ?)", (user_id, username, role))
        await db.commit()

async def get_user_role(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT role FROM users WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else 'executor'

# --- ФУНКЦИИ ДЛЯ ИЗБРАННОГО ---
async def add_to_watchlist(user_id, ticker):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO watchlist (user_id, ticker) VALUES (?, ?)", (user_id, ticker))
        await db.commit()

async def get_watchlist(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT ticker FROM watchlist WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def clear_watchlist(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM watchlist WHERE user_id = ?", (user_id,))
        await db.commit()

# --- ФУНКЦИИ ПРОЕКТОВ (Остались прежними, сократил для удобства чтения тут) ---
async def create_project(name, p_type, limit_t, limit_e):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO projects (name, type, limit_turnover, limit_expenses) VALUES (?, ?, ?, ?)", (name, p_type, limit_t, limit_e))
        await db.commit()

async def get_projects():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM projects WHERE is_active=1") as cursor:
            return await cursor.fetchall()

async def add_report(data):
    async with aiosqlite.connect(DB_NAME) as db:
        # Упрощенная вставка для примера, полная версия была выше
        await db.execute("INSERT INTO reports (user_id, project_id, turnover, total_expenses, net_profit, roi, margin) VALUES (?, ?, ?, ?, ?, ?, ?)", data)
        await db.commit()
