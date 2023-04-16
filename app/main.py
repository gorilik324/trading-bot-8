import json

import pandas as pd
import requests
from alpha_vantage.techindicators import TechIndicators
from alpha_vantage.timeseries import TimeSeries
from fastapi import FastAPI
from fastapi import HTTPException
from find_patterns import find_patterns, Patterns

app = FastAPI()
api_key = "B5RQI94JSMH0JOPU"

ts = TimeSeries(key=api_key)
ti = TechIndicators(key=api_key)


@app.get("/trade_signal/{symbol}/{timeframe}")
async def trade_signal(symbol: str, timeframe: str):
    try:
        current_price, rsi, macd, macd_signal, ema = await get_market_data(symbol, timeframe)
        support, resistance = calculate_support_resistance(symbol)
        market = determine_market_trend(current_price, ema, support, resistance)
        patterns = find_chart_patterns(symbol)
        signal, take_profit, stop_loss, consolidation_price = strategy(symbol, market, current_price, rsi, macd,
                                                                       macd_signal, support, resistance, patterns)
        latest_cpi, latest_nfp = get_cpi_nfp_data()
        cpi_nfp_impact = analyze_cpi_nfp_impact(latest_cpi, latest_nfp)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        'cpi': latest_cpi,
        'nfp': latest_nfp,
        'cpi_nfp_impact': cpi_nfp_impact,
        'patterns': patterns
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

    return current_price, rsi, macd, macd_signal, ema


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


def find_chart_patterns(symbol):
    data, _ = ts.get_daily(symbol, outputsize='full')
    df = pd.DataFrame(data).T
    df.index = pd.to_datetime(df.index)
    df['close'] = df['4. close'].astype(float)
    df['high'] = df['2. high'].astype(float)
    df['low'] = df['3. low'].astype(float)
    patterns = find_patterns(df, patterns=[Patterns.DOUBLE_TOP, Patterns.DOUBLE_BOTTOM])
    return patterns


def strategy(symbol, market, current_price, rsi, macd, macd_signal, support, resistance, patterns):
    signal, take_profit, stop_loss, consolidation_price = None, None, None, None

    if market == 'consolidation':
        consolidation_price = (support + resistance) / 2
        return signal, take_profit, stop_loss, consolidation_price

    sniper_range = 0.005

    if market == 'upside' and (current_price - support) / support < sniper_range:
        signal = 'buy'
        take_profit = current_price * 1.03
        stop_loss = current_price * 0.99
    elif market == 'downside' and (resistance - current_price) / resistance < sniper_range:
        signal = 'sell'
        take_profit = current_price * 0.97
        stop_loss = current_price * 1.01

    if Patterns.DOUBLE_TOP in patterns:
        signal = 'sell'
        take_profit = current_price * 0.97
        stop_loss = current_price * 1.01
    elif Patterns.DOUBLE_BOTTOM in patterns:
        signal = 'buy'
        take_profit = current_price * 1.03
        stop_loss = current_price * 0.99

    return signal, take_profit, stop_loss, consolidation_price


def get_cpi_nfp_data():
    cpi_url = f"https://www.alphavantage.co/query?function=CPI&interval=monthly&apikey={api_key}"
    nfp_url = f"https://www.alphavantage.co/query?function=NONFARM_PAYROLL&apikey={api_key}"

    cpi_response = requests.get(cpi_url)
    nfp_response = requests.get(nfp_url)

    cpi_data = json.loads(cpi_response.text)
    nfp_data = json.loads(nfp_response.text)

    latest_cpi = float(cpi_data['CPI'][0])
    latest_nfp = float(nfp_data['Nonfarm_Payroll'][0])

    return latest_cpi, latest_nfp


def analyze_cpi_nfp_impact(cpi, nfp):
    cpi_impact = "positive" if cpi > 0 else "negative"
    nfp_impact = "positive" if nfp > 0 else "negative"

    return {"cpi_impact": cpi_impact, "nfp_impact": nfp_impact}
