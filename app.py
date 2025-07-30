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

@app.route("/index3")
def index3():
    return render_template("index3.html")

@app.route("/index4")
def index4():
    return render_template("index4.html")

@app.route("/index5")
def index5():
    return render_template("index5.html")

@app.route("/api/account")
def get_account():
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

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
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

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
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

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
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

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
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

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
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

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
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

    request_queue.put("get_unfilled_orders")
    waited = 0
    while waited < 10:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1
    return jsonify({"error": "timeout"})

@app.route("/api/cancel_order", methods=["POST"])
def cancel_order():
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

    data = request.json
    order_no = data.get("order_no")
    code = data.get("code")
    qty = data.get("qty")
    order_type = data.get("order_type", "")

    request_queue.put({
        "type": "cancel_order",
        "order_no": order_no,
        "code": code,
        "qty": qty,
        "order_type": order_type
    })

    waited = 0
    while waited < 10:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route('/get-rsi-data', methods=['POST'])
def do_something():
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

    data = request.json
    rsiCode = data.get("rsiCode")

    request_queue.put({
        "type": "get_rsi_data",
        "rsiCode": rsiCode
    })
    waited = 0
    while waited < 30:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1
    return jsonify({"error": "timeout"})

@app.route('/get-moving-average', methods=['POST'])
def getMovingAverage():
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

    data = request.json
    code = data.get("code")
    history_date = data.get("history_date")
    history_code = data.get("history_code")
    history_price = data.get("history_price")
    history_qty = data.get("history_qty")
    history_flag = data.get("history_flag")

    request_queue.put({
        "type": "get_moving_average",
        "code": code,
        "history_date": history_date,
        "history_code": history_code,
        "history_price": history_price,
        "history_qty": history_qty,
        "history_flag": history_flag
    })

    timeout = 30
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            result = response_queue.get()
            return jsonify(result)
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route('/detect-golden-cross', methods=['POST'])
def detect_golden_cross():
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

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

@app.route('/detect-dead-cross', methods=['POST'])
def detect_dead_cross():
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

    data = request.json
    code = data.get("code")

    request_queue.put({
        "type": "detect_dead_cross",
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
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

    data = request.json
    keyword = data.get("keyword", "").strip()

    if not keyword:
        return jsonify([])

    request_queue.put({
        "type": "search_stock_by_name",
        "keyword": keyword
    })

    timeout = 30
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route('/get_invest_weather')
def get_weather():
    request_queue.put("get_invest_weather")
    waited = 0
    timeout = 60  # ✅ 최대 60초까지 기다리도록 설정

    while waited < timeout:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route('/get_google_news_test')
def get_google_news_test():
    while not response_queue.empty():
        response_queue.get()  # 남아있는 응답 버림

    request_queue.put("get_google_news_test")
    waited = 0
    while waited < 60:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1
    return jsonify({"error": "timeout"})

@app.route("/api/macd", methods=["POST"])
def get_macd():
    while not response_queue.empty():
        response_queue.get()

    data = request.json
    code = data.get("code")

    request_queue.put({
        "type": "get_macd_data",
        "macdCode": code
    })

    timeout = 10
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route("/api/stochastic", methods=["POST"])
def get_stochastic():
    while not response_queue.empty():
        response_queue.get()

    data = request.json
    code = data.get("code")

    request_queue.put({
        "type": "get_stochastic_data",
        "stochasticCode": code
    })

    timeout = 10
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route("/api/stochastic2", methods=["POST"])
def get_stochastic2():
    while not response_queue.empty():
        response_queue.get()

    data = request.json
    code = data.get("code")

    request_queue.put({
        "type": "get_stochastic_data2",
        "stochasticCode": code
    })

    timeout = 10
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            return jsonify(response_queue.get())
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

@app.route('/api/save-volume', methods=['POST'])
def save_volume():
    while not response_queue.empty():
        response_queue.get()

    data = request.json
    code = data.get('code', [])

    request_queue.put({
        'type': 'save_volume_data',
        'code': code
    })

    timeout = 30
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            result = response_queue.get()
            return jsonify(result)
        time.sleep(0.1)
        waited += 0.1
    return jsonify({'error': 'timeout'})

@app.route('/api/volume-search', methods=['POST'])
def volume_search():
    while not response_queue.empty():
        response_queue.get()

    data = request.json
    code = data.get("code")
    name = data.get("name")

    request_queue.put({
        "type": "volume_search",
        "code": code,
        "name": name
    })

    timeout = 30
    waited = 0
    while waited < timeout:
        if not response_queue.empty():
            result = response_queue.get()
            return jsonify(result)
        time.sleep(0.1)
        waited += 0.1

    return jsonify({"error": "timeout"})

def run_flask():
    app.run(debug=False, use_reloader=False)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    kiwoom.run()
