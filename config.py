import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    """키움증권 API 설정 클래스"""
    
    # 키움증권 API 설정
    USER_ID = os.getenv('KIWOOM_USER_ID', 'ksyj115')
    USER_PASSWORD = os.getenv('KIWOOM_USER_PASSWORD', '531011ks')
    CERT_PASSWORD = os.getenv('KIWOOM_CERT_PASSWORD', '')
    
    # 계좌 정보
    ACCNO = os.getenv('ACCNO', '8105608311')
    ACCNO_PASSWORD = os.getenv('ACCNO_PASSWORD', '0000')

    # 거래 설정
    TRADE_MODE = os.getenv('TRADE_MODE', 'SIMULATION')  # REAL 또는 SIMULATION
    MAX_POSITION_SIZE = int(os.getenv('MAX_POSITION_SIZE', 1000000))
    STOP_LOSS_RATE = float(os.getenv('STOP_LOSS_RATE', 0.02))
    TAKE_PROFIT_RATE = float(os.getenv('TAKE_PROFIT_RATE', 0.05))
    
    # 로깅 설정
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'kiwoom_trading.log')
    
    # API 설정
    API_VERSION = "0.1"
    CONNECT_TIMEOUT = 60  # 연결 타임아웃 (초)
    
    # 거래 시간 설정
    MARKET_OPEN_TIME = "09:00"
    MARKET_CLOSE_TIME = "15:30"
    
    @classmethod
    def is_simulation_mode(cls):
        """시뮬레이션 모드인지 확인"""
        return cls.TRADE_MODE.upper() == 'SIMULATION'
    
    @classmethod
    def is_real_mode(cls):
        """실제 거래 모드인지 확인"""
        return cls.TRADE_MODE.upper() == 'REAL' 