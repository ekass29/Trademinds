from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
import os
import json
import time
from datetime import datetime, timedelta
from config import NEWS_API_KEY
from auth import auth
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure random secret key
app.register_blueprint(auth)
# Configure cache directory
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# API configuration
ALPHA_VANTAGE_KEYS = [
    "0QKMK7TVG7UYBU7P",   # Replace with your actual keys
    "5GTSW729JG9T742M",   # Get multiple keys from Alpha Vantage
    "DEMO"                # Last resort demo key
]

def get_alpha_vantage_data(symbol, function, interval=None, retry_count=0):
    """Robust data fetcher with key rotation and caching"""
    # First check cache
    cache_file = f"{CACHE_DIR}/{symbol}_{function}.json"
    if os.path.exists(cache_file):
        cache_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))
        if cache_age < timedelta(hours=6):  # 6 hour cache
            with open(cache_file) as f:
                return json.load(f)

    # Try each API key
    current_key = ALPHA_VANTAGE_KEYS[retry_count % len(ALPHA_VANTAGE_KEYS)]
    
    try:
        url = f"https://www.alphavantage.co/query?function={function}&symbol={symbol}&apikey={current_key}"
        if interval:
            url += f"&interval={interval}"
            
        response = requests.get(url)
        data = response.json()
        
        if "Note" in data or "Information" in data:
            print(f"Key {current_key[:5]}... hit limit, trying next...")
            if retry_count < len(ALPHA_VANTAGE_KEYS) - 1:
                time.sleep(2)  # Brief delay before retry
                return get_alpha_vantage_data(symbol, function, interval, retry_count + 1)
            raise ValueError("All API keys exhausted")

        # Cache successful response
        with open(cache_file, "w") as f:
            json.dump(data, f)
            
        return data
        
    except Exception as e:
        print(f"API Error: {str(e)}")
        raise

def get_top_stocks():
    """Fetch top market stocks with multiple fallback options"""
    # First try Alpha Vantage
    try:
        data = get_alpha_vantage_data("", "TOP_GAINERS_LOSERS")
        if 'top_gainers' in data:
            top_stocks = []
            for stock in data['top_gainers'][:30]:  # Get top 30 gainers
                try:
                    change_pct = float(stock['change_percentage'].replace('%', ''))
                    top_stocks.append({
                        'symbol': stock['ticker'],
                        'name': stock.get('company_name', stock['ticker']),
                        'price': float(stock['price']),
                        'change': change_pct,
                        'low': float(stock['low']),
                        'high': float(stock['high']),
                        'volume': int(stock['volume']),
                        'sentiment': 'positive' if change_pct > 0 else 'negative' if change_pct < 0 else 'neutral'
                    })
                except (ValueError, KeyError) as e:
                    print(f"Error processing stock data: {str(e)}")
                    continue
            return top_stocks
    except Exception as e:
        print(f"Alpha Vantage failed: {str(e)}")

    # If Alpha Vantage fails, try yfinance
    try:
        import yfinance as yf
        # Get top gainers from Yahoo Finance
        tickers = yf.Tickers("^GSPC ^DJI ^IXIC ^RUT")  # Major indices
        top_stocks = []
        
        # Get components of S&P 500 and sort by daily gain
        sp500 = yf.Ticker("^GSPC")
        components = sp500.components
        if components is not None:
            for symbol, company in components.iterrows():
                try:
                    stock = yf.Ticker(symbol)
                    hist = stock.history(period="2d")
                    if len(hist) < 2:
                        continue
                    
                    prev_close = hist['Close'].iloc[-2]
                    current_price = hist['Close'].iloc[-1]
                    change_pct = ((current_price - prev_close) / prev_close) * 100
                    
                    day_info = hist.iloc[-1]
                    top_stocks.append({
                        'symbol': symbol,
                        'name': company['Name'],
                        'price': current_price,
                        'change': change_pct,
                        'low': day_info['Low'],
                        'high': day_info['High'],
                        'volume': day_info['Volume'],
                        'sentiment': 'positive' if change_pct > 0 else 'negative' if change_pct < 0 else 'neutral'
                    })
                except Exception as e:
                    print(f"Error processing {symbol}: {str(e)}")
                    continue
            
            # Sort by percentage change and take top 30
            top_stocks.sort(key=lambda x: x['change'], reverse=True)
            return top_stocks[:30]
    except Exception as e:
        print(f"Yahoo Finance failed: {str(e)}")
    # Fallback to hardcoded if API fails (expanded to 30 stocks)
    return  [
        {'symbol': 'AAPL', 'name': 'Apple Inc.', 'price': 175.32, 'change': 1.23, 'low': 172.50, 'high': 176.80, 'volume': 50000000, 'sentiment': 'positive'},
        {'symbol': 'MSFT', 'name': 'Microsoft', 'price': 310.65, 'change': -0.45, 'low': 308.20, 'high': 312.40, 'volume': 35000000, 'sentiment': 'neutral'},
        {'symbol': 'GOOGL', 'name': 'Alphabet', 'price': 135.78, 'change': 2.15, 'low': 133.50, 'high': 136.20, 'volume': 25000000, 'sentiment': 'positive'},
        {'symbol': 'AMZN', 'name': 'Amazon', 'price': 178.75, 'change': 0.89, 'low': 177.20, 'high': 179.80, 'volume': 30000000, 'sentiment': 'positive'},
        {'symbol': 'META', 'name': 'Meta', 'price': 485.38, 'change': -1.25, 'low': 482.50, 'high': 488.20, 'volume': 20000000, 'sentiment': 'negative'},
        {'symbol': 'TSLA', 'name': 'Tesla', 'price': 170.82, 'change': 3.45, 'low': 168.50, 'high': 172.30, 'volume': 40000000, 'sentiment': 'positive'},
        {'symbol': 'NVDA', 'name': 'NVIDIA', 'price': 950.02, 'change': 5.67, 'low': 940.50, 'high': 955.80, 'volume': 28000000, 'sentiment': 'positive'},
        {'symbol': 'JPM', 'name': 'JPMorgan', 'price': 198.34, 'change': -0.75, 'low': 197.20, 'high': 199.50, 'volume': 15000000, 'sentiment': 'neutral'},
        {'symbol': 'V', 'name': 'Visa', 'price': 275.91, 'change': 1.12, 'low': 274.30, 'high': 277.20, 'volume': 12000000, 'sentiment': 'positive'},
        {'symbol': 'WMT', 'name': 'Walmart', 'price': 60.45, 'change': -0.30, 'low': 60.20, 'high': 60.80, 'volume': 18000000, 'sentiment': 'neutral'},
        # Add 20 more stocks to reach 30...
        {'symbol': 'PG', 'name': 'Procter & Gamble', 'price': 145.67, 'change': 0.45, 'low': 144.80, 'high': 146.20, 'volume': 8000000, 'sentiment': 'positive'},
        {'symbol': 'DIS', 'name': 'Disney', 'price': 95.23, 'change': -1.20, 'low': 94.50, 'high': 96.80, 'volume': 12000000, 'sentiment': 'negative'},
        {'symbol': 'BAC', 'name': 'Bank of America', 'price': 35.67, 'change': 0.25, 'low': 35.20, 'high': 35.90, 'volume': 45000000, 'sentiment': 'neutral'},
        {'symbol': 'INTC', 'name': 'Intel', 'price': 42.15, 'change': -0.75, 'low': 41.80, 'high': 42.60, 'volume': 35000000, 'sentiment': 'negative'},
        {'symbol': 'CSCO', 'name': 'Cisco', 'price': 48.90, 'change': 0.30, 'low': 48.50, 'high': 49.20, 'volume': 18000000, 'sentiment': 'neutral'},
        {'symbol': 'KO', 'name': 'Coca-Cola', 'price': 58.34, 'change': 0.15, 'low': 58.10, 'high': 58.60, 'volume': 12000000, 'sentiment': 'neutral'},
        {'symbol': 'PEP', 'name': 'PepsiCo', 'price': 165.78, 'change': 0.45, 'low': 165.20, 'high': 166.40, 'volume': 5000000, 'sentiment': 'positive'},
        {'symbol': 'XOM', 'name': 'Exxon Mobil', 'price': 102.45, 'change': 1.25, 'low': 101.80, 'high': 103.20, 'volume': 15000000, 'sentiment': 'positive'},
        {'symbol': 'CVX', 'name': 'Chevron', 'price': 156.78, 'change': 0.90, 'low': 156.20, 'high': 157.40, 'volume': 8000000, 'sentiment': 'positive'},
        {'symbol': 'HD', 'name': 'Home Depot', 'price': 312.56, 'change': -0.75, 'low': 311.20, 'high': 313.80, 'volume': 4000000, 'sentiment': 'neutral'},
        {'symbol': 'MCD', 'name': 'McDonald\'s', 'price': 245.67, 'change': 0.35, 'low': 245.20, 'high': 246.30, 'volume': 3000000, 'sentiment': 'neutral'},
        {'symbol': 'NKE', 'name': 'Nike', 'price': 112.34, 'change': -1.20, 'low': 111.80, 'high': 113.20, 'volume': 7000000, 'sentiment': 'negative'},
        {'symbol': 'BA', 'name': 'Boeing', 'price': 205.78, 'change': 2.45, 'low': 204.20, 'high': 207.30, 'volume': 9000000, 'sentiment': 'positive'},
        {'symbol': 'GS', 'name': 'Goldman Sachs', 'price': 345.67, 'change': -0.90, 'low': 344.20, 'high': 346.80, 'volume': 3000000, 'sentiment': 'neutral'},
        {'symbol': 'IBM', 'name': 'IBM', 'price': 134.56, 'change': 0.25, 'low': 134.20, 'high': 135.20, 'volume': 5000000, 'sentiment': 'neutral'},
        {'symbol': 'ORCL', 'name': 'Oracle', 'price': 78.90, 'change': 0.45, 'low': 78.50, 'high': 79.30, 'volume': 10000000, 'sentiment': 'positive'},
        {'symbol': 'ABBV', 'name': 'AbbVie', 'price': 145.67, 'change': 0.35, 'low': 145.20, 'high': 146.20, 'volume': 5000000, 'sentiment': 'neutral'},
        {'symbol': 'T', 'name': 'AT&T', 'price': 18.90, 'change': -0.15, 'low': 18.80, 'high': 19.10, 'volume': 35000000, 'sentiment': 'neutral'},
        {'symbol': 'VZ', 'name': 'Verizon', 'price': 39.45, 'change': -0.25, 'low': 39.20, 'high': 39.70, 'volume': 20000000, 'sentiment': 'neutral'},
        {'symbol': 'UNH', 'name': 'UnitedHealth', 'price': 512.34, 'change': 1.25, 'low': 511.20, 'high': 513.80, 'volume': 2000000, 'sentiment': 'positive'}
    ]

def analyze_sentiment(text):
    """Simple sentiment analysis (positive/negative/neutral)"""
    text = text.lower()
    positive_words = ['buy', 'bullish', 'growth', 'positive', 'strong', 'outperform']
    negative_words = ['sell', 'bearish', 'decline', 'negative', 'weak', 'underperform']
    
    pos_count = sum(1 for word in positive_words if word in text)
    neg_count = sum(1 for word in negative_words if word in text)
    
    if pos_count > neg_count:
        return 'positive'
    elif neg_count > pos_count:
        return 'negative'
    return 'neutral'

@app.route('/')
def home():
    """Home page with top stocks and user watchlist"""
    bookmarked_stocks = session.get('bookmarked_stocks', [])
    top_stocks = get_top_stocks()
    positive_count = sum(1 for stock in top_stocks if stock.get('sentiment') == 'positive')
    negative_count = sum(1 for stock in top_stocks if stock.get('sentiment') == 'negative')
    
    return render_template('home.html',
                         top_stocks=top_stocks,
                         bookmarked_stocks=bookmarked_stocks,
                         positive_count=positive_count,
                         negative_count=negative_count,
                         now=datetime.now())

@app.route('/bookmark', methods=['POST', 'DELETE'])
def bookmark():
    """Handle stock bookmarking"""
    if request.method == 'POST':
        symbol = request.json.get('symbol')
        top_stocks = get_top_stocks()
        stock_details = next((s for s in top_stocks if s['symbol'] == symbol), None)
        
        if stock_details:
            bookmarks = session.get('bookmarked_stocks', [])
            if not any(s['symbol'] == symbol for s in bookmarks):
                bookmarks.append({
                    'symbol': symbol,
                    'price': stock_details['price'],
                    'change': stock_details['change'],
                    'last_analyzed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'trend': 'up' if stock_details['change'] > 0 else 'down' if stock_details['change'] < 0 else 'neutral'
                })
                session['bookmarked_stocks'] = bookmarks
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Stock not found'}), 404
    
    elif request.method == 'DELETE':
        symbol = request.json.get('symbol')
        bookmarks = session.get('bookmarked_stocks', [])
        session['bookmarked_stocks'] = [s for s in bookmarks if s['symbol'] != symbol]
        return jsonify({'success': True})

@app.route('/stock')
def stock_query():
    """Redirect to stock detail page"""
    symbol = request.args.get('symbol', '').upper()
    if symbol:
        return redirect(url_for('stock_detail', stock_symbol=symbol))
    return redirect(url_for('home'))

@app.route('/stock/<stock_symbol>')
def stock_detail(stock_symbol):
    """Stock detail page with analysis"""
    try:
        try:
            price_data = get_alpha_vantage_data(stock_symbol, "TIME_SERIES_INTRADAY", "1min")
            time_series = price_data.get('Time Series (1min)', {})
            latest_time = next(iter(time_series)) if time_series else None
            latest_price = time_series.get(latest_time, {}).get('1. open', 'N/A')

            history_data = get_alpha_vantage_data(stock_symbol, "TIME_SERIES_DAILY")
            time_series_daily = history_data.get('Time Series (Daily)', {})
            
            dates = list(time_series_daily.keys())[:30][::-1]
            prices = [float(time_series_daily[date]['4. close']) for date in dates]

            last_5_days = []
            for date in list(time_series_daily.keys())[:5]:
                day_data = time_series_daily[date]
                last_5_days.append({
                    'date': date,
                    'open': day_data['1. open'],
                    'high': day_data['2. high'],
                    'low': day_data['3. low'],
                    'close': day_data['4. close'],
                    'volume': day_data['5. volume']
                })
                
            source = "Alpha Vantage"
            
        except Exception as av_error:
            print(f"Alpha Vantage failed: {str(av_error)}")
            try:
                import yfinance as yf
                stock = yf.Ticker(stock_symbol)
                hist = stock.history(period="1mo")
                if hist.empty:
                    raise ValueError("No data from Yahoo Finance")
                
                dates = hist.index.strftime('%Y-%m-%d').tolist()[:30][::-1]
                prices = hist['Close'].tolist()[:30][::-1]
                
                last_5_days = []
                for i in range(min(5, len(hist))):
                    day = hist.iloc[i]
                    last_5_days.append({
                        'date': hist.index[i].strftime('%Y-%m-%d'),
                        'open': str(day['Open']),
                        'high': str(day['High']),
                        'low': str(day['Low']),
                        'close': str(day['Close']),
                        'volume': str(int(day['Volume']))
                    })
                    
                latest_price = latest['Close'].iloc[0] if not latest.empty else 'N/A'
                latest_time = latest.index[0].strftime('%Y-%m-%d %H:%M:%S') if not latest.empty else 'N/A'
                source = "Yahoo Finance"
            except Exception as yf_error:
                print(f"Yahoo Finance failed: {str(yf_error)}")
                raise ValueError("All data sources failed")

        # Get news and analyze sentiment
        news_url = f'https://newsapi.org/v2/everything?q={stock_symbol}&apiKey={NEWS_API_KEY}&language=en&sortBy=publishedAt'
        news_response = requests.get(news_url)
        news_data = news_response.json().get('articles', [])
        
        for article in news_data:
            title = article.get('title', '')
            description = article.get('description', '')
            content = f"{title}. {description}"
            article['sentiment'] = analyze_sentiment(content)
        
        sentiments = [article['sentiment'] for article in news_data if 'sentiment' in article]
        overall_sentiment = max(set(sentiments), key=sentiments.count) if sentiments else 'neutral'

        return render_template('stock.html',
                           stock_symbol=stock_symbol,
                           news_articles=news_data[:10],
                           latest_price=latest_price,
                           latest_time=latest_time,
                           dates=dates,
                           prices=prices,
                           last_5_days=last_5_days,
                           data_source=source,
                           overall_sentiment=overall_sentiment)

    except Exception as e:
        return render_template('error.html',
                            message=f"Failed to fetch data for {stock_symbol}: {str(e)}")

@app.route('/analyze', methods=['POST'])
def analyze():
    """Endpoint for analyzing stock sentiment"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        
        if not symbol:
            return jsonify({'error': 'Stock symbol is required'}), 400
        
        # Get news articles
        news_url = f'https://newsapi.org/v2/everything?q={symbol}&apiKey={NEWS_API_KEY}&language=en&sortBy=publishedAt'
        news_response = requests.get(news_url)
        news_data = news_response.json().get('articles', [])
        
        # Analyze sentiment
        analyzed_articles = []
        for article in news_data[:10]:
            title = article.get('title', '')
            description = article.get('description', '')
            content = f"{title}. {description}"
            sentiment = analyze_sentiment(content)
            
            analyzed_articles.append({
                'title': title,
                'description': description,
                'url': article.get('url', '#'),
                'source': article.get('source', {}).get('name', 'Unknown'),
                'publishedAt': article.get('publishedAt', ''),
                'sentiment': sentiment
            })
        
        # Calculate overall sentiment
        sentiments = [article['sentiment'] for article in analyzed_articles]
        overall_sentiment = max(set(sentiments), key=sentiments.count) if sentiments else 'neutral'
        
        return jsonify({
            'symbol': symbol,
            'articles': analyzed_articles,
            'overall_sentiment': overall_sentiment,
            'article_count': len(analyzed_articles)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

if __name__ == '__main__':
    app.run(debug=True)