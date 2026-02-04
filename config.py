import os

# Токен и Админ
BOT_TOKEN = os.getenv('BOT_TOKEN', '8212929038:AAEJ_P_Ttiy8-nrf1W2KfOqxQDiJNY1MlGk')
MAIN_ADMIN_USERNAME = 'SIavyanln'

# Полный список валют для калькуляторов и графиков
TICKERS = {
    '💵 USDT': 'USDT-USD',
    '🇺🇸 USD': 'DX-Y.NYB',
    '₿ BTC': 'BTC-USD',
    '💎 ETH': 'ETH-USD',
    '💎 TON': 'TON11419-USD',
    '🇪🇺 EUR': 'EURUSD=X',
    '🇷🇺 RUB': 'RUB=X',
    '🇰🇬 KGS': 'KGS=X',
    '🇨🇳 CNY': 'CNY=X',
    '🇦🇪 AED': 'AED=X',
    '🇹🇯 TJS': 'TJS=X',
    '🇺🇿 UZS': 'UZS=X'
}

# Валюты, где курс "Х за 1 доллар"
REVERSE_PAIRS = ['RUB=X', 'KGS=X', 'CNY=X', 'AED=X', 'TJS=X', 'UZS=X']
