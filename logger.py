import logging
import os
from datetime import datetime
from config import Config

class TradingLogger:
    """거래 로깅 클래스"""
    
    def __init__(self):
        self.logger = self._setup_logger()
    
    def _setup_logger(self):
        """로거 설정"""
        # 로거 생성
        logger = logging.getLogger('KiwoomTrading')
        logger.setLevel(getattr(logging, Config.LOG_LEVEL))
        
        # 이미 핸들러가 설정되어 있으면 추가하지 않음
        if logger.handlers:
            return logger
        
        # 파일 핸들러 설정
        file_handler = logging.FileHandler(Config.LOG_FILE, encoding='utf-8')
        file_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
        
        # 콘솔 핸들러 설정
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
        
        # 포맷터 설정
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 핸들러 추가
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def info(self, message):
        """정보 로그"""
        self.logger.info(message)
    
    def warning(self, message):
        """경고 로그"""
        self.logger.warning(message)
    
    def error(self, message):
        """에러 로그"""
        self.logger.error(message)
    
    def debug(self, message):
        """디버그 로그"""
        self.logger.debug(message)
    
    def critical(self, message):
        """치명적 오류 로그"""
        self.logger.critical(message)
    
    def log_trade(self, action, symbol, quantity, price, total_amount):
        """거래 로그"""
        trade_msg = f"TRADE: {action} | {symbol} | {quantity}주 | {price:,}원 | {total_amount:,}원"
        self.info(trade_msg)
    
    def log_connection(self, status, message=""):
        """연결 상태 로그"""
        conn_msg = f"CONNECTION: {status} {message}".strip()
        self.info(conn_msg)
    
    def log_error(self, error_type, error_message):
        """에러 로그"""
        error_msg = f"ERROR [{error_type}]: {error_message}"
        self.error(error_msg)

# 전역 로거 인스턴스
logger = TradingLogger() 