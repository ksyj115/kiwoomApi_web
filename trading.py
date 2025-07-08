from PyQt5.QtCore import QEventLoop, QTimer
from config import Config
import logging
from logger import logger
import pandas as pd
import matplotlib.pyplot as plt
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

    def get_moving_average(self):

        # 조회할 종목코드
        code = "005930"  # 삼성전자

        # 일봉 데이터 요청
        df = self.api.ocx.block_request(
            "opt10081",
            종목코드=code,
            기준일자="20250628",
            수정주가구분=1,
            output="주식일봉차트조회",
            next=0
        )

        df = df.sort_values(by='일자')  # 날짜 오름차순
        df['일자'] = pd.to_datetime(df['일자'], format='%Y%m%d').dt.strftime('%Y-%m-%d')

        df['MA_5'] = df['현재가'].rolling(window=5).mean()
        df['MA_20'] = df['현재가'].rolling(window=20).mean()

        result = []
        for _, row in df.iterrows():
            result.append({
                'date': row['일자'],
                'close': row['현재가'],
                'ma_5': round(row['MA_5'], 2) if not pd.isna(row['MA_5']) else None,
                'ma_20': round(row['MA_20'], 2) if not pd.isna(row['MA_20']) else None
            })

        return result

    def get_stock_data(self, code="005930", end_date="20250628"):

        df = self.api.ocx.block_request(
            "opt10081",
            종목코드=code,
            기준일자=end_date,
            수정주가구분=1,
            output="주식일봉차트조회",
            next=0
        )

        df['현재가'] = df['현재가'].astype(int)
        df['일자'] = pd.to_datetime(df['일자'])
        df.sort_values('일자', inplace=True)

        df['MA5'] = df['현재가'].rolling(window=5).mean()
        df['MA20'] = df['현재가'].rolling(window=20).mean()
        df['MA60'] = df['현재가'].rolling(window=60).mean()
        df['MA120'] = df['현재가'].rolling(window=120).mean()

        return {
            "dates": df['일자'].dt.strftime('%Y-%m-%d').tolist(),
            "close": df['현재가'].tolist(),
            "MA5": df['MA5'].fillna('').tolist(),
            "MA20": df['MA20'].fillna('').tolist(),
            "MA60": df['MA60'].fillna('').tolist(),
            "MA120": df['MA120'].fillna('').tolist()
        }

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
        if len(df) < 3:
            return {'code': code, 'golden_cross': 'N', 'reason': 'not enough data'}

        # 최근 3일 기준 분석
        recent = df.iloc[-3:].copy()
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
        closest_ma = long_ma_candidates[min_idx]

        # 조건 체크
        # 가장 가까운 장기이평선 밑으로 1% 이내에 접근한 상태.          또는    가장 가까운 장기이평선 위로 1% 이내로 상승한 상태.
        cond1 = (abs(last_ma5 - closest_ma) / closest_ma <= 0.01) or ((last_ma5 - closest_ma) / closest_ma <= 0.01)
        # 3영업일 전 5일선이 최근 3일간 5일선 가격 중 가장 낮아야 함.
        cond2 = recent['MA5'].iloc[0] == min(ma5s)
        # 2영업일 전 5일선이 가장 최근 5일선 가격 보다 낮아야 함.
        cond3 = recent['MA5'].iloc[1] < recent['MA5'].iloc[2]
        # 가장 최근 5일선 가격이 가장 높아야 함.
        cond4 = recent['MA5'].iloc[2] == max(ma5s)
        # 3영업일 전 5일선은 가장 가까운 장기이평선 가격과 1% 이상의 차이로 하락한 상태.
        cond5 = recent['MA5'].iloc[0] < closest_ma and (abs(recent['MA5'].iloc[0] - closest_ma) / closest_ma > 0.01)

        all_conditions = all([cond1, cond2, cond3, cond4, cond5])   # 가장 이상적인 골든크로스(기대) 상태
        conditions = all([cond3, cond4, cond5])

        all_etc = ''
        if (last_ma5 - closest_ma) > 0 and ((last_ma5 - closest_ma) / closest_ma <= 0.01) and all_conditions:
            all_etc = '골든크로스 돌파! 5일선 추가 1% 상승전! (강력)매수 고려.'
        elif (last_ma5 - closest_ma) > 0 and ((last_ma5 - closest_ma) / closest_ma <= 0.02) and all_conditions:
            all_etc = '골든크로스 돌파! 5일선 추가 2% 상승전! (강력)후발 매수 고려.'
        elif (last_ma5 - closest_ma) > 0 and ((last_ma5 - closest_ma) / closest_ma <= 0.03) and all_conditions:
            all_etc = '골든크로스 돌파! 5일선 추가 3% 상승전! 차익 실현 조심하며 (눌림목)후발 매수 고려.'
        elif (last_ma5 - closest_ma) == 0 and conditions:
            all_etc = '골든크로스 발생! (골든크로스 돌파 확인하며 분할)매수.'
        elif (last_ma5 - closest_ma) < 0 and (abs(last_ma5 - closest_ma) / closest_ma <= 0.01) and conditions:
            all_etc = '골든크로스 발생 전 (1% 이내 근접). 매수 준비 고려.'
        elif (last_ma5 - closest_ma) < 0 and (abs(last_ma5 - closest_ma) / closest_ma <= 0.02) and conditions:
            all_etc = '골든크로스 발생 전 (2% 이내 근접). 골든크로스 시도 지켜볼 것.'
        elif (last_ma5 - closest_ma) < 0 and (abs(last_ma5 - closest_ma) / closest_ma <= 0.03) and conditions:
            all_etc = '골든크로스 발생 전 (3% 이내 근접). 골든크로스 시도 지켜볼 것.'

        return {'code': code, 'golden_cross': 'Y' if all_conditions else 'N', 'etc':all_etc}

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

                    logger.info(f"[trading.py] unfilled_orders_req => {code} | {name} | {qty} | {filled} | {price}")

                    orders.append({
                        "code": code,
                        "name": name,
                        "qty": int(qty.replace(",", "") or 0),
                        "filled": int(filled.replace(",", "") or 0),
                        "price": int(price.replace(",", "") or 0),
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

        finally:
            QTimer.singleShot(0, self.tr_event_loop.quit)
