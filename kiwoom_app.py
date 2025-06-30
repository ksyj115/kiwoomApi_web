from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from kiwoom_api import KiwoomAPI
from trading import Trading
from queue import Queue
from logger import logger

request_queue = Queue()
response_queue = Queue()

class KiwoomAppWrapper:
    def __init__(self):
        self.app = QApplication([])
        self.api = KiwoomAPI()
        self.trading = Trading(self.api)
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_requests)
        self.timer.start(500)

    def run(self):
        self.api.login()
        self.app.exec_()

    def process_requests(self):
        if not request_queue.empty():
            cmd = request_queue.get()
            if cmd == "get_account":
                result = self.trading.get_balance_summary()
                response_queue.put(result)
            elif cmd == "get_available_cash":
                result = self.trading.get_available_cash()
                response_queue.put(result)
            elif cmd == "get_holdings":
                result = self.trading.get_holdings()
                response_queue.put(result)
            elif cmd == "volume_leaders":
                result = self.trading.get_volume_leaders()
                response_queue.put(result)
            elif isinstance(cmd, dict) and cmd.get("type") == "buy":
                result = self.trading.place_order(cmd["code"], cmd["price"], cmd["qty"])
                response_queue.put(result)
            elif isinstance(cmd, dict) and cmd.get("type") == "sell":
                result = self.trading.place_sell_order(cmd["code"], cmd["price"], cmd["qty"])
                response_queue.put(result)
            elif cmd == "get_unfilled_orders":
                result = self.trading.get_unfilled_orders()
                response_queue.put(result)
            elif cmd == "get_rsi_data":
                result = self.trading.analyze_rsi()
                response_queue.put(result)
            elif cmd == "get_moving_average":
                result = self.trading.get_moving_average()

            # response_queue.put(result)