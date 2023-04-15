from fastapi import FastAPI
from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.techindicators import TechIndicators
from alpha_vantage.newsapi import NewsApi
import pandas as pd
import numpy as np

app = FastAPI()
api_key = "B5RQI94JSMH0JOPU"

ts = TimeSeries(key=api_key)
ti = TechIndicators(key=api_key)
newsapi = NewsApi(key=api_key)


@app.get("/trade_signal/{symbol}/{timeframe}")
async def trade_signal(symbol: str, timeframe: str):
    current_price, rsi, macd, macd_signal, ema, last_news = await get_market_data(symbol, timeframe)
    support, resistance = calculate_support_resistance(symbol)
    market = determine_market_trend(current_price, ema, support, resistance)
    signal, take_profit, stop_loss, consolidation_price = strategy(symbol, market, current_price, rsi, macd,
                                                                   macd_signal)

    response = {
        'symbol': symbol,
        'market': market,
        'current_price': current_price,
        'consolidation_price': consolidation_price,
        'rsi': rsi,
        'macd': macd,
        'macd_signal': macd_signal,
        'signal': signal,
        'take_profit': take_profit,
        'stop_loss': stop_loss,
        'support': support,
        'resistance': resistance,
        'last_news': last_news
    }

    return response


async def get_market_data(symbol, timeframe):
    data, _ = ts.get_quote_endpoint(symbol)
    current_price = float(data['05. price'])
    data, _ = ti.get_rsi(symbol, interval=timeframe)
    rsi = float(data['RSI'])
    data, _ = ti.get_macd(symbol, interval=timeframe)
    macd = float(data['MACD_Hist'])
    macd_signal = float(data['MACD_Signal'])
    data, _ = ti.get_ema(symbol, interval=timeframe)
    ema = float(data['EMA'])
    last_news = newsapi.get_last_news(symbol)

    return current_price, rsi, macd, macd_signal, ema, last_news


def calculate_support_resistance(symbol):
    data, _ = ts.get_daily(symbol, outputsize='full')
    df = pd.DataFrame(data).T
    df.index = pd.to_datetime(df.index)
    df['max'] = df['2. high'].rolling(window=20, min_periods=1).max()
    df['min'] = df['3. low'].rolling(window=20, min_periods=1).min()
    support = df['min'].iloc[-1]
    resistance = df['max'].iloc[-1]

    return float(support), float(resistance)


def determine_market_trend(current_price, ema, support, resistance):
    if current_price > ema and current_price > support:
        return 'upside'
    elif current_price < ema and current_price < resistance:
        return 'downside'
    else:
        return 'consolidation'


def strategy(symbol, market, current_price, rsi, macd, macd_signal):
    consolidation_price = 0
    signal = None
    take_profit = 0
    stop_loss = 0

    support, resistance = calculate_support_resistance(symbol)
    sniper_range = 0.005

    if market == 'upside' and (current_price - support) / support < sniper_range:
        signal = 'buy'
        take_profit = current_price * 1.03
        stop_loss = current_price * 0.99
    elif market == 'downside' and (resistance - current_price) / resistance < sniper_range:
        signal = 'sell'
        take_profit = current_price * 0.97
        stop_loss = current_price * 1.01

    return signal, take_profit, stop_loss, consolidation_price
