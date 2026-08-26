import time
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template

app = Flask(__name__)

class ChartinkScanner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://chartink.com',
            'Referer': 'https://chartink.com/screener/'
        })
        self.screener_url = "https://chartink.com/screener/"
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
            print(f"[ERROR] CSRF token failed: {e}")
            return None

    def run_scan(self, scan_clause):
        try:
            csrf_token = self.get_csrf_token()
            if not csrf_token:
                return []
            
            headers = {'X-CSRF-TOKEN': csrf_token}
            payload = {'scan_clause': scan_clause}
            response = self.session.post(self.process_url, data=payload, headers=headers, timeout=20)
            
            if response.status_code == 200:
                return response.json().get('data', [])
            return []
        except Exception as e:
            print(f"[ERROR] Scan failed: {e}")
            return []

scanner = ChartinkScanner()

MONTHLY_CLAUSE = "( {cash} ( latest close > latest open and latest close > latest ema( latest close , 44 ) and latest close > latest ema( latest high , 44 ) and 1 day ago close <= 1 day ago ema( latest high , 44 ) ) )"
INTRADAY_CLAUSE = "( {cash} ( latest volume > 2 * latest sma( volume , 20 ) and latest close > latest open and latest close > 1 candle ago high and latest close > latest sma( close , 20 ) and latest close > 50 and latest volume > 500000 ) )"
STRONG_VOL_HH_CLAUSE = "( {cash} ( latest close > latest open and latest high > 1 day ago high and 1 day ago high > 2 days ago high and latest volume > 1.5 * latest sma( volume , 20 ) and latest close > 50 ) )"
LIQUIDITY_HUNT_CLAUSE = "( {cash} ( 1 day ago volume > 2 * 1 day ago sma( volume , 20 ) and latest low <= 1 day ago low + ( 1 day ago high - 1 day ago low ) * 0.5 and latest close > latest open and latest volume > 100000 ) )"
NEAR_TRENDLINE_CLAUSE = "( {cash} ( latest close > latest sma( latest close , 50 ) and ( latest close - latest sma( latest close , 50 ) ) / latest sma( latest close , 50 ) < 0.05 and latest sma( latest close , 50 ) > 20 days ago sma( latest close , 50 ) and latest close < 5 days ago close and latest close > 50 and latest volume > 500000 and latest close * latest volume > 50000000 ) )"
MARKET_MOMENTUM_CLAUSE = "( {cash} ( latest market cap > 500 and latest close > latest sma( close , 20 ) and latest close > latest sma( close , 50 ) and latest sma( close , 20 ) > latest sma( close , 50 ) and latest rsi( 14 ) > 55 and latest rsi( 14 ) < 75 and latest volume > 1.5 * latest sma( volume , 5 ) and latest sma( volume , 5 ) > latest sma( volume , 20 ) and latest close > 1 day ago high and ( latest close - 1 day ago close ) / 1 day ago close * 100 > 0 and ( latest close - 1 day ago close ) / 1 day ago close * 100 < 8 and latest macd histogram( 26 , 12 , 9 ) > latest macd signal( 26 , 12 , 9 ) and ( latest max( high , 252 ) - latest close ) / latest max( high , 252 ) * 100 < 20 ) )"

latest_results = {
    "monthly": [], 
    "intraday": [], 
    "best_setup": [], 
    "strong_vol_hh": [], 
    "liquidity_hunt": [],
    "near_trendline": [],
    "market_momentum": [],
    "super_probability": []
}
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
    global scanner_active
    while True:
        if scanner_active:
            intraday_data = scanner.run_scan(INTRADAY_CLAUSE)
            time.sleep(1.2)
            monthly_data = scanner.run_scan(MONTHLY_CLAUSE)
            time.sleep(1.2)
            strong_vol_data = scanner.run_scan(STRONG_VOL_HH_CLAUSE)
            time.sleep(1.2)
            liq_hunt_data = scanner.run_scan(LIQUIDITY_HUNT_CLAUSE)
            time.sleep(1.2)
            near_trendline_data = scanner.run_scan(NEAR_TRENDLINE_CLAUSE)
            time.sleep(1.2)
            market_momentum_data = scanner.run_scan(MARKET_MOMENTUM_CLAUSE)
            
            latest_results["intraday"] = intraday_data
            latest_results["monthly"] = monthly_data
            latest_results["best_setup"] = compute_best_setup(intraday_data, monthly_data)
            latest_results["strong_vol_hh"] = strong_vol_data
            latest_results["liquidity_hunt"] = liq_hunt_data
            latest_results["near_trendline"] = near_trendline_data
            latest_results["market_momentum"] = market_momentum_data
            
            latest_results["super_probability"] = compute_super_probability(latest_results)
            
        time.sleep(60)

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

@app.route("/api/toggle-scanner", methods=["POST"])
def toggle_scanner():
    global scanner_active
    scanner_active = not scanner_active
    return jsonify({"status": "active" if scanner_active else "paused"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)