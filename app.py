from flask import Flask, render_template, jsonify, request
from threading import Thread
from kiwoom_app import KiwoomAppWrapper, request_queue, response_queue
import time
from logger import logger

app = Flask(__name__)
kiwoom = KiwoomAppWrapper()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/index2")
def index2():
    return render_template("index2.html")

@app.route("/api/account")
def get_account():
    request_queue.put("get_account")  # 요청 큐에 명령 전달

    timeout = 10
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            result = response_queue.get()
            return jsonify(result)
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route("/api/available_cash")
def get_available_cash():
    request_queue.put("get_available_cash")  # 요청 큐에 명령 전달

    timeout = 10
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            result = response_queue.get()
            return jsonify(result)
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route("/api/holdings")
def get_holdings():
    request_queue.put("get_holdings")  # 요청 큐에 명령 전달

    timeout = 10
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            result = response_queue.get()
            return jsonify(result)
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route("/api/volume-leaders")
def get_volume_leaders():
    request_queue.put("volume_leaders")
    timeout = 10
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            result = response_queue.get()
            return jsonify(result)
        time.sleep(0.1)
        waited += 0.1
    return jsonify({"error": "timeout"})

@app.route("/api/buy", methods=["POST"])
def place_buy_order():
    data = request.json
    code = data.get("code")
    price = data.get("price")
    qty = data.get("qty")

    request_queue.put({
        "type": "buy",
        "code": code,
        "price": price,
        "qty": qty
    })

    timeout = 10
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            result = response_queue.get()
            return jsonify(result)
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route("/api/sell", methods=["POST"])
def place_sell_order():
    data = request.json
    code = data.get("code")
    price = data.get("price")
    qty = data.get("qty")

    request_queue.put({
        "type": "sell",
        "code": code,
        "price": price,
        "qty": qty
    })

    timeout = 10
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            result = response_queue.get()
            return jsonify(result)
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route("/api/unfilled_orders")
def get_unfilled_orders():
    request_queue.put("get_unfilled_orders")
    waited = 0
    while waited < 10:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1
    return jsonify({"error": "timeout"})

@app.route('/get-rsi-data', methods=['POST'])
def do_something():
    request_queue.put("get_rsi_data")
    waited = 0
    while waited < 10:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1
    return jsonify({"error": "timeout"})

@app.route('/get-moving-average', methods=['POST'])
def getMovingAverage():
    request_queue.put("get_moving_average")
    waited = 0
    while waited < 10:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1

    # 아무 응답도 보내지 않고 종료 (void처럼)
    return '', 204  # 또는 return '', 200

@app.route('/api/chart-data')
def chart_data():
    request_queue.put('get_stock_data')
    waited = 0
    while waited < 10:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1
    return jsonify({'error': 'timeout'})

@app.route('/detect-golden-cross', methods=['POST'])
def detect_golden_cross():
    data = request.json
    code = data.get("code")

    request_queue.put({
        "type": "detect_golden_cross",
        "code": code
    })

    timeout = 10
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            result = response_queue.get()
            return jsonify(result)
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route('/api/search-stock', methods=["POST"])
def api_search_stock():
    data = request.json
    keyword = data.get("keyword", "").strip()

    if not keyword:
        return jsonify([])

    request_queue.put({
        "type": "search_stock_by_name",
        "keyword": keyword
    })

    timeout = 10
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

def run_flask():
    app.run(debug=False, use_reloader=False)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    kiwoom.run()
