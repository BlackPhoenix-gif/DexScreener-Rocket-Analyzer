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

try:
    from src.utils.logger import get_logger
    logger = get_logger()
except Exception:
    logger = logging.getLogger("dexscreener")
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO)
try:
    from src.models.token import Token, TokenPair  # optional, не обязателен для сигналов
except Exception:
    Token = TokenPair = None  # безопасный заглушки
try:
    from src.config import config  # optional
except Exception:
    config = None
try:
    from src.analysis.perspective_tokens.token_data_saver import TokenDataSaver  # optional
except Exception:
    TokenDataSaver = None

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

class DexScreenerAPI:
    """
    Класс для взаимодействия с API DEXScreener.
    Предоставляет методы для получения данных о токенах и их анализа.
    """
    
    def __init__(self, test_mode: bool = False):
        """
        Инициализация клиента API DEXScreener.
        
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
        
        logger.info(f"[DEXSCREENER] Инициализация клиента API ({self.base_url})")
        logger.debug(f"[DEXSCREENER] Настройки: таймаут={self.timeout}с, макс.повторы={self.max_retries}")
        self.file_logger.info("=== Начало анализа токенов ===")
        self.file_logger.info(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.file_logger.info(f"Критерии фильтрации:")
        self.file_logger.info(f"- Минимальный рост цены: 20%")
        self.file_logger.info(f"- Максимальный рост цены: 1000%")
        self.file_logger.info(f"- Минимальная ликвидность: $500")
        self.file_logger.info(f"- Минимальный объем торгов: $250")
        self.file_logger.info("=" * 50)
    
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

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Синхронный HTTP запрос к API DEXScreener (использует requests.Session).

        Выполняет до self.max_retries попыток с экспоненциальной задержкой и ротацией User-Agent.
        """
        url = f"{self.base_url}/{endpoint}"
        for attempt in range(self.max_retries):
            try:
                headers = {
                    "User-Agent": random.choice(self.user_agents),
                    "Accept": "application/json",
                }
                resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                if attempt == self.max_retries - 1:
                    self.logger.error(f"API error: {str(e)}")
                    return {}
                time.sleep(2 ** attempt + random.random())
        return {}

    def search(self, chain: str, query: str) -> List[Dict]:
        """Синхронный поиск по адресу/символу с фильтром по сети."""
        data = self._make_request("search", {"q": query, "chain": chain}) or {}
        return data.get("pairs", [])

    def get_token_profile(self, chain_id: str, token_address: str) -> Dict:
        """Возвращает лучшую (по ликвидности) пару для токена как профиль токена.

        Примечание: актуальный endpoint tokens/{tokenAddress} (без chain в пути).
        Фильтруем по chain_id при наличии.
        """
        data = self._make_request(f"tokens/{token_address}") or {}
        pairs = data.get("pairs", [])
        if chain_id:
            pairs = [p for p in pairs if (p.get('chainId') or '').lower() == chain_id.lower()]
        if not pairs:
            return {}
        # Выбираем пару с максимальной ликвидностью
        return max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))

    def get_pair_details(self, chain_id: str, pair_address: str) -> Dict:
        """Возвращает детали конкретной пары."""
        data = self._make_request(f"pairs/{chain_id}/{pair_address}") or {}
        pairs = data.get("pairs", [])
        return pairs[0] if pairs else {}

    async def get_best_pair_async(self, chain_id: str, token_address: str) -> Dict:
        """Асинхронно получает лучшую по ликвидности пару токена."""
        try:
            async with aiohttp.ClientSession() as session:
                data = await self._make_async_request(session, f"tokens/{token_address}")
                pairs = data.get("pairs", []) if data else []
                if chain_id:
                    pairs = [p for p in pairs if (p.get('chainId') or '').lower() == chain_id.lower()]
                if not pairs:
                    return {}
                return max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
        except Exception:
            return {}

    def derive_signals_from_pair(self, pair: Dict) -> Dict[str, Any]:
        """Извлекает сигналы безопасности и метрики из объекта пары DexScreener."""
        if not pair:
            return {"found": False, "warnings": ["Пара не найдена"], "scores": {}, "metrics": {}}

        price_change = pair.get("priceChange", {}) or {}
        liquidity = pair.get("liquidity", {}) or {}
        volume = pair.get("volume", {}) or {}
        txns = pair.get("txns", {}) or {}
        info = pair.get("info", {}) or {}

        liquidity_usd = float(liquidity.get("usd", 0) or 0)
        volume_24h = float(volume.get("h24", 0) or 0)
        h1 = float(price_change.get("h1", 0) or 0)
        h6 = float(price_change.get("h6", 0) or 0)
        h24 = float(price_change.get("h24", 0) or 0)
        pair_created_ms = pair.get("pairCreatedAt") or 0
        age_hours = round((datetime.now() - datetime.fromtimestamp((pair_created_ms or 0) / 1000)).total_seconds() / 3600, 2) if pair_created_ms else None
        dex_id = (pair.get("dexId") or "").lower()

        # Доверие к DEX
        trusted_dex = {"uniswap", "sushiswap", "pancakeswap", "raydium", "quickswap", "jupiter", "syncswap"}
        dex_trust = 1.0 if dex_id in trusted_dex else 0.6 if dex_id else 0.5

        # Соотношение объем/ликвидность
        vol_liq_ratio = (volume_24h / liquidity_usd) if liquidity_usd > 0 else 0.0

        # Транзакции за 24ч (если доступны)
        tx24 = txns.get("h24", {}) or {}
        buys = int(tx24.get("buys", 0) or 0)
        sells = int(tx24.get("sells", 0) or 0)
        total_tx = buys + sells

        # Веб-сайты и соцсети
        websites = info.get("websites", []) or []
        socials = info.get("socials", []) or []

        warnings: List[str] = []
        # Возраст
        if age_hours is not None:
            if age_hours < 24:
                warnings.append("🚨 КРИТИЧНО: Новый пул (<24ч)")
            elif age_hours < 24 * 7:
                warnings.append("⚠️ Молодой пул (<7дней)")

        # Ликвидность
        if liquidity_usd < 25000:
            warnings.append(f"Критически низкая ликвидность (<$25K): ${liquidity_usd:,.2f}")
        elif liquidity_usd < 100000:
            warnings.append(f"Низкая ликвидность (<$100K): ${liquidity_usd:,.2f}")

        # Импульс цены
        if h24 > 300:
            warnings.append(f"Экстремальный рост 24ч: {h24:.2f}%")
        elif h24 < -50:
            warnings.append(f"Сильное падение 24ч: {h24:.2f}%")

        # Объем/ликвидность
        if vol_liq_ratio > 2:
            warnings.append(f"Подозрительно высокое соотношение объем/ликвидность: {vol_liq_ratio:.2f}")
        elif 0 < vol_liq_ratio < 0.05:
            warnings.append(f"Очень низкое соотношение объем/ликвидность: {vol_liq_ratio:.2f}")

        # Транзакционная активность
        if total_tx and (buys == 0 or sells == 0):
            warnings.append("Дисбаланс покупок/продаж за 24ч")

        # Метаданные
        if not websites:
            warnings.append("Нет информации о сайте")
        if not socials:
            warnings.append("Нет ссылок на соцсети")

        # Сводные метрики для скоринга
        metrics = {
            "liquidity_usd": liquidity_usd,
            "volume_24h": volume_24h,
            "price_change_h1": h1,
            "price_change_h6": h6,
            "price_change_h24": h24,
            "age_hours": age_hours,
            "vol_liq_ratio": vol_liq_ratio,
            "dex_id": dex_id,
            "websites_count": len(websites),
            "socials_count": len(socials),
            "tx24_total": total_tx,
        }

        # Нормализованные скоры (0..1, где выше — лучше)
        scores = {
            "dex_trust": dex_trust,
            "liquidity_score": min(1.0, liquidity_usd / 100000.0),
            "volume_score": min(1.0, volume_24h / 50000.0),
            "stability_score": max(0.0, min(1.0, 1.0 - abs(vol_liq_ratio - 1.0) / 3.0)),
            "age_score": 0.0 if age_hours is None else max(0.0, min(1.0, age_hours / (30 * 24))),
            "metadata_score": min(1.0, (len(websites) > 0) + (len(socials) > 0))
        }

        return {
            "found": True,
            "warnings": warnings,
            "scores": scores,
            "metrics": metrics,
            "pair_url": f"https://dexscreener.com/{(pair.get('chainId') or '').lower()}/{pair.get('pairAddress','')}"
        }

    async def _fetch_pairs(self, session: aiohttp.ClientSession, network: str, query: str) -> List[Dict]:
        """
        Асинхронный запрос пар для токена в сети.
        """
        try:
            response = await self._make_async_request(session, "search", {
                "q": query,
                "chain": network
            })
            
            if not response or "pairs" not in response:
                self.logger.warning(f"Некорректный ответ для '{query}' в сети {network}")
                return []
                
            return response.get("pairs", [])
            
        except Exception as e:
            self.logger.error(f"Ошибка при поиске '{query}' в сети {network}: {str(e)}")
            return []

    async def get_latest_token_profiles_async(self) -> List[Dict]:
        """
        Асинхронное получение последних профилей токенов.
        """
        logger.info("[DEXSCREENER] Получение последних профилей токенов")
        try:
            # Используем тестовый список сетей и токенов если включен тестовый режим
            networks = get_test_networks() if self.test_mode else {
                'solana': [
                    'SOL', 'BONK', 'RAY', 'SRM', 'MNGO', 'SAMO', 'ORCA', 'ATLAS', 'POLIS', 'GST', 'SBR',
                    'JUP', 'PYTH', 'BOME', 'WIF', 'MYRO', 'POPCAT', 'WEN', 'BOME', 'SLERF', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME'
                ],
                'base': [
                    'ETH', 'WETH', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI', 'CRV',
                    'USDC', 'USDT', 'DAI', 'WBTC', 'WETH', 'BAL', 'BOND', 'DPI', 'ENJ', 'GRT',
                    'KNC', 'LDO', 'LINK', 'LRC', 'MKR', 'NMR', 'OXT', 'PAX', 'REN', 'REP',
                    'SUSHI', 'SXP', 'TUSD', 'UMA', 'UNI', 'USDT', 'WBTC', 'WETH', 'YFI', 'ZRX',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME'
                ],
                'ethereum': [
                    'ETH', 'WETH', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI', 'CRV',
                    'SHIB', 'PEPE', 'DOGE', 'MATIC', 'AVAX', 'FTM', 'USDC', 'USDT', 'DAI', 'WBTC',
                    'BAL', 'BAT', 'BOND', 'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR',
                    'OXT', 'PAX', 'REN', 'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME'
                ],
                'bsc': [
                    'BNB', 'CAKE', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX',
                    'YFI', 'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BUSD', 'TUSD',
                    'BAL', 'BAT', 'BOND', 'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR',
                    'OXT', 'PAX', 'REN', 'REP', 'SUSHI', 'SXP', 'UMA', 'ZRX', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME'
                ],
                'arbitrum': [
                    'ETH', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'MATIC', 'AVAX', 'FTM', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND',
                    'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN',
                    'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BOME', 'BOME', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME'
                ],
                'polygon': [
                    'MATIC', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND',
                    'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN',
                    'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BOME', 'BOME', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME'
                ],
                'optimism': [
                    'ETH', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'MATIC', 'AVAX', 'FTM', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND',
                    'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN',
                    'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BOME', 'BOME', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME'
                ],
                'avalanche': [
                    'AVAX', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND',
                    'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN',
                    'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BOME', 'BOME', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME'
                ],
                'fantom': [
                    'FTM', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'MATIC', 'AVAX', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND', 'DPI',
                    'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN', 'REP',
                    'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME'
                ],
                'cronos': [
                    'CRO', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'YFI',
                    'CRV', 'SHIB', 'PEPE', 'DOGE', 'USDC', 'USDT', 'DAI', 'BAL', 'BAT', 'BOND',
                    'DPI', 'ENJ', 'GRT', 'KNC', 'LDO', 'LRC', 'NMR', 'OXT', 'PAX', 'REN',
                    'REP', 'SUSHI', 'SXP', 'TUSD', 'UMA', 'ZRX', 'BOME', 'BOME', 'BOME', 'BOME',
                    'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME', 'BOME'
                ]
            }
            
            all_pairs = []
            total_requests = sum(len(queries) for queries in networks.values())
            logger.info(f"[DEXSCREENER] Всего запросов: {total_requests}")
            
            # Создаем прогресс-бар
            pbar = tqdm(total=total_requests, desc="Поиск токенов", unit="запрос")
            
            async with aiohttp.ClientSession() as session:
                # Обрабатываем сети последовательно
                for network, queries in networks.items():
                    # Обрабатываем токены в каждой сети с задержкой
                    for query in queries:
                        try:
                            # Добавляем случайную задержку от 1 до 3 секунд
                            await asyncio.sleep(random.uniform(1, 3))
                            
                            pairs = await self._fetch_pairs(session, network, query)
                            if pairs:
                                self.logger.info(f"Найдено {len(pairs)} пар для '{query}' в сети {network}")
                                all_pairs.extend(pairs)
                            pbar.update(1)
                        except Exception as e:
                            self.logger.error(f"Ошибка при обработке '{query}' в сети {network}: {str(e)}")
                            pbar.update(1)
            
            pbar.close()
            
            if not all_pairs:
                self.logger.warning("Не найдено ни одной пары")
                return []
            
            # Удаляем дубликаты по адресу токена
            unique_pairs = {pair["baseToken"]["address"]: pair for pair in all_pairs}.values()
            self.logger.info(f"Всего найдено {len(unique_pairs)} уникальных пар")
            return list(unique_pairs)
            
        except Exception as e:
            self.logger.error(f"[DEXSCREENER] Критическая ошибка при получении профилей токенов: {str(e)}")
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
        logger.info(f"[DEXSCREENER] Получение пар для токена {token_address} на {chain_id}")
        try:
            return self._make_request(f"tokens/{chain_id}/{token_address}")
        except Exception as e:
            self.logger.error(f"[DEXSCREENER] Ошибка при получении пар токена: {str(e)}")
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

    async def find_rocket_tokens(self, max_age_hours: Optional[int] = None) -> List[Dict]:
        """
        Поиск потенциальных ракет среди токенов.
        
        Args:
            max_age_hours: Максимальный возраст токена в часах
            
        Returns:
            List[Dict]: Список найденных токенов-ракет
        """
        if self.test_mode:
            print("\nПоиск потенциальных ракет...")
            print("🔍 Тестовый режим: сокращенный список токенов и пониженные критерии")
        
        logger.info("Поиск потенциальных ракет")
        self.file_logger.info("\n=== Начало поиска ракет ===")
        self.file_logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Получаем профили токенов
        profiles = await self.get_latest_token_profiles_async()
        
        rockets = []
        seen_tokens = set()
        filtered_stats = {
            "total": len(profiles),
            "duplicates": 0,
            "price_change": 0,
            "liquidity": 0,
            "volume": 0,
            "passed": 0,
            "failed_price": 0,
            "failed_liquidity": 0,
            "failed_volume": 0,
            "stablecoins": 0
        }

        # Список известных стейблкоинов
        stablecoins = {
            'USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'USDH', 'USDK', 'USDN', 'USDX', 
            'UST', 'FRAX', 'LUSD', 'SUSD', 'GUSD', 'HUSD', 'OUSD', 'CUSD', 'USDJ'
        }

        for profile in profiles:
            try:
                token = profile["baseToken"]
                token_address = token["address"]
                token_symbol = token["symbol"].upper()
                
                if token_address in seen_tokens:
                    filtered_stats["duplicates"] += 1
                    self._log_token_analysis(token, profile, "Дубликат")
                    continue
                
                # Фильтруем стейблкоины
                if token_symbol in stablecoins:
                    filtered_stats["stablecoins"] += 1
                    self._log_token_analysis(token, profile, "Стейблкоин")
                    continue
                    
                price_change_1h = float(profile.get("priceChange", {}).get("h1", 0))
                price_change_24h = float(profile.get("priceChange", {}).get("h24", 0))
                liquidity_usd = float(profile.get("liquidity", {}).get("usd", 0))
                volume_24h = float(profile.get("volume", {}).get("h24", 0))

                # Проверяем каждый критерий отдельно
                if not (5 <= price_change_24h <= 1000):
                    filtered_stats["failed_price"] += 1
                    self._log_token_analysis(token, profile, f"Рост {price_change_24h:.2f}% вне диапазона 5-1000%")
                    continue

                if liquidity_usd < 250:
                    filtered_stats["failed_liquidity"] += 1
                    self._log_token_analysis(token, profile, f"Ликвидность ${liquidity_usd:.2f} < $250")
                    continue

                if volume_24h < 100:
                    filtered_stats["failed_volume"] += 1
                    self._log_token_analysis(token, profile, f"Объем ${volume_24h:.2f} < $100")
                    continue
                
                filtered_stats["passed"] += 1
                self.logger.info(f"Найдена ракета: {token['symbol']} (рост 24ч: {price_change_24h:.2f}%, ликвидность ${liquidity_usd:.2f})")
                
                rocket = {
                    "symbol": token["symbol"],
                    "name": token["name"],
                    "address": token_address,
                    "network": profile["chainId"],
                    "age_hours": round((datetime.now() - datetime.fromtimestamp(profile.get("pairCreatedAt", 0) / 1000)).total_seconds() / 3600, 2),
                    "price_change_1h": price_change_1h,
                    "price_change_24h": price_change_24h,
                    "liquidity_usd": liquidity_usd,
                    "volume_24h": volume_24h,
                    "profile": profile
                }
                rockets.append(rocket)
                seen_tokens.add(token_address)
                
                # Логируем успешный токен
                self._log_token_analysis(token, profile)
                
            except Exception as e:
                self.logger.error(f"Ошибка при обработке токена {token.get('symbol', 'unknown')}: {str(e)}")
                continue

        # Логируем подробную статистику фильтрации
        self.file_logger.info("\n=== Подробная статистика фильтрации ===")
        self.file_logger.info(f"Всего токенов: {filtered_stats['total']}")
        self.file_logger.info(f"Дубликатов: {filtered_stats['duplicates']}")
        self.file_logger.info(f"Стейблкоинов: {filtered_stats['stablecoins']}")
        self.file_logger.info(f"Не прошли по росту цены: {filtered_stats['failed_price']}")
        self.file_logger.info(f"Не прошли по ликвидности: {filtered_stats['failed_liquidity']}")
        self.file_logger.info(f"Не прошли по объему: {filtered_stats['failed_volume']}")
        self.file_logger.info(f"Принято: {filtered_stats['passed']}")
        self.file_logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.file_logger.info("=" * 30)

        # После нахождения ракет, записываем подробный анализ
        if rockets:
            self.rockets_logger.info("\n=== Подробный анализ найденных ракет ===")
            self.rockets_logger.info(f"Время анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.rockets_logger.info(f"Всего найдено ракет: {len(rockets)}")
            self.rockets_logger.info("=" * 50)
            
            # Сортируем ракеты по росту цены
            rockets.sort(key=lambda x: x['price_change_24h'], reverse=True)
            
            # Берем только топ-10 ракет для подробного анализа
            top_rockets = rockets[:10]
            
            for i, rocket in enumerate(top_rockets, 1):
                self.rockets_logger.info(f"\n# Ракета #{i}")
                self.rockets_logger.info(self._analyze_rocket(rocket))
                self.rockets_logger.info("=" * 50)
            
            # Добавляем сравнительный анализ только для топ-10
            self.rockets_logger.info("\n## Сравнительный анализ топ-10 ракет")
            
            # Сортируем по разным метрикам (только топ-10)
            self.rockets_logger.info("\n### По ликвидности:")
            rockets_by_liquidity = sorted(top_rockets, key=lambda x: x['liquidity_usd'], reverse=True)
            for i, rocket in enumerate(rockets_by_liquidity, 1):
                self.rockets_logger.info(f"{i}. {rocket['symbol']} - ${rocket['liquidity_usd']:,.2f}")
            
            self.rockets_logger.info("\n### По объему торгов:")
            rockets_by_volume = sorted(top_rockets, key=lambda x: x['volume_24h'], reverse=True)
            for i, rocket in enumerate(rockets_by_volume, 1):
                self.rockets_logger.info(f"{i}. {rocket['symbol']} - ${rocket['volume_24h']:,.2f}")
            
            self.rockets_logger.info("\n### По росту цены:")
            rockets_by_growth = sorted(top_rockets, key=lambda x: x['price_change_24h'], reverse=True)
            for i, rocket in enumerate(rockets_by_growth, 1):
                self.rockets_logger.info(f"{i}. {rocket['symbol']} - {rocket['price_change_24h']:.2f}%")
            
            # Добавляем общие рекомендации
            self.rockets_logger.info("\n## Общие рекомендации по портфелю:")
            
            # Находим наиболее безопасные токены из топ-10
            safe_rockets = [r for r in top_rockets if r['liquidity_usd'] > 100000 and r['volume_24h'] > 50000]
            if safe_rockets:
                self.rockets_logger.info("\n1. Наиболее безопасные для торговли:")
                for rocket in safe_rockets:
                    self.rockets_logger.info(f"   - {rocket['symbol']} (ликвидность: ${rocket['liquidity_usd']:,.2f})")
            
            # Находим спекулятивные возможности из топ-10
            spec_rockets = [r for r in top_rockets if r['price_change_24h'] > 50 and r['liquidity_usd'] > 10000]
            if spec_rockets:
                self.rockets_logger.info("\n2. Спекулятивные возможности:")
                for rocket in spec_rockets:
                    self.rockets_logger.info(f"   - {rocket['symbol']} (рост: {rocket['price_change_24h']:.2f}%)")
            
            # Находим высокорисковые токены из топ-10
            risky_rockets = [r for r in top_rockets if r['liquidity_usd'] < 10000 or r['volume_24h'] < 10000]
            if risky_rockets:
                self.rockets_logger.info("\n3. Высокорисковые токены:")
                for rocket in risky_rockets:
                    self.rockets_logger.info(f"   - {rocket['symbol']} (ликвидность: ${rocket['liquidity_usd']:,.2f}, объем: ${rocket['volume_24h']:,.2f})")
            
            # Добавляем рекомендации по распределению средств
            self.rockets_logger.info("\n## Рекомендации по распределению средств:")
            self.rockets_logger.info("1. Безопасные токены: 40-50% от выделенной суммы")
            self.rockets_logger.info("2. Спекулятивные возможности: 30-40% от выделенной суммы")
            self.rockets_logger.info("3. Высокорисковые токены: 10-20% от выделенной суммы")
            
            # Добавляем предупреждения
            self.rockets_logger.info("\n## Важные предупреждения:")
            self.rockets_logger.info("1. Всегда используйте стоп-лоссы")
            self.rockets_logger.info("2. Не вкладывайте больше, чем готовы потерять")
            self.rockets_logger.info("3. Диверсифицируйте риски между разными токенами")
            self.rockets_logger.info("4. Следите за общим риском портфеля")

        return rockets

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
        'ethereum': ['ETH', 'WETH', 'LINK', 'UNI', 'AAVE'],
        'bsc': ['BNB', 'CAKE', 'WETH', 'WBTC', 'LINK'],
        'polygon': ['MATIC', 'WETH', 'WBTC', 'LINK', 'UNI'],
        'arbitrum': ['ETH', 'WETH', 'WBTC', 'LINK', 'UNI']
    }

def get_test_config():
    """
    Возвращает конфигурацию с пониженными критериями для тестового режима
    """
    return {
        "min_price_change": 2,  # Было 5
        "max_price_change": 1000,
        "min_liquidity": 50,    # Было 250
        "min_volume": 25,       # Было 100
        "networks": list(get_test_networks().keys())
    }

def test_api(test_mode: bool = False):
    api = DexScreenerAPI(test_mode=test_mode)
    
    # Поиск ракет
    print("\nПоиск потенциальных ракет...")
    if test_mode:
        print("🔍 Тестовый режим: сокращенный список токенов и пониженные критерии")
        config = get_test_config()
    else:
        config = {
            "min_price_change": 5,
            "max_price_change": 1000,
            "min_liquidity": 250,
            "min_volume": 100,
            "networks": list(explorers.keys())
        }
    
    rockets = api.find_rocket_tokens()
    
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
    
    test_api(test_mode=args.test) 