import sys
import time
import threading
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop
from PyQt5.QtWidgets import QApplication
from logger import logger
from config import Config

class KiwoomAPI:
    """키움증권 API 클래스"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.connected = False
        self.login_event_loop = QEventLoop()
        self.order_event_loop = QEventLoop()
        
        # 이벤트 핸들러 연결
        self._connect_event_handlers()
    
    def _connect_event_handlers(self):
        """이벤트 핸들러 연결"""
        self.ocx.OnEventConnect.connect(self._on_event_connect)
        self.ocx.OnReceiveTrData.connect(self._on_receive_tr_data)
        self.ocx.OnReceiveRealData.connect(self._on_receive_real_data)
        self.ocx.OnReceiveChejanData.connect(self._on_receive_chejan_data)
        self.ocx.OnReceiveMsg.connect(self._on_receive_msg)
        self.ocx.OnReceiveTrCondition.connect(self._on_receive_tr_condition)
        self.ocx.OnReceiveRealCondition.connect(self._on_receive_real_condition)
    
    def connect(self):
        """키움증권 서버에 연결"""
        try:
            # logger.info("키움증권 서버 연결 시도...")
            result = self.ocx.CommConnect()
            
            if result == 0:
                self.login_event_loop.exec_()
                if self.connected:
                    # logger.log_connection("SUCCESS", "키움증권 서버 연결 성공")
                    return True
                else:
                    logger.log_connection("FAILED", "로그인 실패")
                    return False
            else:
                logger.log_connection("FAILED", f"연결 시도 실패 (에러코드: {result})")
                return False
                
        except Exception as e:
            logger.log_error("CONNECTION", str(e))
            return False
    
    def login(self):
        """로그인"""
        try:
            if not Config.USER_ID or not Config.USER_PASSWORD:
                logger.error("사용자 ID 또는 비밀번호가 설정되지 않았습니다.")
                return False
            
            logger.info("로그인 시도...")
            result = self.ocx.CommConnect()
            
            if result == 0:
                self.login_event_loop.exec_()
                return self.connected
            else:
                logger.log_error("LOGIN", f"로그인 시도 실패 (에러코드: {result})")
                return False
                
        except Exception as e:
            logger.log_error("LOGIN", str(e))
            return False
    
    def disconnect(self):
        """연결 해제"""
        try:
            self.ocx.CommTerminate()
            self.connected = False
            logger.log_connection("DISCONNECTED", "키움증권 서버 연결 해제")
        except Exception as e:
            logger.log_error("DISCONNECT", str(e))
    
    def get_connect_state(self):
        """연결 상태 확인"""
        try:
            return self.ocx.GetConnectState()
        except Exception as e:
            logger.log_error("GET_CONNECT_STATE", str(e))
            return 0
    
    def get_login_info(self, tag):
        """로그인 정보 조회"""
        logger.info(f"로그인 정보 조회")
        try:
            return self.ocx.GetLoginInfo(tag)
        except Exception as e:
            logger.log_error("GET_LOGIN_INFO", str(e))
            return ""
    
    def get_master_code_name(self, code):
        """종목코드에 해당하는 종목명 조회"""
        try:
            return self.ocx.GetMasterCodeName(code)
        except Exception as e:
            logger.log_error("GET_MASTER_CODE_NAME", str(e))
            return ""
    
    def get_master_last_price(self, code):
        """종목코드에 해당하는 최근 체결가 조회"""
        try:
            return self.ocx.GetMasterLastPrice(code)
        except Exception as e:
            logger.log_error("GET_MASTER_LAST_PRICE", str(e))
            return 0
    
    def get_master_stock_info(self, code):
        """종목코드에 해당하는 종목 정보 조회"""
        try:
            return self.ocx.GetMasterStockInfo(code)
        except Exception as e:
            logger.log_error("GET_MASTER_STOCK_INFO", str(e))
            return ""
    
    def get_code_list_by_market(self, market):
        """시장별 종목코드 리스트 조회"""
        try:
            return self.ocx.GetCodeListByMarket(market)
        except Exception as e:
            logger.log_error("GET_CODE_LIST_BY_MARKET", str(e))
            return ""
    
    # 이벤트 핸들러 메서드들
    def _on_event_connect(self, err_code):
        """로그인 이벤트"""
        if err_code == 0:
            self.connected = True
            logger.info("로그인 성공")
        else:
            self.connected = False
            logger.log_error("LOGIN", f"로그인 실패 (에러코드: {err_code})")
        
        self.login_event_loop.exit()
    
    def _on_receive_tr_data(self, screen_no, rqname, trcode, recordname, prev_next, data_len, error_code, message, splm_msg):
        """TR 수신 이벤트"""
        logger.debug(f"TR 수신: {rqname} - {trcode}")
    
    def _on_receive_real_data(self, code, real_type, real_data):
        """실시간 데이터 수신 이벤트"""
        logger.debug(f"실시간 데이터 수신: {code} - {real_type}")
    
    def _on_receive_chejan_data(self, gubun, item_cnt, fid_list):
        """체결잔고 데이터 수신 이벤트"""
        logger.debug(f"체결잔고 데이터 수신: {gubun}")
    
    def _on_receive_msg(self, screen_no, rqname, trcode, msg):
        """메시지 수신 이벤트"""
        logger.debug(f"메시지 수신: {msg}")
    
    def _on_receive_tr_condition(self, screen_no, codes, condition_name, condition_index, next):
        """조건검색 결과 수신 이벤트"""
        logger.debug(f"조건검색 결과: {condition_name}")
    
    def _on_receive_real_condition(self, code, type, condition_name, condition_index):
        """실시간 조건검색 결과 수신 이벤트"""
        logger.debug(f"실시간 조건검색: {code} - {condition_name}")
    
    def run(self):
        """이벤트 루프 실행"""
        self.app.exec_() 