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
        self.app.setQuitOnLastWindowClosed(False)
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
            result = None
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
            elif isinstance(cmd, dict) and cmd.get("type") == "sell":
                result = self.trading.place_sell_order(cmd["code"], cmd["price"], cmd["qty"])
            elif cmd == "get_unfilled_orders":
                result = self.trading.get_unfilled_orders()
            elif isinstance(cmd, dict) and cmd.get("type") == "cancel_order":
                result = self.trading.cancel_order(
                    cmd.get("code"),
                    cmd.get("order_no"),
                    cmd.get("qty", 0),
                    cmd.get("order_type", ""),
                )
            elif cmd == "get_rsi_data":
                result = self.trading.analyze_rsi()
            elif isinstance(cmd, dict) and cmd.get("type") == "get_moving_average":
                result = self.trading.get_moving_average(cmd["code"])
            elif isinstance(cmd, dict) and cmd.get("type") == "detect_golden_cross":
                result = self.trading.detect_golden_cross(cmd["code"])
            elif isinstance(cmd, dict) and cmd.get("type") == "search_stock_by_name":
                result = self.trading.search_stock_by_name(cmd["keyword"])    
            elif cmd == "get_invest_weather":
                result = self.trading.ask_gpt_for_invest_weather()  
            elif cmd == "get_invest_micro":
                result = self.trading.ask_gpt_for_get_invest_micro()  
            elif cmd == "get_google_news_test":
                result = self.trading.get_google_news_test()

            response_queue.put(result)