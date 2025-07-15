from PyQt5.QtCore import QEventLoop, QTimer
from config import Config
import logging
from logger import logger
from multiprocessing import Process
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager, rc
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QDialog, QWidget, QVBoxLayout
from datetime import datetime
from dotenv import load_dotenv
import os
from openai import OpenAI
from google_news_scraper import get_google_news_snippets, get_google_nasdaq_snippets

load_dotenv(dotenv_path="env_template.env")  # 파일 경로 직접 지정

logger = logging.getLogger("KiwoomTrading")

# 윈도우 한글 폰트 경로
font_path = "C:/Windows/Fonts/H2GPRM.TTF"  # 맑은 고딕

# 폰트 적용
font_name = font_manager.FontProperties(fname=font_path).get_name()
rc('font', family=font_name)

# 마이너스 기호 깨짐 방지
plt.rcParams['axes.unicode_minus'] = False

class ChartDialog(QDialog):
    def __init__(self, df):
        super().__init__()
        self.setWindowTitle("삼성전자 이동평균선 차트")
        self.setGeometry(200, 200, 1000, 600)

        layout = QVBoxLayout()
        self.setLayout(layout)

        fig = Figure(figsize=(12, 6))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)

        ax.plot(df.index, df['현재가'], label='종가', color='black', linewidth=1)
        ax.plot(df.index, df['MA5'], label='5일선', color='blue')
        ax.plot(df.index, df['MA20'], label='20일선', color='orange')
        ax.plot(df.index, df['MA60'], label='60일선', color='green')
        ax.plot(df.index, df['MA120'], label='120일선', color='red')
        ax.set_title("삼성전자 이동평균선 차트")
        ax.set_xlabel("날짜")
        ax.set_ylabel("가격")
        ax.legend()
        ax.grid(True)

        layout.addWidget(canvas)

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

        self.tr_data.pop("opt10075", None)
        self.api.ocx.SetInputValue("계좌번호", Config.ACCNO)
        self.api.ocx.SetInputValue("전체", "0") # 전체 계좌
        self.api.ocx.SetInputValue("매매구분", "0") # 전체
        self.api.ocx.SetInputValue("체결구분", "1") # 미체결만
        self.api.ocx.CommRqData("unfilled_orders_req", "opt10075", 0, "9000")
        self.tr_event_loop.exec_()
        return self.tr_data.get("opt10075", {"orders": []})

    def cancel_order(self, code, order_no, qty, order_type=""):
        """미체결 주문 취소"""
        try:
            logger.info(f"[주문취소 요청] {order_no} | {code} | {qty}주 | {order_type}")
            # 매수취소:3, 매도취소:4 - 주문구분으로 판별, 기본은 3(매수취소)
            order_flag = 3 if "매수" in order_type else 4
            self.api.ocx.SendOrder(
                "주문취소",
                "0103",
                Config.ACCNO,
                order_flag,
                code,
                qty,
                0,
                "00",
                order_no,
            )
            return {"message": "✅ 주문 취소 요청 완료"}
        except Exception as e:
            logger.log_error("CANCEL_ORDER", str(e))
            return {"error": str(e)}

    def get_close_prices(self, code="005930", count=250):
        today = datetime.today().strftime('%Y%m%d')
        df = self.api.ocx.block_request("opt10081",
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

    def get_moving_average(self, code, history_date, history_code, history_price, history_qty, history_flag):

        logger.info(f"get_moving_average > str(code) : {str(code)}")
        logger.info(f"get_moving_average > history_date : {history_date}")
        logger.info(f"get_moving_average > history_code : {history_code}")
        logger.info(f"get_moving_average > history_price : {history_price}")
        logger.info(f"get_moving_average > history_qty : {history_qty}")
        logger.info(f"get_moving_average > history_flag : {history_flag}")

        self.tr_data.pop("opt10081", None)
        self.api.ocx.SetInputValue("종목코드", str(code))
        # self.api.ocx.SetInputValue("기준일자", end_date)
        self.api.ocx.SetInputValue("수정주가구분", "1")
        self.api.ocx.CommRqData("opt10081_req", "opt10081", 0, "5001")
        self.tr_event_loop.exec_()

        data = self.tr_data.get("opt10081", [])
        if not data or len(data) < 5:
            return {"error": "데이터 부족"}

        df = pd.DataFrame(data)

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

        # -------------------- 매매 마커 표시 --------------------
        buy_date = []
        buy_price = []
        sell_date = []
        sell_price = []

        history_flag_list = []
        history_date_list = []
        history_price_list = []

        try:
            # 단일값일 경우 리스트로 변환
            if isinstance(history_flag, str):
                history_flag_list = history_flag.split(',')
            if isinstance(history_date, str):
                history_date_list = history_date.split(',')
            if isinstance(history_price, str):
                history_price_list = history_price.split(',')

            for idx, flag in enumerate(history_flag_list):
                dt = pd.to_datetime(history_date_list[idx])
                price = float(history_price_list[idx])
                if flag == 'buy':
                    buy_date.append(dt)
                    buy_price.append(price)
                elif flag == 'sell':
                    sell_date.append(dt)
                    sell_price.append(price)

            # 매수 마커
            if buy_date:
                first = True
                for d, p in zip(buy_date, buy_price):
                    plt.scatter(d, p, color='purple', marker='^', s=100, label='매수' if first else "")
                    first = False

            # 매도 마커
            if sell_date:
                first = True
                for d, p in zip(sell_date, sell_price):
                    plt.scatter(d, p, color='green', marker='v', s=100, label='매도' if first else "")
                    first = False

        except Exception as e:
            logger.warning(f"💥 마커 표시 중 오류: {e}")
        # -------------------- 매매 마커 표시 --------------------

        plt.xlabel('날짜')
        plt.ylabel('가격')
        plt.title('이동평균선 (5/20/60/120일)')
        plt.legend()
        plt.grid(True)
        #------------------
        plt.tight_layout()
        #------------------
        plt.show()

        return {"status": "success"}

    def detect_golden_cross(self, code):
        from datetime import datetime
        import pandas as pd

        logger.info(f"detect_golden_cross > code : {code}")

        end_date = datetime.today().strftime('%Y%m%d')

        # TR 데이터 초기화
        self.tr_data.pop("opt10081", None)

        # 요청 세팅
        self.api.ocx.SetInputValue("종목코드", code)
        self.api.ocx.SetInputValue("기준일자", end_date)
        self.api.ocx.SetInputValue("수정주가구분", "1")
        self.api.ocx.CommRqData("opt10081_req", "opt10081", 0, "5001")

        # 이벤트 루프 대기
        self.tr_event_loop.exec_()

        # 결과 가져오기
        data = self.tr_data.get("opt10081", [])
        if not data or len(data) < 120:
            return {'code': code, 'golden_cross': 'N', 'reason': 'not enough data'}

        df = pd.DataFrame(data)
        df = df[['일자', '현재가']].copy()
        df['현재가'] = df['현재가'].astype(int)
        df.sort_values(by='일자', inplace=True)

        # 이동 평균선 계산
        df['MA5'] = df['현재가'].rolling(window=5).mean()
        df['MA20'] = df['현재가'].rolling(window=20).mean()
        df['MA60'] = df['현재가'].rolling(window=60).mean()
        df['MA120'] = df['현재가'].rolling(window=120).mean()

        df = df.dropna().reset_index(drop=True)
        if len(df) < 5:
            return {'code': code, 'golden_cross': 'N', 'reason': 'not enough data'}

        # 최근 5영업일 기준 분석
        recent = df.iloc[-5:].copy()
        logger.info(f"[trading.py] recent: {recent}")

        ma5s = recent['MA5'].tolist()
        logger.info(f"[trading.py] ma5s: {ma5s}")

        last_ma5 = recent['MA5'].iloc[-1]
        last_ma20 = recent['MA20'].iloc[-1]
        last_ma60 = recent['MA60'].iloc[-1]
        last_ma120 = recent['MA120'].iloc[-1]

        logger.info(f"[trading.py] last_ma5: {last_ma5}, last_ma20: {last_ma20}, last_ma60: {last_ma60}, last_ma120: {last_ma120}")

        long_ma_candidates = [last_ma20, last_ma60, last_ma120]
        diffs = [abs(last_ma5 - x) for x in long_ma_candidates]
        min_idx = diffs.index(min(diffs))

        closest_ma_nm = ''
        closest_ma_nm2 = ''
        if min_idx == 0:
            closest_ma_nm = 'MA20'
            closest_ma_nm2 = '<b style="color:#DAA520;">20일선</b>'
        elif min_idx == 1:
            closest_ma_nm = 'MA60'
            closest_ma_nm2 = '<b style="color:green;">60일선</b>'
        elif min_idx == 2:
            closest_ma_nm = 'MA120'
            closest_ma_nm2 = '<b style="color:red;">120일선</b>'

        closest_ma = long_ma_candidates[min_idx]

        # 조건 체크
        # 가장 가까운 장기이평선 밑으로(또는 상위) 3% 이내에 접근한 상태.
        cond1 = (abs(last_ma5 - closest_ma) / closest_ma <= 0.03)
        # 4영업일(또는 3영업일) 전 5일선이 최근 5일간 5일선 가격 중 가장 낮아야 함.
        cond2 = recent['MA5'].iloc[0] == min(ma5s) or recent['MA5'].iloc[1] == min(ma5s)
        # 2영업일 전 5일선이 가장 최근 5일선 가격 보다 낮아야 함.
        cond3 = recent['MA5'].iloc[3] < recent['MA5'].iloc[4]
        # 가장 최근 5일선 가격이 가장 높아야 함.
        cond4 = recent['MA5'].iloc[4] == max(ma5s)
        # 가장 최근 5일선이 가장 가까운 장기이평선 미돌파 시 5영업일 전 5일선은 5영업일 전 가장 가까운 이평선 아래여야 함.      가장 최근 5일선이 가장 가까운 장기이평선 돌파 시 5영업일 전 5일선은 5영업일 전 가장 가까운 이평선과 같거나 아래여야 함.
        cond5 = ( (last_ma5 - closest_ma) <= 0 and recent['MA5'].iloc[0] < recent[closest_ma_nm].iloc[0] ) or ( (last_ma5 - closest_ma) > 0 and (recent['MA5'].iloc[0] <= recent[closest_ma_nm].iloc[0]) )

        all_conditions = all([cond1, cond2, cond3, cond4, cond5])   # 골든크로스(기대) 상태 1
        conditions = all([cond1, cond3, cond4, cond5])   # 골든크로스(기대) 상태 2

        comment = ''
        comment2 = ''
        if (last_ma5 - closest_ma) > 0 and ((last_ma5 - closest_ma) / closest_ma <= 0.01) and all_conditions:
            comment = '골든크로스 돌파! <b style="color:blue;">5일선</b>이 '+closest_ma_nm2+' 위로 추가 1% 상승전! (강력)매수 고려.'
        elif (last_ma5 - closest_ma) > 0 and ((last_ma5 - closest_ma) / closest_ma <= 0.02) and all_conditions:
            comment = '골든크로스 돌파! <b style="color:blue;">5일선</b>이 '+closest_ma_nm2+' 위로 추가 2% 상승전! (강력)후발 매수 고려.'
        elif (last_ma5 - closest_ma) > 0 and ((last_ma5 - closest_ma) / closest_ma <= 0.03) and all_conditions:
            comment = '골든크로스 돌파! <b style="color:blue;">5일선</b>이 '+closest_ma_nm2+' 위로 추가 3% 상승전! 차익 실현 조심하며 (눌림목)후발 매수 고려.'
        elif (last_ma5 - closest_ma) == 0 and conditions:
            comment = '골든크로스 발생! (<b style="color:blue;">5일선</b>이 '+closest_ma_nm2+' 위로 골든크로스 돌파 확인하며 분할)매수.'
        elif (last_ma5 - closest_ma) < 0 and (abs(last_ma5 - closest_ma) / closest_ma <= 0.01) and conditions:
            comment = '골든크로스 발생 전 (<b style="color:blue;">5일선</b>이 '+closest_ma_nm2+' 향하여 1% 이내 근접). 매수 준비 고려.'
        elif (last_ma5 - closest_ma) < 0 and (abs(last_ma5 - closest_ma) / closest_ma <= 0.02) and conditions:
            comment = '골든크로스 발생 전 (<b style="color:blue;">5일선</b>이 '+closest_ma_nm2+' 향하여 2% 이내 근접). 골든크로스 시도 지켜볼 것.'
        elif (last_ma5 - closest_ma) < 0 and (abs(last_ma5 - closest_ma) / closest_ma <= 0.03) and conditions:
            comment = '골든크로스 발생 전 (<b style="color:blue;">5일선</b>이 '+closest_ma_nm2+' 향하여 3% 이내 근접). 골든크로스 시도 지켜볼 것.'
        elif (last_ma5 - closest_ma) > 0:
            comment = f'<b style="color:blue;">5일선</b>이 '+closest_ma_nm2+f' 위로 {round( ((last_ma5 - closest_ma) / closest_ma) * 100, 1)}% 상위'
        elif (last_ma5 - closest_ma) < 0:
            comment = f'<b style="color:blue;">5일선</b>이 '+closest_ma_nm2+f' 아래로 {round( (abs(last_ma5 - closest_ma) / closest_ma) * 100, 1)}% 하위'

        if (last_ma5 - closest_ma) >= 0:
            comment2 = '발생'
        else:
            comment2 = '대비'

        name = self.api.ocx.dynamicCall("GetMasterCodeName(QString)", [code])    

        self.tr_data.pop("opt10001", None)
        self.api.ocx.SetInputValue("종목코드", code)
        self.api.ocx.CommRqData("opt10001_req", "opt10001", 0, "0103")

        self.tr_event_loop.exec_()

        data = self.tr_data.get("opt10001", {})

        logger.info(f"opt10001 > data : {data}")

        price = data.get("현재가", 0)
        price = int(price.replace(",", "")) if price else 0

        return {'code': code, 'name':name, 'price':price, 'golden_cross': 'Y' if all_conditions else 'N', 'comment':comment, 'comment2':comment2}

    def detect_dead_cross(self, code):
        from datetime import datetime
        import pandas as pd

        logger.info(f"detect_dead_cross > code : {code}")

        end_date = datetime.today().strftime('%Y%m%d')

        # TR 데이터 초기화
        self.tr_data.pop("opt10081", None)

        # 요청 세팅
        self.api.ocx.SetInputValue("종목코드", code)
        self.api.ocx.SetInputValue("기준일자", end_date)
        self.api.ocx.SetInputValue("수정주가구분", "1")
        self.api.ocx.CommRqData("opt10081_req", "opt10081", 0, "5001")

        # 이벤트 루프 대기
        self.tr_event_loop.exec_()

        # 결과 가져오기
        data = self.tr_data.get("opt10081", [])
        if not data or len(data) < 120:
            return {'code': code, 'golden_cross': 'N', 'reason': 'not enough data'}

        df = pd.DataFrame(data)
        df = df[['일자', '현재가']].copy()
        df['현재가'] = df['현재가'].astype(int)
        df.sort_values(by='일자', inplace=True)

        # 이동 평균선 계산
        df['MA5'] = df['현재가'].rolling(window=5).mean()
        df['MA20'] = df['현재가'].rolling(window=20).mean()
        df['MA60'] = df['현재가'].rolling(window=60).mean()
        df['MA120'] = df['현재가'].rolling(window=120).mean()

        df = df.dropna().reset_index(drop=True)
        if len(df) < 5:
            return {'code': code, 'dead_cross': 'N', 'reason': 'not enough data'}

        # 최근 5영업일 기준 분석
        recent = df.iloc[-5:].copy()
        logger.info(f"[trading.py] recent: {recent}")

        ma5s = recent['MA5'].tolist()
        logger.info(f"[trading.py] ma5s: {ma5s}")

        last_ma5 = recent['MA5'].iloc[-1]
        last_ma20 = recent['MA20'].iloc[-1]
        last_ma60 = recent['MA60'].iloc[-1]
        last_ma120 = recent['MA120'].iloc[-1]

        logger.info(f"[trading.py] last_ma5: {last_ma5}, last_ma20: {last_ma20}, last_ma60: {last_ma60}, last_ma120: {last_ma120}")

        long_ma_candidates = [last_ma20, last_ma60, last_ma120]
        diffs = [abs(last_ma5 - x) for x in long_ma_candidates]
        min_idx = diffs.index(min(diffs))

        closest_ma_nm = ''
        closest_ma_nm2 = ''
        if min_idx == 0:
            closest_ma_nm = 'MA20'
            closest_ma_nm2 = '<b style="color:#DAA520;">20일선</b>'
        elif min_idx == 1:
            closest_ma_nm = 'MA60'
            closest_ma_nm2 = '<b style="color:green;">60일선</b>'
        elif min_idx == 2:
            closest_ma_nm = 'MA120'
            closest_ma_nm2 = '<b style="color:red;">120일선</b>'

        closest_ma = long_ma_candidates[min_idx]

        # 조건 체크
        # 가장 가까운 장기이평선 밑으로(또는 상위) 3% 이내에 접근한 상태.
        cond1 = (abs(last_ma5 - closest_ma) / closest_ma <= 0.03)
        # 4영업일(또는 3영업일) 전 5일선이 최근 5일간 5일선 가격 중 가장 높아야 함.
        cond2 = recent['MA5'].iloc[0] == max(ma5s) or recent['MA5'].iloc[1] == max(ma5s)
        # 1영업일 전 5일선이 가장 최근 5일선 가격 보다 높아야 함.
        cond3 = recent['MA5'].iloc[3] > recent['MA5'].iloc[4]
        # 가장 최근 5일선 가격이 가장 낮아야 함.
        cond4 = recent['MA5'].iloc[4] == min(ma5s)
        # 가장 최근 5일선이 가장 가까운 장기이평선 미(하향)돌파 시 5영업일 전 5일선은 5영업일 전 가장 가까운 이평선 상위여야 함.      가장 최근 5일선이 가장 가까운 장기이평선 (하향)돌파 시 5영업일 전 5일선은 5영업일 전 가장 가까운 이평선과 같거나 상위여야 함.
        cond5 = ( (last_ma5 - closest_ma) >= 0 and recent['MA5'].iloc[0] > recent[closest_ma_nm].iloc[0] ) or ( (last_ma5 - closest_ma) < 0 and (recent['MA5'].iloc[0] >= recent[closest_ma_nm].iloc[0]) )

        all_conditions = all([cond1, cond2, cond3, cond4, cond5])   # 데드크로스(기대) 상태 1
        conditions = all([cond1, cond3, cond4, cond5])   # 데드크로스(기대) 상태 2

        comment = ''
        comment2 = ''
        if (last_ma5 - closest_ma) < 0 and (abs(last_ma5 - closest_ma) / closest_ma <= 0.01) and all_conditions:
            comment = '데드크로스 하향 돌파! <b style="color:blue;">5일선</b>이 '+closest_ma_nm2+' 아래로 추가 1% 하락전! (이평선 반등 확인하며 하방 뚫릴 시)매도 고려.'
        elif (last_ma5 - closest_ma) < 0 and (abs(last_ma5 - closest_ma) / closest_ma <= 0.02) and all_conditions:
            comment = '데드크로스 하향 돌파! <b style="color:blue;">5일선</b>이 '+closest_ma_nm2+' 아래로 추가 2% 하락전! (강력)매도 고려.'
        elif (last_ma5 - closest_ma) < 0 and (abs(last_ma5 - closest_ma) / closest_ma <= 0.03) and all_conditions:
            comment = '데드크로스 하향 돌파! <b style="color:blue;">5일선</b>이 '+closest_ma_nm2+' 아래로 추가 3% 하락전! (강력)매도 고려.'
        elif (last_ma5 - closest_ma) == 0 and conditions:
            comment = '데드크로스 발생! (<b style="color:blue;">5일선</b>이 '+closest_ma_nm2+' 아래로 하방 돌파 확인하며 분할)매도 고려. (또는 이평선 지켜주며 반등 시 분할 매수)'
        elif (last_ma5 - closest_ma) > 0 and ((last_ma5 - closest_ma) / closest_ma <= 0.01) and conditions:
            comment = '데드크로스 발생 전 (<b style="color:blue;">5일선</b>이 하방으로 '+closest_ma_nm2+' 향하여 1% 이내 근접). 매도 준비 고려.'
        elif (last_ma5 - closest_ma) > 0 and ((last_ma5 - closest_ma) / closest_ma <= 0.02) and conditions:
            comment = '데드크로스 발생 전 (<b style="color:blue;">5일선</b>이 하방으로 '+closest_ma_nm2+' 향하여 2% 이내 근접). (이평선 지켜주는지 주의하며)매도 준비 고려.'
        elif (last_ma5 - closest_ma) > 0 and (abs(last_ma5 - closest_ma) / closest_ma <= 0.03) and conditions:
            comment = '데드크로스 발생 전 (<b style="color:blue;">5일선</b>이 하방으로 '+closest_ma_nm2+' 향하여 3% 이내 근접). (이평선 지켜주는지 주의하며)매도 준비 고려.'
        elif (last_ma5 - closest_ma) > 0:
            comment = f'<b style="color:blue;">5일선</b>이 '+closest_ma_nm2+f' 위로 {round( ((last_ma5 - closest_ma) / closest_ma) * 100, 1)}% 상위'
        elif (last_ma5 - closest_ma) < 0:
            comment = f'<b style="color:blue;">5일선</b>이 '+closest_ma_nm2+f' 아래로 {round( (abs(last_ma5 - closest_ma) / closest_ma) * 100, 1)}% 하위'

        if (last_ma5 - closest_ma) <= 0:
            comment2 = '발생'
        else:
            comment2 = '주의'

        name = self.api.ocx.dynamicCall("GetMasterCodeName(QString)", [code])    

        self.tr_data.pop("opt10001", None)
        self.api.ocx.SetInputValue("종목코드", code)
        self.api.ocx.CommRqData("opt10001_req", "opt10001", 0, "0104")

        self.tr_event_loop.exec_()

        data = self.tr_data.get("opt10001", {})

        logger.info(f"opt10001 > data : {data}")

        price = data.get("현재가", 0)
        price = int(price.replace(",", "")) if price else 0

        return {'code': code, 'name':name, 'price':price, 'dead_cross': 'Y' if all_conditions else 'N', 'comment':comment, 'comment2':comment2}

    def search_stock_by_name(self, keyword):
        kospi_codes = self.api.ocx.dynamicCall("GetCodeListByMarket(QString)", ["0"]).split(';')
        kosdaq_codes = self.api.ocx.dynamicCall("GetCodeListByMarket(QString)", ["10"]).split(';')
        all_codes = kospi_codes + kosdaq_codes

        result = []
        for code in all_codes:
            if code == '':
                continue
            name = self.api.ocx.dynamicCall("GetMasterCodeName(QString)", [code])
            if keyword in name:
                result.append({"name": name, "code": code})

        return result[:20]

    def ask_gpt_for_invest_weather(self):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        news = get_google_news_snippets("미국 증시", count=10)
        news2 = get_google_news_snippets("한국 증시", count=10)

        system_msg = "주식 투자자의 입장으로써 질문할게. 현재 시간 기준으로 미국 증시의 악재 및 호재 등 이슈가 되는 뉴스를 알려주고, 이로 인한 한국 증시의 영향(또는 미국 증시와 별개로 한국 증시의 (악재, 호재)이슈)을 알려줘. 다음 뉴스들은 너가 참고할 수 있게 내가 추가한 것들이야. 목적은 증시 분위기를 통해 매매 진입 하기에 매력이 있는 상황인지 확인하기 위함이야."

        user_prompt = f"""
            다음은 너가 참고할 수 있도록 추가한 오늘의 증시 관련 주요 뉴스들이야 (내가 추가한 뉴스 외에도 중요한 뉴스가 있다면 포함해줘.):    

            1. 미국 증시 뉴스 :
            -------------------
            {news}
            -------------------
            2. 한국 증시 뉴스 :
            {news2}
            -------------------

            (내가 추가한 뉴스 및 그 밖에 증시에 중요한 뉴스)를 기반으로 아래 내용을 포함해서 분석해줘:
            - 거시경제 흐름
            - 주요 뉴스/리스크 요약
            - 투자 심리가 긍정적인지 부정적인지
            - 오늘 (단기 또는 스윙) 매매 진입에 대해 추천하는지 여부 (예시 => [투자 날씨 맑음 : 매수 적극 권장, 투자 날씨 보통 : 차익 실현 주의하며 눌림목 매수 권장, 투자 날씨 흐림 : 매수 피하고 차익실현 권장, 투자 날씨 비 : 전체 현금화 권장] 등)
            - 마지막에는 오늘 투자 진입하기에 좋은지 여부에 따라 ["positive", "negative"] 중 1개의 단어를 달아줘.
            """

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=600
            )

            answer = response.choices[0].message.content.strip()

            # 투자 분위기 방향성 추론
            positive_keywords = ['positive']
            direction = "negative"
            for word in positive_keywords:
                if word in answer:
                    direction = "positive"
                    break

            return {"answer": answer, "direction": direction}

        except Exception as e:
            from logger import logger
            logger.error(f"GPT API 호출 오류: {e}")
            return {"answer": "❌ GPT 응답 중 오류가 발생했습니다.", "direction": "negative"}

    def ask_gpt_for_get_invest_micro(self):

        try:
            nasdaq = get_google_nasdaq_snippets("나스닥", count=10)
            return nasdaq
        except Exception as e:
            from logger import logger
            logger.error(f"[Google nasdaq 테스트 오류] {e}")
            return {"error": str(e)}

    def ask_gpt_for_get_invest_micro_TMP(self):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        system_msg = "주식 투자자의 입장으로써 질문하는 거야. 항상 답변 해주면서, 만약 답변 내용과 관련되어 추천해줄 수 있는 종목이 있다면 구체적으로 같이 알려주면 좋겠어. 결국 목적은 돈을 벌기 위한(또는 돈을 최대한 잃지 않는) 것이기 때문이야."

        user_prompt = f"""
            현재 시간 기준,
            미국 증시 및 한국 증시의 거시적 시장 상황 점검을 부탁할게.
            (아래의 항목을 기준으로 답변 부탁해. 각 항목은 번호를 붙여 놓았고, "=>" 다음에 오는 내용은 해당 질문을 통해 확인하고자 하는 목적이야. 참고하여 답변해주기를 바래.)

            1. 전날 미국 증시 (나스닥, S&P500, 다우) 흐름 => 장기 지수 추세, 변곡점 여부
            2. 주요 선물지수 (나스닥, S&P500 선물) => 장 시작 전 분위기 파악
            3. VIX (공포지수) 변화 => 시장 불안 심리 점검
            4. 주요 경제지표 발표 일정 (오늘 발표 예정 지표) 또는 큰 악재 및 호재가 있는지 여부 => 금리, 실업률, CPI 등 서프라이즈 이슈 대비
            5. 달러 인덱스, 금리, 유가, 원/달러 환율 => 자금 흐름 및 수출주 영향 판단
            """

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=600
            )

            answer = response.choices[0].message.content.strip()

            return {"answer": answer}

        except Exception as e:
            from logger import logger
            logger.error(f"GPT API 호출 오류: {e}")
            return {"answer": "❌ GPT 응답 중 오류가 발생했습니다.", "direction": "negative"}

    def get_google_news_test(self):
        try:
            news = get_google_news_snippets("미국 증시", count=10)
            return news
        except Exception as e:
            from logger import logger
            logger.error(f"[Google 뉴스 테스트 오류] {e}")
            return {"error": str(e)}

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

            elif rqname == "unfilled_orders_req":
                orders = []
                count = int(self.api.ocx.GetRepeatCnt(trcode, rqname))
                for i in range(count):
                    code = self.api.ocx.GetCommData(trcode, rqname, i, "종목코드").strip()
                    name = self.api.ocx.GetCommData(trcode, rqname, i, "종목명").strip()
                    qty = self.api.ocx.GetCommData(trcode, rqname, i, "주문수량").strip()
                    filled = self.api.ocx.GetCommData(trcode, rqname, i, "체결수량").strip()
                    price = self.api.ocx.GetCommData(trcode, rqname, i, "주문가격").strip()
                    order_no = self.api.ocx.GetCommData(trcode, rqname, i, "주문번호").strip()
                    order_type = self.api.ocx.GetCommData(trcode, rqname, i, "주문구분").strip()

                    logger.info(f"[trading.py] unfilled_orders_req => {code} | {name} | {qty} | {filled} | {price}")

                    orders.append({
                        "code": code,
                        "name": name,
                        "qty": int(qty.replace(",", "") or 0),
                        "filled": int(filled.replace(",", "") or 0),
                        "price": int(price.replace(",", "") or 0),
                        "order_no": order_no,
                        "order_type": order_type,
                    })

                self.tr_data["opt10075"] = {"orders": orders}

            elif rqname == "opt10081_req":
                count = self.api.ocx.GetRepeatCnt(trcode, rqname)
                rows = []
                for i in range(count):
                    date = self.api.ocx.GetCommData(trcode, rqname, i, "일자").strip()
                    close = self.api.ocx.GetCommData(trcode, rqname, i, "현재가").strip()
                    try:
                        close = int(close)
                    except:
                        continue
                    rows.append({"일자": date, "현재가": close})
                self.tr_data["opt10081"] = rows

            elif rqname == "market_news_req":
                news_list = []
                count = self.api.ocx.GetRepeatCnt(trcode, rqname)
                for i in range(count):
                    title = self.api.ocx.GetCommData(trcode, rqname, i, "뉴스제목").strip()
                    time = self.api.ocx.GetCommData(trcode, rqname, i, "시간").strip()
                    news_list.append({"title": title, "time": time})
                self.tr_data["OPT10051"] = news_list

            elif rqname == "opt10001_req":
                price = self.api.ocx.GetCommData(trcode, rqname, 0, "현재가").strip()
                self.tr_data["opt10001"] = {
                    "현재가": price
                }

        finally:
            QTimer.singleShot(0, self.tr_event_loop.quit)
