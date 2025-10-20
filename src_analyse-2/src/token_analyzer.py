import json
import logging
import os
import asyncio
import sys
from datetime import datetime
import importlib.util
from typing import Dict, List, Optional, Union
import pandas as pd
from tqdm import tqdm
from colorama import init, Fore, Style

# Добавляем путь к raket-2 для импорта LiquidityLockChecker
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'raket-2'))
try:
    from src.analysis.liquidity_lock_checker import LiquidityLockChecker
except ImportError:
    print("⚠️ Не удалось импортировать LiquidityLockChecker. Проверка блокировки ликвидности будет пропущена.")
    LiquidityLockChecker = None

# Импорт анализатора безопасности (устойчивый к окружению)
SECURITY_ANALYZER_AVAILABLE = False
SecurityAnalyzer = None
try:
    from .analysis.security_analyzer import SecurityAnalyzer as _SA
    SecurityAnalyzer = _SA
    SECURITY_ANALYZER_AVAILABLE = True
except Exception as _e1:
    try:
        # Fallback: прямой импорт через sys.path
        sys.path.append(os.path.join(os.path.dirname(__file__), 'analysis'))
        from security_analyzer import SecurityAnalyzer as _SA2
        SecurityAnalyzer = _SA2
        SECURITY_ANALYZER_AVAILABLE = True
    except Exception as _e2:
        try:
            # Fallback 2: импорт по абсолютному пути к файлу
            analysis_dir = os.path.join(os.path.dirname(__file__), 'analysis')
            sa_path = os.path.join(analysis_dir, 'security_analyzer.py')
            spec = importlib.util.spec_from_file_location('security_analyzer', sa_path)
            if spec and spec.loader:
                sa_module = importlib.util.module_from_spec(spec)
                sys.modules['security_analyzer'] = sa_module
                spec.loader.exec_module(sa_module)
                SecurityAnalyzer = getattr(sa_module, 'SecurityAnalyzer', None)
                SECURITY_ANALYZER_AVAILABLE = SecurityAnalyzer is not None
        except Exception as _e3:
            print("⚠️ Не удалось импортировать SecurityAnalyzer. Анализ безопасности будет пропущен.")
            SECURITY_ANALYZER_AVAILABLE = False

# Инициализация colorama для цветного вывода
init()

def format_tax_percentage(tax_value):
    """Форматирование налогов в проценты"""
    if not tax_value or tax_value == '' or tax_value == '0':
        return '0'
    try:
        tax_float = float(tax_value)
        if tax_float == 0:
            return '0'
        elif tax_float < 1:
            # Если меньше 1, то это десятичная дробь - конвертируем в проценты
            return f"{tax_float * 100:.0f}"
        else:
            # Если больше или равно 1, то уже в процентах
            return f"{tax_float:.0f}"
    except (ValueError, TypeError):
        return str(tax_value) if tax_value else '0'

class Token:
    """Класс для хранения информации о токене"""
    def __init__(self, data: Dict):
        # Базовая информация о токене
        base_token = data.get('baseToken', {})
        self.address = base_token.get('address', '')
        self.name = base_token.get('name', '')
        self.symbol = base_token.get('symbol', '')
        self.network = data.get('chainId', '')
        
        # Информация о паре
        self.pair_address = data.get('pairAddress', '')
        self.dex_id = data.get('dexId', '')
        self.url = data.get('url', '')
        
        # Ценовые метрики
        self.price_usd = float(data.get('priceUsd', 0))
        self.price_native = float(data.get('priceNative', 0))
        
        # Объемы и ликвидность
        liquidity = data.get('liquidity', {})
        self.liquidity_usd = float(liquidity.get('usd', 0))
        
        volume = data.get('volume', {})
        self.volume_24h = float(volume.get('h24', 0))
        self.volume_6h = float(volume.get('h6', 0))
        self.volume_1h = float(volume.get('h1', 0))
        
        # Изменения цены
        price_change = data.get('priceChange', {})
        self.price_change_24h = float(price_change.get('h24', 0))
        self.price_change_6h = float(price_change.get('h6', 0))
        self.price_change_1h = float(price_change.get('h1', 0))
        
        # Транзакции
        txns = data.get('txns', {}).get('h24', {})
        self.buys_24h = int(txns.get('buys', 0))
        self.sells_24h = int(txns.get('sells', 0))
        
        # Рыночные показатели
        self.fdv = float(data.get('fdv', 0))
        self.market_cap = float(data.get('marketCap', 0))
        
        # Время создания
        created_at = data.get('pairCreatedAt', 0)
        self.age_hours = (datetime.now().timestamp() * 1000 - created_at) / (3600 * 1000) if created_at else 0
        
        # Дополнительная информация
        self.info = data.get('info', {})
        
        # Аналитические поля
        self.risk_score = 0
        self.risk_level = "Низкий"
        self.risk_factors = []
        
        # Поля безопасности
        self.security_report = None
        self.security_score = 0.0
        self.security_issues = []
        self.contract_verified = False
        self.ownership_renounced = False
        self.liquidity_locked = False
        self.liquidity_lock_period = None
        self.honeypot_probability = 0.0
        
    def calculate_risk_score(self, config: Dict) -> int:
        """Расчет риск-скора на основе метрик токена с весовыми коэффициентами"""
        score = 0
        score_breakdown = []  # Детальная разбивка для прозрачности
        risk_thresholds = config.get('risk_thresholds', {})
        
        # Проверка изменения цены
        if self.price_change_24h > config.get('price_change_thresholds', {}).get('suspicious', {}).get('min', 1000):
            score += 30
            self.risk_factors.append(f"Аномальный рост цены: {self.price_change_24h:.2f}%")
        
        # 🚨 КРИТИЧНО: Проверка возраста токена - молодые токены автоматически высокий риск
        if self.age_hours < 24:
            score += 50  # Критичный штраф для токенов младше 24ч
            self.risk_factors.append(f"🚨 КРИТИЧНО: Новый токен (<24ч): {self.age_hours:.2f} часов")
        elif self.age_hours < 168:  # Меньше недели
            score += 20
            self.risk_factors.append(f"Молодой токен (<7 дней): {self.age_hours:.2f} часов")
        
        # Проверка ликвидности
        if self.liquidity_usd < config.get('liquidity_thresholds', {}).get('high_risk', 1000):
            score += 15
            self.risk_factors.append(f"Низкая ликвидность: ${self.liquidity_usd:.2f}")
        
        # Соотношение объема к ликвидности
        vol_liq_ratio = self.volume_24h / self.liquidity_usd if self.liquidity_usd > 0 else 0
        if vol_liq_ratio > config.get('volume_liquidity_ratios', {}).get('suspicious', {}).get('min', 5):
            score += 25
            self.risk_factors.append(f"Подозрительное соотношение объема к ликвидности: {vol_liq_ratio:.2f}")
        
        # Проверка наличия сайта и соцсетей
        has_website = bool(self.info.get("websites", []))
        has_socials = bool(self.info.get("socials", []))
        if not has_website and not has_socials:
            score += 20
            self.risk_factors.append("Нет информации о сайте и социальных сетях")
        
        # Анализ транзакций
        total_txns = self.buys_24h + self.sells_24h
        if total_txns > 0:
            sell_ratio = self.sells_24h / total_txns
            if sell_ratio > 0.8:  # Если более 80% транзакций - продажи
                score += 25
                self.risk_factors.append(f"Высокий процент продаж: {sell_ratio*100:.1f}%")
        
        # 🚨 КРИТИЧНО: Блокировка ликвидности - без нее автоматом +2 уровня риска
        if hasattr(self, 'liquidity_lock_score') and self.liquidity_lock_score is not None:
            if self.liquidity_lock_score == 0:
                score += 60  # Критичный штраф за отсутствие блокировки
                self.risk_factors.append("🚨 КРИТИЧНО: Ликвидность НЕ заблокирована - высокий риск rug pull!")
            elif self.liquidity_lock_score < 30:
                score += 40  # Усиленный штраф за плохую блокировку
                self.risk_factors.append(f"⚠️ Низкий уровень блокировки ликвидности: {self.liquidity_lock_score}/100")
            elif self.liquidity_lock_score < 60:
                score += 20  # Умеренный штраф
                self.risk_factors.append(f"⚠️ Средний уровень блокировки ликвидности: {self.liquidity_lock_score}/100")
        else:
            # СМЯГЧЕНО: Для крупных/зрелых токенов меньший штраф
            has_high_liquidity = self.liquidity_usd >= 100000
            has_mature_age = self.age_hours >= 720  # 30+ дней
            
            if has_high_liquidity and has_mature_age:
                score += 10  # Минимальный штраф для крупных токенов
                self.risk_factors.append("Статус блокировки ликвидности не проверен (но токен крупный/зрелый)")
            else:
                score += 20  # Обычный штраф
                self.risk_factors.append("Статус блокировки ликвидности не проверен")
        
        # 🎯 КРИТИЧЕСКИЕ ФИЛЬТРЫ БЕЗОПАСНОСТИ
        
        # 1. Проверка блокировки ликвидности
        liquidity_lock_percentage = 0
        if hasattr(self, 'liquidity_lock_info') and self.liquidity_lock_info and self.liquidity_lock_info.is_locked:
            liquidity_lock_percentage = self.liquidity_lock_info.locked_percentage
        
        # 2. 📊 КРИТИЧЕСКИЙ ФАКТОР: Соотношение объем/ликвидность (вес: высокий)
        volume_ratio = self.volume_24h / self.liquidity_usd if self.liquidity_usd > 0 else 0
        if volume_ratio > 20:
            penalty = 25  # Красный флаг - возможна манипуляция
            score += penalty
            score_breakdown.append(f"V/L>20: +{penalty}")
            self.risk_factors.append("Подозрительно высокое соотношение объем/ликвидность - возможна манипуляция")
        elif volume_ratio > 5:
            penalty = 10  # Желтый флаг - повышенная волатильность
            score += penalty
            score_breakdown.append(f"V/L>5: +{penalty}")
            self.risk_factors.append("Высокое соотношение объем/ликвидность - повышенная волатильность")
        
        # 3. ⚠️ ВАЖНЫЙ ФАКТОР: Экстремальный рост (вес: высокий)
        if self.price_change_24h > 500:
            penalty = 30
            score += penalty
            score_breakdown.append(f"Рост>500%: +{penalty}")
            self.risk_factors.append("Экстремальный рост >500% - подозрение на памп-схему")
        
        # 🚨 УЖЕСТОЧЕННЫЕ ПОРОГИ РИСКА с учетом критичных штрафов
        if score >= 120:  # Критичные проблемы (молодость + отсутствие блокировки = 110+ баллов)
            self.risk_level = "Скам"
        elif score >= 80:   # Серьезные проблемы
            self.risk_level = "Высокий"
        elif score >= 50:   # Умеренные проблемы
            self.risk_level = "Средний"
        elif score >= 25:   # Небольшие проблемы
            self.risk_level = "Умеренный"
        else:
            # 🚨 УЖЕСТОЧЕННАЯ ЛОГИКА для "Низкий риск" - только безопасные токены
            # Базовые требования для низкого риска (реалистичные для инвестиций)
            if self.liquidity_usd < 100000:  # Возвращаем требование $100K
                self.risk_level = "Умеренный"
                self.risk_factors.append("Недостаточная ликвидность для низкого риска (<$100K)")
            # 🚨 КРИТИЧНО: Без блокировки ликвидности НЕ может быть "Низкий риск"!
            elif liquidity_lock_percentage == 0:
                is_verified = False
                if hasattr(self, 'verification_result') and self.verification_result:
                    is_verified = self.verification_result.is_verified
                
                if not is_verified:
                    self.risk_level = "Средний"  # Неверифицированный без блокировки = средний риск
                    self.risk_factors.append("Неверифицированный контракт без блокировки ликвидности")
                else:
                    # Даже верифицированный без блокировки = максимум умеренный риск
                    self.risk_level = "Умеренный"
                    self.risk_factors.append("Ликвидность не заблокирована - риск rug pull даже для верифицированного контракта")
            # Частичная блокировка (30%+) с хорошей ликвидностью = низкий риск
            elif liquidity_lock_percentage >= 30 and self.liquidity_usd >= 100000:
                self.risk_level = "Низкий"
            # Полная блокировка (75%+) = низкий риск независимо от верификации
            elif liquidity_lock_percentage >= 75:
                self.risk_level = "Низкий"
            else:
                self.risk_level = "Умеренный"
        
        # ДОПОЛНИТЕЛЬНЫЕ ПРОВЕРКИ для среднего риска
        if self.risk_level == "Средний":
            # Минимальная ликвидность $50K для среднего риска
            if self.liquidity_usd < 50000:
                self.risk_level = "Высокий"
                self.risk_factors.append("Недостаточная ликвидность для среднего риска (<$50K)")
        
        # ДОПОЛНИТЕЛЬНЫЕ ПРОВЕРКИ для высокого риска
        if self.risk_level == "Высокий":
            # Минимальная ликвидность $25K для высокого риска
            if self.liquidity_usd < 25000:
                self.risk_level = "Скам"
                self.risk_factors.append("Критически низкая ликвидность (<$25K)")
        
        # Сохраняем детальную разбивку для отчетов
        self.score_breakdown = score_breakdown
        self.risk_score = score
        
        # Логируем детальную разбивку для прозрачности
        if score_breakdown:
            # Используем print для отладки, так как logger не доступен в методе Token
            print(f"[RISK_SCORE] {self.symbol}: Итого {score} баллов. Разбивка: {', '.join(score_breakdown)}")
        
        return score
    
    def get_explorer_url(self) -> str:
        """Возвращает URL на блокчейн-эксплорер для просмотра токена"""
        explorers = {
            'solana': f'https://solscan.io/token/{self.address}',
            'ethereum': f'https://etherscan.io/token/{self.address}',
            'bsc': f'https://bscscan.com/token/{self.address}',
            'arbitrum': f'https://arbiscan.io/token/{self.address}',
            'polygon': f'https://polygonscan.com/token/{self.address}'
        }
        return explorers.get(self.network.lower(), f'https://dexscreener.com/{self.network}/{self.address}')
    
    def get_dex_url(self) -> str:
        """Возвращает URL на DEX для торговли токеном"""
        dex_urls = {
            'solana': f'https://jup.ag/swap/SOL-{self.address}',
            'ethereum': f'https://app.uniswap.org/#/swap?outputCurrency={self.address}',
            'bsc': f'https://pancakeswap.finance/swap?outputCurrency={self.address}',
            'arbitrum': f'https://app.uniswap.org/#/swap?outputCurrency={self.address}',
            'polygon': f'https://quickswap.exchange/#/swap?outputCurrency={self.address}',
            'zksync': f'https://syncswap.xyz/swap?outputCurrency={self.address}',
            'pulsechain': f'https://app.pulsex.com/swap?outputCurrency={self.address}'
        }
        return dex_urls.get(self.network.lower(), f'https://dexscreener.com/{self.network}/{self.address}')
    
    def get_dexscreener_url(self) -> str:
        """Возвращает URL на DexScreener для анализа графика"""
        return f'https://dexscreener.com/{self.network.lower()}/{self.address}'
    
    def format_age(self) -> str:
        """Форматирует возраст токена в читаемый вид"""
        hours = self.age_hours
        
        years = int(hours / (24 * 365))
        hours = hours % (24 * 365)
        
        months = int(hours / (24 * 30))
        hours = hours % (24 * 30)
        
        weeks = int(hours / (24 * 7))
        hours = hours % (24 * 7)
        
        days = int(hours / 24)
        hours = int(hours % 24)
        
        parts = []
        if years > 0:
            parts.append(f"{years}г")
        if months > 0:
            parts.append(f"{months}м")
        if weeks > 0:
            parts.append(f"{weeks}н")
        if days > 0:
            parts.append(f"{days}д")
        if hours > 0 and len(parts) == 0:
            parts.append(f"{hours}ч")
            
        return " ".join(parts)
    
    def format_money(self, amount: float) -> str:
        """Форматирует денежные значения в читаемый вид"""
        if amount >= 1_000_000_000:  # миллиарды
            return f"${amount / 1_000_000_000:.2f}B"
        elif amount >= 1_000_000:  # миллионы
            return f"${amount / 1_000_000:.2f}M"
        elif amount >= 1_000:  # тысячи
            return f"${amount / 1_000:.2f}K"
        else:
            return f"${amount:.2f}"
    
    def to_dict(self) -> Dict:
        """Преобразует токен в словарь для экспорта"""
        base_dict = {
            'address': self.address,
            'name': self.name,
            'symbol': self.symbol,
            'network': self.network,
            'pair_address': self.pair_address,
            'dex_id': self.dex_id,
            'url': self.url,
            'price_usd': self.price_usd,
            'price_native': self.price_native,
            'liquidity_usd': self.liquidity_usd,
            'volume_24h': self.volume_24h,
            'volume_6h': self.volume_6h,
            'volume_1h': self.volume_1h,
            'price_change_24h': self.price_change_24h,
            'price_change_6h': self.price_change_6h,
            'price_change_1h': self.price_change_1h,
            'buys_24h': self.buys_24h,
            'sells_24h': self.sells_24h,
            'fdv': self.fdv,
            'market_cap': self.market_cap,
            'age_hours': self.age_hours,
            'risk_score': self.risk_score,
            'risk_level': self.risk_level,
            'risk_factors': self.risk_factors,
            'info': self.info
        }
        
        # Добавляем поля безопасности
        if hasattr(self, 'security_score'):
            base_dict.update({
                'security_score': self.security_score,
                'security_issues': self.security_issues,
                'contract_verified': self.contract_verified,
                'ownership_renounced': self.ownership_renounced,
                'liquidity_locked': self.liquidity_locked,
                'honeypot_probability': self.honeypot_probability
            })
        
        return base_dict

class TokenAnalyzer:
    """Класс для анализа списка токенов"""
    def __init__(self, config_path: str = 'config.json'):
        self.tokens: List[Token] = []
        self.filtered_tokens: List[Token] = []
        self.scam_tokens: List[Token] = []
        self.high_risk_tokens: List[Token] = []
        self.medium_risk_tokens: List[Token] = []
        self.low_risk_tokens: List[Token] = []
        self.config = self._load_config(config_path)
        self.logger = self._setup_logger()
        self.contract_verifier = None  # Будет инициализирован при необходимости
        
        # Инициализация анализатора безопасности
        self.security_analyzer = None
        if SECURITY_ANALYZER_AVAILABLE and self.config.get('security_analysis', {}).get('enabled', False):
            try:
                self.security_analyzer = SecurityAnalyzer(self.config)
                self.logger.info("✅ Анализатор безопасности инициализирован")
            except Exception as e:
                self.logger.warning(f"⚠️ Не удалось инициализировать анализатор безопасности: {e}")
                self.security_analyzer = None
    
    def _load_config(self, config_path: str) -> Dict:
        """Загружает конфигурацию из файла"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"{Fore.RED}Ошибка при загрузке конфигурации: {str(e)}{Style.RESET_ALL}")
            return {}
    
    def _setup_logger(self) -> logging.Logger:
        """Настройка логгера"""
        logger = logging.getLogger("token_analyzer")
        logger.setLevel(logging.DEBUG)
        
        # Создание директории для логов
        os.makedirs('logs', exist_ok=True)
        
        # Создание хендлера для вывода в консоль
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Создание хендлера для записи в файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_handler = logging.FileHandler(f"logs/analysis_{timestamp}.log")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s')
        file_handler.setFormatter(file_formatter)
        
        # Добавление хендлеров к логгеру
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger
    
    def load_from_json(self, file_path: str) -> int:
        """Загружает токены из JSON-файла"""
        self.logger.info(f"Загрузка токенов из файла: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if 'rockets' in data:
                tokens_data = data['rockets']
                self.tokens = []
                for token_data in tqdm(tokens_data, desc="Загрузка токенов"):
                    token = Token(token_data)
                    self.tokens.append(token)
                
                self.logger.info(f"Загружено {len(self.tokens)} токенов")
                return len(self.tokens)
            else:
                error_msg = "Некорректный формат JSON: отсутствует ключ 'rockets'"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Ошибка при загрузке файла: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    async def verify_contracts(self, tokens: List[Token]) -> None:
        """Верификация контрактов через API с batch-оптимизацией"""
        if not tokens:
            return
        
        self.logger.info(f"[VERIFICATION] Начало batch верификации {len(tokens)} контрактов")
        
        # Инициализируем верификатор если нужно
        if self.contract_verifier is None:
            try:
                import sys
                import os
                sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'raket-2'))
                from src.analysis.contract_verifier import ContractVerifier
                self.contract_verifier = ContractVerifier()
            except ImportError:
                self.logger.warning("[VERIFICATION] Модуль верификации недоступен, пропускаем верификацию")
                return
        
        async with self.contract_verifier as verifier:
            # Подготавливаем данные для batch-запросов
            contracts_data = [(token.address, token.network) for token in tokens]
            
            # Выполняем batch верификацию с прогресс-баром
            verification_results = await verifier.verify_contracts_batch(contracts_data, show_progress=True)
            
            # Применяем результаты к токенам
            honeypot_count = 0
            verified_count = 0
            suspicious_count = 0
            
            for token in tokens:
                if token.address in verification_results:
                    verification_result = verification_results[token.address]
                    token.verification_result = verification_result
                    
                    # Счетчики для статистики
                    if verification_result.is_verified:
                        verified_count += 1
                    if verification_result.is_honeypot:
                        honeypot_count += 1
                    
                    # Добавляем факторы риска на основе верификации
                    if verification_result.is_honeypot:
                        token.risk_factors.append("Honeypot токен")
                        token.risk_score += 50
                        self.logger.warning(f"🚨 HONEYPOT обнаружен: {token.symbol} ({token.address[:20]}...)")
                    
                    if not verification_result.is_verified:
                        # СМЯГЧЕНО: Проверяем исключения для крупных/зрелых токенов
                        has_high_liquidity = token.liquidity_usd >= 100000  # $100K+
                        has_mature_age = token.age_hours >= 720  # 30+ дней
                        has_social_presence = bool(token.info.get("websites", [])) or bool(token.info.get("socials", []))
                        
                        # Если токен соответствует критериям исключения - меньший штраф
                        if has_high_liquidity and (has_mature_age or has_social_presence):
                            token.risk_factors.append("Неверифицированный контракт (но крупный/зрелый)")
                            token.risk_score += 5  # Минимальный штраф
                        else:
                            token.risk_factors.append("Неверифицированный контракт")
                            token.risk_score += 15  # Обычный штраф
                    
                    if verification_result.can_take_back_ownership:
                        token.risk_factors.append("Владелец может вернуть права")
                        token.risk_score += 20
                        suspicious_count += 1
                    
                    if verification_result.has_mint_function:
                        token.risk_factors.append("Есть функция mint")
                        token.risk_score += 10
                        suspicious_count += 1
                    
                    if verification_result.has_blacklist:
                        token.risk_factors.append("Есть функция blacklist")
                        token.risk_score += 15
                        suspicious_count += 1
                    
                    if verification_result.is_proxy:
                        token.risk_factors.append("Proxy контракт")
                        token.risk_score += 10
                        suspicious_count += 1
                    
                    # Обновляем уровень риска
                    if token.risk_score >= 80:
                        token.risk_level = "Скам"
                    elif token.risk_score >= 60:
                        token.risk_level = "Высокий"
                    elif token.risk_score >= 40:
                        token.risk_level = "Средний"
                    else:
                        token.risk_level = "Низкий"
                else:
                    # Создаем пустой результат для токенов без верификации
                    try:
                        import sys
                        import os
                        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'raket-2'))
                        from src.analysis.contract_verifier import ContractVerificationResult
                        token.verification_result = ContractVerificationResult()
                        token.verification_result.error_message = "Не удалось верифицировать"
                    except ImportError:
                        # Создаем простой объект если импорт не удался
                        class SimpleVerificationResult:
                            def __init__(self):
                                self.is_verified = False
                                self.is_honeypot = False
                                self.error_message = "Не удалось верифицировать"
                        token.verification_result = SimpleVerificationResult()
            
            # Выводим детальную статистику верификации
            self.logger.info(f"[VERIFICATION] Batch верификация завершена.")
            self.logger.info(f"[VERIFICATION] 📊 Статистика:")
            self.logger.info(f"[VERIFICATION]   🔍 Всего контрактов: {len(tokens)}")
            self.logger.info(f"[VERIFICATION]   ✅ Верифицировано: {verified_count}")
            self.logger.info(f"[VERIFICATION]   🍯 Honeypot найдено: {honeypot_count}")
            self.logger.info(f"[VERIFICATION]   ⚠️  Подозрительных функций: {suspicious_count}")
            
            if honeypot_count > 0:
                self.logger.warning(f"[VERIFICATION] 🚨 ВНИМАНИЕ: Обнаружено {honeypot_count} honeypot токенов!")
            else:
                self.logger.info(f"[VERIFICATION] ✅ Honeypot токены не обнаружены")
    
    async def check_liquidity_locks(self, tokens: List['Token']):
        """Проверяет блокировку ликвидности для всех токенов"""
        if LiquidityLockChecker is None:
            self.logger.warning("[LIQUIDITY_LOCK] LiquidityLockChecker недоступен, проверка пропущена")
            for token in tokens:
                token.liquidity_lock_info = None
                token.liquidity_lock_score = 0
            return
            
        self.logger.info(f"[LIQUIDITY_LOCK] Начало проверки блокировки ликвидности для {len(tokens)} токенов")
        
        async with LiquidityLockChecker() as lock_checker:
            checked_count = 0
            locked_count = 0
            
            for token in tqdm(tokens, desc="🔒 Проверка блокировки ликвидности"):
                try:
                    if token.pair_address and token.address and token.network:
                        # Проверяем блокировку ликвидности
                        lock_info = await lock_checker.check_liquidity_lock(
                            token.address, 
                            token.pair_address, 
                            token.network
                        )
                        
                        # Сохраняем информацию о блокировке
                        token.liquidity_lock_info = lock_info
                        token.liquidity_lock_score = lock_checker.get_lock_score(lock_info)
                        # ВАЖНО: Проставляем агрегированные поля, используемые далее в SecurityAnalyzer
                        token.liquidity_locked = bool(lock_info.is_locked)
                        token.liquidity_lock_period = lock_info.lock_duration_days if lock_info.lock_duration_days else None
                        
                        checked_count += 1
                        if lock_info.is_locked:
                            locked_count += 1
                            
                        self.logger.debug(f"[LIQUIDITY_LOCK] {token.symbol}: блокировка={lock_info.is_locked}, оценка={token.liquidity_lock_score}/100")
                    else:
                        # Если нет необходимых данных
                        token.liquidity_lock_info = None
                        token.liquidity_lock_score = 0
                        token.liquidity_locked = False
                        token.liquidity_lock_period = None
                        self.logger.debug(f"[LIQUIDITY_LOCK] {token.symbol}: пропущен (нет pair_address или address)")
                        
                except Exception as e:
                    self.logger.error(f"[LIQUIDITY_LOCK] Ошибка при проверке {token.symbol}: {str(e)}")
                    token.liquidity_lock_info = None
                    token.liquidity_lock_score = 0
                    token.liquidity_locked = False
                    token.liquidity_lock_period = None
                    
        self.logger.info(f"[LIQUIDITY_LOCK] 📊 Статистика:")
        self.logger.info(f"[LIQUIDITY_LOCK]   🔍 Проверено токенов: {checked_count}")
        self.logger.info(f"[LIQUIDITY_LOCK]   🔒 С заблокированной ликвидностью: {locked_count}")
        self.logger.info(f"[LIQUIDITY_LOCK]   ⚠️ Пропущено (нет данных): {len(tokens) - checked_count}")
    
    async def analyze_security(self, tokens: List[Token]):
        """Анализ безопасности токенов"""
        if not self.security_analyzer:
            return
        
        # Фильтруем токены - исключаем скам
        tokens_to_analyze = [token for token in tokens if token.risk_level != "Скам"]
        
        self.logger.info(f"[SECURITY] Начало анализа безопасности {len(tokens_to_analyze)} токенов (исключая {len(tokens) - len(tokens_to_analyze)} скам-токенов)")
        
        analyzed_count = 0
        security_issues_count = 0
        
        for token in tqdm(tokens_to_analyze, desc="Анализ безопасности"):
            try:
                # Подготовка данных для анализа
                token_data = {
                    'address': token.address,
                    'name': token.name,
                    'symbol': token.symbol,
                    'chainId': token.network,
                    'volume_24h': token.volume_24h,
                    'price_change_24h': token.price_change_24h,
                    'buys_24h': token.buys_24h,
                    'sells_24h': token.sells_24h,
                    'market_cap': token.market_cap,
                    'liquidity_locked': getattr(token, 'liquidity_locked', False),
                    'liquidity_lock_period': getattr(token, 'liquidity_lock_period', None),
                    'total_holders': getattr(token, 'total_holders', 0),
                    'top_10_percent': getattr(token, 'top_10_percent', 0.0)
                }
                
                # Анализ безопасности
                security_report = await self.security_analyzer.analyze_token_security(token_data)
                
                # Обновление полей токена
                token.security_report = security_report
                token.security_score = security_report.risk_assessment.overall_score
                token.contract_verified = security_report.contract_analysis.verified
                token.ownership_renounced = security_report.ownership.renounced
                token.liquidity_locked = security_report.distribution.liquidity_locked
                token.honeypot_probability = security_report.contract_analysis.honeypot_probability
                
                # Сбор проблем безопасности
                security_issues = []
                if security_report.contract_analysis.security_issues:
                    security_issues.extend(security_report.contract_analysis.security_issues)
                if security_report.ownership.security_issues:
                    security_issues.extend(security_report.ownership.security_issues)
                if security_report.distribution.security_issues:
                    security_issues.extend(security_report.distribution.security_issues)
                if security_report.trading.security_issues:
                    security_issues.extend(security_report.trading.security_issues)
                
                token.security_issues = security_issues
                
                if security_issues:
                    security_issues_count += 1
                
                analyzed_count += 1
                
                # Небольшая задержка для избежания rate limiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"[SECURITY] Ошибка при анализе безопасности {token.symbol}: {str(e)}")
                token.security_score = 1.0  # Максимальный риск при ошибке
                token.security_issues = [f"Ошибка анализа: {str(e)}"]
        
        self.logger.info(f"[SECURITY] 📊 Статистика безопасности:")
        self.logger.info(f"[SECURITY]   🔍 Проанализировано токенов: {analyzed_count}")
        self.logger.info(f"[SECURITY]   ⚠️ С проблемами безопасности: {security_issues_count}")
        self.logger.info(f"[SECURITY]   ⚠️ Пропущено (ошибки): {len(tokens) - analyzed_count}")
    
    async def analyze_all_tokens(self):
        """Анализирует все токены и распределяет их по категориям риска"""
        self.logger.info("Начало анализа всех токенов")
        
        # Сначала верифицируем контракты
        self.logger.info("[ANALYSIS] Этап 1: Верификация контрактов")
        await self.verify_contracts(self.tokens)
        
        # Проверяем блокировку ликвидности
        self.logger.info("[ANALYSIS] Этап 2: Проверка блокировки ликвидности")
        await self.check_liquidity_locks(self.tokens)
        
        # Анализ безопасности
        if self.security_analyzer:
            self.logger.info("[ANALYSIS] Этап 3: Анализ безопасности")
            await self.analyze_security(self.tokens)
        
        # Затем анализируем риски
        self.logger.info("[ANALYSIS] Этап 4: Анализ рисков")
        self.scam_tokens = []
        self.high_risk_tokens = []
        self.medium_risk_tokens = []
        self.low_risk_tokens = []
        
        for token in tqdm(self.tokens, desc="Анализ токенов"):
            risk_score = token.calculate_risk_score(self.config)
            
            if token.risk_level == "Скам":
                self.scam_tokens.append(token)
            elif token.risk_level == "Высокий":
                self.high_risk_tokens.append(token)
            elif token.risk_level == "Средний":
                self.medium_risk_tokens.append(token)
            else:
                self.low_risk_tokens.append(token)
        
        self.logger.info(f"[ANALYSIS] Анализ завершен. Скам: {len(self.scam_tokens)}, Высокий риск: {len(self.high_risk_tokens)}, Средний риск: {len(self.medium_risk_tokens)}, Низкий риск: {len(self.low_risk_tokens)}")
    
    def analyze_all_tokens_sync(self):
        """Синхронная версия анализа (без верификации)"""
        self.logger.info("Начало анализа всех токенов (без верификации)")
        
        self.scam_tokens = []
        self.high_risk_tokens = []
        self.medium_risk_tokens = []
        self.low_risk_tokens = []
        
        for token in tqdm(self.tokens, desc="Анализ токенов"):
            risk_score = token.calculate_risk_score(self.config)
            
            if token.risk_level == "Скам":
                self.scam_tokens.append(token)
            elif token.risk_level == "Высокий":
                self.high_risk_tokens.append(token)
            elif token.risk_level == "Средний":
                self.medium_risk_tokens.append(token)
            else:
                self.low_risk_tokens.append(token)
        
        self.logger.info(f"Анализ завершен. Скам: {len(self.scam_tokens)}, Высокий риск: {len(self.high_risk_tokens)}, Средний риск: {len(self.medium_risk_tokens)}, Низкий риск: {len(self.low_risk_tokens)}")
    
    def filter_tokens(self, filters: Optional[Dict] = None) -> List[Token]:
        """Фильтрует токены по заданным критериям"""
        if filters is None:
            filters = {}
        
        self.logger.info("Применение фильтров к списку токенов")
        
        self.filtered_tokens = []
        filter_criteria = []
        
        for token in tqdm(self.tokens, desc="Фильтрация токенов"):
            # Пропускаем скам-токены, если указано
            if filters.get('exclude_scam', self.config.get('exclude_scam', True)) and token.risk_level == "Скам":
                continue
            
            # Проверка по возрасту
            if filters.get('min_age') is not None and token.age_hours < filters['min_age']:
                continue
            if filters.get('max_age') is not None and token.age_hours > filters['max_age']:
                continue
            
            # Проверка по изменению цены
            if filters.get('min_price_change') is not None and token.price_change_24h < filters['min_price_change']:
                continue
            if filters.get('max_price_change') is not None and token.price_change_24h > filters['max_price_change']:
                continue
            
            # Проверка по ликвидности
            if filters.get('min_liquidity') is not None and token.liquidity_usd < filters['min_liquidity']:
                continue
            if filters.get('max_liquidity') is not None and token.liquidity_usd > filters['max_liquidity']:
                continue
            
            # Проверка по сети
            if filters.get('networks') is not None and token.network.lower() not in [net.lower() for net in filters['networks']]:
                continue
            
            # Если прошли все фильтры, добавляем токен
            self.filtered_tokens.append(token)
        
        self.logger.info(f"После фильтрации осталось {len(self.filtered_tokens)} токенов")
        return self.filtered_tokens
    
    def export_to_csv(self, file_path: str, tokens_list: Optional[List[Token]] = None) -> bool:
        """Экспортирует список токенов в CSV-файл"""
        if tokens_list is None:
            tokens_list = self.filtered_tokens if self.filtered_tokens else self.tokens
        
        self.logger.info(f"Экспорт {len(tokens_list)} токенов в CSV: {file_path}")
        try:
            df = pd.DataFrame([token.to_dict() for token in tokens_list])
            df.to_csv(file_path, index=False, encoding='utf-8')
            self.logger.info(f"Экспорт в CSV успешно завершен")
            return True
        except Exception as e:
            error_msg = f"Ошибка при экспорте в CSV: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def generate_text_report(self, file_path: str, tokens_list: Optional[List[Token]] = None, detailed: bool = True, report_title: str = "АНАЛИЗ ТОКЕНОВ") -> bool:
        """Генерирует текстовый отчет по токенам"""
        if tokens_list is None:
            tokens_list = self.filtered_tokens if self.filtered_tokens else self.tokens
        
        report_type = "Детальный" if detailed else "Краткий"
        self.logger.info(f"Генерация {report_type.lower()} текстового отчета: {file_path}")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # Заголовок отчета
                f.write("=" * 80 + "\n")
                f.write(" " * 30 + "ОТЧЕТ ПО АНАЛИЗУ ТОКЕНОВ" + " " * 30 + "\n")
                f.write("=" * 80 + "\n\n")
                
                # Основная информация
                f.write("ОСНОВНАЯ ИНФОРМАЦИЯ\n")
                f.write("-" * 80 + "\n")
                f.write(f"Дата и время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Тип отчета: {report_type}\n")
                f.write(f"Всего анализируемых токенов: {len(tokens_list)}\n\n")
                
                # Статистика
                f.write("СТАТИСТИКА\n")
                f.write("-" * 80 + "\n")
                
                # Таблица распределения по уровням риска
                risk_levels = {"Скам": 0, "Высокий": 0, "Средний": 0, "Умеренный": 0, "Низкий": 0}
                networks = {}
                
                for token in tokens_list:
                    risk_levels[token.risk_level] = risk_levels.get(token.risk_level, 0) + 1
                    networks[token.network] = networks.get(token.network, 0) + 1
                
                f.write("Распределение по уровням риска:\n")
                f.write("┌────────────────┬──────────┬──────────┐\n")
                f.write("│ Уровень риска  │Количество│ Процент  │\n")
                f.write("├────────────────┼──────────┼──────────┤\n")
                for level, count in risk_levels.items():
                    percentage = (count / len(tokens_list)) * 100 if tokens_list else 0
                    f.write(f"│ {level:14} │ {count:8} │ {percentage:7.1f}% │\n")
                f.write("└────────────────┴──────────┴──────────┘\n\n")
                
                f.write("Распределение по сетям:\n")
                f.write("┌────────────────┬──────────┬──────────┐\n")
                f.write("│ Сеть           │Количество│ Процент  │\n")
                f.write("├────────────────┼──────────┼──────────┤\n")
                for network, count in sorted(networks.items()):
                    percentage = (count / len(tokens_list)) * 100 if tokens_list else 0
                    f.write(f"│ {network:14} │ {count:8} │ {percentage:7.1f}% │\n")
                f.write("└────────────────┴──────────┴──────────┘\n\n")
                
                # Отчет по категориям риска
                for risk_level in ["Скам", "Высокий", "Средний", "Умеренный", "Низкий"]:
                    level_tokens = [t for t in tokens_list if t.risk_level == risk_level]
                    if not level_tokens:
                        continue
                    
                    f.write(f"ТОКЕНЫ С УРОВНЕМ РИСКА: {risk_level.upper()}\n")
                    f.write("-" * 80 + "\n")
                    f.write(f"Количество: {len(level_tokens)}\n\n")
                    
                    # Сортировка токенов по убыванию риск-скора
                    level_tokens.sort(key=lambda x: x.risk_score, reverse=True)
                    
                    for i, token in enumerate(level_tokens, 1):
                        f.write(f"{i}. {token.symbol} ({token.network})\n")
                        f.write("   " + "-" * 40 + "\n")
                        f.write(f"   Рост: 1ч: {token.price_change_1h:.2f}%, 6ч: {token.price_change_6h:.2f}%, 24ч: {token.price_change_24h:.2f}%\n")
                        f.write(f"   Риск: {token.risk_level}\n")
                        f.write(f"   Возраст: {token.format_age()}\n")
                        f.write(f"   Изменение цены (24ч): {token.price_change_24h:.2f}%\n")
                        f.write(f"   Ликвидность: {token.format_money(token.liquidity_usd)}\n")
                        f.write(f"   Объем торгов (24ч): {token.format_money(token.volume_24h)}\n")
                        # Соотношение объема к ликвидности (в основной блок)
                        volume_liquidity_ratio_short = token.volume_24h / token.liquidity_usd if token.liquidity_usd > 0 else 0
                        f.write(f"   Соотношение объема к ликвидности: {volume_liquidity_ratio_short:.2f}\n")
                        
                        # Информация о безопасности
                        if hasattr(token, 'security_score'):
                            f.write(f"   🔒 Безопасность: {token.security_score:.3f}\n")
                            if hasattr(token, 'contract_verified'):
                                f.write(f"   Контракт: {'✅ Верифицирован' if token.contract_verified else '❌ Не верифицирован'}\n")
                            if hasattr(token, 'ownership_renounced'):
                                f.write(f"   Владелец: {'✅ Ренонсирован' if token.ownership_renounced else '❌ Не ренонсирован'}\n")
                            if hasattr(token, 'liquidity_locked'):
                                f.write(f"   Ликвидность: {'✅ Заблокирована' if token.liquidity_locked else '❌ Не заблокирована'}\n")
                                # Детали блокировки ликвидности (платформа/срок), если доступны
                                if hasattr(token, 'liquidity_lock_info') and token.liquidity_lock_info:
                                    lock_info = token.liquidity_lock_info
                                    if getattr(lock_info, 'is_locked', False):
                                        unlock_str = ''
                                        try:
                                            if getattr(lock_info, 'unlock_date', None):
                                                # unlock_date может быть datetime
                                                unlock_str = f", до {lock_info.unlock_date.strftime('%Y-%m-%d')}"
                                        except Exception:
                                            pass
                                        f.write(
                                            f"   🔒 Блокировка ликвидности: {lock_info.locked_percentage:.1f}% на {lock_info.lock_duration_days} дней ({lock_info.platform}{unlock_str})\n"
                                        )
                            if hasattr(token, 'honeypot_probability'):
                                f.write(f"   Honeypot: {token.honeypot_probability:.1%}\n")

                            # Налоги buy/sell из верификации контракта, если доступны
                            if hasattr(token, 'verification_result') and token.verification_result:
                                buy_tax_formatted = format_tax_percentage(token.verification_result.buy_tax)
                                sell_tax_formatted = format_tax_percentage(token.verification_result.sell_tax)
                                if buy_tax_formatted != "0" or sell_tax_formatted != "0":
                                    f.write(f"   Налоги: {buy_tax_formatted}% покупка / {sell_tax_formatted}% продажа\n")
                            
                            # Сигналы DEXScreener (если есть)
                            try:
                                external_checks = getattr(token, 'security_report', {}).external_checks if hasattr(token, 'security_report') and token.security_report else {}
                            except Exception:
                                external_checks = {}
                            ds = (external_checks or {}).get('dexscreener') or {}
                            if ds:
                                f.write(f"   🔍 DEXScreener:\n")
                                if ds.get('pair_url'):
                                    f.write(f"      • Пара: {ds['pair_url']}\n")
                                metrics = ds.get('metrics', {}) or {}
                                warnings = ds.get('warnings', []) or []
                                if metrics:
                                    liq = metrics.get('liquidity_usd')
                                    vol = metrics.get('volume_24h')
                                    ch24 = metrics.get('price_change_h24')
                                    ageh = metrics.get('age_hours')
                                    ratio = metrics.get('vol_liq_ratio')
                                    if liq is not None:
                                        f.write(f"      • Ликвидность: ${float(liq):,.0f}\n")
                                    if vol is not None:
                                        f.write(f"      • Объем 24ч: ${float(vol):,.0f}\n")
                                    if ch24 is not None:
                                        f.write(f"      • Изм. цены 24ч: {float(ch24):+.2f}%\n")
                                    if ageh is not None:
                                        f.write(f"      • Возраст пула: {float(ageh):.1f} ч\n")
                                    if ratio is not None:
                                        f.write(f"      • Объем/Ликвидность: {float(ratio):.2f}\n")
                                if warnings:
                                    for w in warnings[:5]:
                                        f.write(f"      • ⚠️ {w}\n")
                        
                        # Краткая сводка по держателям (в основной блок)
                        holders = token.info.get("holders", {}) if hasattr(token, 'info') else {}
                        if holders:
                            total_holders = holders.get('total')
                            top = holders.get('top', []) or []
                            # Если есть предрассчитанный показатель
                            top10_percent = getattr(token, 'top_10_percent', None)
                            if top10_percent is None:
                                # Пытаемся посчитать из top[]
                                accum = 0.0
                                for h in top[:10]:
                                    try:
                                        accum += float(h.get('percentage', 0) or 0)
                                    except (TypeError, ValueError):
                                        continue
                                top10_percent = accum
                            if total_holders is not None:
                                f.write(f"   Держатели: всего {total_holders} | Топ-10: {float(top10_percent):.1f}%\n")
                            else:
                                f.write(f"   Топ-10 держателей: {float(top10_percent):.1f}%\n")

                        if detailed:
                            volume_liquidity_ratio = token.volume_24h / token.liquidity_usd if token.liquidity_usd > 0 else 0
                            f.write(f"   Соотношение объема к ликвидности: {volume_liquidity_ratio:.2f}\n")
                            
                            # Информация о контракте
                            if hasattr(token, 'verification_result') and token.verification_result:
                                vr = token.verification_result
                                f.write(f"   Контракт: {'Верифицирован' if vr.is_verified else 'Не верифицирован'}\n")
                                f.write(f"   Источник верификации: {vr.verification_source}\n")
                                if vr.is_honeypot:
                                    f.write(f"   ⚠️ HONEYPOT: ДА\n")
                                buy_tax_formatted = format_tax_percentage(vr.buy_tax)
                                sell_tax_formatted = format_tax_percentage(vr.sell_tax)
                                if buy_tax_formatted != "0" or sell_tax_formatted != "0":
                                    f.write(f"   Налоги: {buy_tax_formatted}% покупка / {sell_tax_formatted}% продажа\n")
                            else:
                                contract_info = token.info.get("contract", {})
                                f.write(f"   Контракт: {'Верифицирован' if contract_info.get('verified') else 'Не верифицирован'}\n")
                            
                            # Информация о держателях
                            holders = token.info.get("holders", {})
                            if holders:
                                f.write(f"   Количество держателей: {holders.get('total', 'Н/Д')}\n")
                                top_holders = holders.get("top", [])
                                if top_holders:
                                    f.write("   Топ-5 держателей:\n")
                                    for j, holder in enumerate(top_holders[:5], 1):
                                        f.write(f"    {j}. {holder.get('address', 'Н/Д')}: {holder.get('percentage', 0):.2f}%\n")
                            
                            # Сайты и социальные сети
                            websites = token.info.get("websites", [])
                            socials = token.info.get("socials", [])
                            
                            if websites:
                                f.write(f"   Сайты:\n")
                                for website in websites:
                                    if isinstance(website, dict):
                                        url = website.get('url', '')
                                        f.write(f"    - {url}\n")
                                    else:
                                        f.write(f"    - {website}\n")
                            else:
                                f.write("   Сайты: Нет\n")
                                
                            if socials:
                                f.write(f"   Социальные сети:\n")
                                for social in socials:
                                    if isinstance(social, dict):
                                        url = social.get('url', '')
                                        f.write(f"    - {url}\n")
                                    else:
                                        f.write(f"    - {social}\n")
                            else:
                                f.write("   Социальные сети: Нет\n")
                            
                            if token.risk_factors:
                                f.write("   Факторы риска:\n")
                                for factor in token.risk_factors:
                                    f.write(f"    - {factor}\n")
                            
                            f.write("   Ссылки:\n")
                            f.write(f"    - DEX: {token.get_dex_url()}\n")
                            f.write(f"    - Explorer: {token.get_explorer_url()}\n")
                            f.write(f"    - DexScreener: {token.get_dexscreener_url()}\n")
                            f.write("\n")
                        
                        f.write("\n")
                
                # Заголовок отчета
                f.write(f"{report_title}\n")
                f.write("-" * 80 + "\n")
                # Используем переданный список токенов без дополнительной фильтрации
                # (фильтрация уже выполнена в get_top_tokens_by_growth)
                recommended = tokens_list
                
                if recommended:
                    recommended.sort(key=lambda x: x.price_change_24h, reverse=True)
                    for i, token in enumerate(recommended, 1):
                        f.write(f"{i}. {token.symbol} ({token.network})\n")
                        f.write("   " + "-" * 40 + "\n")
                        f.write(f"   Рост: 1ч: {token.price_change_1h:.2f}%, 6ч: {token.price_change_6h:.2f}%, 24ч: {token.price_change_24h:.2f}%\n")
                        f.write(f"   Риск: {token.risk_level}\n")
                        
                        # Добавляем краткую рекомендацию на основе динамики
                        trend_1h = token.price_change_1h
                        trend_6h = token.price_change_6h
                        trend_24h = token.price_change_24h
                        
                        recommendation = ""
                        if trend_1h > 0 and trend_1h > trend_6h:
                            recommendation = "🚀 АКТИВНЫЙ РОСТ - рекомендуется для краткосрочной торговли"
                        elif trend_1h < 0 and trend_6h < 0:
                            recommendation = "📉 КОРРЕКЦИЯ - возможна точка входа"
                        elif trend_1h > 0 and trend_6h > 0 and trend_24h > 0:
                            recommendation = "📈 УСТОЙЧИВЫЙ РОСТ - хорошая среднесрочная перспектива"
                        elif trend_1h < 0 and trend_6h > 0:
                            recommendation = "⚡ ОТКАТ - возможен отскок"
                        elif abs(trend_1h) < 2 and abs(trend_6h) < 5:
                            recommendation = "⏸️ КОНСОЛИДАЦИЯ - накопление позиций"
                        elif trend_24h > 100 and trend_1h < 0:
                            recommendation = "⚠️ ПЕРЕКУПЛЕН - высокий риск коррекции"
                        else:
                            recommendation = "📊 СМЕШАННАЯ ДИНАМИКА - требуется наблюдение"
                            
                        f.write(f"   {recommendation}\n")
                        
                        f.write(f"   Ликвидность: {token.format_money(token.liquidity_usd)}, Объем: {token.format_money(token.volume_24h)}\n")
                        
                        # КРИТИЧНО: Информация о блокировке ликвидности
                        if hasattr(token, 'liquidity_lock_info') and token.liquidity_lock_info:
                            lock_info = token.liquidity_lock_info
                            if lock_info.is_locked:
                                f.write(f"   🔒 Ликвидность заблокирована: {lock_info.locked_percentage}% на {lock_info.lock_duration_days} дней ({lock_info.platform})\n")
                                
                                # Оценка безопасности
                                lock_score = getattr(token, 'liquidity_lock_score', 0)
                                if lock_score >= 80:
                                    f.write(f"   🟢 Безопасность блокировки: ВЫСОКАЯ ({lock_score}/100)\n")
                                elif lock_score >= 50:
                                    f.write(f"   🟡 Безопасность блокировки: СРЕДНЯЯ ({lock_score}/100)\n")
                                else:
                                    f.write(f"   🔴 Безопасность блокировки: НИЗКАЯ ({lock_score}/100)\n")
                            else:
                                f.write(f"   ❌ КРИТИЧНО: Ликвидность НЕ заблокирована! Высокий риск rug pull!\n")
                        else:
                            f.write(f"   ⚠️ Статус блокировки ликвидности не проверен\n")
                        
                        # Добавляем обоснование рекомендации
                        f.write("\n   ПОЧЕМУ МЫ РЕКОМЕНДУЕМ:\n")
                        
                        # Анализ ликвидности
                        if token.liquidity_usd > 1000000:
                            f.write("   ✅ Высокая ликвидность (>$1M) снижает риск манипуляций\n")
                        elif token.liquidity_usd > 250000:
                            f.write("   ✅ Хорошая ликвидность (>$250K) обеспечивает стабильность\n")
                        else:
                            f.write("   ⚠️ Средняя ликвидность - рекомендуется осторожность\n")
                        
                        # Анализ объема торгов
                        vol_liq_ratio = token.volume_24h / token.liquidity_usd if token.liquidity_usd > 0 else 0
                        if 0.5 <= vol_liq_ratio <= 5:
                            f.write("   ✅ Здоровое соотношение объема к ликвидности\n")
                        elif vol_liq_ratio > 5:
                            f.write("   ⚠️ Высокая торговая активность - возможна повышенная волатильность\n")
                        else:
                            f.write("   ℹ️ Низкая торговая активность - возможно накопление\n")
                        
                        # Анализ возраста
                        if token.age_hours > 720:  # 30 дней
                            f.write("   ✅ Проверенный временем токен (>30 дней)\n")
                        elif token.age_hours > 168:  # 7 дней
                            f.write("   ✅ Токен прошел начальную стабилизацию (>7 дней)\n")
                        else:
                            f.write("   ⚠️ Относительно новый токен - требуется осторожность\n")
                        
                        # Анализ транзакций
                        total_txns = token.buys_24h + token.sells_24h
                        if total_txns > 0:
                            buy_ratio = token.buys_24h / total_txns
                            if buy_ratio > 0.6:
                                f.write(f"   ✅ Преобладают покупки ({buy_ratio*100:.1f}% транзакций)\n")
                            elif buy_ratio > 0.4:
                                f.write(f"   ✅ Сбалансированные покупки/продажи\n")
                            else:
                                f.write(f"   ⚠️ Преобладают продажи - возможна коррекция\n")
                        
                        # Анализ роста
                        if token.price_change_24h > 100:
                            f.write("   🚀 Сильный рост - высокий потенциал, но повышенные риски\n")
                        elif token.price_change_24h > 50:
                            f.write("   📈 Уверенный рост с хорошей динамикой\n")
                        else:
                            f.write("   📊 Стабильный рост\n")
                        
                        # Проверка наличия информации
                        has_website = bool(token.info.get("websites", []))
                        has_socials = bool(token.info.get("socials", []))
                        if has_website and has_socials:
                            f.write("   ✅ Есть сайт и социальные сети\n")
                            # Добавляем ссылки на сайты и социальные сети
                            websites = token.info.get("websites", [])
                            socials = token.info.get("socials", [])
                            
                            if websites:
                                f.write("   Сайты:\n")
                                for website in websites:
                                    if isinstance(website, dict):
                                        url = website.get('url', '')
                                        f.write(f"    - {url}\n")
                                    else:
                                        f.write(f"    - {website}\n")
                            
                            if socials:
                                f.write("   Социальные сети:\n")
                                for social in socials:
                                    if isinstance(social, dict):
                                        url = social.get('url', '')
                                        f.write(f"    - {url}\n")
                                    else:
                                        f.write(f"    - {social}\n")
                        elif has_website or has_socials:
                            f.write("   ⚠️ Частично представлен в сети\n")
                            # Добавляем доступные ссылки
                            websites = token.info.get("websites", [])
                            socials = token.info.get("socials", [])
                            
                            if websites:
                                f.write("   Сайты:\n")
                                for website in websites:
                                    if isinstance(website, dict):
                                        url = website.get('url', '')
                                        f.write(f"    - {url}\n")
                                    else:
                                        f.write(f"    - {website}\n")
                            
                            if socials:
                                f.write("   Социальные сети:\n")
                                for social in socials:
                                    if isinstance(social, dict):
                                        url = social.get('url', '')
                                        f.write(f"    - {url}\n")
                                    else:
                                        f.write(f"    - {social}\n")
                        
                        # Добавляем информацию о верификации контракта
                        if hasattr(token, 'verification_result') and token.verification_result:
                            f.write("\n   🔍 ВЕРИФИКАЦИЯ КОНТРАКТА:\n")
                            f.write(f"    - Статус: {'✅ Верифицирован' if token.verification_result.is_verified else '❌ Не верифицирован'}\n")
                            f.write(f"    - Honeypot: {'🚨 ДА' if token.verification_result.is_honeypot else '✅ НЕТ'}\n")
                            buy_tax_formatted = format_tax_percentage(token.verification_result.buy_tax)
                            sell_tax_formatted = format_tax_percentage(token.verification_result.sell_tax)
                            # Показываем налоги только если они не равны 0%
                            if buy_tax_formatted != "0" or sell_tax_formatted != "0":
                                f.write(f"    - Налоги: {buy_tax_formatted}% покупка / {sell_tax_formatted}% продажа\n")
                            if token.verification_result.owner_address:
                                f.write(f"    - Владелец: {token.verification_result.owner_address[:10]}...\n")
                            if token.verification_result.can_take_back_ownership:
                                f.write(f"    - ⚠️ Владелец может вернуть права\n")
                            if token.verification_result.has_mint_function:
                                f.write(f"    - ⚠️ Есть функция mint\n")
                            if token.verification_result.has_blacklist:
                                f.write(f"    - ⚠️ Есть blacklist функция\n")
                            
                            # Дополнительные данные из raw_data
                            if hasattr(token.verification_result, 'raw_data') and token.verification_result.raw_data:
                                raw = token.verification_result.raw_data
                                if raw.get('is_blacklisted') == '1':
                                    f.write(f"    - 🚫 В черном списке GoPlus\n")
                                if raw.get('slippage_modifiable') == '1':
                                    f.write(f"    - ⚠️ Модифицируемый slippage\n")
                                if raw.get('is_anti_whale') == '1':
                                    f.write(f"    - ⚠️ Anti-whale механизм\n")
                                if raw.get('cannot_sell_all') == '1':
                                    f.write(f"    - 🚨 Нельзя продать все токены\n")
                                if raw.get('cannot_buy') == '1':
                                    f.write(f"    - 🚨 Нельзя покупать\n")
                                if raw.get('trading_cooldown') and raw.get('trading_cooldown') != '0':
                                    f.write(f"    - ⏰ Кулдаун торговли: {raw.get('trading_cooldown')}с\n")
                            
                            if token.verification_result.verification_source:
                                f.write(f"    - Источник: {token.verification_result.verification_source}\n")
                        
                        f.write("\n   Ссылки:\n")
                        f.write(f"    - DEX: {token.get_dex_url()}\n")
                        f.write(f"    - Explorer: {token.get_explorer_url()}\n")
                        f.write(f"    - DexScreener: {token.get_dexscreener_url()}\n")
                        f.write("\n")
                else:
                    f.write("Нет токенов, соответствующих критериям для рекомендации\n")
                
                # Выводы и рекомендации
                f.write("\nВЫВОДЫ И РЕКОМЕНДАЦИИ\n")
                f.write("-" * 80 + "\n")
                f.write("1. Критерии риска:\n")
                f.write("   - Аномальный рост цены (>200%) за короткий период\n")
                f.write("   - Аномальное соотношение объема к ликвидности (>50)\n")
                f.write("   - Отсутствие сайта и социальных сетей\n")
                f.write("   - Возраст токена < 24 часов\n")
                f.write("   - Низкая ликвидность (<25,000 USD)\n")
                f.write("   - Неверифицированный контракт\n")
                f.write("   - Высокая концентрация токенов у малого количества держателей\n\n")
                
                f.write("2. Рекомендации для инвестирования:\n")
                f.write("   - Отдавать предпочтение токенам с уровнем риска 'Низкий' или 'Средний'\n")
                f.write("   - Проверять соотношение объема к ликвидности (оптимально: 0.5-10)\n")
                f.write("   - Избегать токенов без сайта и социальных сетей\n")
                f.write("   - Предпочитать токены с возрастом > 48 часов\n")
                f.write("   - Проверять верификацию контракта\n")
                f.write("   - Анализировать распределение токенов среди держателей\n")
                
                self.logger.info(f"Генерация отчета успешно завершена")
                return True
        
        except Exception as e:
            error_msg = f"Ошибка при генерации отчета: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def get_top_tokens_by_growth(self, limit: int = None, min_liquidity: float = 50000, min_age: float = 24) -> List[Token]:
        """Возвращает топ токенов с улучшенными фильтрами безопасности"""
        self.logger.info(f"🎯 Поиск топ-{limit if limit else 'all'} токенов с критическими фильтрами безопасности")
        
        # 🚨 ИСКЛЮЧЕНИЯ из рекомендаций - НЕТ СКАМА!
        safe_tokens = []
        for token in self.tokens:
            # Базовые требования: исключаем только скам и высокий риск
            if token.risk_level in ["Скам", "Высокий"]:
                continue
            
            # 1. Возраст < 24 часов (исключение)
            if token.age_hours < 24:
                continue
            
            # 2. 🚨 КРИТИЧНО: Рост > 100% за 24ч = ПАМП! Исключаем из рекомендаций
            if token.price_change_24h > 100:
                continue
            
            # 3. 🚨 КРИТИЧНО: Объем < $5K за 24ч = МЕРТВЫЙ токен! (PEPE $890 - не торгуется)
            if token.volume_24h < 5000:
                continue
            
            # 4. Нет соцсетей И нет сайта
            websites = token.info.get("websites", [])
            socials = token.info.get("socials", [])
            if not websites and not socials:
                continue
            
            # 5. КРИТИЧНО: Проверка блокировки ликвидности
            liquidity_lock_percentage = 0
            liquidity_lock_score = 0
            if hasattr(token, 'liquidity_lock_info') and token.liquidity_lock_info and token.liquidity_lock_info.is_locked:
                liquidity_lock_percentage = token.liquidity_lock_info.locked_percentage
            if hasattr(token, 'liquidity_lock_score'):
                liquidity_lock_score = token.liquidity_lock_score
            
            is_verified = False
            if hasattr(token, 'verification_result') and token.verification_result:
                is_verified = token.verification_result.is_verified
            
            # 🚨 КРИТИЧНО: Блокировка ликвидности обязательна для рекомендаций
            # Исключения только для:
            # 1. Мега-токенов с ликвидностью > $500K + верификация + возраст > 30 дней
            # 2. Или токенов с блокировкой > 25%
            
            has_liquidity_lock = liquidity_lock_percentage > 25
            is_mega_safe = (token.liquidity_usd > 500000 and 
                          is_verified and 
                          token.age_hours > 720)  # 30 дней
            
            if not (has_liquidity_lock or is_mega_safe):
                continue
            
            # Дополнительные критерии безопасности (при наличии блокировки или мега-статуса)
            # Условие 1: 🚨 КРИТИЧНО: Минимальная ликвидность $100K для безопасности
            if token.liquidity_usd < 100000:
                continue
            
            # Условие 2: Для токенов без блокировки - только мега-безопасные
            if not has_liquidity_lock and not is_mega_safe:
                continue
                
            safe_tokens.append(token)
        
        self.logger.info(f"📊 После критических фильтров: {len(safe_tokens)} токенов")
        
        # Сортируем: сначала по уровню риска (Низкий -> Умеренный -> Средний), потом по росту цены
        safe_tokens.sort(key=lambda x: (
            0 if x.risk_level == "Низкий" else 1 if x.risk_level == "Умеренный" else 2,
            -x.price_change_24h  # Затем по убыванию роста цены
        ))
        
        # Применяем специальную логику для топ-10 рекомендаций
        if limit and limit <= 10:
            self.logger.info("🏆 Применяем строгие критерии для ТОП-10 рекомендаций")
            top_tokens = []
            for token in safe_tokens:
                # ТОП-10: СМЯГЧЕННЫЕ критерии - ликвидность > $75K
                if token.liquidity_usd < 75000:
                    continue
                
                # ТОП-10: Возраст > 3 дня (смягчено)
                if token.age_hours < 72:  # 3 дня
                    continue
                
                # ТОП-10: Приоритет низкому и умеренному риску
                if token.risk_level not in ["Низкий", "Умеренный"]:
                    continue
                
                top_tokens.append(token)
                
                if len(top_tokens) >= limit:
                    break
            
            result = top_tokens
            self.logger.info(f"🏆 ТОП-{limit}: {len(result)} элитных токенов")
        else:
            result = safe_tokens[:limit] if limit else safe_tokens
            self.logger.info(f"📈 Общие рекомендации: {len(result)} токенов")
        
        return result
    
    def generate_compact_recommendations_report(self, file_path: str, tokens_list: List = None) -> bool:
        """Генерирует профессиональный отчет ТОЛЬКО с рекомендуемыми токенами (убирает дублирование сверху)"""
        self.logger.info(f"Генерация отчета рекомендаций без дублирования: {file_path}")
        
        try:
            # Используем переданный список или получаем рекомендуемые токены
            if tokens_list is None:
                tokens_list = self.get_top_tokens_by_growth(
                    limit=None,
                    min_liquidity=self.config.get("min_liquidity", 50000),
                    min_age=24
                )
            
            if not tokens_list:
                self.logger.warning("Нет токенов для генерации отчета")
                return False
            
            # Сортируем токены: сначала низкий риск, потом средний, внутри каждой группы по росту
            sorted_tokens = sorted(tokens_list, key=lambda x: (
                0 if x.risk_level == "Низкий" else 1,
                -x.price_change_24h
            ))
            
            with open(file_path, 'w', encoding='utf-8') as f:
                # ТОЛЬКО заголовок рекомендаций - убираем всё дублирование сверху
                f.write("\nРЕКОМЕНДУЕМЫЕ ТОКЕНЫ\n")
                f.write("-" * 80 + "\n")
                
                for i, token in enumerate(sorted_tokens, 1):
                    f.write(f"{i}. {token.symbol} ({token.network})\n")
                    f.write("   " + "-" * 40 + "\n")
                    f.write(f"   Рост: 1ч: {token.price_change_1h:.2f}%, 6ч: {token.price_change_6h:.2f}%, 24ч: {token.price_change_24h:.2f}%\n")
                    f.write(f"   Риск: {token.risk_level}\n")
                    
                    # 🎯 ДОБАВЛЯЕМ ЭМОДЗИ ОБРАТНО
                    if token.price_change_1h < 0:
                        if token.price_change_24h > 50:
                            f.write("   ⚡ ОТКАТ - возможен отскок\n")
                        else:
                            f.write("   📉 КОРРЕКЦИЯ - возможна точка входа\n")
                    
                    f.write(f"   Возраст: {self._format_age(token.age_hours)}\n")
                    f.write(f"   Изменение цены (24ч): {token.price_change_24h:.2f}%\n")
                    f.write(f"   Ликвидность: ${token.liquidity_usd:,.2f}K, Объем: ${token.volume_24h:,.2f}K\n")
                    f.write(f"   Соотношение объема к ликвидности: {token.volume_24h/token.liquidity_usd if token.liquidity_usd > 0 else 0:.2f}\n")
                    
                    # Блокировка ликвидности - С ЭМОДЗИ
                    if hasattr(token, 'liquidity_lock_info') and token.liquidity_lock_info:
                        lock_info = token.liquidity_lock_info
                        if lock_info.is_locked:
                            f.write(f"   🔒 Ликвидность заблокирована: {lock_info.locked_percentage:.1f}% на {lock_info.lock_duration_days} дней ({lock_info.platform})\n")
                        else:
                            f.write(f"   ❌ КРИТИЧНО: Ликвидность НЕ заблокирована! Высокий риск rug pull!\n")
                    
                    # Собираем положительные и отрицательные факторы
                    positive_factors = []
                    negative_factors = []
                    
                    # Анализ ликвидности
                    if token.liquidity_usd >= 100000:
                        positive_factors.append("✅ Высокая ликвидность - низкие риски")
                    elif token.liquidity_usd >= 50000:
                        negative_factors.append("⚠️ Средняя ликвидность - рекомендуется осторожность")
                    else:
                        negative_factors.append("🔴 Низкая ликвидность - высокие риски")
                    
                    # Анализ объема с улучшенной градацией
                    volume_ratio = token.volume_24h / token.liquidity_usd if token.liquidity_usd > 0 else 0
                    if volume_ratio > 20:
                        negative_factors.append("🔴 КРИТИЧНО: Аномальное соотношение V/L - возможна манипуляция")
                    elif volume_ratio > 5:
                        negative_factors.append("🟡 Высокое соотношение V/L - повышенная волатильность")
                    elif volume_ratio >= 0.1:
                        positive_factors.append("🟢 Здоровое соотношение объема к ликвидности")
                    else:
                        negative_factors.append("⚠️ Низкая торговая активность")
                    
                    # Анализ возраста
                    if token.age_hours >= 720:  # 30+ дней
                        positive_factors.append("✅ Проверенный временем токен (>30 дней)")
                    else:
                        negative_factors.append("⚠️ Молодой токен - повышенные риски")
                    
                    # Анализ роста
                    if token.price_change_24h > 100:
                        positive_factors.append("🚀 Сильный рост - высокий потенциал")
                        negative_factors.append("⚠️ Высокая волатильность - повышенные риски")
                    elif token.price_change_24h > 50:
                        positive_factors.append("📈 Умеренный рост - хороший потенциал")
                    else:
                        positive_factors.append("📊 Стабильный рост - низкие риски")
                    
                    # Верификация контракта
                    if hasattr(token, 'verification_result') and token.verification_result:
                        if token.verification_result.is_verified:
                            positive_factors.append("✅ Контракт верифицирован")
                        else:
                            negative_factors.append("❌ Контракт не верифицирован")
                        
                        if token.verification_result.is_honeypot:
                            negative_factors.append("🍯 HONEYPOT - крайне опасно!")
                        else:
                            positive_factors.append("✅ Не является honeypot")
                    
                    # Блокировка ликвидности
                    if hasattr(token, 'liquidity_lock_info') and token.liquidity_lock_info:
                        if token.liquidity_lock_info.is_locked:
                            lock_score = getattr(token, 'liquidity_lock_score', 0)
                            if lock_score >= 80:
                                positive_factors.append("🔒 Высокий уровень блокировки ликвидности")
                            elif lock_score >= 50:
                                positive_factors.append("🔒 Средний уровень блокировки ликвидности")
                            else:
                                negative_factors.append("🔓 Низкий уровень блокировки ликвидности")
                        else:
                            negative_factors.append("❌ Ликвидность НЕ заблокирована - риск rug pull!")
                    
                    # Социальные сети и сайты
                    websites = token.info.get("websites", [])
                    socials = token.info.get("socials", [])
                    if websites and socials:
                        positive_factors.append("✅ Полное онлайн-присутствие (сайт + соцсети)")
                    elif websites or socials:
                        positive_factors.append("✅ Есть онлайн-присутствие")
                    else:
                        negative_factors.append("⚠️ Нет официального онлайн-присутствия")
                    
                    # Выводим факторы
                    if positive_factors:
                        f.write("\n   💚 ПОЧЕМУ РЕКОМЕНДУЕМ:\n")
                        for factor in positive_factors:
                            f.write(f"   {factor}\n")
                    
                    if negative_factors:
                        f.write("\n   ❤️‍🔥 РИСКИ И ПРЕДУПРЕЖДЕНИЯ:\n")
                        for factor in negative_factors:
                            f.write(f"   {factor}\n")
                    
                    # Сайты
                    if websites:
                        f.write("   Сайты:\n")
                        for website in websites:
                            if isinstance(website, dict):
                                url = website.get('url', '')
                            else:
                                url = str(website)
                            if url:
                                f.write(f"    - {url}\n")
                    
                    # Социальные сети
                    if socials:
                        f.write("   Социальные сети:\n")
                        for social in socials:
                            if isinstance(social, dict):
                                url = social.get('url', '')
                            else:
                                url = str(social)
                            if url:
                                f.write(f"    - {url}\n")
                    
                    # 🔍 ВЕРИФИКАЦИЯ КОНТРАКТА с эмодзи
                    if hasattr(token, 'verification_result') and token.verification_result:
                        f.write("\n   🔍 ВЕРИФИКАЦИЯ КОНТРАКТА:\n")
                        verification_status = "✅ Верифицирован" if token.verification_result.is_verified else "❌ Не верифицирован"
                        honeypot_status = "🍯 HONEYPOT" if token.verification_result.is_honeypot else "✅ НЕТ"
                        f.write(f"    - Статус: {verification_status}\n")
                        f.write(f"    - Honeypot: {honeypot_status}\n")
                        if token.verification_result.verification_source:
                            f.write(f"    - Источник: {token.verification_result.verification_source}\n")
                    
                    # 📊 ДЕТАЛЬНАЯ РАЗБИВКА РИСК-СКОРА (для прозрачности)
                    if hasattr(token, 'score_breakdown') and token.score_breakdown:
                        f.write(f"\n   📊 РИСК-СКОР: {token.risk_score} баллов\n")
                        f.write("   Разбивка по факторам:\n")
                        for factor in token.score_breakdown:
                            f.write(f"    • {factor}\n")
                    
                    # Ссылки - В КОНЦЕ, отдельным блоком
                    f.write("\n   Ссылки:\n")
                    f.write(f"    - DEX: {token.get_dex_url()}\n")
                    f.write(f"    - Explorer: {token.get_explorer_url()}\n")
                    f.write(f"    - DexScreener: {token.get_dexscreener_url()}\n")
                    
                    f.write("\n")
                
            self.logger.info(f"Профессиональный отчет рекомендаций успешно создан")
            return True
            
        except Exception as e:
            error_msg = f"Ошибка при генерации отчета рекомендаций: {str(e)}"
            self.logger.error(error_msg)
            return False
    
    def _format_age(self, hours: float) -> str:
        """Форматирует возраст токена в читаемый вид"""
        if hours < 24:
            return f"{hours:.1f}ч"
        elif hours < 24 * 7:
            days = hours / 24
            return f"{days:.1f}д"
        elif hours < 24 * 30:
            weeks = hours / (24 * 7)
            days = (hours % (24 * 7)) / 24
            return f"{weeks:.0f}н {days:.0f}д"
        else:
            months = hours / (24 * 30)
            weeks = (hours % (24 * 30)) / (24 * 7)
            days = (hours % (24 * 7)) / 24
            return f"{months:.0f}м {weeks:.0f}н {days:.0f}д"
    
    def format_tax_percentage(self, tax_value) -> str:
        """Форматирует значение налога в процентах"""
        if tax_value is None or tax_value == '' or tax_value == 'N/A':
            return '0%'
        
        try:
            # Если это уже строка с процентами
            if isinstance(tax_value, str) and '%' in tax_value:
                return tax_value
            
            # Преобразуем в число
            tax_num = float(tax_value)
            
            # Если число больше 1, считаем что это уже проценты
            if tax_num > 1:
                return f"{tax_num:.1f}%"
            else:
                # Если меньше 1, умножаем на 100
                return f"{tax_num * 100:.1f}%"
        except:
            return '0%'
    
    def export_recommended_to_json(self, file_path: str) -> bool:
        """Экспортирует рекомендованные токены в JSON с расширенной информацией"""
        self.logger.info(f"Экспорт рекомендованных токенов в JSON: {file_path}")
        try:
            recommended = [t for t in self.tokens if 
                          t.risk_level in ["Низкий", "Умеренный", "Средний"] and 
                          t.price_change_24h > 10 and 
                          t.liquidity_usd > 50000]
            
            recommended.sort(key=lambda x: x.price_change_24h, reverse=True)
            
            export_data = {
                "timestamp": datetime.now().isoformat(),
                "total_tokens": len(self.tokens),
                "recommended_count": len(recommended),
                "risk_distribution": {
                    "scam": len(self.scam_tokens),
                    "high": len(self.high_risk_tokens),
                    "medium": len(self.medium_risk_tokens),
                    "low": len(self.low_risk_tokens)
                },
                "recommended_tokens": []
            }
            
            for token in recommended:
                # Анализ динамики цены
                trend_1h = token.price_change_1h
                trend_6h = token.price_change_6h
                trend_24h = token.price_change_24h
                
                # Определение тренда
                trend_analysis = ""
                if trend_1h > 0 and trend_1h > trend_6h:
                    trend_analysis = "АКТИВНЫЙ РОСТ - рекомендуется для краткосрочной торговли"
                elif trend_1h < 0 and trend_6h < 0:
                    trend_analysis = "КОРРЕКЦИЯ - возможна точка входа"
                elif trend_1h > 0 and trend_6h > 0 and trend_24h > 0:
                    trend_analysis = "УСТОЙЧИВЫЙ РОСТ - хорошая среднесрочная перспектива"
                elif trend_1h < 0 and trend_6h > 0:
                    trend_analysis = "ОТКАТ - возможен отскок"
                elif abs(trend_1h) < 2 and abs(trend_6h) < 5:
                    trend_analysis = "КОНСОЛИДАЦИЯ - накопление позиций"
                elif trend_24h > 100 and trend_1h < 0:
                    trend_analysis = "ПЕРЕКУПЛЕН - высокий риск коррекции"
                else:
                    trend_analysis = "СМЕШАННАЯ ДИНАМИКА - требуется наблюдение"
                
                # Анализ ликвидности и объема
                vol_liq_ratio = token.volume_24h / token.liquidity_usd if token.liquidity_usd > 0 else 0
                liquidity_analysis = ""
                if token.liquidity_usd > 1000000:
                    liquidity_analysis = "Высокая ликвидность (>$1M) снижает риск манипуляций"
                elif token.liquidity_usd > 250000:
                    liquidity_analysis = "Хорошая ликвидность (>$250K) обеспечивает стабильность"
                else:
                    liquidity_analysis = "Средняя ликвидность - рекомендуется осторожность"
                
                # Анализ возраста
                age_analysis = ""
                if token.age_hours > 720:  # 30 дней
                    age_analysis = "Проверенный временем токен (>30 дней)"
                elif token.age_hours > 168:  # 7 дней
                    age_analysis = "Токен прошел начальную стабилизацию (>7 дней)"
                else:
                    age_analysis = "Относительно новый токен - требуется осторожность"
                
                # Анализ транзакций
                transaction_analysis = ""
                total_txns = token.buys_24h + token.sells_24h
                if total_txns > 0:
                    buy_ratio = token.buys_24h / total_txns
                    if buy_ratio > 0.6:
                        transaction_analysis = f"Преобладают покупки ({buy_ratio*100:.1f}% транзакций)"
                    elif buy_ratio > 0.4:
                        transaction_analysis = "Сбалансированные покупки/продажи"
                    else:
                        transaction_analysis = "Преобладают продажи - возможна коррекция"
                
                # Анализ роста
                growth_analysis = ""
                if token.price_change_24h > 100:
                    growth_analysis = "Сильный рост - высокий потенциал, но повышенные риски"
                elif token.price_change_24h > 50:
                    growth_analysis = "Уверенный рост с хорошей динамикой"
                else:
                    growth_analysis = "Стабильный рост"
                
                token_data = {
                    "basic_info": {
                        "symbol": token.symbol,
                        "name": token.name,
                        "network": token.network,
                        "address": token.address,
                        "age": token.format_age(),
                        "age_hours": token.age_hours
                    },
                    "price_metrics": {
                        "price_usd": token.price_usd,
                        "price_native": token.price_native,
                        "price_change_1h": token.price_change_1h,
                        "price_change_6h": token.price_change_6h,
                        "price_change_24h": token.price_change_24h
                    },
                    "market_metrics": {
                        "liquidity_usd": token.liquidity_usd,
                        "volume_24h": token.volume_24h,
                        "volume_6h": token.volume_6h,
                        "volume_1h": token.volume_1h,
                        "volume_liquidity_ratio": vol_liq_ratio,
                        "market_cap": token.market_cap,
                        "fdv": token.fdv
                    },
                    "transaction_metrics": {
                        "buys_24h": token.buys_24h,
                        "sells_24h": token.sells_24h,
                        "buy_sell_ratio": token.buys_24h / (token.buys_24h + token.sells_24h) if (token.buys_24h + token.sells_24h) > 0 else 0
                    },
                    "risk_metrics": {
                        "risk_score": token.risk_score,
                        "risk_level": token.risk_level,
                        "risk_factors": token.risk_factors
                    },
                    "analysis": {
                        "trend": trend_analysis,
                        "liquidity": liquidity_analysis,
                        "age": age_analysis,
                        "transactions": transaction_analysis,
                        "growth": growth_analysis
                    },
                    "links": {
                        "dex": token.get_dex_url(),
                        "explorer": token.get_explorer_url(),
                        "dexscreener": token.get_dexscreener_url(),
                        "websites": token.info.get("websites", []),
                        "socials": token.info.get("socials", [])
                    },
                    "contract_info": {
                        "verified": token.info.get("contract", {}).get("verified", False),
                        "holders": token.info.get("holders", {})
                    },
                    "verification_data": {
                        "is_verified": getattr(token, 'verification_result', None) and token.verification_result.is_verified or False,
                        "is_honeypot": getattr(token, 'verification_result', None) and token.verification_result.is_honeypot or False,
                        "buy_tax": getattr(token, 'verification_result', None) and token.verification_result.buy_tax or "0",
                        "sell_tax": getattr(token, 'verification_result', None) and token.verification_result.sell_tax or "0",
                        "owner_address": getattr(token, 'verification_result', None) and token.verification_result.owner_address or "",
                        "can_take_back_ownership": getattr(token, 'verification_result', None) and token.verification_result.can_take_back_ownership or False,
                        "has_mint_function": getattr(token, 'verification_result', None) and token.verification_result.has_mint_function or False,
                        "has_blacklist": getattr(token, 'verification_result', None) and token.verification_result.has_blacklist or False,
                        "is_proxy": getattr(token, 'verification_result', None) and token.verification_result.is_proxy or False,
                        "verification_source": getattr(token, 'verification_result', None) and token.verification_result.verification_source or "",
                        "error_message": getattr(token, 'verification_result', None) and token.verification_result.error_message or ""
                    },
                    "liquidity_lock": {
                        "is_locked": getattr(token, 'liquidity_lock_info', None) and token.liquidity_lock_info.is_locked or False,
                        "locked_percentage": getattr(token, 'liquidity_lock_info', None) and token.liquidity_lock_info.locked_percentage or 0.0,
                        "unlock_date": getattr(token, 'liquidity_lock_info', None) and token.liquidity_lock_info.unlock_date and token.liquidity_lock_info.unlock_date.isoformat() or "",
                        "lock_duration_days": getattr(token, 'liquidity_lock_info', None) and token.liquidity_lock_info.lock_duration_days or 0,
                        "platform": getattr(token, 'liquidity_lock_info', None) and token.liquidity_lock_info.platform or "",
                        "lock_contract": getattr(token, 'liquidity_lock_info', None) and token.liquidity_lock_info.lock_contract or "",
                        "total_locked_amount": getattr(token, 'liquidity_lock_info', None) and token.liquidity_lock_info.total_locked_amount or 0.0,
                        "lock_transaction": getattr(token, 'liquidity_lock_info', None) and token.liquidity_lock_info.lock_transaction or "",
                        "is_renewable": getattr(token, 'liquidity_lock_info', None) and token.liquidity_lock_info.is_renewable or False,
                        "lock_owner": getattr(token, 'liquidity_lock_info', None) and token.liquidity_lock_info.lock_owner or "",
                        "lock_score": getattr(token, 'liquidity_lock_score', 0),
                        "safety_level": "HIGH" if getattr(token, 'liquidity_lock_score', 0) >= 80 else "MEDIUM" if getattr(token, 'liquidity_lock_score', 0) >= 50 else "LOW",
                        "warnings": getattr(token, 'liquidity_lock_info', None) and token.liquidity_lock_info.warnings or []
                    },
                    "security_analysis": {
                        "security_score": getattr(token, 'security_score', 0.0),
                        "contract_verified": getattr(token, 'contract_verified', False),
                        "ownership_renounced": getattr(token, 'ownership_renounced', False),
                        "liquidity_locked": getattr(token, 'liquidity_locked', False),
                        "honeypot_probability": getattr(token, 'honeypot_probability', 0.0),
                        "security_issues": getattr(token, 'security_issues', []),
                        "security_level": "LOW" if getattr(token, 'security_score', 1.0) <= 0.4 else "MEDIUM" if getattr(token, 'security_score', 1.0) <= 0.6 else "HIGH" if getattr(token, 'security_score', 1.0) <= 0.8 else "CRITICAL",
                        "security_recommendations": self.get_security_recommendations(token),
                        "external_checks": getattr(token, 'security_report', {}).external_checks if hasattr(token, 'security_report') and token.security_report else {}
                    }
                }
                
                export_data["recommended_tokens"].append(token_data)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Экспорт рекомендованных токенов в JSON успешно завершен")
            return True
            
        except Exception as e:
            error_msg = f"Ошибка при экспорте рекомендованных токенов в JSON: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg) 
    
    def get_security_recommendations(self, token: Token) -> List[str]:
        """Генерирует рекомендации по безопасности для токена"""
        recommendations = []
        
        if hasattr(token, 'security_score'):
            # Рекомендации на основе security score
            if token.security_score >= 0.8:
                recommendations.append("🚨 КРИТИЧЕСКИЙ РИСК - НЕ РЕКОМЕНДУЕТСЯ К ИНВЕСТИРОВАНИЮ")
            elif token.security_score >= 0.6:
                recommendations.append("🔴 ВЫСОКИЙ РИСК - ТРЕБУЕТСЯ ОСТОРОЖНОСТЬ")
            elif token.security_score >= 0.4:
                recommendations.append("🟡 СРЕДНИЙ РИСК - ТРЕБУЕТСЯ ДОПОЛНИТЕЛЬНЫЙ АНАЛИЗ")
            else:
                recommendations.append("🟢 НИЗКИЙ РИСК - ОТНОСИТЕЛЬНО БЕЗОПАСЕН")
            
            # Специфические рекомендации
            if hasattr(token, 'contract_verified') and not token.contract_verified:
                recommendations.append("⚠️ Контракт не верифицирован - проверьте исходный код")
            
            if hasattr(token, 'ownership_renounced') and not token.ownership_renounced:
                recommendations.append("⚠️ Владелец не ренонсирован - риск централизации")
            
            if hasattr(token, 'liquidity_locked') and not token.liquidity_locked:
                recommendations.append("⚠️ Ликвидность не заблокирована - риск rug pull")
            
            if hasattr(token, 'honeypot_probability') and token.honeypot_probability > 0.5:
                recommendations.append("🚨 Высокая вероятность honeypot - НЕ ПОКУПАТЬ")
            
            if hasattr(token, 'security_issues') and token.security_issues:
                for issue in token.security_issues[:3]:  # Первые 3 проблемы
                    recommendations.append(f"⚠️ {issue}")
        
        return recommendations
    
    def generate_security_report(self, file_path: str, tokens_list: List[Token] = None) -> bool:
        """Генерация отчета по безопасности токенов"""
        if tokens_list is None:
            tokens_list = self.tokens
        
        # Фильтруем токены - исключаем скам
        tokens_to_analyze = [token for token in tokens_list if token.risk_level != "Скам"]
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = f"{file_path}_security_{timestamp}.txt"
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("🔒 ОТЧЕТ ПО АНАЛИЗУ БЕЗОПАСНОСТИ ТОКЕНОВ\n")
                f.write("=" * 80 + "\n")
                f.write(f"Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Всего токенов: {len(tokens_list)}\n")
                f.write(f"Токенов для анализа безопасности: {len(tokens_to_analyze)} (исключая {len(tokens_list) - len(tokens_to_analyze)} скам-токенов)\n\n")
                
                # Статистика безопасности
                security_stats = self.calculate_security_statistics(tokens_to_analyze)
                f.write("📊 СТАТИСТИКА БЕЗОПАСНОСТИ:\n")
                f.write("-" * 40 + "\n")
                f.write(f"🔍 Проанализировано с безопасностью: {security_stats['analyzed']}\n")
                f.write(f"✅ Безопасные токены: {security_stats['safe']}\n")
                f.write(f"⚠️ Токены с проблемами: {security_stats['issues']}\n")
                f.write(f"🚨 Критический риск: {security_stats['critical']}\n")
                f.write(f"🔴 Высокий риск: {security_stats['high']}\n")
                f.write(f"🟡 Средний риск: {security_stats['medium']}\n")
                f.write(f"🟢 Низкий риск: {security_stats['low']}\n\n")
                
                # Детальный анализ по категориям
                f.write("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ БЕЗОПАСНОСТИ:\n")
                f.write("=" * 80 + "\n\n")
                
                # Критический риск
                if security_stats['critical_tokens']:
                    f.write("🚨 ТОКЕНЫ С КРИТИЧЕСКИМ РИСКОМ:\n")
                    f.write("-" * 50 + "\n")
                    for token in security_stats['critical_tokens'][:10]:  # Показываем топ 10
                        f.write(self.format_security_token_info(token, "КРИТИЧЕСКИЙ"))
                    f.write("\n")
                
                # Высокий риск
                if security_stats['high_tokens']:
                    f.write("🔴 ТОКЕНЫ С ВЫСОКИМ РИСКОМ:\n")
                    f.write("-" * 50 + "\n")
                    for token in security_stats['high_tokens'][:10]:
                        f.write(self.format_security_token_info(token, "ВЫСОКИЙ"))
                    f.write("\n")
                
                # Средний риск
                if security_stats['medium_tokens']:
                    f.write("🟡 ТОКЕНЫ СО СРЕДНИМ РИСКОМ:\n")
                    f.write("-" * 50 + "\n")
                    for token in security_stats['medium_tokens'][:5]:
                        f.write(self.format_security_token_info(token, "СРЕДНИЙ"))
                    f.write("\n")
                
                # Безопасные токены
                if security_stats['safe_tokens']:
                    f.write("🟢 БЕЗОПАСНЫЕ ТОКЕНЫ:\n")
                    f.write("-" * 50 + "\n")
                    for token in security_stats['safe_tokens'][:5]:
                        f.write(self.format_security_token_info(token, "БЕЗОПАСНЫЙ"))
                    f.write("\n")
                
                # Анализ проблем безопасности
                f.write("⚠️ АНАЛИЗ ПРОБЛЕМ БЕЗОПАСНОСТИ:\n")
                f.write("=" * 80 + "\n\n")
                
                security_issues_analysis = self.analyze_security_issues(tokens_to_analyze)
                for issue_type, count in security_issues_analysis.items():
                    f.write(f"{issue_type}: {count} токенов\n")
                
                f.write("\n" + "=" * 80 + "\n")
                f.write("📋 РЕКОМЕНДАЦИИ ПО БЕЗОПАСНОСТИ:\n")
                f.write("=" * 80 + "\n")
                f.write("1. Всегда проверяйте верификацию контракта\n")
                f.write("2. Убедитесь, что владелец ренонсирован или использует multisig/timelock\n")
                f.write("3. Проверьте блокировку ликвидности на длительный срок\n")
                f.write("4. Избегайте токенов с высокой вероятностью honeypot\n")
                f.write("5. Проверяйте распределение токенов между держателями\n")
                f.write("6. Анализируйте торговые паттерны на предмет wash trading\n")
                f.write("7. Используйте несколько источников для проверки безопасности\n")
                # Ранее здесь была рекомендация по проверке 1inch — удалена
            
            self.logger.info(f"✅ Отчет по безопасности сохранен: {report_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка при создании отчета по безопасности: {str(e)}")
            return False
    
    def calculate_security_statistics(self, tokens: List[Token]) -> Dict:
        """Расчет статистики безопасности"""
        stats = {
            'analyzed': 0,
            'safe': 0,
            'issues': 0,
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'critical_tokens': [],
            'high_tokens': [],
            'medium_tokens': [],
            'safe_tokens': []
        }
        
        for token in tokens:
            if hasattr(token, 'security_score') and token.security_score is not None:
                stats['analyzed'] += 1
                
                if token.security_score >= 0.8:
                    stats['critical'] += 1
                    stats['critical_tokens'].append(token)
                elif token.security_score >= 0.6:
                    stats['high'] += 1
                    stats['high_tokens'].append(token)
                elif token.security_score >= 0.4:
                    stats['medium'] += 1
                    stats['medium_tokens'].append(token)
                else:
                    stats['low'] += 1
                    stats['safe_tokens'].append(token)
                
                if token.security_issues:
                    stats['issues'] += 1
                else:
                    stats['safe'] += 1
        
        # Сортировка по security_score
        stats['critical_tokens'].sort(key=lambda x: x.security_score, reverse=True)
        stats['high_tokens'].sort(key=lambda x: x.security_score, reverse=True)
        stats['medium_tokens'].sort(key=lambda x: x.security_score, reverse=True)
        stats['safe_tokens'].sort(key=lambda x: x.security_score)
        
        return stats
    
    def format_security_token_info(self, token: Token, risk_level: str) -> str:
        """Форматирование информации о токене для отчета безопасности"""
        info = f"🔸 {token.symbol} ({token.name})\n"
        info += f"   Адрес: {token.address}\n"
        info += f"   Сеть: {token.network}\n"
        info += f"   Цена: ${token.price_usd:.6f}\n"
        info += f"   Цена (нативная): {token.price_native:.8f}\n"
        info += f"   Ликвидность: ${token.liquidity_usd:,.0f}\n"
        info += f"   Объем 24ч: ${token.volume_24h:,.0f}\n"
        info += f"   Объем 6ч: ${token.volume_6h:,.0f}\n"
        info += f"   Объем 1ч: ${token.volume_1h:,.0f}\n"
        info += f"   Изменение цены 24ч: {token.price_change_24h:+.1f}%\n"
        info += f"   Изменение цены 6ч: {token.price_change_6h:+.1f}%\n"
        info += f"   Изменение цены 1ч: {token.price_change_1h:+.1f}%\n"
        info += f"   Покупки 24ч: {token.buys_24h}\n"
        info += f"   Продажи 24ч: {token.sells_24h}\n"
        info += f"   FDV: ${token.fdv:,.0f}\n"
        info += f"   Market Cap: ${token.market_cap:,.0f}\n"
        info += f"   Возраст: {token.format_age()}\n"
        info += f"   Risk Score: {token.risk_score}\n"
        info += f"   Risk Level: {token.risk_level}\n"
        info += f"   Security Score: {token.security_score:.3f} ({risk_level})\n"
        
        # Информация о безопасности
        if hasattr(token, 'contract_verified'):
            info += f"   Контракт верифицирован: {'✅' if token.contract_verified else '❌'}\n"
        if hasattr(token, 'ownership_renounced'):
            info += f"   Владелец ренонсирован: {'✅' if token.ownership_renounced else '❌'}\n"
        if hasattr(token, 'liquidity_locked'):
            info += f"   Ликвидность заблокирована: {'✅' if token.liquidity_locked else '❌'}\n"
        if hasattr(token, 'honeypot_probability'):
            info += f"   Вероятность honeypot: {token.honeypot_probability:.1%}\n"
        
        # Проблемы безопасности
        if token.security_issues:
            info += f"   Проблемы безопасности:\n"
            for issue in token.security_issues[:3]:  # Показываем первые 3 проблемы
                info += f"     ⚠️ {issue}\n"
        
        # Все 3 ссылки
        info += f"   🔗 Ссылки:\n"
        info += f"     📊 DexScreener: {token.get_dexscreener_url()}\n"
        info += f"     🔍 Explorer: {token.get_explorer_url()}\n"
        info += f"     💱 DEX: {token.get_dex_url()}\n"
        
        # Блок 1inch удален
        
        info += "\n"
        
        return info
    
    def analyze_security_issues(self, tokens: List[Token]) -> Dict[str, int]:
        """Анализ типов проблем безопасности"""
        issues_count = {}
        
        for token in tokens:
            if hasattr(token, 'security_issues') and token.security_issues:
                for issue in token.security_issues:
                    # Категоризация проблем
                    if 'не верифицирован' in issue.lower():
                        issues_count['Неверифицированные контракты'] = issues_count.get('Неверифицированные контракты', 0) + 1
                    elif 'ренонс' in issue.lower():
                        issues_count['Не ренонсированные контракты'] = issues_count.get('Не ренонсированные контракты', 0) + 1
                    elif 'ликвидность' in issue.lower():
                        issues_count['Незаблокированная ликвидность'] = issues_count.get('Незаблокированная ликвидность', 0) + 1
                    elif 'honeypot' in issue.lower():
                        issues_count['Honeypot признаки'] = issues_count.get('Honeypot признаки', 0) + 1
                    elif 'комиссии' in issue.lower():
                        issues_count['Высокие комиссии'] = issues_count.get('Высокие комиссии', 0) + 1
                    elif 'паттерн' in issue.lower():
                        issues_count['Опасные паттерны'] = issues_count.get('Опасные паттерны', 0) + 1
                    else:
                        issues_count['Другие проблемы'] = issues_count.get('Другие проблемы', 0) + 1
        
        return dict(sorted(issues_count.items(), key=lambda x: x[1], reverse=True))
    
    def generate_unified_report(self, file_path: str, tokens_list: Optional[List[Token]] = None) -> bool:
        """Генерирует объединенный отчет с безопасностью и без дублирования"""
        if tokens_list is None:
            tokens_list = self.filtered_tokens if self.filtered_tokens else self.tokens
        
        self.logger.info(f"Генерация объединенного отчета: {file_path}")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # Заголовок отчета
                f.write("=" * 100 + "\n")
                f.write(" " * 25 + "ОБЪЕДИНЕННЫЙ ОТЧЕТ: АНАЛИЗ ТОКЕНОВ И БЕЗОПАСНОСТЬ" + " " * 25 + "\n")
                f.write("=" * 100 + "\n\n")
                
                # Основная информация
                f.write("📊 ОСНОВНАЯ ИНФОРМАЦИЯ\n")
                f.write("=" * 100 + "\n")
                f.write(f"📅 Дата и время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"🔍 Всего токенов: {len(tokens_list)}\n")
                f.write(f"🔒 Токенов для анализа безопасности: {len([t for t in tokens_list if t.risk_level != 'Скам'])}\n\n")
                
                # Общая статистика
                f.write("📈 ОБЩАЯ СТАТИСТИКА\n")
                f.write("=" * 100 + "\n")
                
                # Распределение по рискам
                risk_levels = {"Скам": 0, "Высокий": 0, "Средний": 0, "Умеренный": 0, "Низкий": 0}
                networks = {}
                security_stats = {"Безопасные": 0, "С проблемами": 0, "Критический риск": 0}
                
                for token in tokens_list:
                    risk_levels[token.risk_level] = risk_levels.get(token.risk_level, 0) + 1
                    networks[token.network] = networks.get(token.network, 0) + 1
                    
                    # Статистика безопасности
                    if hasattr(token, 'security_score'):
                        if token.security_score >= 0.8:
                            security_stats["Критический риск"] += 1
                        elif token.security_score >= 0.6:
                            security_stats["С проблемами"] += 1
                        else:
                            security_stats["Безопасные"] += 1
                
                f.write("🎯 Распределение по уровням риска:\n")
                f.write("┌────────────────┬──────────┬──────────┬─────────────┐\n")
                f.write("│ Уровень риска  │Количество│ Процент  │ Эмодзи      │\n")
                f.write("├────────────────┼──────────┼──────────┼─────────────┤\n")
                risk_emojis = {"Скам": "🚨", "Высокий": "🔴", "Средний": "🟡", "Умеренный": "🟠", "Низкий": "🟢"}
                for level, count in risk_levels.items():
                    percentage = (count / len(tokens_list)) * 100 if tokens_list else 0
                    emoji = risk_emojis.get(level, "❓")
                    f.write(f"│ {level:14} │ {count:8} │ {percentage:7.1f}% │ {emoji:10} │\n")
                f.write("└────────────────┴──────────┴──────────┴─────────────┘\n\n")
                
                f.write("🌐 Распределение по сетям:\n")
                f.write("┌────────────────┬──────────┬──────────┐\n")
                f.write("│ Сеть           │Количество│ Процент  │\n")
                f.write("├────────────────┼──────────┼──────────┤\n")
                for network, count in sorted(networks.items()):
                    percentage = (count / len(tokens_list)) * 100 if tokens_list else 0
                    f.write(f"│ {network:14} │ {count:8} │ {percentage:7.1f}% │\n")
                f.write("└────────────────┴──────────┴──────────┘\n\n")
                
                # Статистика безопасности
                if any(hasattr(t, 'security_score') for t in tokens_list):
                    f.write("🔒 СТАТИСТИКА БЕЗОПАСНОСТИ\n")
                    f.write("=" * 100 + "\n")
                    f.write("┌──────────────────┬──────────┬──────────┐\n")
                    f.write("│ Категория        │Количество│ Процент  │\n")
                    f.write("├──────────────────┼──────────┼──────────┤\n")
                    security_tokens = [t for t in tokens_list if hasattr(t, 'security_score')]
                    for category, count in security_stats.items():
                        percentage = (count / len(security_tokens)) * 100 if security_tokens else 0
                        f.write(f"│ {category:18} │ {count:8} │ {percentage:7.1f}% │\n")
                    f.write("└──────────────────┴──────────┴──────────┘\n\n")
                
                # Детальный анализ по категориям риска
                f.write("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ ПО КАТЕГОРИЯМ\n")
                f.write("=" * 100 + "\n\n")
                
                for risk_level in ["Скам", "Высокий", "Средний", "Умеренный", "Низкий"]:
                    level_tokens = [t for t in tokens_list if t.risk_level == risk_level]
                    if not level_tokens:
                        continue
                    
                    emoji = risk_emojis.get(risk_level, "❓")
                    f.write(f"{emoji} ТОКЕНЫ С УРОВНЕМ РИСКА: {risk_level.upper()}\n")
                    f.write("─" * 100 + "\n")
                    f.write(f"📊 Количество: {len(level_tokens)}\n\n")
                    
                    # Сортировка токенов по убыванию риск-скора
                    level_tokens.sort(key=lambda x: x.risk_score, reverse=True)
                    
                    for i, token in enumerate(level_tokens, 1):
                        f.write(f"{i}. {token.symbol} ({token.network})\n")
                        f.write("   " + "─" * 80 + "\n")
                        # Дополнительные идентификаторы
                        if hasattr(token, 'address'):
                            f.write(f"   Адрес: {token.address}\n")
                        if hasattr(token, 'network'):
                            f.write(f"   Сеть: {token.network}\n")
                        
                        # Основная информация
                        f.write(f"   💰 Цена: ${token.price_usd:.6f} | {token.price_native:.8f} {token.network.upper()}\n")
                        f.write(f"   📈 Рост: 1ч: {token.price_change_1h:+.1f}% | 6ч: {token.price_change_6h:+.1f}% | 24ч: {token.price_change_24h:+.1f}%\n")
                        f.write(f"   💎 Ликвидность: ${token.liquidity_usd:,.0f} | Объем 24ч: ${token.volume_24h:,.0f}\n")
                        if hasattr(token, 'volume_6h'):
                            f.write(f"   Объем 6ч: ${token.volume_6h:,.0f}\n")
                        if hasattr(token, 'volume_1h'):
                            f.write(f"   Объем 1ч: ${token.volume_1h:,.0f}\n")
                        if hasattr(token, 'buys_24h'):
                            f.write(f"   Покупки 24ч: {token.buys_24h}\n")
                        if hasattr(token, 'sells_24h'):
                            f.write(f"   Продажи 24ч: {token.sells_24h}\n")
                        f.write(f"   📊 FDV: ${token.fdv:,.0f} | Market Cap: ${token.market_cap:,.0f}\n")
                        f.write(f"   ⏰ Возраст: {token.format_age()} | Risk Score: {token.risk_score}\n")
                        
                        # Информация о безопасности
                        if hasattr(token, 'security_score'):
                            f.write(f"   🔒 Безопасность: {token.security_score:.3f}\n")
                            
                            # Статусы безопасности
                            security_status = []
                            if hasattr(token, 'contract_verified'):
                                security_status.append(f"Контракт: {'✅' if token.contract_verified else '❌'}")
                            if hasattr(token, 'ownership_renounced'):
                                security_status.append(f"Владелец: {'✅' if token.ownership_renounced else '❌'}")
                            if hasattr(token, 'liquidity_locked'):
                                security_status.append(f"Ликвидность: {'✅' if token.liquidity_locked else '❌'}")
                            if hasattr(token, 'honeypot_probability'):
                                security_status.append(f"Honeypot: {token.honeypot_probability:.1%}")
                            
                            if security_status:
                                f.write("   🛡️  Статусы безопасности:\n")
                                for item in security_status:
                                    f.write(f"     - {item}\n")
                                # Детали блокировки ликвидности (если есть успешная блокировка)
                                if hasattr(token, 'liquidity_lock_info') and token.liquidity_lock_info:
                                    lock_info = token.liquidity_lock_info
                                    if getattr(lock_info, 'is_locked', False):
                                        unlock_str = ''
                                        try:
                                            if getattr(lock_info, 'unlock_date', None):
                                                unlock_str = f", до {lock_info.unlock_date.strftime('%Y-%m-%d')}"
                                        except Exception:
                                            pass
                                        f.write(
                                            f"   🔒 Блокировка ликвидности: {lock_info.locked_percentage:.1f}% на {lock_info.lock_duration_days} дней ({lock_info.platform}{unlock_str})\n"
                                        )
                                        # Предупреждения/заметки по блокировке (если есть)
                                        try:
                                            warnings_list = getattr(lock_info, 'warnings', []) or []
                                            if warnings_list:
                                                f.write("   🔎 Примечания по блокировке:\n")
                                                for w in warnings_list[:3]:
                                                    f.write(f"      • {w}\n")
                                        except Exception:
                                            pass
                            
                            # Блок 1inch удален
                        
                        # Проблемы безопасности
                        if hasattr(token, 'security_issues') and token.security_issues:
                            f.write(f"   🚨 Проблемы безопасности:\n")
                            for issue in token.security_issues[:3]:  # Показываем первые 3
                                f.write(f"      • {issue}\n")
                        
                        # Факторы риска
                        if token.risk_factors:
                            f.write(f"   ⚠️  Факторы риска:\n")
                            for factor in token.risk_factors[:3]:  # Показываем первые 3
                                f.write(f"      • {factor}\n")
                        
                        # Рекомендации по безопасности (кратко)
                        try:
                            recommendations = self.get_security_recommendations(token)
                        except Exception:
                            recommendations = []
                        if recommendations:
                            f.write(f"   ✅ Рекомендации:\n")
                            for rec in recommendations[:3]:
                                f.write(f"      • {rec}\n")
                        
                        # Сайты и социальные сети
                        websites = token.info.get("websites", [])
                        socials = token.info.get("socials", [])
                        
                        if websites or socials:
                            f.write(f"   🌐 Информация:\n")
                            if websites:
                                for website in websites[:2]:  # Показываем первые 2
                                    if isinstance(website, dict):
                                        url = website.get('url', '')
                                        f.write(f"      • Сайт: {url}\n")
                                    else:
                                        f.write(f"      • Сайт: {website}\n")
                            
                            if socials:
                                for social in socials[:2]:  # Показываем первые 2
                                    if isinstance(social, dict):
                                        url = social.get('url', '')
                                        f.write(f"      • Соцсеть: {url}\n")
                                    else:
                                        f.write(f"      • Соцсеть: {social}\n")
                        
                        # Универсальные проверки (бесплатные источники)
                        try:
                            external_checks = getattr(token, 'security_report', {}).external_checks if hasattr(token, 'security_report') and token.security_report else {}
                        except Exception:
                            external_checks = {}
                        utc = (external_checks or {}).get('universal_checks') or {}
                        if utc:
                            srcs = utc.get('sources', [])
                            trust = utc.get('trust_level')
                            f.write("   🌐 Универсальные проверки:\n")
                            if srcs:
                                f.write(f"      • Источники: {', '.join(srcs)}\n")
                            if trust:
                                f.write(f"      • Уровень доверия: {trust}\n")
                            cg = utc.get('coingecko') or {}
                            if cg.get('found'):
                                f.write(f"      • CoinGecko: {cg.get('name','')} ({cg.get('symbol','')})\n")
                            uni = utc.get('uniswap') or {}
                            if uni.get('found'):
                                tvl = ((uni.get('info') or {}).get('totalValueLockedUSD'))
                                if tvl is not None:
                                    f.write(f"      • Uniswap v3: TVL ${float(tvl):,.0f}\n")
                            jup = utc.get('jupiter') or {}
                            if jup.get('found'):
                                f.write("      • Jupiter (Solana): найден/strict\n")

                        # Ссылки
                        f.write(f"   🔗 Ссылки:\n")
                        f.write(f"      • DexScreener: {token.get_dexscreener_url()}\n")
                        f.write(f"      • Explorer: {token.get_explorer_url()}\n")
                        f.write(f"      • DEX: {token.get_dex_url()}\n")
                        
                        f.write("\n")
                
                # Рекомендации
                f.write("💡 РЕКОМЕНДАЦИИ\n")
                f.write("=" * 100 + "\n")
                f.write("🔍 Всегда проверяйте:\n")
                f.write("   • Верификацию контракта\n")
                f.write("   • Ренонс владельца или использование multisig/timelock\n")
                f.write("   • Блокировку ликвидности на длительный срок\n")
                f.write("   • Наличие honeypot признаков\n")
                f.write("   • Распределение токенов между держателями\n")
                # Ранее здесь выводился статус токена в 1inch — удалено
                
                f.write("⚠️  Избегайте токенов с:\n")
                f.write("   • Аномальным ростом цены (>200%) за короткий период\n")
                f.write("   • Высоким соотношением объема к ликвидности (>50)\n")
                f.write("   • Отсутствием сайта и социальных сетей\n")
                f.write("   • Возрастом < 24 часов\n")
                f.write("   • Низкой ликвидностью (<$25,000)\n")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Ошибка генерации объединенного отчета: {e}")
            return False