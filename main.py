#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import signal
from datetime import datetime
from kiwoom_api import KiwoomAPI
from trading import Trading
from logger import logger
from config import Config

class KiwoomTradingApp:
    """키움증권 자동매매 애플리케이션"""
    
    def __init__(self):
        self.api = None
        self.trading = None
        self.running = False
        
        # 시그널 핸들러 설정
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # logger.info("키움증권 자동매매 프로그램 시작")
    
    def initialize(self):
        """초기화"""
        try:
            # logger.info("시스템 초기화 중...")
            
            # 키움증권 API 초기화
            self.api = KiwoomAPI()
            
            # 거래 기능 초기화
            self.trading = Trading(self.api)
            
            # logger.info("시스템 초기화 완료")
            return True
            
        except Exception as e:
            logger.log_error("INITIALIZATION", str(e))
            return False
    
    def connect(self):
        """키움증권 서버 연결"""
        try:
            # logger.info("키움증권 서버 연결 시도...")
            
            if self.api.connect():
                # logger.info("키움증권 서버 연결 성공")
                
                # 계좌 정보 출력
                account_info = self.trading.get_account_info()
                if account_info:
                    logger.info("==================== 계좌 정보 ====================")
                    for key, value in account_info.items():
                        logger.info(f"{key}: {value}")

                    
                
                total = self.trading.get_total_investment()
                available = self.trading.get_available_funds()
                holdings = self.trading.get_holdings()

                logger.info("")
                logger.info(f"총 투자금액: {total:,}원")
                logger.info(f"주문 가능 금액: {available:,}원")
                logger.info("===================================================")
                logger.info("")
                logger.info("")
                logger.info("")

                if holdings:
                    logger.info("************************************** 보유 종목 **************************************")
                    for h in holdings:
                        logger.info(f"{h['name']} (종목코드 : {h['code']}) [ 현재가 : {h['current_price']:,}원 ]")
                        logger.info(f"[ 내평균 : {h['purchase_price']:,}원 ] [ 보유수량 : {h['quantity']}주 ]")
                        logger.info(f"평가금 : {((h['purchase_price'] * h['quantity']) + ((h['current_price'] - h['purchase_price']) * h['quantity'])):,}원")
                        logger.info(f"손익상태 : {((h['current_price'] - h['purchase_price']) * h['quantity']):,}원 ({round((((h['current_price'] - h['purchase_price']) * h['quantity']) / (h['purchase_price'] * h['quantity']))*100, 2)}%)")
                        logger.info("")
                    logger.info("***************************************************************************************")
                    logger.info("")
                    logger.info("")
                    logger.info("")
                else:
                    logger.info("************************************** 보유 종목 **************************************")
                    logger.info("보유 종목이 없습니다.")  
                    logger.info("***************************************************************************************")
                    logger.info("")
                    logger.info("")
                    logger.info("")
                return True
            else:
                logger.error("키움증권 서버 연결 실패")
                return False
                
        except Exception as e:
            logger.log_error("CONNECT", str(e))
            return False
    
    def test_basic_functions(self):
        """기본 기능 테스트"""
        try:
            logger.debug("기본 기능 테스트 시작...")
            
            # 연결 상태 확인
            connect_state = self.api.get_connect_state()
            logger.debug(f"연결 상태: {connect_state}")
            
            # 삼성전자 종목 정보 조회 테스트
            # samsung_code = "005930"
            # samsung_name = self.trading.get_stock_name(samsung_code)
            # samsung_price = self.trading.get_stock_price(samsung_code)
            
            # if samsung_name and samsung_price > 0:
            #     logger.info(f"테스트 종목: {samsung_name}({samsung_code}) - {samsung_price:,}원")
            # else:
            #     logger.warning("종목 정보 조회 실패")
            
            # 시뮬레이션 모드에서 매수/매도 테스트
            # if Config.is_simulation_mode():
            #     logger.info("시뮬레이션 모드에서 거래 테스트...")
                
            #     # 매수 테스트
            #     if self.trading.buy_stock(samsung_code, 1):
            #         logger.info("매수 테스트 성공")
            #     else:
            #         logger.error("매수 테스트 실패")
                
            #     # 매도 테스트
            #     if self.trading.sell_stock(samsung_code, 1):
            #        logger.info("매도 테스트 성공")
            #     else:
            #        logger.error("매도 테스트 실패")
            
            # logger.info("기본 기능 테스트 완료")
            return True
            
        except Exception as e:
            logger.log_error("TEST_FUNCTIONS", str(e))
            return False
    
    def test_get_top_stocks_functions(self):
        """거래량 상위 종목 조회 기능 테스트"""
        try:
            stocks = self.trading.get_stocks()
            if stocks:
                logger.info("************************************** 거래량 상위 종목 **************************************")
                for s in stocks:
                    logger.info(f"({s['code']}) {s['name']} | 거래량: {s['vol']:,}주 | 거래금액: {int((round(s['amount'], -2))/100):,}억원 | 현재가: {abs(s['price']):,}원")
                logger.info("*********************************************************************************************")
                logger.info("")
                logger.info("")
                logger.info("")
            else:
                logger.info("거래량 상위 종목이 없습니다.")
            return True

        except Exception as e:
            logger.log_error("TEST_GET_STOCKS", str(e))
            return False

    def test_get_upsurge_stocks_functions(self):
        """거래량 급증 상위 종목 조회 기능 테스트"""
        try:
            upsurge_stocks = self.trading.get_upsurge_stocks()
            if upsurge_stocks:
                logger.info("************************************** 거래량 급증 상위 종목 **************************************")
                for u in upsurge_stocks:
                    logger.info(f"({u['code']}) {u['name']} | 이전거래량: {u['pre_vol']:,}주 | 현재거래량: {u['cur_vol']:,}주 | 등락률: {u['fluctuation_rate']} | 현재가: {abs(u['price']):,}원")
                logger.info("*************************************************************************************************")
                logger.info("")
                logger.info("")
                logger.info("")
            else:
                logger.info("거래량 급증 상위 종목이 없습니다.")
            return True

        except Exception as e:
            logger.log_error("TEST_GET_UPSURGE_STOCKS", str(e))
            return False
            
            
            

    def run(self):
        """메인 실행 루프"""
        try:
            self.running = True
            
            # 초기화
            if not self.initialize():
                logger.error("초기화 실패")
                return False
            
            # 연결
            if not self.connect():
                logger.error("연결 실패")
                return False
            
            # 기본 기능 테스트
            if not self.test_basic_functions():
                logger.error("기본 기능 테스트 실패")
                return False

            # 거래량 상위 종목 조회 기능 테스트
            if not self.test_get_top_stocks_functions():
                logger.error("거래량 상위 종목 조회 기능 테스트 실패")
                return False

            # 거래량 급증 상위 종목 조회 기능 테스트
            if not self.test_get_upsurge_stocks_functions():
                logger.error("거래량 급증 상위 종목 조회 기능 테스트 실패")
                return False
            
            # 이벤트 루프 실행
            self.api.run()
            
        except KeyboardInterrupt:
            logger.info("사용자에 의해 프로그램이 중단되었습니다.")
        except Exception as e:
            logger.log_error("MAIN_LOOP", str(e))
        finally:
            self.cleanup()
    
    def cleanup(self):
        """정리 작업"""
        try:
            logger.info("프로그램 정리 중...")
            
            if self.api:
                self.api.disconnect()
            
            self.running = False
            logger.info("프로그램이 정상적으로 종료되었습니다.")
            
        except Exception as e:
            logger.log_error("CLEANUP", str(e))
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        logger.info(f"시그널 {signum} 수신, 프로그램 종료 중...")
        self.cleanup()
        sys.exit(0)

def main():
    """메인 함수"""
    try:
        # 설정 정보 출력
        logger.info("============= 키움증권 자동매매 프로그램 =============")
        logger.info(f"거래 모드: {Config.TRADE_MODE}")
        # logger.info(f"최대 포지션 크기: {Config.MAX_POSITION_SIZE:,}원")
        # logger.info(f"손절 비율: {Config.STOP_LOSS_RATE*100}%")
        # logger.info(f"익절 비율: {Config.TAKE_PROFIT_RATE*100}%")
        logger.info("======================================================")
        logger.info("")
        logger.info("")
        logger.info("")
        
        # 애플리케이션 실행
        app = KiwoomTradingApp()
        app.run()
        
    except Exception as e:
        logger.log_error("MAIN", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main() 