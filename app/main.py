import os
from datetime import datetime, timedelta
import pandas as pd
import pandas_ta as pta
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from starlette.responses import JSONResponse

from pydantic import BaseModel

app = FastAPI()


class AlphaVantageError(Exception):
    pass


class PredictionResponse(BaseModel):
    symbol: str
    market: str
    current_price: float
    consolidation_price: float
    rsi: float
    macd: float
    macd_signal: float
    signal: str
    take_profit: float = None
    stop_loss: float = None
    last_news: dict = None


def get_ema(symbol, interval, time_period, series_type):
    url = f"https://www.alphavantage.co/query?function=EMA&symbol={symbol}&interval={interval}&time_period={time_period}&series_type={series_type}&apikey=B5RQI94JSMH0JOPU"
    response = requests.get(url)
    json_data = response.json()

    if "Technical Analysis: EMA" not in json_data:
        raise AlphaVantageError("Could not fetch data from AlphaVantage. Check your API key and rate limits.")

    ema_data = json_data["Technical Analysis: EMA"]
    last_ema = float(next(iter(ema_data.values()))["EMA"])
    return last_ema


def get_current_price(symbol):
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=B5RQI94JSMH0JOPU"
    response = requests.get(url)
    json_data = response.json()

    if "Global Quote" not in json_data:
        raise AlphaVantageError("Could not fetch data from AlphaVantage. Check your API key and rate limits.")

    current_price = float(json_data["Global Quote"]["05. price"])
    return current_price


@app.get("/prediction", response_model=PredictionResponse)
async def get_prediction(
    symbol: str = Query(..., description="The symbol to make predictions for"),
    market: str = Query(..., description="The market the symbol belongs to (e.g. forex, crypto, metals, nasdaq, nyse)"),
    timeframe: str = Query("15min", description="The timeframe for the candlestick data (e.g. 1min, 5min, 15min, 30min, 60min)"),
):
    # get candles data
    try:
        current_price = get_current_price(symbol)

        # calculate technical indicators
        macd = pta.macd(pd.Series([current_price]), fastperiod=12, slowperiod=26, signalperiod=9)
        ema_short = pta.ema(pd.Series([current_price]), length=50).iloc[-1]
        ema_long = pta.ema(pd.Series([current_price]), length=100).iloc[-1]
        consolidation_price = (ema_short + ema_long) / 2

        # get news data
        last_news = None

        # determine trading signal
        # determine trading signal
        rsi = pta.rsi(pd.Series([current_price]), length=14).iloc[-1]
        if current_price > consolidation_price and macd.iloc[-1]['MACD_12_26_9'] > macd.iloc[-1][
            'MACDh_12_26_9'] and rsi > 50:
            signal = 'buy'
        elif current_price < consolidation_price and macd.iloc[-1]['MACD_12_26_9'] < macd.iloc[-1][
            'MACDh_12_26_9'] and rsi < 50:
            signal = 'sell'
        else:
            signal = 'hold'

        # calculate take profit and stop loss
        if signal in ('buy', 'sell'):
            take_profit = current_price * 1.06
            stop_loss = current_price * 0.98
        else:
            take_profit = None
            stop_loss = None

        # construct response
        response = {
            'symbol': symbol,
            'market': market,
            'current_price': current_price,
            'consolidation_price': consolidation_price,
            'rsi': rsi,
            'macd': macd.iloc[-1]['MACD_12_26_9'],
            'macd_signal': macd.iloc[-1]['MACDh_12_26_9'],
            'signal': signal,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'last_news': last_news
        }

        return response

    except AlphaVantageError as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

