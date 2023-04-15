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

API_KEY = "B5RQI94JSMH0JOPU"


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


def get_macd(symbol, interval, series_type):
    url = f"https://www.alphavantage.co/query?function=MACD&symbol={symbol}&interval={interval}&series_type={series_type}&apikey={API_KEY}"
    response = requests.get(url)
    json_data = response.json()

    if "Technical Analysis: MACD" not in json_data:
        raise AlphaVantageError("Could not fetch MACD data from AlphaVantage. Check your API key and rate limits.")

    macd_data = json_data["Technical Analysis: MACD"]
    latest_macd = list(macd_data.values())[0]

    macd = float(latest_macd["MACD"])
    macd_signal = float(latest_macd["MACD_Signal"])

    return macd, macd_signal


def get_ema(symbol, interval, time_period, series_type):
    url = f"https://www.alphavantage.co/query?function=EMA&symbol={symbol}&interval={interval}&time_period={time_period}&series_type={series_type}&apikey={API_KEY}"
    response = requests.get(url)
    json_data = response.json()

    if "Technical Analysis: EMA" not in json_data:
        raise AlphaVantageError("Could not fetch data from AlphaVantage. Check your API key and rate limits.")

    ema_data = json_data["Technical Analysis: EMA"]
    last_ema = float(next(iter(ema_data.values()))["EMA"])
    return last_ema


def get_current_price(symbol):
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={API_KEY}"
    response = requests.get(url)
    json_data = response.json()

    if "Global Quote" not in json_data:
        raise AlphaVantageError("Could not fetch data from AlphaVantage. Check your API key and rate limits.")

    current_price = float(json_data["Global Quote"]["05. price"])
    return current_price


@app.get("/prediction", response_model=PredictionResponse)
async def get_prediction(
        symbol: str = Query(..., description="The symbol to make predictions for"),
        market: str = Query(...,
                            description="The market the symbol belongs to (e.g. forex, crypto, metals, nasdaq, nyse)"),
        timeframe: str = Query("15min",
                               description="The timeframe for the candlestick data (e.g. 1min, 5min, 15min, 30min, 60min)"),
):
    # get candles data
    try:
        current_price = get_current_price(symbol)

        # get MACD and MACD signal
        try:
            macd, macd_signal = get_macd(symbol, timeframe, "close")

        except AlphaVantageError as e:
            return JSONResponse(status_code=500, content={"detail": str(e)})

        # get EMA data
        try:
            ema_short = get_ema(symbol, timeframe, "50", "close")
            ema_long = get_ema(symbol, timeframe, "100", "close")

        except AlphaVantageError as e:
            return JSONResponse(status_code=500, content={"detail": str(e)})

            # get RSI
        try:
            url = f"https://www.alphavantage.co/query?function=RSI&symbol={symbol}&interval={timeframe}&time_period=14&series_type=close&apikey={API_KEY}"
            response = requests.get(url)
            json_data = response.json()

            if "Technical Analysis: RSI" not in json_data:
                raise AlphaVantageError(
                    "Could not fetch RSI data from AlphaVantage. Check your API key and rate limits.")

            rsi_data = json_data["Technical Analysis: RSI"]
            latest_rsi = list(rsi_data.values())[0]
            rsi = float(latest_rsi["RSI"])

        except AlphaVantageError as e:
            return JSONResponse(status_code=500, content={"detail": str(e)})

        consolidation_price = (ema_short + ema_long) / 2

        last_news = None

        # determine trading signal

        if current_price > consolidation_price and macd > macd_signal and rsi > 50:
            signal = 'buy'
        elif current_price < consolidation_price and macd < macd_signal and rsi < 50:
            signal = 'sell'
        else:
            signal = 'hold'

        # calculate take profit and stop loss
        if signal in ('buy', 'sell'):
            take_profit = current_price * 1.03
            stop_loss = current_price * 0.99
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
            'macd': macd,
            'macd_signal': macd_signal,
            'signal': signal,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'last_news': last_news
        }

        return response

    except AlphaVantageError as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})
