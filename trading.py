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
from PyQt5.QtWidgets import QDialog, QVBoxLayout
from datetime import datetime
from dotenv import load_dotenv
import os
import csv
from openai import OpenAI
from google_news_scraper import get_google_news_snippets
import sqlite3
from threading import Thread, Event
import schedule
import requests
import time

load_dotenv(dotenv_path="env_template.env")  # 파일 경로 직접 지정

logger = logging.getLogger("KiwoomTrading")

# 윈도우 한글 폰트 경로
font_path = "C:/Windows/Fonts/H2GPRM.TTF"  # 맑은 고딕

# 폰트 적용
font_name = font_manager.FontProperties(fname=font_path).get_name()
rc('font', family=font_name)

# 마이너스 기호 깨짐 방지
plt.rcParams['axes.unicode_minus'] = False

# 앱 시작 시 1회만 DB 초기화
def initialize_db():
    conn = sqlite3.connect("stock_indicators.db")
    cursor = conn.cursor()

    # 1. RSI 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rsi_data (
            code TEXT,
            date TEXT,
            rsi REAL,
            avg_gain REAL,
            avg_loss REAL,
            PRIMARY KEY (code, date)
        )
    ''')

    # 2. MACD 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS macd_data (
            code TEXT,
            date TEXT,
            macd REAL,
            signal REAL,
            histogram REAL,
            PRIMARY KEY (code, date)
        )
    ''')

    # 3. STC (Slow Stochastic) 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stc_data (
            code TEXT,
            date TEXT,
            percent_k REAL,
            percent_d REAL,
            PRIMARY KEY (code, date)
        )
    ''')

    # 4. 거래량 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS volume_data (
            code TEXT,
            date TEXT,
            volume INTEGER,
            checkYn TEXT,
            PRIMARY KEY (code, date)
        )
    ''')

    # 5. BASKET 종목 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS basket_data (
            code TEXT,
            name TEXT,
            etc TEXT,
            PRIMARY KEY (code)
        )
    ''')

    # 6. 스케줄러 작동 여부 확인용 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sch_data (
            schNm TEXT,
            status TEXT
        )
    ''')

    conn.commit()
    conn.close()

# 앱 시작 시 호출
initialize_db()


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

    def send_slack_message(self, text):
        webhook_url = "https://hooks.slack.com/services/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"
        payload = { "text": text }

        response = requests.post(webhook_url, json=payload, verify=False)   # (개발 환경에서만 임시로. 운영 배포 시 절대 사용 금지!)

        if response.status_code != 200:
            print("Slack 전송 실패:", response.status_code, response.text)

    def volume_search(self, code, name):
        logger.info(f"trading > volume_search, code,name : {code},{name}")

        prices = self.get_close_prices(code, 2)

        curr_row = prices[0]
        curr_volume = curr_row.get('거래량', 0)
        
        prev_row = prices[1]
        prev_volume = prev_row.get('거래량', 0)

        logger.info(f"curr_volume : {curr_volume}")
        logger.info(f"prev_volume : {prev_volume}")

        try:
            curr_volume = int(curr_volume)
            logger.info(f"curr_volume : {curr_volume}")
        except Exception:
            curr_volume = 0

        try:
            prev_volume = int(prev_volume)
            logger.info(f"prev_volume : {prev_volume}")
        except Exception:
            prev_volume = 0

        result = ''
        if curr_volume >= (prev_volume * 2):
            logger.info("curr_volume >= (prev_volume * 2)")

            #-----------------------------------------------------------------

            stc_macd_result = self.analyze_stochastic(code)
            stc = stc_macd_result['stc']
            macd = stc_macd_result['macd']

            if (stc['K'] >= 20 and stc['K'] < 40 and stc['K'] >= stc['D']) and (macd['macd'] > macd['signal']):
                self.send_slack_message(f"⚠️ {name}[{code}] 거래량 급증 감지")
                result = 'Y'
            else:
                result = 'N'

            #-----------------------------------------------------------------

        else:
            logger.info("not curr_volume >= (prev_volume * 2)")
            result = 'N'

        return {
            'result':result
        }

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

    def get_close_prices(self, code, count):
        today = datetime.today().strftime('%Y%m%d')

        self.tr_data.pop("opt10081", None)
        self.api.ocx.SetInputValue("종목코드", code)
        self.api.ocx.SetInputValue("기준일자", today)
        self.api.ocx.SetInputValue("수정주가구분", "1")
        self.api.ocx.SetInputValue("output", "주식일봉차트조회")
        self.api.ocx.CommRqData("opt10081_req", "opt10081", 0, "5000")
        self.tr_event_loop.exec_()

        df = self.tr_data.get("opt10081", [])

        if(count == 0):
            close_prices = df
        else:
            close_prices = df[:count]

        logger.info(f"close_prices : {close_prices}")
        return close_prices

    def calculate_rsi(self, prices, period=14):
        gains = []
        losses = []
        rsi = 0

        for i in range(1, len(prices)):
            delta = prices[i] - prices[i - 1]
            if delta > 0:
                gains.append(delta)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(delta))

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(prices) - 1):
            gain = gains[i]
            loss = losses[i]
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

        return {
            "rsi" : round(rsi, 2)
            ,"avg_gain" : round(avg_gain, 2)
            ,"avg_loss" : round(avg_loss, 2)
        }

    def analyze_rsi(self, rsiCode):
        logger.info(f"analyze_rsi > rsiCode : {rsiCode}")
        
        prices = self.get_close_prices(rsiCode, 0)

        #1. 가격만 추출 (종가 리스트 만들기)
        close_values = [item['현재가'] for item in prices]

        #2. 가격 순서 뒤집기 (과거 → 최근 순으로)
        #   get_close_prices()는 최신 데이터부터 먼저 오기 때문에, RSI 계산을 위해서는 과거 → 최신 순서로 뒤집어야 함.
        close_values = close_values[::-1]

        #3. RSI 계산 함수 만들기
        rsi_dict = self.calculate_rsi(close_values, period=14)
        logger.info(f"RSI 정보: {rsi_dict}")

        if rsi_dict:
            """
            # [rsi, avg_gain, avg_loss] csv 파일에 저장
            today_rsi_data = str(rsi_dict['rsi']) + '_' + str(rsi_dict['avg_gain']) + '_' + str(rsi_dict['avg_loss'])
            logger.info(f"today_rsi_data : {today_rsi_data}")
            self.save_single_rsi_to_csv(rsiCode, today_rsi_data)
            """

            today = datetime.today().strftime('%Y-%m-%d')
            self.insert_rsi(rsiCode, today, str(rsi_dict['rsi']), str(rsi_dict['avg_gain']), str(rsi_dict['avg_loss']))

            return rsi_dict
        else:
            logger.warning("RSI 계산에 필요한 데이터가 부족합니다.")
            return None

    def save_single_rsi_to_csv(self, rsiCode: str, today_rsi_data: str):

        # 1. (YYYY-MM-DD 형식)오늘 날짜와 RSI 데이터, 해당 데이터를 담을 csv 파일 준비
        today = datetime.today().strftime('%Y-%m-%d')
        file_path = 'rsi_data.csv'

        # 2. 기존 CSV 읽기
        if os.path.exists(file_path):
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                rows = list(reader)
        else:
            # 파일이 없으면 헤더부터 새로 작성
            rows = [["종목코드"]]

        # 3. 날짜 열 추가 (헤더 확장). 오늘 날짜가 헤더에 없으면 새 열로 추가.
        header = rows[0]
        if today not in header:
            header.append(today)
        today_index = header.index(today)  # 오늘 날짜 열 번호


        #   rows는 csv 파일의 전체 행 리스트 (예시)
        #   rows = [
        #       ["종목코드", "2025-07-15", "2025-07-16"],                                       rows[0] = 헤더
        #       ["005930", "67.42_715.15_304.78", "70.43_726.09_304.78"],                     rows[1]
        #       ["047200", "42.75_960.51_1257.22", "43.85_981.81_1257.32"],                   rows[2]
        #   ]

        code_to_row = {row[0]: row for row in rows[1:]}  # "rows[1:]"은 헤더를 제외한 데이터 행들만 추출. "row[0]"은 해당 row의 첫번째 열 "005930"
        # 결과적으로, **종목코드를 키(key)**로 하고 **해당 행 전체를 값(value)**으로 하는 딕셔너리가 생성
        #   code_to_row = {
        #       '005930': ['005930', '67.42_715.15_304.78', '70.43_726.09_304.78'],
        #       '047200': ['047200', '42.75_960.51_1257.22', '43.85_981.81_1257.32']
        #   }


        # 4. 조건문: 해당 종목코드가 이미 있는지 확인
        if rsiCode in code_to_row:          # 종목코드가 code_to_row 딕셔너리에 이미 있다면
            row = code_to_row[rsiCode]      # 그 종목의 기존 행(row)을 불러옴 ( 이미 있는 행이므로 append() 하지 않음 )
        else:
            row = [rsiCode]                 # 새 종목코드라면 새 행 생성
            rows.append(row)

        # 5. 기존 행 길이를 헤더에 맞춤
        while len(row) <= today_index:
            row.append("")

        # 6. RSI 값을 덮어쓰기 or 새로 추가
        row[today_index] = today_rsi_data

        # 7. 전체 행 다시 구성
        new_rows = [header]
        for r in rows[1:]:
            if r[0] != rsiCode:
                new_rows.append(r)
        new_rows.append(row)

        # 8. csv 파일 저장
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerows(new_rows)

    def insert_rsi(self, code, date, rsi, avg_gain, avg_loss):
        conn = sqlite3.connect("stock_indicators.db")
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO rsi_data (code, date, rsi, avg_gain, avg_loss)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code, date) DO UPDATE SET
                rsi = excluded.rsi,
                avg_gain = excluded.avg_gain,
                avg_loss = excluded.avg_loss
        ''', (code, date, rsi, avg_gain, avg_loss))
        conn.commit()
        conn.close()

    def get_moving_average(self, code, history_date, history_code, history_price, history_qty, history_flag):

        logger.info(f"get_moving_average > str(code) : {str(code)}")
        logger.info(f"get_moving_average > history_date : {history_date}")
        logger.info(f"get_moving_average > history_code : {history_code}")
        logger.info(f"get_moving_average > history_price : {history_price}")
        logger.info(f"get_moving_average > history_qty : {history_qty}")
        logger.info(f"get_moving_average > history_flag : {history_flag}")

        self.tr_data.pop("opt10081", None)
        self.api.ocx.SetInputValue("종목코드", str(code))
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
        plt.plot(df.index, df['현재가'], label='현재가', color='black', linestyle='--')  # ✅ 현재가 선 추가
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
        plt.tight_layout()
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

    def get_google_news_test(self):
        try:
            news = get_google_news_snippets("미국 증시", count=10)
            return news
        except Exception as e:
            from logger import logger
            logger.error(f"[Google 뉴스 테스트 오류] {e}")
            return {"error": str(e)}

    def insert_macd(self, code, date, macd, signal, histogram):
        conn = sqlite3.connect("stock_indicators.db")
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO macd_data (code, date, macd, signal, histogram)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code, date) DO UPDATE SET
                macd = excluded.macd,
                signal = excluded.signal,
                histogram = excluded.histogram
        ''', (code, date, macd, signal, histogram))
        conn.commit()
        conn.close()

    def calculate_macd(self, prices, code, short_period=12, long_period=26, signal_period=9):
        short_ema = pd.Series(prices).ewm(span=short_period, adjust=False).mean()
        long_ema = pd.Series(prices).ewm(span=long_period, adjust=False).mean()
        macd_line = short_ema - long_ema
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        macd_histogram = macd_line - signal_line

        today = datetime.today().strftime('%Y-%m-%d')
        self.insert_macd(code, today, round(macd_line.iloc[-1], 2), round(signal_line.iloc[-1], 2), round(macd_histogram.iloc[-1], 2))

        return {
            "macd": round(macd_line.iloc[-1], 2),
            "signal": round(signal_line.iloc[-1], 2),
            "histogram": round(macd_histogram.iloc[-1], 2)
        }

    def analyze_macd(self, code):
        logger.info(f"analyze_macd > code : {code}")
        
        prices = self.get_close_prices(code, 0)
        close_values = [item['현재가'] for item in prices]
        close_values = close_values[::-1]  # 최신 데이터가 먼저이므로 반전

        if len(close_values) < 35:
            return {"error": "MACD 계산에 필요한 데이터 부족"}

        macd_result = self.calculate_macd(close_values, code)
        logger.info(f"MACD 정보: {macd_result}")
        return macd_result

    def get_price_data(self, code, count=30):
        """
        키움 API를 통해 일봉 데이터에서 고가, 저가, 현재가(종가)를 가져오는 함수
        """
        from datetime import datetime
        import pandas as pd

        logger.info(f"get_price_data > code : {code}")

        end_date = datetime.today().strftime('%Y%m%d')

        # 기존 데이터 초기화
        self.tr_data.pop("opt10081", None)

        # 요청 세팅
        self.api.ocx.SetInputValue("종목코드", code)
        self.api.ocx.SetInputValue("기준일자", end_date)
        self.api.ocx.SetInputValue("수정주가구분", "1")
        self.api.ocx.CommRqData("opt10081_req", "opt10081", 0, "5002")

        # 이벤트 루프 대기
        self.tr_event_loop.exec_()

        data = self.tr_data.get("opt10081", [])
        if not data or len(data) < 5:
            return []

        df = pd.DataFrame(data)
        df = df[['현재가', '고가', '저가']].copy()
        df = df.astype(int)
        df = df[::-1].reset_index(drop=True)  # 과거 → 최신 순으로 정렬

        result = df.to_dict(orient='records')  # 리스트[dict] 형식으로 변환

        if count == 0:
            return result
        else:
            return result[:count]  # 최신 기준 N개만 리턴

    def insert_stc(self, code, date, percent_k, percent_d):
        conn = sqlite3.connect("stock_indicators.db")
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO stc_data (code, date, percent_k, percent_d)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(code, date) DO UPDATE SET
                percent_k = excluded.percent_k,
                percent_d = excluded.percent_d
        ''', (code, date, percent_k, percent_d))
        conn.commit()
        conn.close()

    def calculate_slow_stochastic(self, highs, lows, closes, code, n=12, m=5, t=3):
        import pandas as pd

        df = pd.DataFrame({
            "High": highs[::-1],
            "Low": lows[::-1],
            "Close": closes[::-1]
        })

        # Raw %K
        df['lowest_low'] = df['Low'].rolling(window=n).min()
        df['highest_high'] = df['High'].rolling(window=n).max()

        df['%K_raw'] = (df['Close'] - df['lowest_low']) / (df['highest_high'] - df['lowest_low']) * 100

        # Slow %K (SMA of %K)
        df['%K'] = df['%K_raw'].rolling(window=m).mean()

        # Slow %D (SMA of Slow %K)
        df['%D'] = df['%K'].rolling(window=t).mean()

        last_k = round(df['%K'].iloc[-1], 2)
        last_d = round(df['%D'].iloc[-1], 2)

        today = datetime.today().strftime('%Y-%m-%d')
        self.insert_stc(code, today, last_k, last_d)

        return {
            "K": last_k
            ,"D": last_d
        }

    def analyze_stochastic(self, code):
        logger.info(f"analyze_stochastic > code : {code}")

        prices = self.get_price_data(code, 0)  # TR 요청해서 가격 가져옴

        if len(prices) < 20:
            return {"error": "데이터 부족"}

        closes = [p['현재가'] for p in prices]
        highs = [p['고가'] for p in prices]
        lows = [p['저가'] for p in prices]

        closes = closes[::-1]
        highs = highs[::-1]
        lows = lows[::-1]

        result = self.calculate_slow_stochastic(highs, lows, closes, code)
        logger.info(f"Slow Stochastic: {result}")

        close_values = closes[::-1]  # 최신 데이터가 먼저이므로 반전
        macd_result = self.calculate_macd(close_values, code)

        return {
            'stc':result
            ,'macd':macd_result
        }

    def calculate_slow_stochastic2(self, highs, lows, closes, code, n=12, m=5, t=3):
        import pandas as pd

        df = pd.DataFrame({
            "High": highs[::-1],
            "Low": lows[::-1],
            "Close": closes[::-1]
        })

        # Raw %K
        df['lowest_low'] = df['Low'].rolling(window=n).min()
        df['highest_high'] = df['High'].rolling(window=n).max()

        df['%K_raw'] = (df['Close'] - df['lowest_low']) / (df['highest_high'] - df['lowest_low']) * 100

        # Slow %K (SMA of %K)
        df['%K'] = df['%K_raw'].rolling(window=m).mean()

        # Slow %D (SMA of Slow %K)
        df['%D'] = df['%K'].rolling(window=t).mean()

        last_k = round(df['%K'].iloc[-1], 2)
        last_d = round(df['%D'].iloc[-1], 2)

        today = datetime.today().strftime('%Y-%m-%d')
        self.insert_stc(code, today, last_k, last_d)

        #---------------------- db 해당 code 로 (오늘을 포함)2일치 stc_data 테이블의 rows 를 조회 후 통합 조건 적용 ---------------------
        conn = sqlite3.connect("stock_indicators.db")
        cursor = conn.cursor()

        # 최근 2일치 데이터 조회
        cursor.execute("SELECT date, percent_k, percent_d FROM stc_data WHERE code=? ORDER BY date DESC LIMIT 2", (code,))
        stc_rows = cursor.fetchall()

        cursor.execute("SELECT date, macd, signal FROM macd_data WHERE code=? ORDER BY date DESC LIMIT 2", (code,))
        macd_rows = cursor.fetchall()

        cursor.execute("SELECT date, rsi FROM rsi_data WHERE code=? ORDER BY date DESC LIMIT 2", (code,))
        rsi_rows = cursor.fetchall()

        conn.close()

        # 정렬 (과거 → 최근)
        stc_rows = sorted(stc_rows)
        macd_rows = sorted(macd_rows)
        rsi_rows = sorted(rsi_rows)

        # 조건 1. STC 최소 2일 이상 연속 상승
        # stc_up = 'N'
        # if len(stc_rows) >= 2:
        #     k_vals = [r[1] for r in stc_rows[-2:]]
        #     if k_vals[0] < k_vals[1]:
        #         stc_up = 'Y'

        # 조건 2. MACD 최소 2일 이상 연속 상승
        # macd_up = 'N'
        # if len(macd_rows) >= 2:
        #     m_vals = [m[1] for m in macd_rows[-2:]]
        #     if m_vals[0] < m_vals[1]:
        #         macd_up = 'Y'

        # 조건 3. 오늘 MACD > Signal
        macd_break = 'N'
        if len(macd_rows) >= 1 and macd_rows[-1][1] > macd_rows[-1][2]:
            macd_break = 'Y'

        # 조건 4. 오늘 RSI > 50
        rsi_up = 'N'
        if len(rsi_rows) >= 1 and rsi_rows[-1][1] >= 50:
            rsi_up = 'Y'

        return {
            "K": last_k
            ,"D": last_d
            # ,"stc_up":stc_up
            # ,"macd_up":macd_up
            ,"macd_break":macd_break
            ,"rsi_up":rsi_up
        }
        #---------------------- db 해당 code 로 (오늘을 포함)2일치 stc_data 테이블의 rows 를 조회 후 통합 조건 적용 ---------------------

    def analyze_stochastic2(self, code):
        logger.info(f"analyze_stochastic2 > code : {code}")

        prices = self.get_price_data(code, 0)  # TR 요청해서 가격 가져옴

        if len(prices) < 20:
            return {"error": "데이터 부족"}

        closes = [p['현재가'] for p in prices]
        highs = [p['고가'] for p in prices]
        lows = [p['저가'] for p in prices]

        closes = closes[::-1]
        highs = highs[::-1]
        lows = lows[::-1]

        result = self.calculate_slow_stochastic2(highs, lows, closes, code)
        logger.info(f"Slow Stochastic: {result}")
        return result

    def insert_volume(self, code, date, volume):
        conn = sqlite3.connect("stock_indicators.db")
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO volume_data (code, date, volume)
            VALUES (?, ?, ?)
            ON CONFLICT(code, date) DO UPDATE SET
                volume = excluded.volume
        ''', (code, date, volume))
        conn.commit()
        conn.close()

    def insert_get_today_volume(self, code):
        today = datetime.today().strftime('%Y%m%d')
        prices = self.get_close_prices(code, 1)
        if not prices:
            return {"code": code, "error": "no data"}

        row = prices[0]
        volume = row.get('거래량', 0)
        try:
            volume = int(volume)
        except Exception:
            volume = 0

        self.insert_volume(code, today, volume)
        return {"code": code, "volume": volume}

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
                    high = self.api.ocx.GetCommData(trcode, rqname, i, "고가").strip()
                    low = self.api.ocx.GetCommData(trcode, rqname, i, "저가").strip()
                    volume = self.api.ocx.GetCommData(trcode, rqname, i, "거래량").strip()

                    try:
                        close = int(close)
                    except:
                        continue
                    try:
                        volume = int(volume.replace(',', ''))
                    except Exception:
                        volume = 0

                    rows.append({"일자": date, "현재가": close, "고가": high, "저가": low, "거래량": volume})
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
