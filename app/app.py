import os
from datetime import datetime, timedelta
import pandas as pd
import talib
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from pydantic import BaseModel

app = FastAPI()


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
    data = response.json()['Time Series ({})'.format(timeframe)]
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
def get_prediction(symbol: str = Query(..., description="The symbol to make predictions for"), market
: str = Query(..., description="The market the symbol belongs to (e.g. forex, crypto, metals, nasdaq, nyse)")):
    # get candles data
    candles = get_candles(symbol, "15min")
    closes = candles['close'].values.astype(float)
    # calculate indicators
    macd, macdsignal, macdhist = talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)
    ema_short = talib.EMA(closes, timeperiod=50)[-1]
    ema_long = talib.EMA(closes, timeperiod=100)[-1]
    current_price = closes[-1]
    consolidation_price = (ema_short + ema_long) / 2

    # get news data
    news = get_news(symbol, market)
    last_news = news[0] if len(news) > 0 else None

    # determine trading signal
    rsi = talib.RSI(closes, timeperiod=14)[-1]
    if current_price > consolidation_price and macd[-1] > macdsignal[-1] and rsi > 50:
        signal = 'buy'
    elif current_price < consolidation_price and macd[-1] < macdsignal[-1] and rsi < 50:
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
        'macd': macd[-1],
        'macd_signal': macdsignal[-1],
        'signal': signal,
        'take_profit': take_profit,
        'stop_loss': stop_loss,
        'last_news': last_news
    }

    return response
