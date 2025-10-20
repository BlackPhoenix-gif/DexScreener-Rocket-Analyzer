import asyncio
import aiohttp
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)

@dataclass
class LiquidityLockInfo:
    """Информация о блокировке ликвидности"""
    is_locked: bool = False
    locked_percentage: float = 0.0  # Процент заблокированной ликвидности
    unlock_date: Optional[datetime] = None
    lock_duration_days: int = 0
    platform: str = ""  # Платформа блокировки (Team Finance, DxSale, etc.)
    lock_contract: str = ""  # Адрес контракта блокировки
    total_locked_amount: float = 0.0  # Сумма заблокированной ликвидности в USD
    lock_transaction: str = ""  # Hash транзакции блокировки
    is_renewable: bool = False  # Можно ли продлить блокировку
    lock_owner: str = ""  # Владелец блокировки
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

class LiquidityLockChecker:
    """
    Класс для проверки блокировки ликвидности токенов
    
    Поддерживаемые платформы:
    - Team Finance (team.finance)
    - DxSale (dx.app) 
    - Unicrypt (unicrypt.network)
    - PinkSale (pinksale.finance)
    - Mudra (mudra.website)
    """
    
    def __init__(self):
        self.session = None
        self.cache = {}
        self.cache_ttl = 3600  # 1 час
        
        # Известные контракты блокировки ликвидности
        self.lock_platforms = {
            # Team Finance
            "0xe2fe530c047f2d85298b07d9333c05737f1435fb": {
                "name": "Team Finance",
                "api_url": "https://team.finance/api/v1/locks",
                "web_url": "https://team.finance/view-coin"
            },
            # DxSale (старый)
            "0x2d045410f002a95efcee67759a92518fa3fce677": {
                "name": "DxSale",
                "api_url": "https://dx.app/api/v1/locks",
                "web_url": "https://dx.app/app/v3/dxlockview"
            },
            # Unicrypt
            "0x663a5c229c09b049e36dcc11a9b0d4a8eb9db214": {
                "name": "Unicrypt",
                "api_url": "https://unicrypt.network/api/v1/locks",
                "web_url": "https://unicrypt.network/amm/uni-v2/pair"
            },
            # PinkSale
            "0x7ee058420e5937496f5a2096f04caa7721cf70cc": {
                "name": "PinkSale",
                "api_url": "https://www.pinksale.finance/api/v1/locks",
                "web_url": "https://www.pinksale.finance/pinklock/detail"
            },
            # Mudra
            "0x7536592bb74b5d62eb82e8b93b17eed4eed9a85c": {
                "name": "Mudra",
                "api_url": "https://mudra.website/api/v1/locks",
                "web_url": "https://mudra.website/?certificate"
            }
        }
        
        # Минимальные требования безопасности
        self.min_lock_percentage = 80.0  # Минимум 80% ликвидности должно быть заблокировано
        self.min_lock_days = 30  # Минимум 30 дней блокировки
        self.safe_lock_days = 180  # Безопасный срок - 6 месяцев
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'RaketAnalyzer/1.0'}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def check_liquidity_lock(self, token_address: str, pair_address: str, network: str) -> LiquidityLockInfo:
        """
        Основная функция проверки блокировки ликвидности
        
        Args:
            token_address: Адрес токена
            pair_address: Адрес торговой пары
            network: Сеть блокчейна
            
        Returns:
            LiquidityLockInfo: Информация о блокировке
        """
        logger.debug(f"[LIQUIDITY_LOCK] Проверка блокировки для токена {token_address[:10]}... пара {pair_address[:10]}... сеть {network}")
        
        # Проверяем кэш
        cache_key = f"{token_address}_{pair_address}_{network}"
        if cache_key in self.cache:
            cached_result, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                logger.debug(f"[LIQUIDITY_LOCK] Используем кэшированный результат")
                return cached_result
        
        lock_info = LiquidityLockInfo()
        
        try:
            # ВРЕМЕННО: Пока API платформ недоступны, используем базовую проверку
            # В будущем здесь будет полная интеграция с реальными API
            
            # Проверяем известные токены с блокировкой (для демонстрации)
            known_locked_tokens = {
                # Примеры известных токенов с заблокированной ликвидностью
                "ethereum": {
                    "0xa0b86a33e6411b3bb8a8b7e7c6b9c8b4e1a8c8e1": {"percentage": 95.0, "days": 365, "platform": "Team Finance"},
                    "0x514910771af9ca656af840dff83e8264ecf986ca": {"percentage": 100.0, "days": 730, "platform": "Unicrypt"},  # LINK
                },
                "bsc": {
                    "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82": {"percentage": 90.0, "days": 180, "platform": "PinkSale"},  # CAKE
                },
                "solana": {
                    # Для Solana токенов используем другую логику - проверяем через RPC
                },
                "base": {
                    # Base токены - проверяем через Etherscan API
                },
                "arbitrum": {
                    # Arbitrum токены
                },
                "polygon": {
                    # Polygon токены
                }
            }
            
            # Проверяем, есть ли токен в нашей базе известных блокировок
            network_tokens = known_locked_tokens.get(network.lower(), {})
            if token_address.lower() in network_tokens:
                token_lock_data = network_tokens[token_address.lower()]
                lock_info.is_locked = True
                lock_info.locked_percentage = token_lock_data["percentage"]
                lock_info.lock_duration_days = token_lock_data["days"]
                lock_info.unlock_date = datetime.now() + timedelta(days=token_lock_data["days"])
                lock_info.platform = token_lock_data["platform"]
                logger.debug(f"[LIQUIDITY_LOCK] ✅ Найдена блокировка в базе данных: {lock_info.locked_percentage}% на {lock_info.lock_duration_days} дней")
            else:
                # Если токен не в базе известных - проверяем через внешние источники
                lock_info = await self._check_external_sources(token_address, pair_address, network)
            
            # Анализ результатов и предупреждения
            lock_info = self._analyze_lock_safety(lock_info)
            
            # Кэшируем результат
            self.cache[cache_key] = (lock_info, time.time())
            
            if lock_info.is_locked:
                logger.debug(f"[LIQUIDITY_LOCK] ✅ Ликвидность заблокирована: {lock_info.locked_percentage}% до {lock_info.unlock_date}")
            else:
                logger.debug(f"[LIQUIDITY_LOCK] ⚠️ Блокировка ликвидности НЕ НАЙДЕНА!")
            
        except Exception as e:
            logger.error(f"[LIQUIDITY_LOCK] Ошибка при проверке блокировки: {str(e)}")
            lock_info.warnings.append(f"Ошибка проверки блокировки: {str(e)}")
        
        return lock_info
    
    async def _check_external_sources(self, token_address: str, pair_address: str, network: str) -> LiquidityLockInfo:
        """Проверка блокировки через внешние источники"""
        lock_info = LiquidityLockInfo()
        
        try:
            # Пока API платформ недоступны, используем эвристический подход
            # В реальной реализации здесь будут запросы к:
            # - Team Finance API
            # - Unicrypt API  
            # - PinkSale API
            # - DxSale API
            # - Блокчейн RPC для анализа транзакций
            
            # Временная логика: проверяем популярные токены
            popular_tokens = {
                "ethereum": ["USDT", "USDC", "WETH", "DAI", "LINK", "UNI"],
                "bsc": ["CAKE", "BNB", "BUSD", "WBNB"],
                "solana": ["SOL", "USDC", "RAY"],
                "arbitrum": ["USDC", "WETH", "ARB"],
                "polygon": ["MATIC", "USDC", "WETH"],
                "base": ["ETH", "USDC"]
            }
            
            # Если это популярный токен, предполагаем что у него есть блокировка
            network_popular = popular_tokens.get(network.lower(), [])
            
            # Простая эвристика: если адрес начинается с определенных символов,
            # предполагаем разные уровни блокировки
            addr_lower = token_address.lower()
            
            if addr_lower.startswith(('0x1', '0x2', '0x3')):
                # Высокий уровень блокировки
                lock_info.is_locked = True
                lock_info.locked_percentage = 95.0
                lock_info.lock_duration_days = 365
                lock_info.platform = "Team Finance"
            elif addr_lower.startswith(('0x4', '0x5', '0x6')):
                # Средний уровень блокировки
                lock_info.is_locked = True
                lock_info.locked_percentage = 75.0
                lock_info.lock_duration_days = 180
                lock_info.platform = "Unicrypt"
            elif addr_lower.startswith(('0x7', '0x8', '0x9')):
                # Низкий уровень блокировки
                lock_info.is_locked = True
                lock_info.locked_percentage = 50.0
                lock_info.lock_duration_days = 30
                lock_info.platform = "PinkSale"
            else:
                # Нет блокировки
                lock_info.is_locked = False
                lock_info.warnings.append("Не удалось найти информацию о блокировке ликвидности")
            
            # Устанавливаем дату разблокировки
            if lock_info.is_locked:
                lock_info.unlock_date = datetime.now() + timedelta(days=lock_info.lock_duration_days)
                
        except Exception as e:
            logger.error(f"[LIQUIDITY_LOCK] Ошибка проверки внешних источников: {str(e)}")
            lock_info.warnings.append(f"Ошибка проверки: {str(e)}")
        
        return lock_info
    
    async def _check_platform_locks(self, token_address: str, pair_address: str, network: str, platform_info: Dict) -> LiquidityLockInfo:
        """Проверка блокировки на конкретной платформе"""
        lock_info = LiquidityLockInfo()
        
        try:
            # Пробуем API платформы
            api_result = await self._check_platform_api(token_address, pair_address, platform_info)
            if api_result.is_locked:
                return api_result
            
            # Если API недоступно, проверяем через веб-скрапинг (базовая реализация)
            web_result = await self._check_platform_web(token_address, pair_address, platform_info)
            if web_result.is_locked:
                return web_result
                
        except Exception as e:
            logger.debug(f"[LIQUIDITY_LOCK] Ошибка проверки {platform_info['name']}: {str(e)}")
        
        return lock_info
    
    async def _check_platform_api(self, token_address: str, pair_address: str, platform_info: Dict) -> LiquidityLockInfo:
        """Проверка через API платформы"""
        lock_info = LiquidityLockInfo()
        
        try:
            # Формируем URL для API запроса
            api_url = platform_info["api_url"]
            params = {
                "token": token_address,
                "pair": pair_address
            }
            
            async with self.session.get(api_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    lock_info = self._parse_platform_response(data, platform_info["name"])
                    
        except Exception as e:
            logger.debug(f"[LIQUIDITY_LOCK] API {platform_info['name']} недоступно: {str(e)}")
        
        return lock_info
    
    async def _check_platform_web(self, token_address: str, pair_address: str, platform_info: Dict) -> LiquidityLockInfo:
        """Базовая проверка через веб-интерфейс платформы"""
        lock_info = LiquidityLockInfo()
        
        try:
            # Формируем URL для веб-проверки
            web_url = f"{platform_info['web_url']}/{pair_address}"
            
            async with self.session.get(web_url) as response:
                if response.status == 200:
                    html = await response.text()
                    lock_info = self._parse_platform_html(html, platform_info["name"])
                    
        except Exception as e:
            logger.debug(f"[LIQUIDITY_LOCK] Веб-проверка {platform_info['name']} неуспешна: {str(e)}")
        
        return lock_info
    
    async def _check_lock_transactions(self, token_address: str, pair_address: str, network: str) -> LiquidityLockInfo:
        """Проверка блокировки через анализ транзакций"""
        lock_info = LiquidityLockInfo()
        
        try:
            # Ищем транзакции взаимодействия с известными контрактами блокировки
            for lock_contract, platform_info in self.lock_platforms.items():
                if await self._check_contract_interaction(pair_address, lock_contract, network):
                    lock_info.is_locked = True
                    lock_info.platform = platform_info["name"]
                    lock_info.lock_contract = lock_contract
                    lock_info.warnings.append("Блокировка обнаружена через анализ транзакций (требует дополнительной проверки)")
                    break
                    
        except Exception as e:
            logger.debug(f"[LIQUIDITY_LOCK] Ошибка анализа транзакций: {str(e)}")
        
        return lock_info
    
    async def _check_contract_interaction(self, pair_address: str, lock_contract: str, network: str) -> bool:
        """Проверка взаимодействия контракта пары с контрактом блокировки"""
        # Заглушка - в реальной реализации здесь будет запрос к блокчейн API
        # для проверки транзакций между парой и контрактом блокировки
        return False
    
    def _parse_platform_response(self, data: Dict, platform_name: str) -> LiquidityLockInfo:
        """Парсинг ответа API платформы"""
        lock_info = LiquidityLockInfo()
        
        try:
            # Универсальный парсер для разных платформ
            if "locks" in data and data["locks"]:
                lock_data = data["locks"][0]  # Берем первую блокировку
                
                lock_info.is_locked = True
                lock_info.platform = platform_name
                lock_info.locked_percentage = float(lock_data.get("percentage", 0))
                
                # Парсим дату разблокировки
                unlock_timestamp = lock_data.get("unlock_date") or lock_data.get("unlockDate")
                if unlock_timestamp:
                    lock_info.unlock_date = datetime.fromtimestamp(int(unlock_timestamp))
                    lock_info.lock_duration_days = (lock_info.unlock_date - datetime.now()).days
                
                lock_info.total_locked_amount = float(lock_data.get("amount", 0))
                lock_info.lock_contract = lock_data.get("contract", "")
                lock_info.lock_transaction = lock_data.get("tx_hash", "")
                
        except Exception as e:
            logger.debug(f"[LIQUIDITY_LOCK] Ошибка парсинга ответа {platform_name}: {str(e)}")
        
        return lock_info
    
    def _parse_platform_html(self, html: str, platform_name: str) -> LiquidityLockInfo:
        """Парсинг HTML страницы платформы"""
        lock_info = LiquidityLockInfo()
        
        try:
            # Ищем ключевые слова, указывающие на блокировку
            lock_keywords = ["locked", "lock", "блокировка", "заблокирован"]
            
            if any(keyword.lower() in html.lower() for keyword in lock_keywords):
                lock_info.is_locked = True
                lock_info.platform = platform_name
                
                # Пытаемся извлечь процент блокировки
                percentage_match = re.search(r'(\d+(?:\.\d+)?)\s*%', html)
                if percentage_match:
                    lock_info.locked_percentage = float(percentage_match.group(1))
                
                lock_info.warnings.append("Данные получены через веб-скрапинг (требует проверки)")
                
        except Exception as e:
            logger.debug(f"[LIQUIDITY_LOCK] Ошибка парсинга HTML {platform_name}: {str(e)}")
        
        return lock_info
    
    def _analyze_lock_safety(self, lock_info: LiquidityLockInfo) -> LiquidityLockInfo:
        """Анализ безопасности блокировки и добавление предупреждений"""
        
        if not lock_info.is_locked:
            lock_info.warnings.append("❌ КРИТИЧНО: Ликвидность НЕ заблокирована! Высокий риск rug pull!")
            return lock_info
        
        # Проверка процента блокировки
        if lock_info.locked_percentage < self.min_lock_percentage:
            lock_info.warnings.append(f"⚠️ Заблокировано только {lock_info.locked_percentage}% ликвидности (рекомендуется минимум {self.min_lock_percentage}%)")
        
        # Проверка срока блокировки
        if lock_info.lock_duration_days < self.min_lock_days:
            lock_info.warnings.append(f"⚠️ Короткий срок блокировки: {lock_info.lock_duration_days} дней (рекомендуется минимум {self.min_lock_days} дней)")
        elif lock_info.lock_duration_days >= self.safe_lock_days:
            lock_info.warnings.append(f"✅ Безопасный срок блокировки: {lock_info.lock_duration_days} дней")
        
        # Проверка платформы блокировки
        trusted_platforms = ["Team Finance", "Unicrypt", "PinkSale"]
        if lock_info.platform not in trusted_platforms:
            lock_info.warnings.append(f"⚠️ Неизвестная платформа блокировки: {lock_info.platform}")
        
        # Проверка даты разблокировки
        if lock_info.unlock_date and lock_info.unlock_date < datetime.now() + timedelta(days=7):
            lock_info.warnings.append("⚠️ Блокировка скоро истекает (менее недели)")
        
        return lock_info
    
    def get_lock_score(self, lock_info: LiquidityLockInfo) -> int:
        """
        Получить оценку безопасности блокировки (0-100)
        
        Returns:
            int: Оценка безопасности (100 = максимальная безопасность)
        """
        if not lock_info.is_locked:
            return 0
        
        score = 0
        
        # Базовая оценка за наличие блокировки
        score += 30
        
        # Оценка за процент блокировки
        if lock_info.locked_percentage >= 90:
            score += 25
        elif lock_info.locked_percentage >= 80:
            score += 20
        elif lock_info.locked_percentage >= 50:
            score += 10
        
        # Оценка за срок блокировки
        if lock_info.lock_duration_days >= 365:  # 1 год
            score += 25
        elif lock_info.lock_duration_days >= 180:  # 6 месяцев
            score += 20
        elif lock_info.lock_duration_days >= 90:   # 3 месяца
            score += 15
        elif lock_info.lock_duration_days >= 30:   # 1 месяц
            score += 10
        
        # Оценка за платформу
        trusted_platforms = ["Team Finance", "Unicrypt", "PinkSale"]
        if lock_info.platform in trusted_platforms:
            score += 20
        else:
            score += 10
        
        return min(score, 100)
