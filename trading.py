from PyQt5.QtCore import QEventLoop, QTimer
from config import Config
import logging

logger = logging.getLogger("KiwoomTrading")

class Trading:
    def __init__(self, kiwoom_api):
        self.api = kiwoom_api
        self.tr_event_loop = QEventLoop()
        self.tr_data = {}

        self.api.ocx.OnReceiveTrData.connect(self._on_receive_tr_data)

    def get_balance_summary(self):
        try:
            if not self.api.connected:
                return {}

            logger.info("[trading.py] get_balance_summary")
            self.tr_data.pop('opw00018', None)
            self.api.ocx.SetInputValue("계좌번호", Config.ACCNO)
            self.api.ocx.SetInputValue("비밀번호", Config.ACCNO_PASSWORD)
            self.api.ocx.SetInputValue("비밀번호입력매체구분", "00")
            self.api.ocx.SetInputValue("조회구분", "2")
            self.api.ocx.CommRqData("opw00018_req", "opw00018", 0, "9200")
            self.tr_event_loop.exec_()
            return self.tr_data.get('opw00018', {})
        except Exception as e:
            logger.error(f"잔고조회 오류: {e}")
            return {}

    def get_available_cash(self):
        try:
            if not self.api.connected:
                return {}

            logger.info("[trading.py] get_available_cash")
            self.tr_data.pop('opw00001', None)
            self.api.ocx.SetInputValue("계좌번호", Config.ACCNO)
            self.api.ocx.SetInputValue("비밀번호", Config.ACCNO_PASSWORD)
            self.api.ocx.SetInputValue("비밀번호입력매체구분", "00")
            self.api.ocx.SetInputValue("조회구분", "2")
            self.api.ocx.CommRqData("opw00001_req", "opw00001", 0, "9201")
            self.tr_event_loop.exec_()
            return self.tr_data.get('opw00001', {})
        except Exception as e:
            logger.error(f"주문가능금액 조회 오류: {e}")
            return {}    

    def _on_receive_tr_data(self, screen_no, rqname, trcode, recordname, prev_next, data_len, error_code, message, splm_msg):
        try:
            if rqname == "opw00018_req":
                total = self.api.ocx.GetCommData(trcode, rqname, 0, "총매입금액")
                valuation = self.api.ocx.GetCommData(trcode, rqname, 0, "총평가금액")

                try:
                    total = total.lstrip("0") or "0"
                    valuation = valuation.lstrip("0") or "0"

                    total = int(total)
                    valuation = int(valuation)

                    total = f"{total:,}"
                    valuation = f"{valuation:,}"

                except:
                    total, valuation, available = 0, 0, 0

                self.tr_data["opw00018"] = {
                    "total_investment": total,
                    "total_valuation": valuation
                }

            elif rqname == "opw00001_req":
                available = self.api.ocx.GetCommData(trcode, rqname, 0, "주문가능금액")
                available = available.lstrip("0") or "0"
                available = int(available)
                available = f"{available:,}"

                self.tr_data["opw00001"] = {
                    "available_cash": available
                }
        finally:
            QTimer.singleShot(0, self.tr_event_loop.quit)
