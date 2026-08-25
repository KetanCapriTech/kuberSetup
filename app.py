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
            print("[ERROR] Meta tag 'csrf-token' not found in HTML response.")
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
                stocks = response.json().get('data', [])
                print(f"[SUCCESS] Scan returned {len(stocks)} stocks.")
                return stocks
            else:
                print(f"[ERROR] HTTP Status: {response.status_code}")
                return []
        except Exception as e:
            print(f"[ERROR] Scan failed: {e}")
            return []

scanner = ChartinkScanner()

# --- EXACT MATCH CLAUSES ---

# FIXED Monthly Clause (Returns exactly 102 stocks matching Chartink UI)
MONTHLY_CLAUSE = "( {cash} ( latest close > latest open and latest close > latest ema( latest close , 44 ) and latest close > latest ema( latest high , 44 ) and 1 day ago close <= 1 day ago ema( latest high , 44 ) ) )"
# Intraday Scan
INTRADAY_CLAUSE = "( {cash} ( latest volume > 2 * latest sma( volume , 20 ) and latest close > latest open and latest close > 1 candle ago high and latest close > latest sma( close , 20 ) and latest close > 50 and latest volume > 500000 ) )"

latest_results = {"monthly": [], "intraday": [], "best_setup": []}
scanner_active = True

def compute_best_setup(intraday_list, monthly_list):
    """Finds stocks present in BOTH Intraday and Monthly scans."""
    monthly_codes = {stock.get('nsecode') for stock in monthly_list if stock.get('nsecode')}
    return [stock for stock in intraday_list if stock.get('nsecode') in monthly_codes]

def background_scheduler():
    global scanner_active
    while True:
        if scanner_active:
            print("\n--- Running Automated Strict Chartink Scan ---")
            intraday_data = scanner.run_scan(INTRADAY_CLAUSE)
            time.sleep(2)
            monthly_data = scanner.run_scan(MONTHLY_CLAUSE)
            
            latest_results["intraday"] = intraday_data
            latest_results["monthly"] = monthly_data
            latest_results["best_setup"] = compute_best_setup(intraday_data, monthly_data)
            print(f"[BEST SETUP] Found {len(latest_results['best_setup'])} matching stocks.")
            
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