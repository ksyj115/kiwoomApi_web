from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from kiwoom_api import KiwoomAPI
from trading import Trading
from queue import Queue

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