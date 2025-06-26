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
            elif cmd == "get_available_cash":
                result = self.trading.get_available_cash()
            elif cmd == "get_holdings":
                result = self.trading.get_holdings()
            elif cmd == "volume_leaders":
                result = self.trading.get_volume_leaders()
            elif isinstance(cmd, dict) and cmd.get("type") == "buy":
                result = self.trading.place_order(cmd["code"], cmd["price"], cmd["qty"])

            response_queue.put(result)