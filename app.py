import time
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template

app = Flask(__name__)

# Pre-formatted Cookie string containing your session and XSRF tokens
PAID_SESSION_COOKIE = (
    "ci_session=eyJpdiI6IjBCMkJMUzRCakp0QnZLUHFlRlBHeEE9PSIsInZhbHVlIjoiSHdmUXlGdlpLY2RIaitlTCtJN0ZadzQwS1RZQ1QzMEE5VjlOQWozOEhENEpEbmc0dlN1Wm9FNUQzcmhlMTBGbyt3cEJ0UnJwYzFseVVldlJuTFZpZUxGQUlCeU1NOVVwbExiUng3dmNRdUVYUnFIbGJ2dnN6RDhBZ051QzhIcmciLCJtYWMiOiJiZGQyODAwODM4YTk0ZWU3NmExODBiM2M0MjFlNTQzM2U0OTU1YTM2ZmZlMjQ1ZTAxNDBjMmViNzA3NjEzYTBmIiwidGFnIjoiIn0%3D; "
    "XSRF-TOKEN=eyJpdiI6ImdSck0wenVYL0RNVHVnWllpR0hHV1E9PSIsInZhbHVlIjoiYmUxZFpxQXpSYnZHT09nOHBDSGQ1dEhTUWorYTYwaTVQMGxWalN4R3RMbWlmUEpsbGJ5OXpNNVJkeTZwUEl6Y2tCemIxakowbXRnelFmQ3l3WG5YUS84eW1Qdng1cEZNRklRd1ZyZ240bjdsZ1RiemV3aGQxMDZRdytwQ1h6bGsiLCJtYWMiOiJhZTJjZTc1MWQxYWM0YTY0NTNmMmI1NjcxNjJkZGY5NmM1YjQ4MDc4OTQ1YzFiZWUyNTdmODAzODIzODZhZTIwIiwidGFnIjoiIn0%3D%3D"
)

class ChartinkScanner:
    def __init__(self, raw_cookie_string=""):
        self.session = requests.Session()
        self.csrf_token = None
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://chartink.com',
            'Referer': 'https://chartink.com/screener/process'
        }
        self.session.headers.update(self.headers)

        if raw_cookie_string:
            for item in raw_cookie_string.split('; '):
                if '=' in item:
                    key, val = item.split('=', 1)
                    self.session.cookies.set(key.strip(), val.strip(), domain='chartink.com')

        self.screener_url = "https://chartink.com/screener/paid"
        self.process_url = "https://chartink.com/screener/process"

    def get_csrf_token(self, force_refresh=False):
        if not self.csrf_token or force_refresh:
            try:
                response = self.session.get(self.screener_url, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                meta = soup.select_one("meta[name='csrf-token']")
                if meta and meta.get('content'):
                    self.csrf_token = meta['content']
            except Exception as e:
                print(f"[ERROR] CSRF token fetch failed: {e}")
                self.csrf_token = None
        return self.csrf_token

    def run_scan(self, scan_clause):
        try:
            csrf_token = self.get_csrf_token()
            if not csrf_token:
                print("[ERROR] Missing CSRF Token.")
                return []
            
            post_headers = {'X-CSRF-TOKEN': csrf_token}
            payload = {'scan_clause': scan_clause.strip()}
            
            response = self.session.post(self.process_url, data=payload, headers=post_headers, timeout=10)
            
            if response.status_code in [419, 403]:
                csrf_token = self.get_csrf_token(force_refresh=True)
                post_headers = {'X-CSRF-TOKEN': csrf_token}
                response = self.session.post(self.process_url, data=payload, headers=post_headers, timeout=10)
            
            if response.status_code == 200:
                res_json = response.json()
                if 'data' not in res_json:
                    print(f"[CHARTINK WARNING]: Response missing data field -> {res_json}")
                return res_json.get('data', [])
            else:
                print(f"[ERROR] Failed with HTTP Status {response.status_code}: {response.text}")
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

scanner = ChartinkScanner(PAID_SESSION_COOKIE)

# EXISTING STRATEGY CLAUSES
MONTHLY_CLAUSE = "( {cash} ( latest close > latest open and latest close > latest ema( latest close , 44 ) and latest close > latest ema( latest high , 44 ) and 1 day ago close <= 1 day ago ema( latest high , 44 ) ) )"
INTRADAY_CLAUSE = "( {cash} ( latest volume > 2 * latest sma( volume , 20 ) and latest close > latest open and latest close > 1 candle ago high and latest close > latest sma( close , 20 ) and latest close > 50 and latest volume > 500000 ) )"
STRONG_VOL_HH_CLAUSE = "( {cash} ( latest close > latest open and latest high > 1 day ago high and 1 day ago high > 2 days ago high and latest volume > 1.5 * latest sma( volume , 20 ) and latest close > 50 ) )"
LIQUIDITY_HUNT_CLAUSE = "( {cash} ( 1 day ago volume > 2 * 1 day ago sma( volume , 20 ) and latest low <= 1 day ago low + ( 1 day ago high - 1 day ago low ) * 0.5 and latest close > latest open and latest volume > 100000 ) )"
NEAR_TRENDLINE_CLAUSE = "( {cash} ( latest close > latest sma( latest close , 50 ) and ( latest close - latest sma( latest close , 50 ) ) / latest sma( latest close , 50 ) < 0.05 and latest sma( latest close , 50 ) > 20 days ago sma( latest close , 50 ) and latest close < 5 days ago close and latest close > 50 and latest volume > 500000 and latest close * latest volume > 50000000 ) )"
MARKET_MOMENTUM_CLAUSE = "( {cash} ( latest market cap > 500 and latest close > latest sma( close , 20 ) and latest close > latest sma( close , 50 ) and latest sma( close , 20 ) > latest sma( close , 50 ) and latest rsi( 14 ) > 55 and latest rsi( 14 ) < 75 and latest volume > 1.5 * latest sma( volume , 5 ) and latest sma( volume , 5 ) > latest sma( volume , 20 ) and latest close > 1 day ago high and ( latest close - 1 day ago close ) / 1 day ago close * 100 > 0 and ( latest close - 1 day ago close ) / 1 day ago close * 100 < 8 and latest macd histogram( 26 , 12 , 9 ) > latest macd signal( 26 , 12 , 9 ) and ( latest max( high , 252 ) - latest close ) / latest max( high , 252 ) * 100 < 20 ) )"
BULL_CALL_CONFIRMED_CLAUSE = "( {cash} ( latest close > latest open and 1 candle ago close > 1 candle ago open and latest close > 1 candle ago close and latest low >= 1 candle ago low and latest high > 1 candle ago high and ( latest close - latest open ) > 1.3 * ( 1 candle ago close - 1 candle ago open ) and ( latest high - latest close ) < 0.2 * ( latest high - latest low ) and ( 1 candle ago high - 1 candle ago close ) < 0.3 * ( 1 candle ago high - 1 candle ago low ) and latest volume > 1.5 * 1 candle ago volume and latest close > latest sma( latest close , 20 ) and latest close > 1 day ago close and latest volume > 100000 and latest close > 50 ) )"
THREE_STEP_CANDLE_CLAUSE = "( {cash} ( latest close > latest open and 1 candle ago close > 1 candle ago open and 2 candles ago close > 2 candles ago open and latest high > 1 candle ago high and 1 candle ago high > 2 candles ago high and latest low > 1 candle ago low and 1 candle ago low > 2 candles ago low and ( latest close - latest open ) > 0.6 * ( latest high - latest low ) and ( 1 candle ago close - 1 candle ago open ) > 0.6 * ( 1 candle ago high - 1 candle ago low ) and ( 2 candles ago close - 2 candles ago open ) > 0.6 * ( 2 candles ago high - 2 candles ago low ) ) )"

THREE_MIN_CLAUSE_CONFIRMATION = (
    "( {cash} ( "
    "[ 0 ] 3 minute close > [ 0 ] 3 minute open and "
    "[ 1 ] 3 minute close > [ 1 ] 3 minute open and "
    "[ 0 ] 3 minute close > [ 1 ] 3 minute close and "
    "[ 0 ] 3 minute low >= [ 1 ] 3 minute low and "
    "[ 0 ] 3 minute high > [ 1 ] 3 minute high and "
    "( [ 0 ] 3 minute close - [ 0 ] 3 minute open ) > 1.3 * ( [ 1 ] 3 minute close - [ 1 ] 3 minute open ) and "
    "( [ 0 ] 3 minute high - [ 0 ] 3 minute close ) < 0.2 * ( [ 0 ] 3 minute high - [ 0 ] 3 minute low ) and "
    "[ 0 ] 3 minute volume > 1.5 * [ 1 ] 3 minute volume and "
    "[ 0 ] 3 minute close > sma( [ 0 ] 3 minute close , 20 ) and "
    "[ 0 ] 3 minute volume > 10000 and "
    "[ 0 ] 3 minute close > 50 "
    ") )"
)

INSTITUTIONAL_ROCKET_CLAUSE = (
    "( {cash} ( "
    "latest close > latest open and "
    "latest close > latest ema( close , 44 ) and "
    "latest close > latest ema( high , 44 ) and "
    "latest close > latest vwap and "
    "latest volume > 3 * latest sma( volume , 20 ) and "
    "latest rsi( 14 ) >= 60 and "
    "latest rsi( 14 ) <= 80 and "
    "( latest high - latest close ) < 0.15 * ( latest high - latest low ) and "
    "latest close > 50 and "
    "latest volume > 200000 "
    ") )"
)

LIQUIDITY_SWEEP_SELL_CLAUSE = (
    "( {cash} ( "
    "[ 0 ] 5 minute High > 1 day ago High and "
    "[ 0 ] 5 minute High > [ -1 ] 5 minute High and "
    "[ 0 ] 5 minute Close < [ 0 ] 5 minute Open and "
    "( [ 0 ] 5 minute High - [ 0 ] 5 minute Close ) >= 0.55 * ( [ 0 ] 5 minute High - [ 0 ] 5 minute Low ) and "
    "[ 0 ] 5 minute Close < [ 0 ] 5 minute VWAP and "
    "[ 0 ] 5 minute Volume > [ 0 ] 5 minute sma( volume , 20 ) * 2.5 and "
    "[ 0 ] 5 minute Volume > 50000 "
    ") )"
)

LIQUIDITY_SWEEP_BUY_STRONG_CLAUSE = (
    "( {cash} ( "
    "[ 0 ] 3 minute Low < 1 day ago Low and "
    "[ 0 ] 3 minute Low < [ -1 ] 3 minute Low and "
    "[ 0 ] 3 minute Close > [ 0 ] 3 minute Open and "
    "( [ 0 ] 3 minute Close - [ 0 ] 3 minute Low ) >= 0.55 * ( [ 0 ] 3 minute High - [ 0 ] 3 minute Low ) and "
    "[ 0 ] 3 minute Close > [ 0 ] 3 minute VWAP and "
    "[ 0 ] 3 minute Volume > [ 0 ] 3 minute sma( volume , 20 ) * 2.5 and "
    "[ 0 ] 3 minute Volume > 30000 "
    ") )"
)

# NEW ADDITION: 1-HOUR BEARISH SHOOTING STAR REJECTION (44 CLOSE & 44 HIGH EMA TOUCH)
SHOOTING_STAR_BEARISH_CLAUSE = (
    "( {cash} ( "
    "[ 0 ] 1 hour close < [ 0 ] 1 hour open and "
    "[ 0 ] 1 hour high >= [ 0 ] 1 hour ema( high , 44 ) and "
    "[ 0 ] 1 hour close < [ 0 ] 1 hour ema( close , 44 ) and "
    "[ 0 ] 1 hour close < [ 0 ] 1 hour ema( high , 44 ) and "
    "( [ 0 ] 1 hour open - [ 0 ] 1 hour close ) <= 0.35 * ( [ 0 ] 1 hour high - [ 0 ] 1 hour low ) and "
    "( [ 0 ] 1 hour high - [ 0 ] 1 hour open ) >= 0.55 * ( [ 0 ] 1 hour high - [ 0 ] 1 hour low ) and "
    "( [ 0 ] 1 hour close - [ 0 ] 1 hour low ) <= 0.15 * ( [ 0 ] 1 hour high - [ 0 ] 1 hour low ) and "
    "[ 0 ] 1 hour volume > 100000 and "
    "[ 0 ] 1 hour close > 50 "
    ") )"
)

latest_results = {
    "institutional_rocket": [],
    "three_min_confirmation": [],
    "three_step_candle": [],
    "liquidity_sweep_sell": [],
    "liquidity_sweep_buy": [],
    "shooting_star_bearish": [],  # NEW ADDITION
    "intraday": [], 
    "monthly": [], 
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
            rocket_data = scanner.run_scan(INSTITUTIONAL_ROCKET_CLAUSE)
            three_min_data = scanner.run_scan(THREE_MIN_CLAUSE_CONFIRMATION)
            three_step_data = scanner.run_scan(THREE_STEP_CANDLE_CLAUSE)
            liq_sweep_sell_data = scanner.run_scan(LIQUIDITY_SWEEP_SELL_CLAUSE)
            liq_sweep_buy_data = scanner.run_scan(LIQUIDITY_SWEEP_BUY_STRONG_CLAUSE)
            shooting_star_data = scanner.run_scan(SHOOTING_STAR_BEARISH_CLAUSE) # NEW
            bull_call_data = scanner.run_scan(BULL_CALL_CONFIRMED_CLAUSE)
            intraday_data = scanner.run_scan(INTRADAY_CLAUSE)
            monthly_data = scanner.run_scan(MONTHLY_CLAUSE)
            strong_vol_data = scanner.run_scan(STRONG_VOL_HH_CLAUSE)
            liq_hunt_data = scanner.run_scan(LIQUIDITY_HUNT_CLAUSE)
            near_trendline_data = scanner.run_scan(NEAR_TRENDLINE_CLAUSE)
            market_momentum_data = scanner.run_scan(MARKET_MOMENTUM_CLAUSE)
            
            sectors = scanner.get_sector_advances()
            if sectors:
                latest_sector_data = sectors

            latest_results["institutional_rocket"] = rocket_data
            latest_results["three_min_confirmation"] = three_min_data
            latest_results["three_step_candle"] = three_step_data
            latest_results["liquidity_sweep_sell"] = liq_sweep_sell_data
            latest_results["liquidity_sweep_buy"] = liq_sweep_buy_data
            latest_results["shooting_star_bearish"] = shooting_star_data # NEW
            latest_results["bull_call_confirmed"] = bull_call_data
            latest_results["intraday"] = intraday_data
            latest_results["monthly"] = monthly_data
            latest_results["best_setup"] = compute_best_setup(intraday_data, monthly_data)
            latest_results["strong_vol_hh"] = strong_vol_data
            latest_results["liquidity_hunt"] = liq_hunt_data
            latest_results["near_trendline"] = near_trendline_data
            latest_results["market_momentum"] = market_momentum_data
            
            latest_results["super_probability"] = compute_super_probability(latest_results)
            
            print("\n================ [ SCAN RESULTS COUNT ] ================")
            print(f"Institutional Rocket : {len(latest_results['institutional_rocket'])} stocks")
            print(f"3 Min Confirmation   : {len(latest_results['three_min_confirmation'])} stocks")
            print(f"3 Step Candle        : {len(latest_results['three_step_candle'])} stocks")
            print(f"Sweep Sell (9:20 AM) : {len(latest_results['liquidity_sweep_sell'])} stocks")
            print(f"Sweep Buy (9:20-9:30): {len(latest_results['liquidity_sweep_buy'])} stocks")
            print(f"Shooting Star 44 EMA : {len(latest_results['shooting_star_bearish'])} stocks")
            print(f"Bull Call Confirmed  : {len(latest_results['bull_call_confirmed'])} stocks")
            print(f"Intraday             : {len(latest_results['intraday'])} stocks")
            print(f"Monthly              : {len(latest_results['monthly'])} stocks")
            print(f"Best Setup           : {len(latest_results['best_setup'])} stocks")
            print(f"Super Probability    : {len(latest_results['super_probability'])} stocks")
            print("========================================================\n")
            
        time.sleep(3)

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