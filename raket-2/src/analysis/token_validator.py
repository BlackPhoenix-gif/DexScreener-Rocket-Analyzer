import asyncio
import aiohttp
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

from .fake_token_detector import FakeTokenDetector, FakeTokenResult
from .liquidity_lock_checker import LiquidityLockChecker, LiquidityLockInfo

logger = logging.getLogger(__name__)

@dataclass
class TokenValidationResult:
    """Результат валидации токена"""
    is_valid: bool
    is_verified: bool
    is_fake: bool
    original_network: Optional[str] = None
    real_address: Optional[str] = None
    liquidity_usd: float = 0.0
    volume_24h: float = 0.0
    holder_count: int = 0
    contract_age_days: int = 0
    liquidity_lock_info: Optional[LiquidityLockInfo] = None  # Информация о блокировке ликвидности
    liquidity_lock_score: int = 0  # Оценка безопасности блокировки (0-100)
    warnings: List[str] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []

class TokenValidator:
    """
    Класс для валидации и верификации токенов
    """
    
    def __init__(self):
        self.min_liquidity_usd = 50000  # Минимальная ликвидность $50K
        self.min_volume_24h = 10000     # Минимальный объем $10K
        self.min_holders = 100          # Минимальное количество держателей
        self.min_contract_age_days = 7  # Минимальный возраст контракта 7 дней
        
        # Инициализация детектора поддельных токенов
        self.fake_detector = FakeTokenDetector()
        
        # Инициализация проверки блокировки ликвидности
        self.liquidity_lock_checker = None
        
    async def validate_token(self, token_address: str, network: str, token_name: str, pair_address: str = "") -> TokenValidationResult:
        """
        Полная валидация токена
        
        Args:
            token_address: Адрес контракта
            network: Сеть блокчейна
            token_name: Название токена
            pair_address: Адрес торговой пары (для проверки блокировки ликвидности)
            
        Returns:
            TokenValidationResult: Результат валидации
        """
        result = TokenValidationResult(
            is_valid=False,
            is_verified=False,
            is_fake=False
        )
        
        try:
            # 1. Проверка существования контракта
            contract_exists = await self._check_contract_exists(token_address, network)
            if not contract_exists:
                result.errors.append(f"Контракт {token_address} не найден в сети {network}")
                return result
            
            # 2. Проверка на поддельный токен с использованием улучшенного детектора
            fake_result = await self.fake_detector.detect_fake_token(token_name, token_address, network)
            if fake_result.is_fake:
                result.is_fake = True
                result.errors.append(f"Обнаружен поддельный токен: {fake_result.reason}")
                logger.info(f"[VALIDATOR] Поддельный токен {token_name} обнаружен: {fake_result.reason} (уверенность: {fake_result.confidence:.2f})")
                return result
            
            # 3. Проверка верификации контракта
            is_verified = await self._check_contract_verification(token_address, network)
            result.is_verified = is_verified
            
            # 4. Проверка ликвидности и объема
            liquidity_data = await self._get_liquidity_data(token_address, network)
            if liquidity_data['liquidity_usd'] < self.min_liquidity_usd:
                result.warnings.append(f"Низкая ликвидность: ${liquidity_data['liquidity_usd']:,.2f}")
            
            if liquidity_data['volume_24h'] < self.min_volume_24h:
                result.warnings.append(f"Низкий объем торгов: ${liquidity_data['volume_24h']:,.2f}")
            
            result.liquidity_usd = liquidity_data['liquidity_usd']
            result.volume_24h = liquidity_data['volume_24h']
            
            # 5. Проверка количества держателей
            holder_count = await self._get_holder_count(token_address, network)
            if holder_count < self.min_holders:
                result.warnings.append(f"Мало держателей: {holder_count}")
            result.holder_count = holder_count
            
            # 6. Проверка возраста контракта
            contract_age = await self._get_contract_age(token_address, network)
            if contract_age < self.min_contract_age_days:
                result.warnings.append(f"Молодой контракт: {contract_age} дней")
            result.contract_age_days = contract_age
            
            # 7. Проверка на DEX
            dex_presence = await self._check_dex_presence(token_address, network)
            if not dex_presence:
                result.warnings.append("Токен отсутствует на основных DEX")
            
            # 8. КРИТИЧНО: Проверка блокировки ликвидности
            if pair_address:
                if not self.liquidity_lock_checker:
                    self.liquidity_lock_checker = LiquidityLockChecker()
                
                async with self.liquidity_lock_checker as lock_checker:
                    lock_info = await lock_checker.check_liquidity_lock(token_address, pair_address, network)
                    result.liquidity_lock_info = lock_info
                    result.liquidity_lock_score = lock_checker.get_lock_score(lock_info)
                    
                    # Добавляем предупреждения о блокировке
                    result.warnings.extend(lock_info.warnings)
                    
                    logger.info(f"[VALIDATOR] Проверка блокировки ликвидности: {lock_info.is_locked}, оценка: {result.liquidity_lock_score}/100")
            else:
                result.warnings.append("⚠️ Адрес торговой пары не указан - проверка блокировки ликвидности пропущена")
            
            # Финальная оценка с учетом блокировки ликвидности
            result.is_valid = (
                not result.is_fake and
                result.liquidity_usd >= self.min_liquidity_usd * 0.5 and  # Допускаем 50% от минимума
                result.volume_24h >= self.min_volume_24h * 0.5 and
                len(result.errors) == 0 and
                result.liquidity_lock_score >= 30  # Минимальная оценка безопасности блокировки
            )
            
        except Exception as e:
            logger.error(f"Ошибка при валидации токена {token_address}: {str(e)}")
            result.errors.append(f"Ошибка валидации: {str(e)}")
        
        return result
    
    async def _check_contract_exists(self, address: str, network: str) -> bool:
        """Проверка существования контракта"""
        # Реализация проверки через API блокчейн-сканеров
        pass
    
    async def _check_fake_token(self, token_name: str, network: str, address: str) -> bool:
        """Проверка на поддельный токен (устаревший метод - используйте fake_detector)"""
        fake_result = await self.fake_detector.detect_fake_token(token_name, address, network)
        return fake_result.is_fake
    
    async def _check_contract_verification(self, address: str, network: str) -> bool:
        """Проверка верификации контракта"""
        # Реализация через API Etherscan, BscScan и др.
        pass
    
    async def _get_liquidity_data(self, address: str, network: str) -> Dict[str, float]:
        """Получение данных о ликвидности"""
        # Реализация через DEX API
        return {'liquidity_usd': 0.0, 'volume_24h': 0.0}
    
    async def _get_holder_count(self, address: str, network: str) -> int:
        """Получение количества держателей"""
        # Реализация через API блокчейн-сканеров
        return 0
    
    async def _get_contract_age(self, address: str, network: str) -> int:
        """Получение возраста контракта в днях"""
        # Реализация через API блокчейн-сканеров
        return 0
    
    async def _check_dex_presence(self, address: str, network: str) -> bool:
        """Проверка присутствия на основных DEX"""
        # Проверка на Uniswap, PancakeSwap, Raydium и др.
        return True 