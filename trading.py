from PyQt5.QtCore import QEventLoop, QTimer
from config import Config
import logging
from logger import logger
import pandas as pd
import matplotlib.pyplot as plt
from pykiwoom.kiwoom import Kiwoom
import time
from datetime import datetime

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

    def get_holdings(self):
        """보유 종목 조회"""
        try:
            if not self.api.connected:
                return []

            logger.info("[trading.py] get_holdings")
            self.tr_data.pop('opw00018', None)
            self.api.ocx.SetInputValue("계좌번호", Config.ACCNO)
            self.api.ocx.SetInputValue("비밀번호", Config.ACCNO_PASSWORD)
            self.api.ocx.SetInputValue("비밀번호입력매체구분", "00")
            self.api.ocx.SetInputValue("조회구분", "2")
            self.api.ocx.CommRqData("opw00018_holdings_req", "opw00018", 0, "9202")
            self.tr_event_loop.exec_()
            return self.tr_data.get('opw00018', [])
        except Exception as e:
            logger.error(f"보유종목 조회 오류: {e}")
            return []

    def get_volume_leaders(self):
        try:
            self.tr_data.pop("OPT10030", None)
            self.api.ocx.SetInputValue("시장구분", "000")  # 전체 시장
            self.api.ocx.SetInputValue("정렬구분", "1")    # 거래량순
            self.api.ocx.SetInputValue("관리종목포함", "1")
            self.api.ocx.SetInputValue("신용구분", "0")
            self.api.ocx.CommRqData("volume_rank_req", "OPT10030", 0, "4001")
            self.tr_event_loop.exec_()
            return self.tr_data.get("OPT10030", {"stocks": []})
        except Exception as e:
            return {"error": str(e)}

    def place_order(self, code, price, qty):
        try:
            logger.info(f"[매수 요청] {code} | {price}원 | {qty}주")
            self.api.ocx.SendOrder(
                "매수주문",  # 주문종류
                "0101",      # 화면번호
                Config.ACCNO,  # 계좌번호
                1,  # 주문타입 (1:신규매수)
                code,
                qty,
                price,
                "00",  # "00": 지정가, "03": 시장가
                ""
            )
            return {"message": "✅ 매수 주문 요청 완료"}
        except Exception as e:
            logger.log_error("BUY_ORDER", str(e))
            return {"error": str(e)}

    def place_sell_order(self, code, price, qty):
        try:
            logger.info(f"[매도 요청] {code} | {price}원 | {qty}주")
            self.api.ocx.SendOrder(
                "매도주문",  # 주문종류
                "0102",      # 화면번호
                Config.ACCNO,  # 계좌번호
                2,  # 주문타입 (2:신규매도)
                code,
                qty,
                price,
                "00",  # "00": 지정가, "03": 시장가
                ""
            )
            return {"message": "✅ 매도 주문 요청 완료"}
        except Exception as e:
            logger.log_error("SELL_ORDER", str(e))
            return {"error": str(e)}

    def get_unfilled_orders(self):
        """미체결 주문 조회"""
        if not self.api.connected:
            return {"error": "API 미연결"}

        logger.info("[trading.py] get_unfilled_orders")
        self.tr_data.pop("opt10075", None)
        self.api.ocx.SetInputValue("계좌번호", Config.ACCNO)
        self.api.ocx.SetInputValue("전체", "0") # 전체 계좌
        self.api.ocx.SetInputValue("매매구분", "0") # 전체
        self.api.ocx.SetInputValue("체결구분", "1") # 미체결만
        self.api.ocx.CommRqData("unfilled_orders_req", "opt10075", 0, "9000")
        self.tr_event_loop.exec_()
        return self.tr_data.get("opt10075", {"orders": []})

    def get_close_prices(self, code="005930", count=250):
        today = datetime.today().strftime('%Y%m%d')
        df = self.kiwoom.block_request("opt10081",
                                    종목코드=code,
                                    기준일자=today,
                                    수정주가구분=1,
                                    output="주식일봉차트조회",
                                    next=0)
        close_prices = df['현재가'].astype(int).tolist()
        return close_prices[:count]

    def calculate_rsi(self, prices, period=14, method='ema'):
        close = pd.Series(prices)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        if method == 'sma':
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()
        elif method == 'ema':
            avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        else:
            raise ValueError("method must be 'sma' or 'ema'")

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def analyze_rsi(self):
        self.kiwoom = Kiwoom()
        self.kiwoom.CommConnect()

        prices = self.get_close_prices()

        rsi_ema_today = self.calculate_rsi(prices, method='ema').dropna().iloc[-1]
        rsi_ema_yesterday = self.calculate_rsi(prices[1:], method='ema').dropna().iloc[-1]

        rsi_sma_today = self.calculate_rsi(prices, method='sma').dropna().iloc[-1]
        rsi_sma_yesterday = self.calculate_rsi(prices[1:], method='sma').dropna().iloc[-1]

        return {
            "RSI(EMA)_today": round(rsi_ema_today, 2),
            "RSI(EMA)_yesterday": round(rsi_ema_yesterday, 2),
            "RSI(SMA)_today": round(rsi_sma_today, 2),
            "RSI(SMA)_yesterday": round(rsi_sma_yesterday, 2)
        }

    def get_moving_average(self):
        kiwoom = Kiwoom()
        kiwoom.CommConnect()

        # 조회할 종목코드
        code = "005930"  # 삼성전자

        # 일봉 데이터 요청
        df = kiwoom.block_request(
            "opt10081",
            종목코드=code,
            기준일자="20250628",
            수정주가구분=1,
            output="주식일봉차트조회",
            next=0
        )

        # 데이터 가공
        df['현재가'] = df['현재가'].astype(int)
        df['일자'] = pd.to_datetime(df['일자'])
        df.sort_values('일자', inplace=True)
        df.set_index('일자', inplace=True)

        # 이동평균 계산
        df['MA5'] = df['현재가'].rolling(window=5).mean()
        df['MA20'] = df['현재가'].rolling(window=20).mean()
        df['MA60'] = df['현재가'].rolling(window=60).mean()
        df['MA120'] = df['현재가'].rolling(window=120).mean()

        # 그래프 그리기 (이동평균선만)
        plt.figure(figsize=(12, 6))
        plt.plot(df.index, df['MA5'], label='5일선', color='blue')
        plt.plot(df.index, df['MA20'], label='20일선', color='orange')
        plt.plot(df.index, df['MA60'], label='60일선', color='green')
        plt.plot(df.index, df['MA120'], label='120일선', color='red')

        plt.xlabel('날짜')
        plt.ylabel('가격')
        plt.title('이동평균선 (5/20/60/120일)')
        plt.legend()
        plt.grid(True)
        plt.show()

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

            elif rqname == "opw00018_holdings_req":
                holdings = []
                cnt = self.api.ocx.GetRepeatCnt(trcode, rqname)
                for i in range(cnt):
                    code = self.api.ocx.GetCommData(trcode, rqname, i, "종목번호").strip()
                    name = self.api.ocx.GetCommData(trcode, rqname, i, "종목명").strip()
                    qty = self.api.ocx.GetCommData(trcode, rqname, i, "보유수량").strip()
                    prcs = self.api.ocx.GetCommData(trcode, rqname, i, "매입가").strip()
                    cur = self.api.ocx.GetCommData(trcode, rqname, i, "현재가").strip()

                    try:
                        qty = int(qty.replace(',', ''))
                    except ValueError:
                        qty = 0
                    try:
                        prcs = int(prcs.replace(',', ''))
                    except ValueError:
                        prcs = 0
                    try:
                        cur = int(cur.replace(',', ''))
                    except ValueError:
                        cur = 0

                    holdings.append({
                        "code": code,
                        "name": name,
                        "quantity": qty,
                        "purchase_price": prcs,
                        "current_price": cur,
                    })

                self.tr_data["opw00018"] = holdings

            elif rqname == "volume_rank_req":
                stocks = []
                count = int(self.api.ocx.GetRepeatCnt(trcode, rqname))
                for i in range(min(count, 50)):
                    code = self.api.ocx.GetCommData(trcode, rqname, i, "종목코드").strip()
                    name = self.api.ocx.GetCommData(trcode, rqname, i, "종목명").strip()
                    volume = self.api.ocx.GetCommData(trcode, rqname, i, "거래량").strip()
                    amount = self.api.ocx.GetCommData(trcode, rqname, i, "거래금액").strip()
                    price = self.api.ocx.GetCommData(trcode, rqname, i, "현재가").strip()

                    try:
                        volume = int(volume.replace(',', ''))
                    except (ValueError, AttributeError):
                        volume = 0
                    try:
                        amount = int(amount.replace(',', ''))
                    except (ValueError, AttributeError):
                        amount = 0
                    try:
                        price = int(price.replace(',', ''))
                    except (ValueError, AttributeError):
                        price = 0

                    stocks.append({
                        "code": code,
                        "name": name,
                        "price": price,
                        "vol": volume,
                        "amount": amount,
                    })

                self.tr_data["OPT10030"] = {"stocks": stocks}
                # QTimer.singleShot(0, self.tr_event_loop.quit)

            elif rqname == "unfilled_orders_req":
                orders = []
                count = int(self.api.ocx.GetRepeatCnt(trcode, rqname))
                for i in range(count):
                    code = self.api.ocx.GetCommData(trcode, rqname, i, "종목코드").strip()
                    name = self.api.ocx.GetCommData(trcode, rqname, i, "종목명").strip()
                    qty = self.api.ocx.GetCommData(trcode, rqname, i, "주문수량").strip()
                    filled = self.api.ocx.GetCommData(trcode, rqname, i, "체결수량").strip()
                    price = self.api.ocx.GetCommData(trcode, rqname, i, "주문가격").strip()

                    logger.info(f"[trading.py] unfilled_orders_req => {code} | {name} | {qty} | {filled} | {price}")

                    orders.append({
                        "code": code,
                        "name": name,
                        "qty": int(qty.replace(",", "") or 0),
                        "filled": int(filled.replace(",", "") or 0),
                        "price": int(price.replace(",", "") or 0),
                    })

                self.tr_data["opt10075"] = {"orders": orders}

        finally:
            QTimer.singleShot(0, self.tr_event_loop.quit)
