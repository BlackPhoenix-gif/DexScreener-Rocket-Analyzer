import os
import json
import time
import random
import logging
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Set, Tuple
import requests
from datetime import datetime, timedelta
from tqdm import tqdm
from pathlib import Path
import argparse

from src.utils.logger import get_logger
from src.models.token import Token, TokenPair
from src.config import config
from src.analysis.perspective_tokens.token_data_saver import TokenDataSaver

logger = get_logger()

# Создаем директорию для кеша если её нет
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

# Время жизни кеша в секундах (по умолчанию 1 час)
CACHE_TTL = int(os.getenv("DEXSCREENER_CACHE_TTL", "3600"))

def get_cache_path(network: str, query: str) -> Path:
    """
    Возвращает путь к файлу кеша для конкретного запроса
    """
    # Создаем безопасное имя файла
    safe_query = "".join(c for c in query if c.isalnum() or c in ('-', '_')).rstrip()
    return CACHE_DIR / f"{network}_{safe_query}.json"

def is_cache_valid(cache_path: Path) -> bool:
    """
    Проверяет, действителен ли кеш
    """
    if not cache_path.exists():
        return False
        
    # Проверяем время создания файла
    cache_time = cache_path.stat().st_mtime
    current_time = time.time()
    
    return (current_time - cache_time) < CACHE_TTL

def save_to_cache(network: str, query: str, data: Dict) -> None:
    """
    Сохраняет данные в кеш
    """
    cache_path = get_cache_path(network, query)
    try:
        with open(cache_path, 'w') as f:
            json.dump({
                'timestamp': time.time(),
                'data': data
            }, f)
    except Exception as e:
        logger.error(f"Ошибка при сохранении в кеш: {str(e)}")

def load_from_cache(network: str, query: str) -> Optional[Dict]:
    """
    Загружает данные из кеша
    """
    cache_path = get_cache_path(network, query)
    try:
        if is_cache_valid(cache_path):
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
                return cache_data['data']
    except Exception as e:
        logger.error(f"Ошибка при загрузке из кеша: {str(e)}")
    return None

def clean_old_cache():
    """
    Удаляет все устаревшие кеш-файлы
    """
    try:
        if not CACHE_DIR.exists():
            return
            
        current_time = time.time()
        deleted_count = 0
        
        for cache_file in CACHE_DIR.glob("*.json"):
            try:
                # Проверяем время создания файла
                cache_time = cache_file.stat().st_mtime
                if (current_time - cache_time) >= CACHE_TTL:
                    cache_file.unlink()
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Ошибка при удалении кеш-файла {cache_file}: {str(e)}")
                
        if deleted_count > 0:
            logger.info(f"Удалено {deleted_count} устаревших кеш-файлов")
            
    except Exception as e:
        logger.error(f"Ошибка при очистке кеша: {str(e)}")

# Словарь с блокчейн-эксплорерами для разных сетей
explorers = {
    'solana': 'https://solscan.io/token/',
    'base': 'https://basescan.org/token/',
    'ethereum': 'https://etherscan.io/token/',
    'bsc': 'https://bscscan.com/token/',
    'arbitrum': 'https://arbiscan.io/token/',
    'polygon': 'https://polygonscan.com/token/',
    'optimism': 'https://optimistic.etherscan.io/token/',
    'avalanche': 'https://snowtrace.io/token/',
    'fantom': 'https://ftmscan.com/token/',
    'cronos': 'https://cronoscan.com/token/',
    'pulsechain': 'https://scan.pulsechain.com/token/',
    'polygon_zkevm': 'https://zkevm.polygonscan.com/token/',
    'linea': 'https://lineascan.build/token/',
    'manta': 'https://pacific-explorer.manta.network/token/',
    'mantle': 'https://explorer.mantle.xyz/token/',
    'blast': 'https://blastscan.io/token/',
    'mode': 'https://explorer.mode.network/token/',
    'scroll': 'https://scrollscan.com/token/',
    'zksync': 'https://explorer.zksync.io/token/',
    'starknet': 'https://starkscan.co/token/',
    'celo': 'https://celoscan.io/token/',
    'gnosis': 'https://gnosisscan.io/token/',
    'core': 'https://scan.coredao.org/token/',
    'kava': 'https://explorer.kava.io/token/',
    'metis': 'https://andromeda-explorer.metis.io/token/',
    'moonbeam': 'https://moonscan.io/token/',
    'moonriver': 'https://moonriver.moonscan.io/token/',
    'harmony': 'https://explorer.harmony.one/token/',
    'aurora': 'https://aurorascan.dev/token/',
    'near': 'https://explorer.near.org/token/',
    'sui': 'https://suiexplorer.com/token/',
    'aptos': 'https://explorer.aptoslabs.com/token/',
    'sei': 'https://sei.explorers.guru/token/',
    'injective': 'https://explorer.injective.network/token/',
    'osmosis': 'https://www.mintscan.io/osmosis/token/',
    'cosmos': 'https://www.mintscan.io/cosmos/token/',
    'thorchain': 'https://viewblock.io/thorchain/token/'
}

def play_completion_sound():
    """Воспроизводит звук при завершении сканирования"""
    try:
        # Увеличиваем громкость до максимума
        os.system('osascript -e "set volume output volume 100"')
        
        # Воспроизводим звук
        os.system('afplay /System/Library/Sounds/Glass.aiff')
        
        # Устанавливаем громкость на 40
        time.sleep(0.5)
        os.system('osascript -e "set volume output volume 40"')
        
        # Дополнительная проверка через 1 секунду
        time.sleep(1)
        os.system('osascript -e "set volume output volume 40"')
        
        logger.info("[SYSTEM] Воспроизведен звук завершения сканирования. Установлена громкость: 40")
    except Exception as e:
        logger.error(f"[SYSTEM] Ошибка при воспроизведении звука: {str(e)}")

class TokenScanner:
    """
    Класс для сканирования криптовалютных токенов.
    Предоставляет методы для получения данных о токенах и их анализа.
    """
    
    def __init__(self, test_mode: bool = False):
        """
        Инициализация клиента для сканирования криптовалютных токенов.
        
        Args:
            test_mode: Режим тестирования с сокращенным списком токенов
        """
        self.base_url = "https://api.dexscreener.com/latest/dex"
        self.session = requests.Session()
        self.test_mode = test_mode
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        })
        self.timeout = int(os.getenv("DEXSCREENER_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("DEXSCREENER_MAX_RETRIES", "3"))
        self.min_liquidity = float(os.getenv("DEXSCREENER_MIN_LIQUIDITY", "50" if test_mode else "250"))
        self.min_volume_24h = float(os.getenv("DEXSCREENER_MIN_VOLUME_24H", "25" if test_mode else "100"))
        self.logger = logging.getLogger("dexscreener")
        
        # Создаем директорию для логов если её нет
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Создаем файлы логов с текущей датой
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = self.log_dir / f"token_analysis_{timestamp}.log"
        self.rockets_analysis_file = self.log_dir / f"rockets_analysis_{timestamp}.log"
        
        # Настраиваем файловый логгер для анализа токенов
        self.file_logger = logging.getLogger("token_analysis")
        self.file_logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        self.file_logger.addHandler(file_handler)
        
        # Настраиваем файловый логгер для анализа ракет
        self.rockets_logger = logging.getLogger("rockets_analysis")
        self.rockets_logger.setLevel(logging.DEBUG)
        rockets_handler = logging.FileHandler(self.rockets_analysis_file)
        rockets_handler.setLevel(logging.DEBUG)
        rockets_handler.setFormatter(formatter)
        self.rockets_logger.addHandler(rockets_handler)
        
        # Расширенный список User-Agent для ротации
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        ]
        
        logger.info(f"[СКАНИРОВАНИЕ] Инициализация клиента ({self.base_url})")
        logger.debug(f"[СКАНИРОВАНИЕ] Настройки: таймаут={self.timeout}с, макс.повторы={self.max_retries}")
        self.file_logger.info("=== Начало анализа токенов ===")
        self.file_logger.info(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.file_logger.info(f"Критерии фильтрации:")
        self.file_logger.info(f"- Минимальный рост цены: 5%")
        self.file_logger.info(f"- Максимальный рост цены: 1000%")
        self.file_logger.info(f"- Минимальная ликвидность: $250")
        self.file_logger.info(f"- Минимальный объем торгов: $100")
        self.file_logger.info("=" * 50)
    
    def _get_tokens_to_analyze(self) -> List[Tuple[str, str]]:
        """
        Возвращает список токенов для анализа в формате (сеть, токен).
        
        Returns:
            List[Tuple[str, str]]: Список кортежей (сеть, токен)
        """
        tokens_to_analyze = []
        
        # Используем тестовый список сетей и токенов если включен тестовый режим
        networks = get_test_networks() if self.test_mode else {
            'solana': [
                'SOL', 'BONK', 'RAY', 'SRM', 'MNGO', 'SAMO', 'ORCA', 'ATLAS', 'POLIS', 'GST', 'SBR',
                'JUP', 'PYTH', 'WIF', 'MYRO', 'POPCAT', 'WEN', 'SLERF', 'BOME', 'MEME'
            ],
            'base': [
                'ETH', 'WETH', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI', 'CRV',
                'USDC', 'USDT', 'DAI', 'WBTC', 'BAL', 'BOND', 'DPI', 'ENJ', 'GRT', 'KNC'
            ],
            'ethereum': [
                'ETH', 'WETH', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI', 'CRV',
                'SHIB', 'PEPE', 'DOGE', 'MATIC', 'AVAX', 'FTM', 'USDC', 'USDT', 'DAI', 'WBTC'
            ],
            'bsc': [
                'BNB', 'CAKE', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX',
                'YFI', 'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BUSD', 'TUSD'
            ],
            'arbitrum': [
                'ETH', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                'CRV', 'MATIC', 'AVAX', 'FTM', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND'
            ],
            'polygon': [
                'MATIC', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND'
            ],
            'optimism': [
                'ETH', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                'CRV', 'MATIC', 'AVAX', 'FTM', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND'
            ],
            'avalanche': [
                'AVAX', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND'
            ],
            'fantom': [
                'FTM', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                'CRV', 'MATIC', 'AVAX', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND', 'DPI'
            ],
            'cronos': [
                'CRO', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND'
            ]
        }
        
        # Формируем список токенов для анализа
        for network, tokens in networks.items():
            for token in tokens:
                tokens_to_analyze.append((network, token))
                
        return tokens_to_analyze

    async def _make_async_request(self, session: aiohttp.ClientSession, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Асинхронный HTTP запрос к API DEXScreener.
        """
        url = f"{self.base_url}/{endpoint}"
        user_agent = random.choice(self.user_agents)
        headers = {"User-Agent": user_agent}
        
        for attempt in range(self.max_retries):
            try:
                async with session.get(url, params=params, headers=headers, timeout=self.timeout) as response:
                    response.raise_for_status()
                    return await response.json()
            except Exception as e:
                if attempt == self.max_retries - 1:
                    self.logger.error(f"API error: {str(e)}")
                    return {}
                await asyncio.sleep(2 ** attempt + random.random())
        
        return {}

    async def _fetch_pairs(self, session: aiohttp.ClientSession, network: str, query: str) -> List[Dict]:
        """
        Асинхронный запрос пар для токена в сети с использованием кеша.
        """
        try:
            # Проверяем кеш
            cached_data = load_from_cache(network, query)
            if cached_data:
                logger.debug(f"Используем кешированные данные для '{query}' в сети {network}")
                return cached_data.get("pairs", [])
            
            # Если данных нет в кеше, делаем запрос к API
            response = await self._make_async_request(session, "search", {
                "q": query,
                "chain": network
            })
            
            if not response or "pairs" not in response:
                self.logger.warning(f"Некорректный ответ для '{query}' в сети {network}")
                return []
            
            # Сохраняем результат в кеш
            save_to_cache(network, query, response)
            
            return response.get("pairs", [])
            
        except Exception as e:
            self.logger.error(f"Ошибка при поиске '{query}' в сети {network}: {str(e)}")
            return []

    async def get_latest_token_profiles_async(self) -> List[Dict]:
        """
        Асинхронное получение последних профилей токенов.
        """
        logger.info("[СКАНИРОВАНИЕ] Получение последних профилей токенов")
        try:
            networks = get_test_networks() if self.test_mode else {
                'solana': [
                    'SOL', 'BONK', 'RAY', 'SRM', 'MNGO', 'SAMO', 'ORCA', 'ATLAS', 'POLIS', 'GST', 'SBR',
                    'JUP', 'PYTH', 'WIF', 'MYRO', 'POPCAT', 'WEN', 'SLERF', 'BOME', 'MEME'
                ],
                'base': [
                    'ETH', 'WETH', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI', 'CRV',
                    'USDC', 'USDT', 'DAI', 'WBTC', 'WETH', 'BAL', 'BOND', 'DPI', 'ENJ', 'GRT',
                    'KNC', 'LDO', 'LRC', 'MKR', 'NMR', 'OXT', 'PAX', 'REN', 'REP', 'SUSHI',
                    'SXP', 'TUSD', 'UMA', 'UNI', 'USDT', 'WBTC', 'WETH', 'YFI', 'ZRX', 'BAL',
                    'BAT', 'BOND', 'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT',
                    'PAX', 'REN', 'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT'
                ],
                'ethereum': [
                    'ETH', 'WETH', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI', 'CRV',
                    'SHIB', 'PEPE', 'DOGE', 'MATIC', 'AVAX', 'FTM', 'USDC', 'USDT', 'DAI', 'WBTC',
                    'BAL', 'BAT', 'BOND', 'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR',
                    'OXT', 'PAX', 'REN', 'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL',
                    'BAT', 'BOND', 'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT',
                    'PAX', 'REN', 'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT'
                ],
                'bsc': [
                    'BNB', 'CAKE', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX',
                    'YFI', 'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BUSD', 'TUSD',
                    'BAL', 'BAT', 'BOND', 'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR',
                    'OXT', 'PAX', 'REN', 'REP', 'SUSHI', 'SXP', 'UMA', 'ZRX', 'BAL', 'BAT',
                    'BOND', 'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX',
                    'REN', 'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND'
                ],
                'arbitrum': [
                    'ETH', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'MATIC', 'AVAX', 'FTM', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND',
                    'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN',
                    'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI',
                    'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN', 'REP',
                    'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI', 'ENJ'
                ],
                'polygon': [
                    'MATIC', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND',
                    'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN',
                    'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI',
                    'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN', 'REP',
                    'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI', 'ENJ'
                ],
                'optimism': [
                    'ETH', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'MATIC', 'AVAX', 'FTM', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND',
                    'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN',
                    'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI',
                    'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN', 'REP',
                    'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI', 'ENJ'
                ],
                'avalanche': [
                    'AVAX', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND',
                    'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN',
                    'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI',
                    'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN', 'REP',
                    'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI', 'ENJ'
                ],
                'fantom': [
                    'FTM', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'MATIC', 'AVAX', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND', 'DPI',
                    'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN', 'REP',
                    'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI', 'ENJ',
                    'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN', 'REP', 'SUSHI',
                    'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI', 'ENJ', 'GRT'
                ],
                'cronos': [
                    'CRO', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND',
                    'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN',
                    'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI',
                    'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN', 'REP',
                    'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BAL', 'BAT', 'BOND', 'DPI', 'ENJ'
                ]
            }
            
            all_pairs = []
            total_requests = sum(len(queries) for queries in networks.values())
            logger.info(f"[СКАНИРОВАНИЕ] Всего запросов: {total_requests}")
            
            # Сбрасываем счетчики перед началом
            found_tokens = 0
            filtered_tokens = 0
            
            # Создаем новый прогресс-бар с нуля
            with tqdm(total=total_requests, desc="Поиск токенов", unit="запрос", 
                     position=0, leave=True, 
                     bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}, {postfix}]') as pbar:
                async with aiohttp.ClientSession() as session:
                    # Обрабатываем сети последовательно
                    for network, queries in networks.items():
                        # Обрабатываем токены в каждой сети с задержкой
                        for query in queries:
                            try:
                                # Проверяем кеш перед запросом
                                cached_data = load_from_cache(network, query)
                                if cached_data:
                                    # Для кешированных данных не делаем задержку
                                    pairs = cached_data.get("pairs", [])
                                else:
                                    # Задержка только для новых запросов к API
                                    await asyncio.sleep(random.uniform(1, 3))
                                    pairs = await self._fetch_pairs(session, network, query)
                                
                                if pairs:
                                    # Фильтруем пары по критериям
                                    filtered_pairs = [pair for pair in pairs if self._is_rocket_token(pair)]
                                    found_tokens += len(pairs)
                                    filtered_tokens += len(filtered_pairs)
                                    all_pairs.extend(filtered_pairs)  # Добавляем отфильтрованные пары
                                    self.logger.info(f"Найдено {len(pairs)} пар, из них {len(filtered_pairs)} прошли фильтр для '{query}' в сети {network}")
                                pbar.set_postfix({'Всего токенов': found_tokens, 'Прошли фильтр': filtered_tokens})
                                pbar.update(1)
                            except Exception as e:
                                self.logger.error(f"Ошибка при обработке '{query}' в сети {network}: {str(e)}")
                                pbar.update(1)
            
            if not all_pairs:
                self.logger.warning("Не найдено ни одной пары")
                return []
            
            # Удаляем дубликаты по адресу токена
            unique_pairs = {pair["baseToken"]["address"]: pair for pair in all_pairs}.values()
            self.logger.info(f"Всего найдено {len(unique_pairs)} уникальных пар")
            return list(unique_pairs)
            
        except Exception as e:
            self.logger.error(f"[СКАНИРОВАНИЕ] Критическая ошибка при получении профилей токенов: {str(e)}")
            return []

    def get_token_pairs(self, chain_id: str, token_address: str) -> List[Dict]:
        """
        Получает все пары для указанного токена.
        
        Args:
            chain_id: Идентификатор блокчейна
            token_address: Адрес токена
            
        Returns:
            List[Dict]: Список пар токена
        """
        logger.info(f"[СКАНИРОВАНИЕ] Получение пар для токена {token_address} на {chain_id}")
        try:
            return self._make_request(f"tokens/{chain_id}/{token_address}")
        except Exception as e:
            self.logger.error(f"[СКАНИРОВАНИЕ] Ошибка при получении пар токена: {str(e)}")
            return []
    
    def _log_token_analysis(self, token: Dict, profile: Dict, reason: str = None):
        """
        Логирует краткий анализ токена в файл
        """
        self.file_logger.info("\n" + "=" * 30)
        self.file_logger.info(f"Токен: {token['symbol']} ({token['address'][:8]}...)")
        self.file_logger.info(f"Сеть: {profile['chainId']}")
        
        # Ключевые показатели
        price_change_24h = float(profile.get("priceChange", {}).get("h24", 0))
        liquidity_usd = float(profile.get("liquidity", {}).get("usd", 0))
        volume_24h = float(profile.get("volume", {}).get("h24", 0))
        
        self.file_logger.info(f"Рост 24ч: {price_change_24h:.2f}% | Ликвидность: ${liquidity_usd:.2f} | Объем: ${volume_24h:.2f}")
        
        if reason:
            self.file_logger.info(f"❌ Отклонен: {reason}")
        else:
            self.file_logger.info("✅ Принят")
        
        self.file_logger.info("=" * 30)

    def _analyze_rocket(self, token: Dict) -> str:
        """
        Анализирует найденную ракету и возвращает подробный отчет
        """
        profile = token['profile']
        price_change_24h = token['price_change_24h']
        liquidity_usd = token['liquidity_usd']
        volume_24h = token['volume_24h']
        age_hours = token['age_hours']
        price_usd = float(profile.get('priceUsd', 0))
        
        # Рассчитываем дополнительные метрики
        volume_to_liquidity_ratio = volume_24h / liquidity_usd if liquidity_usd > 0 else 0
        age_days = round(age_hours / 24, 2)
        
        # Анализ импульса цены
        price_changes = profile.get('priceChange', {})
        momentum = (
            float(price_changes.get('h1', 0)) * 0.2 +
            float(price_changes.get('h6', 0)) * 0.3 +
            float(price_changes.get('h24', 0)) * 0.5
        )
        
        # Расчет скоров
        liquidity_score = min(100, (liquidity_usd / 100000) * 100)
        volume_score = min(100, (volume_24h / 50000) * 100)
        momentum_score = min(100, max(0, 50 + momentum))
        stability_score = min(100, volume_to_liquidity_ratio * 100)
        age_score = min(100, (age_days / 30) * 100)
        
        # Общий риск-скор (0-100, чем ниже тем лучше)
        risk_score = (
            (100 - liquidity_score) * 0.3 +
            (100 - volume_score) * 0.2 +
            (100 - stability_score) * 0.2 +
            (100 - age_score) * 0.15 +
            (100 - momentum_score) * 0.15
        )
        
        # Определяем категории показателей
        liquidity_category = "высокая" if liquidity_usd > 100000 else "средняя" if liquidity_usd > 10000 else "низкая"
        volume_category = "высокий" if volume_24h > 100000 else "средний" if volume_24h > 10000 else "низкий"
        growth_category = "высокий" if price_change_24h > 50 else "умеренный" if price_change_24h > 20 else "низкий"
        risk_category = "низкий" if risk_score < 30 else "средний" if risk_score < 60 else "высокий"
        
        # Формируем анализ
        analysis = f"""
# Анализ ракеты: {token['symbol']} ({token['network']})

## Ключевые показатели:
- **Рост 24ч:** {price_change_24h:.2f}% ({growth_category})
- **Ликвидность:** ${liquidity_usd:,.2f} ({liquidity_category})
- **Объем торгов 24ч:** ${volume_24h:,.2f} ({volume_category})
- **Возраст:** {age_hours:.2f} часов (≈{age_days} дней)
- **Цена:** ${price_usd:.8f}
- **Соотношение объема к ликвидности:** {volume_to_liquidity_ratio:.3f}

## Метрики риска:
- **Общий риск:** {risk_score:.1f}% ({risk_category})
- **Скор ликвидности:** {liquidity_score:.1f}%
- **Скор объема:** {volume_score:.1f}%
- **Скор стабильности:** {stability_score:.1f}%
- **Скор возраста:** {age_score:.1f}%
- **Скор импульса:** {momentum_score:.1f}%

## Анализ:
"""
        # Добавляем специфический анализ в зависимости от показателей
        if volume_to_liquidity_ratio < 0.1:
            analysis += "- Низкое соотношение объема к ликвидности указывает на возможную низкую реальную торговую активность\n"
        elif volume_to_liquidity_ratio > 1:
            analysis += "- Высокое соотношение объема к ликвидности указывает на активную торговлю\n"
            
        if age_days < 7:
            analysis += "- Новый токен с высоким потенциалом роста\n"
        elif age_days < 30:
            analysis += "- Относительно новый токен\n"
        else:
            analysis += "- Зрелый токен с установленной историей\n"
            
        if liquidity_usd < 10000:
            analysis += "- Низкая ликвидность создает риск высокого проскальзывания\n"
        elif liquidity_usd > 100000:
            analysis += "- Высокая ликвидность обеспечивает стабильность торговли\n"
            
        if price_usd < 0.0001:
            analysis += "- Очень низкая цена может указывать на высокую волатильность\n"
        elif price_usd > 1:
            analysis += "- Высокая цена может ограничивать потенциал роста\n"

        analysis += "\n## Риски:\n"
        if liquidity_usd < 10000:
            analysis += "- Риск высокого проскальзывания при входе/выходе\n"
        if volume_24h < 10000:
            analysis += "- Возможность манипуляций на низкообъемном рынке\n"
        if price_change_24h > 100:
            analysis += "- Высокий риск отката после резкого роста\n"
        if age_days < 7:
            analysis += "- Риск нестабильности нового токена\n"
            
        analysis += "\n## Рекомендации:\n"
        if risk_score < 30:
            analysis += "- Безопасный для средних и крупных позиций\n"
            analysis += "- Рекомендуемый размер позиции: 5-10% от портфеля\n"
        elif risk_score < 60:
            analysis += "- Подходит для небольших позиций\n"
            analysis += "- Рекомендуемый размер позиции: 2-5% от портфеля\n"
        else:
            analysis += "- Рекомендуется только для очень небольших спекулятивных позиций\n"
            analysis += "- Рекомендуемый размер позиции: до 1% от портфеля\n"
            
        # Добавляем рекомендации по входу
        analysis += "\n## Стратегия входа:\n"
        if momentum > 0:
            analysis += "- Токен показывает положительный импульс, можно рассмотреть вход\n"
        else:
            analysis += "- Токен показывает отрицательный импульс, лучше дождаться разворота\n"
            
        if price_change_24h > 50:
            analysis += "- Высокий рост может привести к откату, лучше дождаться коррекции\n"
        elif price_change_24h < 20:
            analysis += "- Умеренный рост позволяет рассмотреть вход\n"
            
        return analysis

    async def find_rocket_tokens(self, max_age_hours: int = 24) -> List[Dict]:
        """
        Поиск токенов-ракет с учетом всех критериев.
        """
        try:
            self.logger.info("[СКАНИРОВАНИЕ] Начало поиска токенов-ракет")
            
            # Получаем все токены через существующий метод
            tokens = await self.get_latest_token_profiles_async()
            
            # Фильтруем токены по критериям ракеты
            rocket_tokens = []
            for token_data in tokens:
                if self._is_rocket_token(token_data, max_age_hours):
                    rocket_tokens.append(token_data)
            
            self.logger.info(f"[СКАНИРОВАНИЕ] Найдено {len(rocket_tokens)} токенов-ракет")
            return rocket_tokens
                
        except Exception as e:
            self.logger.error(f"Ошибка при поиске ракет: {str(e)}")
            return []

    def _is_rocket_token(self, token: Dict, max_age_hours: int = None) -> bool:
        """
        Проверяет, является ли токен ракетой на основе его характеристик.
        """
        try:
            # Получаем базовые данные токена
            base_token = token.get('baseToken', {})
            quote_token = token.get('quoteToken', {})
            
            # Получаем значения с правильными путями в JSON
            try:
                price_change = float(token.get('priceChange', {}).get('h24', 0))
            except (TypeError, ValueError, AttributeError):
                try:
                    price_change = float(token.get('priceChange24h', 0))
                except (TypeError, ValueError):
                    price_change = 0
                
            try:
                liquidity = float(token.get('liquidity', {}).get('usd', 0))
            except (TypeError, ValueError, AttributeError):
                try:
                    liquidity = float(token.get('liquidity', 0))
                except (TypeError, ValueError):
                    liquidity = 0
                
            try:
                volume_24h = float(token.get('volume', {}).get('h24', 0))
            except (TypeError, ValueError, AttributeError):
                try:
                    volume_24h = float(token.get('volume24h', 0))
                except (TypeError, ValueError):
                    volume_24h = 0
                
            try:
                age_hours = float(token.get('ageHours', 0))
            except (TypeError, ValueError):
                age_hours = 0
            
            # Логируем значения для отладки
            self.logger.info(f"\nАнализ токена {base_token.get('symbol', 'Unknown')}:")
            self.logger.info(f"- Рост цены: {price_change}%")
            self.logger.info(f"- Ликвидность: ${liquidity:,.2f}")
            self.logger.info(f"- Объем 24ч: ${volume_24h:,.2f}")
            self.logger.info(f"- Возраст: {age_hours:.1f}ч")
            
            # Проверяем минимальные требования
            if liquidity < self.min_liquidity:
                self.logger.info(f"❌ Недостаточная ликвидность: ${liquidity:,.2f} < ${self.min_liquidity:,.2f}")
                return False
                
            if volume_24h < self.min_volume_24h:
                self.logger.info(f"❌ Недостаточный объем: ${volume_24h:,.2f} < ${self.min_volume_24h:,.2f}")
                return False
                
            # Проверяем рост цены
            min_price_change = 2 if self.test_mode else 20  # 2% для тестового режима, 20% для основного
            if price_change < min_price_change:
                self.logger.info(f"❌ Недостаточный рост цены: {price_change}% (должен быть > {min_price_change}%)")
                return False
                
            # Проверяем возраст токена
            if max_age_hours and age_hours > max_age_hours:
                self.logger.info(f"❌ Токен слишком старый: {age_hours:.1f}ч > {max_age_hours}ч")
                return False
                
            # Если все проверки пройдены
            self.logger.info(f"✅ Найдена ракета: {base_token.get('symbol', 'Unknown')}")
            self.logger.info(f"   - Рост: {price_change}%")
            self.logger.info(f"   - Ликвидность: ${liquidity:,.2f}")
            self.logger.info(f"   - Объем: ${volume_24h:,.2f}")
            self.logger.info(f"   - Возраст: {age_hours:.1f}ч")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при проверке токена-ракеты: {str(e)}")
            self.logger.error(f"Данные токена: {json.dumps(token, indent=2)}")
            return False

def filter_duplicate_tokens(tokens):
    """
    Фильтрует дубликаты токенов, оставляя только версию с наибольшей ликвидностью.
    
    Args:
        tokens (list): Список токенов
        
    Returns:
        list: Отфильтрованный список токенов без дубликатов
    """
    # Создаем словарь для хранения токенов с максимальной ликвидностью
    unique_tokens = {}
    
    for token in tokens:
        symbol = token['symbol']
        liquidity = token['liquidity_usd']
        
        # Если токен с таким символом уже есть, сравниваем ликвидность
        if symbol in unique_tokens:
            if liquidity > unique_tokens[symbol]['liquidity_usd']:
                unique_tokens[symbol] = token
        else:
            unique_tokens[symbol] = token
    
    # Возвращаем список уникальных токенов
    return list(unique_tokens.values())

def get_test_networks():
    """
    Возвращает сокращенный список сетей и токенов для тестового режима
    """
    return {
        'solana': ['SOL', 'BONK', 'RAY', 'SRM', 'MNGO'],
        'ethereum': ['ETH', 'LINK', 'UNI', 'AAVE', 'COMP'],
        'bsc': ['BNB', 'CAKE', 'WBTC', 'LINK', 'UNI'],
        'polygon': ['MATIC', 'WETH', 'LINK', 'UNI', 'AAVE'],
        'arbitrum': ['ETH', 'WBTC', 'LINK', 'UNI', 'AAVE']
    }

def get_test_config():
    """
    Возвращает конфигурацию с пониженными критериями для тестового режима
    """
    return {
        "min_price_change": 2,  # 2% для тестового режима
        "max_price_change": 999999,  # Практически не ограничено
        "min_liquidity": 50,    # Было 250
        "min_volume": 25,       # Было 100
        "networks": list(get_test_networks().keys())
    }

async def test_api(test_mode: bool = False):
    api = TokenScanner(test_mode=test_mode)
    
    # Поиск ракет
    print("\nПоиск потенциальных ракет...")
    if test_mode:
        print("🔍 Тестовый режим: сокращенный список токенов и пониженные критерии")
        config = get_test_config()
    else:
        config = {
            "min_price_change": 5,  # 5% для основного режима
            "max_price_change": 999999,  # Практически не ограничено
            "min_liquidity": 250,
            "min_volume": 100,
            "networks": list(explorers.keys())
        }
    
    rockets = await api.find_rocket_tokens()
    
    if not rockets:
        print("\nРакеты не найдены")
        return
        
    # Сортировка ракет по суточному приросту
    rockets.sort(key=lambda x: x['price_change_24h'], reverse=True)
    
    # Фильтрация дубликатов, оставляем только версии с наибольшей ликвидностью
    unique_rockets = filter_duplicate_tokens(rockets)
    
    print(f"\nНайдено всего {len(rockets)} потенциальных ракет")
    print(f"После фильтрации дубликатов: {len(unique_rockets)}")
    print(f"Все найденные ракеты (без дубликатов):\n")
    
    # Сохраняем результаты в JSON
    output_dir = Path("results")
    saver = TokenDataSaver(output_dir)
    json_path = saver.save_tokens_data(unique_rockets, config)
    print(f"\nРезультаты сохранены в: {json_path}")
    
    # Вывод информации о каждой ракете
    for i, token in enumerate(unique_rockets, 1):
        print(f"{'='*80}")
        print(f"🚀 #{i} | {token['symbol']} | Сеть: {token['network']}")
        print(f"{'='*80}")
        
        # Основные показатели
        profile = token['profile']
        price_changes = profile.get('priceChange', {})
        
        print(f"📈 Рост: 24ч: {price_changes.get('h24', 0):+.2f}% | 1ч: {price_changes.get('h1', 0):+.2f}%")
        print(f"💰 Цена: ${profile.get('priceUsd', '0')} | Ликв: ${token['liquidity_usd']:,.2f} | Объем 24ч: ${token['volume_24h']:,.2f}")
        print(f"⏰ Возраст: {token['age_hours']:.1f}ч | DEX: {profile.get('dexId', 'Неизвестно')}")
        
        # Ссылки
        print("\n🔗 Ссылки:")
        
        # DEXScreener
        print(f"📊 DEXScreener: https://dexscreener.com/{token['network'].lower()}/{token['address']}")
        
        # Ссылка на DEX
        dex_id = profile.get('dexId', '').lower()
        if dex_id == 'pancakeswap':
            print(f"🥞 PancakeSwap: https://pancakeswap.finance/swap?outputCurrency={token['address']}")
        elif dex_id == 'raydium':
            print(f"🌟 Raydium: https://raydium.io/swap/?inputCurrency=sol&outputCurrency={token['address']}")
        elif dex_id == 'uniswap':
            print(f"🦄 Uniswap: https://app.uniswap.org/#/swap?outputCurrency={token['address']}")
        elif dex_id == 'sushi':
            print(f"🍣 SushiSwap: https://app.sushi.com/swap?outputCurrency={token['address']}")
        
        # Ссылка на блокчейн-эксплорер
        network = token['network'].lower()
        if network in explorers:
            print(f"🔍 Explorer: {explorers[network]}{token['address']}")
            
        print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Поиск ракет на DEX')
    parser.add_argument('-test', action='store_true', help='Запуск в тестовом режиме (сокращенный список токенов и пониженные критерии)')
    args = parser.parse_args()
    
    asyncio.run(test_api(test_mode=args.test)) 