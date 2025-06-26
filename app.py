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

def run_flask():
    app.run(debug=False, use_reloader=False)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    kiwoom.run()
