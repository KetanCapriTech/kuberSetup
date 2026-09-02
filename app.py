import time
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template

app = Flask(__name__)

# Pre-formatted Cookie string containing your session and XSRF tokens
PAID_SESSION_COOKIE = (
    "ci_session=eyJpdiI6IkJ4VXdMWUsxSlE2anI1NEJCaVdHNnc9PSIsInZhbHVlIjoiRGZWcCtPNXJCMDVFemFLajFxVVVsaFF1MFcwU3JmbFZ2S0RRT0dMV2V5cjR0S3JUSTBIZ3NLSkc0ZGtRaUIvbGw3Y05pZXl5TkJ2Z21aeEJXckdYZGt4aHVIaFJOU0U2OElBYjUrdkJpL0txcFlsWE9aUWVGeTJ5VkJ3WnpwM3giLCJtYWMiOiJiYWMyZGM5ZDkxODIwNTgxNDIzNWE3OWIxYzMwNjNmM2M2YzAyNTE4ZTUxYmRlNzRmNjZhY2U2NTI5NzkzZjIwIiwidGFnIjoiIn0%3D; "
    "XSRF-TOKEN=eyJpdiI6IjV1ZHh2UjFZblppemFtc2RzbGVwWXc9PSIsInZhbHVlIjoiQVk1NFc0S0xmSytiNkVyRy9LWWYwUXhzZU8vSTh5THF5UE13ajN3eWNvWjlrY3FjOUluN0pETFdra0s2RHZyU28zeFNXck13MGo3dExLNlk4SnM5MzVOaHd2Zi9XZHdvWXZDc3R6WnV5Y1JPdHRtdjZIdG5WcjBqelJkR2ZFNnYiLCJtYWMiOiIxZDA4NmM0MTE1NjJmYTc5YmExNzkwYTFlNGFiNDQ3YTE4YmJjYjAwODk1NDJkMTAwNGMyMjJhZjY0YjBiZjg1IiwidGFnIjoiIn0%3D"
)

class ChartinkScanner:
    def __init__(self, raw_cookie_string=""):
        self.session = requests.Session()
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://chartink.com',
            'Referer': 'https://chartink.com/screener/paid'
        }
        self.session.headers.update(self.headers)

        # Parse and inject cookies directly into the session jar
        if raw_cookie_string:
            for item in raw_cookie_string.split('; '):
                if '=' in item:
                    key, val = item.split('=', 1)
                    self.session.cookies.set(key.strip(), val.strip(), domain='chartink.com')

        self.screener_url = "https://chartink.com/screener/paid"
        self.process_url = "https://chartink.com/screener/process"

    def get_csrf_token(self):
        try:
            response = self.session.get(self.screener_url, timeout=20)
            soup = BeautifulSoup(response.text, 'html.parser')
            meta = soup.select_one("meta[name='csrf-token']")
            if meta and meta.get('content'):
                return meta['content']
            return None
        except Exception as e:
            print(f"[ERROR] CSRF token fetch failed: {e}")
            return None

    def run_scan(self, scan_clause):
        try:
            csrf_token = self.get_csrf_token()
            if not csrf_token:
                print("[ERROR] Missing CSRF Token. Session might be expired.")
                return []
            
            post_headers = {
                'X-CSRF-TOKEN': csrf_token
            }
            
            payload = {'scan_clause': scan_clause}
            response = self.session.post(self.process_url, data=payload, headers=post_headers, timeout=20)
            
            print(f"[DEBUG] Scan Status Code: {response.status_code}")
            
            if response.status_code == 200:
                return response.json().get('data', [])
            else:
                print(f"[ERROR] Failed with HTTP Status {response.status_code}")
                return []
        except Exception as e:
            print(f"[ERROR] Scan execution failed: {e}")
            return []

    def get_sector_advances(self):
        SECTOR_CLAUSE = "( {cash} ( latest sector advances % > 0 ) )"
        try:
            data = self.run_scan(SECTOR_CLAUSE)
            if data:
                return sorted(data, key=lambda x: float(x.get('per_chg', 0)), reverse=True)
            return []
        except Exception as e:
            print(f"[ERROR] Sector fetch failed: {e}")
            return []

# Initialize scanner with your session cookie
scanner = ChartinkScanner(PAID_SESSION_COOKIE)

# Define your scan clauses
MONTHLY_CLAUSE = "( {cash} ( latest close > latest open and latest close > latest ema( latest close , 44 ) and latest close > latest ema( latest high , 44 ) and 1 day ago close <= 1 day ago ema( latest high , 44 ) ) )"
INTRADAY_CLAUSE = "( {cash} ( latest volume > 2 * latest sma( volume , 20 ) and latest close > latest open and latest close > 1 candle ago high and latest close > latest sma( close , 20 ) and latest close > 50 and latest volume > 500000 ) )"
STRONG_VOL_HH_CLAUSE = "( {cash} ( latest close > latest open and latest high > 1 day ago high and 1 day ago high > 2 days ago high and latest volume > 1.5 * latest sma( volume , 20 ) and latest close > 50 ) )"
LIQUIDITY_HUNT_CLAUSE = "( {cash} ( 1 day ago volume > 2 * 1 day ago sma( volume , 20 ) and latest low <= 1 day ago low + ( 1 day ago high - 1 day ago low ) * 0.5 and latest close > latest open and latest volume > 100000 ) )"
NEAR_TRENDLINE_CLAUSE = "( {cash} ( latest close > latest sma( latest close , 50 ) and ( latest close - latest sma( latest close , 50 ) ) / latest sma( latest close , 50 ) < 0.05 and latest sma( latest close , 50 ) > 20 days ago sma( latest close , 50 ) and latest close < 5 days ago close and latest close > 50 and latest volume > 500000 and latest close * latest volume > 50000000 ) )"
MARKET_MOMENTUM_CLAUSE = "( {cash} ( latest market cap > 500 and latest close > latest sma( close , 20 ) and latest close > latest sma( close , 50 ) and latest sma( close , 20 ) > latest sma( close , 50 ) and latest rsi( 14 ) > 55 and latest rsi( 14 ) < 75 and latest volume > 1.5 * latest sma( volume , 5 ) and latest sma( volume , 5 ) > latest sma( volume , 20 ) and latest close > 1 day ago high and ( latest close - 1 day ago close ) / 1 day ago close * 100 > 0 and ( latest close - 1 day ago close ) / 1 day ago close * 100 < 8 and latest macd histogram( 26 , 12 , 9 ) > latest macd signal( 26 , 12 , 9 ) and ( latest max( high , 252 ) - latest close ) / latest max( high , 252 ) * 100 < 20 ) )"
BULL_CALL_CONFIRMED_CLAUSE = "( {cash} ( latest close > latest open and 1 candle ago close > 1 candle ago open and latest close > 1 candle ago close and latest low >= 1 candle ago low and latest high > 1 candle ago high and ( latest close - latest open ) > 1.3 * ( 1 candle ago close - 1 candle ago open ) and ( latest high - latest close ) < 0.2 * ( latest high - latest low ) and ( 1 candle ago high - 1 candle ago close ) < 0.3 * ( 1 candle ago high - 1 candle ago low ) and latest volume > 1.5 * 1 candle ago volume and latest close > latest sma( latest close , 20 ) and latest close > 1 day ago close and latest volume > 100000 and latest close > 50 ) )"

latest_results = {
    "monthly": [], 
    "intraday": [], 
    "best_setup": [], 
    "strong_vol_hh": [], 
    "liquidity_hunt": [],
    "near_trendline": [],
    "market_momentum": [],
    "bull_call_confirmed": [],
    "super_probability": []
}
latest_sector_data = []
scanner_active = True

def compute_best_setup(intraday_list, monthly_list):
    monthly_codes = {stock.get('nsecode') for stock in monthly_list if stock.get('nsecode')}
    return [stock for stock in intraday_list if stock.get('nsecode') in monthly_codes]

def compute_super_probability(all_scanner_lists):
    stock_occurrences = {}
    for strategy_name, stock_list in all_scanner_lists.items():
        if strategy_name in ["best_setup", "super_probability"]:
            continue
            
        for stock in stock_list:
            symbol = stock.get('nsecode')
            if not symbol:
                continue
                
            if symbol not in stock_occurrences:
                stock_occurrences[symbol] = {
                    "data": stock,
                    "matched_strategies": [strategy_name]
                }
            else:
                if strategy_name not in stock_occurrences[symbol]["matched_strategies"]:
                    stock_occurrences[symbol]["matched_strategies"].append(strategy_name)

    super_stocks = []
    for symbol, info in stock_occurrences.items():
        if len(info["matched_strategies"]) >= 2:
            stock_data = dict(info["data"])
            stock_data["matched_strategies"] = info["matched_strategies"]
            stock_data["match_count"] = len(info["matched_strategies"])
            super_stocks.append(stock_data)

    super_stocks.sort(key=lambda x: x["match_count"], reverse=True)
    return super_stocks

def background_scheduler():
    global scanner_active, latest_sector_data
    while True:
        if scanner_active:
            intraday_data = scanner.run_scan(INTRADAY_CLAUSE)
            time.sleep(1)
            monthly_data = scanner.run_scan(MONTHLY_CLAUSE)
            time.sleep(1)
            strong_vol_data = scanner.run_scan(STRONG_VOL_HH_CLAUSE)
            time.sleep(1)
            liq_hunt_data = scanner.run_scan(LIQUIDITY_HUNT_CLAUSE)
            time.sleep(1)
            near_trendline_data = scanner.run_scan(NEAR_TRENDLINE_CLAUSE)
            time.sleep(1)
            market_momentum_data = scanner.run_scan(MARKET_MOMENTUM_CLAUSE)
            time.sleep(1)
            bull_call_data = scanner.run_scan(BULL_CALL_CONFIRMED_CLAUSE)
            time.sleep(1)
            
            sectors = scanner.get_sector_advances()
            if sectors:
                latest_sector_data = sectors

            latest_results["intraday"] = intraday_data
            latest_results["monthly"] = monthly_data
            latest_results["best_setup"] = compute_best_setup(intraday_data, monthly_data)
            latest_results["strong_vol_hh"] = strong_vol_data
            latest_results["liquidity_hunt"] = liq_hunt_data
            latest_results["near_trendline"] = near_trendline_data
            latest_results["market_momentum"] = market_momentum_data
            latest_results["bull_call_confirmed"] = bull_call_data
            
            latest_results["super_probability"] = compute_super_probability(latest_results)
            
            # --- CONSOLE LOGGING ---
            print("\n================ [ SCAN RESULTS COUNT ] ================")
            print(f"Intraday            : {len(latest_results['intraday'])} stocks")
            print(f"Monthly             : {len(latest_results['monthly'])} stocks")
            print(f"Best Setup          : {len(latest_results['best_setup'])} stocks")
            print(f"Strong Vol HH       : {len(latest_results['strong_vol_hh'])} stocks")
            print(f"Liquidity Hunt      : {len(latest_results['liquidity_hunt'])} stocks")
            print(f"Near Trendline      : {len(latest_results['near_trendline'])} stocks")
            print(f"Market Momentum     : {len(latest_results['market_momentum'])} stocks")
            print(f"Bull Call Confirmed : {len(latest_results['bull_call_confirmed'])} stocks")
            print(f"Super Probability   : {len(latest_results['super_probability'])} stocks")
            print("========================================================\n")
            
        time.sleep(10)

# Start background thread
threading.Thread(target=background_scheduler, daemon=True).start()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/data")
def get_data():
    return jsonify({
        "results": latest_results,
        "is_paused": not scanner_active
    })

@app.route("/api/sector-advances")
def get_sector_advances_api():
    if not latest_sector_data:
        fallback = [
            {"sector": "Telecom-service", "value": 50.00},
            {"sector": "Bank", "value": 43.90},
            {"sector": "Auto", "value": 42.72},
            {"sector": "Healthcare", "value": 42.50},
            {"sector": "Financials", "value": 42.13}
        ]
        return jsonify(fallback)
    return jsonify(latest_sector_data)

@app.route("/api/toggle-scanner", methods=["POST"])
def toggle_scanner():
    global scanner_active
    scanner_active = not scanner_active
    return jsonify({"status": "active" if scanner_active else "paused"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)