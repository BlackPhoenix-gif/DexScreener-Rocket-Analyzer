import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass
import logging

from .token_validator import TokenValidator, TokenValidationResult
from .fake_token_detector import FakeTokenDetector

logger = logging.getLogger(__name__)

@dataclass
class EnhancedFilterCriteria:
    """Улучшенные критерии фильтрации"""
    # Базовые критерии роста
    min_price_growth_1h: float = 20.0      # Минимальный рост за 1 час
    min_price_growth_24h: float = 50.0     # Минимальный рост за 24 часа
    max_price_growth_24h: float = 999999.0  # Практически не ограничено
    
    # Критерии ликвидности и объема
    min_liquidity_usd: float = 50000.0     # Минимальная ликвидность $50K
    min_volume_24h: float = 10000.0        # Минимальный объем $10K
    max_volume_liquidity_ratio: float = 20.0  # Максимальное соотношение объем/ликвидность
    
    # Критерии токена
    min_holders: int = 100                 # Минимальное количество держателей
    min_contract_age_days: int = 7         # Минимальный возраст контракта
    max_token_age_hours: int = 168         # Максимальный возраст токена (7 дней)
    
    # Критерии качества
    require_verified_contract: bool = True  # Требовать верифицированный контракт
    require_dex_presence: bool = True       # Требовать присутствие на DEX
    exclude_fake_tokens: bool = True        # Исключать поддельные токены

class EnhancedRocketFilter:
    """
    Улучшенная система фильтрации "ракет" с валидацией токенов
    """
    
    def __init__(self, criteria: EnhancedFilterCriteria = None):
        self.criteria = criteria or EnhancedFilterCriteria()
        self.validator = TokenValidator()
        self.fake_detector = FakeTokenDetector()
        
        # Список токенов для исключения (известные скам-токены)
        self.blacklisted_tokens = {
            'SAFEMOON', 'SAFEMARS', 'HONEY', 'MOONSHOT', 'PUMP',
            'DUMP', 'SCAM', 'FAKE', 'TEST', 'DUMMY'
        }
        
        # Список подозрительных паттернов в названиях
        self.suspicious_patterns = [
            'INU', 'DOGE', 'SHIB', 'MOON', 'SAFE', 'ELON', 'MUSK',
            'BABY', 'MINI', 'MICRO', 'NANO', 'PICO'
        ]
    
    async def filter_rockets(self, tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Фильтрация токенов с улучшенными критериями
        
        Args:
            tokens: Список токенов для фильтрации
            
        Returns:
            List[Dict]: Отфильтрованные и валидированные токены
        """
        logger.info(f"[ENHANCED_FILTER] Начало фильтрации {len(tokens)} токенов")
        
        filtered_tokens = []
        validation_results = []
        
        for token in tokens:
            try:
                # 1. Базовая проверка названия и поддельных токенов
                if not self._check_token_name(token.get('symbol', '')):
                    continue
                
                # 1.5. Проверка на поддельный токен с использованием улучшенного детектора
                fake_result = await self.fake_detector.detect_fake_token(
                    token.get('symbol', ''),
                    token.get('address', ''),
                    token.get('chain_id', '')
                )
                if fake_result.is_fake:
                    logger.info(f"[ENHANCED_FILTER] Исключен поддельный токен {token.get('symbol')}: {fake_result.reason}")
                    continue
                
                # 2. Проверка базовых критериев
                if not self._check_basic_criteria(token):
                    continue
                
                # 3. Валидация токена
                validation_result = await self.validator.validate_token(
                    token.get('address', ''),
                    token.get('chain_id', ''),
                    token.get('symbol', '')
                )
                
                # 4. Применение результатов валидации
                if self._apply_validation_result(token, validation_result):
                    token['validation_result'] = validation_result
                    token['risk_score'] = self._calculate_risk_score(token, validation_result)
                    filtered_tokens.append(token)
                    validation_results.append(validation_result)
                
            except Exception as e:
                logger.error(f"Ошибка при фильтрации токена {token.get('symbol', 'unknown')}: {str(e)}")
                continue
        
        # Сортировка по риску и потенциалу
        filtered_tokens.sort(key=lambda x: x['risk_score'], reverse=True)
        
        logger.info(f"[ENHANCED_FILTER] Фильтрация завершена. Найдено {len(filtered_tokens)} валидных токенов")
        
        # Логирование статистики валидации
        self._log_validation_stats(validation_results)
        
        return filtered_tokens
    
    def _check_token_name(self, symbol: str) -> bool:
        """Проверка названия токена на подозрительность"""
        symbol_upper = symbol.upper()
        
        # Проверка черного списка
        if symbol_upper in self.blacklisted_tokens:
            logger.debug(f"Токен {symbol} в черном списке")
            return False
        
        # Проверка подозрительных паттернов
        suspicious_count = sum(1 for pattern in self.suspicious_patterns if pattern in symbol_upper)
        if suspicious_count >= 2:  # Если 2+ подозрительных паттерна
            logger.debug(f"Токен {symbol} содержит подозрительные паттерны")
            return False
        
        return True
    
    def _check_basic_criteria(self, token: Dict[str, Any]) -> bool:
        """Проверка базовых критериев"""
        # Проверка роста цены
        price_change_1h = token.get('price_change_1h', 0)
        price_change_24h = token.get('price_change_24h', 0)
        
        if price_change_1h < self.criteria.min_price_growth_1h:
            return False
        
        if price_change_24h < self.criteria.min_price_growth_24h:
            return False
        
        # Убрали ограничение максимального роста
        # if price_change_24h > self.criteria.max_price_growth_24h:
        #     logger.debug(f"Токен {token.get('symbol')} имеет подозрительно высокий рост: {price_change_24h}%")
        #     return False
        
        # Проверка ликвидности
        liquidity = token.get('liquidity_usd', 0)
        if liquidity < self.criteria.min_liquidity_usd:
            return False
        
        # Проверка объема
        volume = token.get('volume_24h', 0)
        if volume < self.criteria.min_volume_24h:
            return False
        
        # Проверка соотношения объем/ликвидность
        if liquidity > 0:
            volume_liquidity_ratio = volume / liquidity
            if volume_liquidity_ratio > self.criteria.max_volume_liquidity_ratio:
                logger.debug(f"Токен {token.get('symbol')} имеет подозрительное соотношение объем/ликвидность: {volume_liquidity_ratio}")
                return False
        
        return True
    
    def _apply_validation_result(self, token: Dict[str, Any], validation_result: TokenValidationResult) -> bool:
        """Применение результатов валидации"""
        # Проверка на поддельный токен
        if validation_result.is_fake:
            logger.info(f"Исключен поддельный токен: {token.get('symbol')}")
            return False
        
        # Проверка ошибок валидации
        if validation_result.errors:
            logger.info(f"Токен {token.get('symbol')} имеет ошибки валидации: {validation_result.errors}")
            return False
        
        # Проверка верификации контракта
        if self.criteria.require_verified_contract and not validation_result.is_verified:
            logger.debug(f"Токен {token.get('symbol')} не верифицирован")
            return False
        
        # Проверка ликвидности
        if validation_result.liquidity_usd < self.criteria.min_liquidity_usd:
            return False
        
        # Проверка объема
        if validation_result.volume_24h < self.criteria.min_volume_24h:
            return False
        
        # Проверка держателей
        if validation_result.holder_count < self.criteria.min_holders:
            return False
        
        # Проверка возраста контракта
        if validation_result.contract_age_days < self.criteria.min_contract_age_days:
            return False
        
        return True
    
    def _calculate_risk_score(self, token: Dict[str, Any], validation_result: TokenValidationResult) -> float:
        """Расчет оценки риска токена (0-100, где 100 - самый безопасный)"""
        score = 50.0  # Базовый балл
        
        # Бонусы за качество
        if validation_result.is_verified:
            score += 20
        
        if validation_result.holder_count > 1000:
            score += 15
        elif validation_result.holder_count > 500:
            score += 10
        
        if validation_result.contract_age_days > 30:
            score += 15
        elif validation_result.contract_age_days > 14:
            score += 10
        
        if validation_result.liquidity_usd > 100000:
            score += 10
        elif validation_result.liquidity_usd > 50000:
            score += 5
        
        # Штрафы за риски
        if validation_result.warnings:
            score -= len(validation_result.warnings) * 5
        
        # Штраф за высокую волатильность
        price_change_24h = abs(token.get('price_change_24h', 0))
        if price_change_24h > 200:
            score -= 20
        elif price_change_24h > 100:
            score -= 10
        
        return max(0, min(100, score))
    
    def _log_validation_stats(self, validation_results: List[TokenValidationResult]):
        """Логирование статистики валидации"""
        total = len(validation_results)
        if total == 0:
            return
        
        verified_count = sum(1 for r in validation_results if r.is_verified)
        fake_count = sum(1 for r in validation_results if r.is_fake)
        avg_liquidity = sum(r.liquidity_usd for r in validation_results) / total
        avg_holders = sum(r.holder_count for r in validation_results) / total
        
        logger.info(f"[ENHANCED_FILTER] Статистика валидации:")
        logger.info(f"  - Всего проверено: {total}")
        logger.info(f"  - Верифицированных: {verified_count} ({verified_count/total*100:.1f}%)")
        logger.info(f"  - Поддельных: {fake_count}")
        logger.info(f"  - Средняя ликвидность: ${avg_liquidity:,.0f}")
        logger.info(f"  - Среднее количество держателей: {avg_holders:.0f}") 