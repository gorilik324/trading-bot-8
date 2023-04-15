import os
from datetime import datetime, timedelta
import pandas as pd
import pandas_ta as pta
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, JSONResponse
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


def get_candles(symbol, timeframe):
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={timeframe}&outputsize=full&apikey=B5RQI94JSMH0JOPU"
    response = requests.get(url)
    json_data = response.json()
    time_series_key = f'Time Series ({timeframe})'

    if time_series_key not in json_data:
        raise AlphaVantageError("Could not fetch data from AlphaVantage. Check your API key and rate limits.")

    data = json_data[time_series_key]
    data = {datetime.fromisoformat(k): {k2.split()[-1]: float(v2) for k2, v2 in v.items()} for k, v in data.items()}
    data = pd.DataFrame.from_dict(data, orient='index')
    data.sort_index(inplace=True)
    data.index.name = 'timestamp'
    data.reset_index(inplace=True)
    return data


def get_news(symbol, market):
    if market == 'nasdaq':
        news_url = f"https://www.nasdaq.com/market-activity/stocks/{symbol}/news-headlines"
    elif market == 'nyse':
        news_url = f"https://www.nyse.com/quote/{symbol}/news"
    elif market == 'forex':
        news_url = f"https://www.dailyfx.com/{symbol}-news"
    elif market == 'crypto':
        news_url = f"https://cointelegraph.com/tags/{symbol}-news"
    elif market == 'metals':
        news_url = f"https://www.kitco.com/news/{symbol}-news.html"
    else:
        raise ValueError(f"Unsupported market: {market}")

    response = requests.get(news_url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(response.text, 'html.parser')
    if market in ['nasdaq', 'nyse']:
        news_items = soup.find_all('a', class_='quote-news-headlines__link') if market == 'nasdaq' else soup.find_all(
            'a', class_='news-link')
        news_timestamps = soup.find_all('span',
                                        class_='quote-news-headlines__date') if market == 'nasdaq' else soup.find_all(
            'time')
    else:
        news_items = soup.find_all('a', class_='post-card-title')
        news_timestamps = soup.find_all('time')

    news_list = []
    for i, item in enumerate(news_items):
        if market in ['nasdaq', 'nyse']:
            timestamp = datetime.strptime(news_timestamps[i].text.strip(),
                                          "%m/%d/%Y %I:%M%p") if market == 'nasdaq' else datetime.fromisoformat(
                news_timestamps[i]['datetime'])
        else:
            timestamp = datetime.strptime(news_timestamps[i]['datetime'], '%Y-%m-%dT%H:%M:%S%z')
        news_list.append({
            'title': item.text.strip(),
            'url': item['href'],
            'timestamp': timestamp
        })

    return news_list


@app.get("/prediction", response_model=PredictionResponse)
async def get_prediction(
    symbol: str = Query(..., description="The symbol to make predictions for"),
    market: str = Query(..., description="The market the symbol belongs to (e.g. forex, crypto, metals, nasdaq, nyse)"),
    timeframe: str = Query("15min", description="The timeframe for the candlestick data (e.g. 1min, 5min, 15min, 30min, 60min)"),
):
    # get candles data
    try:
        candles = get_candles(symbol, timeframe)
        closes = candles['close'].values.astype(float)
        candles['close'] = closes

        macd = pta.macd(candles['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        ema_short = pta.ema(candles['close'], length=50).iloc[-1]
        ema_long = pta.ema(candles['close'], length=100).iloc[-1]
        current_price = closes[-1]
        consolidation_price = (ema_short + ema_long) / 2

        # get news data
        news = get_news(symbol, market)
        last_news = news[0] if len(news) > 0 else None

        # determine trading signal
        rsi = pta.rsi(candles['close'], length=14).iloc[-1]
        if current_price > consolidation_price and macd.iloc[-1]['MACD_12_26_9'] > macd.iloc[-1][
            'SIGNAL_12_26_9'] and rsi > 50:
            signal = 'buy'
        elif current_price < consolidation_price and macd.iloc[-1]['MACD_12_26_9'] < macd.iloc[-1][
            'SIGNAL_12_26_9'] and rsi < 50:
            signal = 'sell'
        else:
            signal = 'hold'

        # calculate take profit and stop loss
        if signal in ('buy', 'sell'):
            take_profit = current_price * 1.06
            stop_loss = current_price * 0.97
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
            'macd_signal': macd.iloc[-1]['SIGNAL_12_26_9'],
            'signal': signal,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'last_news': last_news
        }

        return response

    except AlphaVantageError as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

