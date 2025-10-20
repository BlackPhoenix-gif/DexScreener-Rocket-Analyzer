import os
import dotenv
from pathlib import Path

# Загрузка переменных окружения из .env файла
dotenv.load_dotenv()

# Базовые настройки
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Создание необходимых директорий
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# API настройки
DEXSCREENER_API_URL = os.environ.get('DEXSCREENER_API_URL', 'https://api.dexscreener.com/latest/dex')
ETHERSCAN_API_URL = os.environ.get('ETHERSCAN_API_URL', 'https://api.etherscan.io/api')
BSCSCAN_API_URL = os.environ.get('BSCSCAN_API_URL', 'https://api.bscscan.com/api')

# API ключи
ETHERSCAN_API_KEY = os.environ.get('ETHERSCAN_API_KEY', '')
BSCSCAN_API_KEY = os.environ.get('BSCSCAN_API_KEY', '')

# Настройки производительности и лимитов
MAX_TOKENS_PER_HOUR = int(os.environ.get('MAX_TOKENS_PER_HOUR', 1000))
REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 30))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', 3))
RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', 10))
RATE_LIMIT_PERIOD = int(os.environ.get('RATE_LIMIT_PERIOD', 60))

# Оптимизированные настройки для ускорения сканирования
DEXSCREENER_CONCURRENCY = int(os.environ.get('DEXSCREENER_CONCURRENCY', 2))  # Одновременных запросов к DEXScreener (уменьшено для избежания 429)
GOPLUS_BATCH_SIZE = int(os.environ.get('GOPLUS_BATCH_SIZE', 25))              # Размер batch для GoPlus API
GOPLUS_CONCURRENCY = int(os.environ.get('GOPLUS_CONCURRENCY', 8))             # Одновременных batch-запросов к GoPlus
GOPLUS_RATE_LIMIT = int(os.environ.get('GOPLUS_RATE_LIMIT', 30))             # Запросов в минуту к GoPlus (снижено для избежания блокировок)
ETHERSCAN_RATE_LIMIT = int(os.environ.get('ETHERSCAN_RATE_LIMIT', 12))       # Запросов в минуту к Etherscan (1/5с)
BSCSCAN_RATE_LIMIT = int(os.environ.get('BSCSCAN_RATE_LIMIT', 12))           # Запросов в минуту к BscScan (1/5с)
RPC_CONCURRENCY = int(os.environ.get('RPC_CONCURRENCY', 10))                  # Одновременных RPC запросов

# Настройки кеширования - более агрессивное кеширование для снижения нагрузки на API
CACHE_ENABLED = bool(int(os.environ.get('CACHE_ENABLED', 1)))
CACHE_TTL = int(os.environ.get('CACHE_TTL', 1800))  # 30 минут (вместо стандартных 5 минут)
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# Критерии отбора "ракет" (обновленные)
MIN_PRICE_GROWTH_1H = float(os.environ.get('MIN_PRICE_GROWTH_1H', 20))
MIN_PRICE_GROWTH_24H = float(os.environ.get('MIN_PRICE_GROWTH_24H', 50))
MAX_PRICE_GROWTH_24H = float(os.environ.get('MAX_PRICE_GROWTH_24H', 999999))  # Практически не ограничено
MIN_LIQUIDITY = float(os.environ.get('MIN_LIQUIDITY', 50000))  # Увеличено до $50K
MIN_VOLUME_24H = float(os.environ.get('MIN_VOLUME_24H', 10000))  # Увеличено до $10K
MAX_TOKEN_AGE_HOURS = float(os.environ.get('MAX_TOKEN_AGE_HOURS', 168))  # 7 дней
MAX_VOLUME_LIQUIDITY_RATIO = float(os.environ.get('MAX_VOLUME_LIQUIDITY_RATIO', 20))

# Улучшенные критерии фильтрации
ENHANCED_MIN_LIQUIDITY = float(os.environ.get('ENHANCED_MIN_LIQUIDITY', 50000))
ENHANCED_MIN_VOLUME_24H = float(os.environ.get('ENHANCED_MIN_VOLUME_24H', 10000))
ENHANCED_MIN_HOLDERS = int(os.environ.get('ENHANCED_MIN_HOLDERS', 100))
ENHANCED_MIN_CONTRACT_AGE_DAYS = int(os.environ.get('ENHANCED_MIN_CONTRACT_AGE_DAYS', 7))
ENHANCED_MAX_PRICE_GROWTH_24H = float(os.environ.get('ENHANCED_MAX_PRICE_GROWTH_24H', 999999))  # Практически не ограничено
ENHANCED_MAX_VOLUME_LIQUIDITY_RATIO = float(os.environ.get('ENHANCED_MAX_VOLUME_LIQUIDITY_RATIO', 20))

# Настройки валидации
REQUIRE_VERIFIED_CONTRACT = os.environ.get('REQUIRE_VERIFIED_CONTRACT', 'true').lower() == 'true'
REQUIRE_DEX_PRESENCE = os.environ.get('REQUIRE_DEX_PRESENCE', 'true').lower() == 'true'
EXCLUDE_FAKE_TOKENS = os.environ.get('EXCLUDE_FAKE_TOKENS', 'true').lower() == 'true'

# API ключи для блокчейн-сканеров
ETHERSCAN_API_KEY = os.environ.get('ETHERSCAN_API_KEY', '')
BSCSCAN_API_KEY = os.environ.get('BSCSCAN_API_KEY', '')
POLYGONSCAN_API_KEY = os.environ.get('POLYGONSCAN_API_KEY', '')
ARBISCAN_API_KEY = os.environ.get('ARBISCAN_API_KEY', '')

# Настройки логирования
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
LOG_TO_FILE = os.environ.get('LOG_TO_FILE', 'true').lower() == 'true'
LOG_FILENAME = os.environ.get('LOG_FILENAME', str(LOGS_DIR / 'raket.log'))

# Поддерживаемые блокчейны
SUPPORTED_CHAINS = {
    'ethereum': {
        'name': 'Ethereum',
        'scanner_url': 'https://etherscan.io',
        'api_url': ETHERSCAN_API_URL,
        'api_key': ETHERSCAN_API_KEY
    },
    'bsc': {
        'name': 'Binance Smart Chain',
        'scanner_url': 'https://bscscan.com',
        'api_url': BSCSCAN_API_URL,
        'api_key': BSCSCAN_API_KEY
    },
    'polygon': {
        'name': 'Polygon',
        'scanner_url': 'https://polygonscan.com',
        'api_url': os.environ.get('POLYGONSCAN_API_URL', 'https://api.polygonscan.com/api'),
        'api_key': os.environ.get('POLYGONSCAN_API_KEY', '')
    },
    'arbitrum': {
        'name': 'Arbitrum',
        'scanner_url': 'https://arbiscan.io',
        'api_url': os.environ.get('ARBISCAN_API_URL', 'https://api.arbiscan.io/api'),
        'api_key': os.environ.get('ARBISCAN_API_KEY', '')
    }
}

# Настройки отчетов
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)
DEFAULT_REPORT_FORMAT = os.environ.get('DEFAULT_REPORT_FORMAT', 'json')

# Функция для получения путей к файлам данных
def get_data_file_path(filename):
    """
    Получает полный путь к файлу данных
    
    Args:
        filename: Имя файла
        
    Returns:
        Path: Полный путь к файлу
    """
    return DATA_DIR / filename 

class Config:
    def __init__(self):
        for key, value in globals().items():
            if key.isupper():
                setattr(self, key, value)

config = Config() 