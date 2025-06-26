from flask import Flask, render_template, jsonify
from threading import Thread
from kiwoom_app import KiwoomAppWrapper, request_queue, response_queue
import time

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

def run_flask():
    app.run(debug=False, use_reloader=False)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    kiwoom.run()
