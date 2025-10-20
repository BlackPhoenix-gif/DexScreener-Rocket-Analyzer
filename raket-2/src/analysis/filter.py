import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from src.models.token import Token, TokenPair
from src.utils.logger import get_logger

logger = get_logger()

class RocketFilter:
    """
    Класс для фильтрации токенов и выявления потенциальных "ракет".
    """
    
    def __init__(self):
        """
        Инициализация фильтра с улучшенными параметрами.
        """
        # Загрузка критериев из переменных окружения
        self.min_price_growth_1h = float(os.environ.get('MIN_PRICE_GROWTH_1H', 20))
        self.min_price_growth_24h = float(os.environ.get('MIN_PRICE_GROWTH_24H', 50))
        self.max_price_growth_24h = float(os.environ.get('MAX_PRICE_GROWTH_24H', 999999))  # Практически не ограничено
        self.min_liquidity = float(os.environ.get('MIN_LIQUIDITY', 50000))  # Увеличено до $50K
        self.min_volume_24h = float(os.environ.get('MIN_VOLUME_24H', 10000))  # Увеличено до $10K
        self.max_token_age_hours = float(os.environ.get('MAX_TOKEN_AGE_HOURS', 168))  # 7 дней
        self.max_volume_liquidity_ratio = float(os.environ.get('MAX_VOLUME_LIQUIDITY_RATIO', 20))
        
        # Черный список подозрительных токенов
        self.blacklisted_tokens = {
            'SAFEMOON', 'SAFEMARS', 'HONEY', 'MOONSHOT', 'PUMP',
            'DUMP', 'SCAM', 'FAKE', 'TEST', 'DUMMY', 'BABY', 'MINI'
        }
        
        # Подозрительные паттерны в названиях
        self.suspicious_patterns = [
            'INU', 'DOGE', 'SHIB', 'MOON', 'SAFE', 'ELON', 'MUSK',
            'BABY', 'MINI', 'MICRO', 'NANO', 'PICO', 'PUMP', 'DUMP'
        ]
        
        # Известные токены и их правильные сети
        self.known_tokens_networks = {
            'BIAO': 'bsc',      # BIAO должен быть в BSC, не в Solana
            'PEPE': 'ethereum', # PEPE должен быть в Ethereum
            'UMA': 'ethereum',  # UMA должен быть в Ethereum
            'WOJAK': 'ethereum', # WOJAK должен быть в Ethereum
            'DOGE': 'ethereum', # DOGE должен быть в Ethereum
            'SHIB': 'ethereum', # SHIB должен быть в Ethereum
        }
        
        logger.info(f"[FILTER] Инициализация улучшенного фильтра ракет:")
        logger.info(f"[FILTER] Мин. рост цены 1ч: {self.min_price_growth_1h}%")
        logger.info(f"[FILTER] Мин. рост цены 24ч: {self.min_price_growth_24h}%")
        logger.info(f"[FILTER] Макс. рост цены 24ч: {self.max_price_growth_24h}%")
        logger.info(f"[FILTER] Мин. ликвидность: ${self.min_liquidity:,}")
        logger.info(f"[FILTER] Мин. объем торгов 24ч: ${self.min_volume_24h:,}")
        logger.info(f"[FILTER] Макс. возраст токена: {self.max_token_age_hours}ч")
        logger.info(f"[FILTER] Макс. соотношение объем/ликвидность: {self.max_volume_liquidity_ratio}")
    
    def is_rocket(self, token: Token) -> bool:
        """Проверяет, является ли токен потенциальной ракетой с улучшенными критериями"""
        
        # 1. Проверка названия токена
        if not self._check_token_name(token.symbol):
            logger.debug(f"[FILTER] Токен {token.symbol} исключен по названию")
            return False
        
        # 2. Проверка на поддельный токен
        if self._is_fake_token(token.symbol, token.chain_id):
            logger.info(f"[FILTER] Обнаружен поддельный токен {token.symbol} в сети {token.chain_id}")
            return False
        
        # 3. Проверка минимального объема торгов
        if token.total_volume_24h < self.min_volume_24h:
            logger.debug(f"[FILTER] Токен {token.symbol} исключен: низкий объем ${token.total_volume_24h:,.2f}")
            return False
            
        # 4. Проверка минимальной ликвидности
        if token.total_liquidity_usd < self.min_liquidity:
            logger.debug(f"[FILTER] Токен {token.symbol} исключен: низкая ликвидность ${token.total_liquidity_usd:,.2f}")
            return False
        
        # 5. Проверка соотношения объем/ликвидность
        if token.total_liquidity_usd > 0:
            volume_liquidity_ratio = token.total_volume_24h / token.total_liquidity_usd
            if volume_liquidity_ratio > self.max_volume_liquidity_ratio:
                logger.debug(f"[FILTER] Токен {token.symbol} исключен: подозрительное соотношение объем/ликвидность {volume_liquidity_ratio:.2f}")
                return False
            
        # 6. Проверка роста цены за 1 час
        if token.max_price_change_1h < self.min_price_growth_1h:
            logger.debug(f"[FILTER] Токен {token.symbol} исключен: низкий рост за 1ч {token.max_price_change_1h:.2f}%")
            return False
            
        # 7. Проверка роста цены за 24 часа
        if token.max_price_change_24h < self.min_price_growth_24h:
            logger.debug(f"[FILTER] Токен {token.symbol} исключен: низкий рост за 24ч {token.max_price_change_24h:.2f}%")
            return False
        
        # 8. Проверка максимального роста (убрана - теперь не ограничиваем)
        # if token.max_price_change_24h > self.max_price_growth_24h:
        #     logger.debug(f"[FILTER] Токен {token.symbol} исключен: подозрительно высокий рост {token.max_price_change_24h:.2f}%")
        #     return False
        
        # 9. Проверка возраста токена
        if token.age_hours > self.max_token_age_hours:
            logger.debug(f"[FILTER] Токен {token.symbol} исключен: слишком старый {token.age_hours:.1f}ч")
            return False
        
        logger.debug(f"[FILTER] Токен {token.symbol} прошел все проверки")
        return True
    
    def _check_token_name(self, symbol: str) -> bool:
        """Проверка названия токена на подозрительность"""
        symbol_upper = symbol.upper()
        
        # Проверка черного списка
        if symbol_upper in self.blacklisted_tokens:
            logger.debug(f"[FILTER] Токен {symbol} в черном списке")
            return False
        
        # Проверка подозрительных паттернов
        suspicious_count = sum(1 for pattern in self.suspicious_patterns if pattern in symbol_upper)
        if suspicious_count >= 2:  # Если 2+ подозрительных паттерна
            logger.debug(f"[FILTER] Токен {symbol} содержит {suspicious_count} подозрительных паттернов")
            return False
        
        return True
    
    def _is_fake_token(self, symbol: str, chain_id: str) -> bool:
        """Проверка на поддельный токен"""
        symbol_upper = symbol.upper()
        
        # Проверка известных токенов в неправильных сетях
        if symbol_upper in self.known_tokens_networks:
            correct_network = self.known_tokens_networks[symbol_upper]
            if chain_id != correct_network:
                logger.info(f"[FILTER] Поддельный токен: {symbol} должен быть в {correct_network}, а не в {chain_id}")
                return True
        
        return False
    
    def filter_rockets(self, tokens: List[Token]) -> List[Token]:
        """
        Фильтрует список токенов, оставляя только "ракеты" с улучшенными критериями.
        
        Args:
            tokens: Список токенов для фильтрации
            
        Returns:
            List[Token]: Список токенов, соответствующих критериям "ракет"
        """
        logger.info(f"[FILTER] Начало улучшенной фильтрации {len(tokens)} токенов")
        
        rockets = []
        excluded_count = 0
        fake_tokens_count = 0
        blacklisted_count = 0
        
        for token in tokens:
            try:
                if self.is_rocket(token):
                    token.is_rocket = True
                    rockets.append(token)
                else:
                    excluded_count += 1
                    
                    # Подсчет причин исключения
                    if self._is_fake_token(token.symbol, token.chain_id):
                        fake_tokens_count += 1
                    elif not self._check_token_name(token.symbol):
                        blacklisted_count += 1
                        
            except Exception as e:
                logger.error(f"[FILTER] Ошибка при фильтрации токена {token.symbol}: {str(e)}")
                excluded_count += 1
        
        logger.info(f"[FILTER] Фильтрация завершена:")
        logger.info(f"[FILTER] - Всего токенов: {len(tokens)}")
        logger.info(f"[FILTER] - Найдено ракет: {len(rockets)}")
        logger.info(f"[FILTER] - Исключено: {excluded_count}")
        logger.info(f"[FILTER] - Поддельных токенов: {fake_tokens_count}")
        logger.info(f"[FILTER] - В черном списке: {blacklisted_count}")
        
        return rockets
    
    def sort_rockets_by_potential(self, rockets: List[Token]) -> List[Token]:
        """
        Сортирует "ракеты" по потенциалу (комбинация роста цены и ликвидности).
        
        Args:
            rockets: Список "ракет" для сортировки
            
        Returns:
            List[Token]: Отсортированный список "ракет"
        """
        logger.info(f"[FILTER] Сортировка {len(rockets)} ракет по потенциалу")
        
        # Функция для расчета потенциала токена
        def calculate_potential(token: Token) -> float:
            # Комбинация роста цены и ликвидности с нормализацией
            price_growth = max(token.max_price_change_1h, token.max_price_change_24h / 3)
            liquidity_factor = min(1.0, token.total_liquidity_usd / 50000)  # Нормализация до 1.0
            volume_factor = min(1.0, token.total_volume_24h / 10000)  # Нормализация до 1.0
            
            # Формула потенциала (можно настроить веса)
            potential = price_growth * 0.6 + liquidity_factor * 0.3 + volume_factor * 0.1
            
            logger.debug(f"[FILTER] Потенциал токена {token.symbol}: {potential:.2f}")
            return potential
        
        # Сортировка по убыванию потенциала
        sorted_rockets = sorted(rockets, key=calculate_potential, reverse=True)
        
        logger.info(f"[FILTER] Сортировка завершена")
        return sorted_rockets

if __name__ == "__main__":
    # Пример использования
    from src.models.token import Token, TokenPair
    from datetime import datetime, timedelta
    
    # Создание тестовых данных
    now = datetime.now()
    
    # Создание тестовой пары
    pair1 = TokenPair(
        pair_address="0x1234567890abcdef",
        base_token=Token("0xabc", "Test Token", "TEST", chain_id="ethereum"),
        quote_token=Token("0xdef", "Ethereum", "ETH", chain_id="ethereum"),
        price_usd=0.5,
        price_native=0.0002,
        volume_24h=5000,
        liquidity_usd=10000,
        liquidity_native=4,
        price_change_1h=35,
        price_change_24h=120,
        created_at=now - timedelta(hours=24),
        dex_id="uniswap",
        chain_id="ethereum"
    )
    
    # Создание тестового токена
    token1 = Token(
        address="0xabc",
        name="Test Token",
        symbol="TEST",
        pairs=[pair1],
        chain_id="ethereum"
    )
    
    # Создание фильтра и проверка токена
    filter = RocketFilter()
    is_rocket = filter.is_rocket(token1)
    
    print(f"Токен {token1.symbol} является ракетой: {is_rocket}")
    
    # Проверка фильтрации списка
    tokens = [token1]
    rockets = filter.filter_rockets(tokens)
    
    print(f"Найдено {len(rockets)} ракет из {len(tokens)} токенов") 