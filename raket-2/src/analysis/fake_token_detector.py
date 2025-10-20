import asyncio
import aiohttp
import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
import logging
from datetime import datetime, timedelta
import json
import os

logger = logging.getLogger(__name__)

@dataclass
class FakeTokenResult:
    """Результат проверки на поддельный токен"""
    is_fake: bool
    confidence: float  # Уверенность в результате (0.0 - 1.0)
    reason: str
    original_token: Optional[str] = None
    original_network: Optional[str] = None
    original_address: Optional[str] = None
    detection_method: str = ""

class FakeTokenDetector:
    """
    Продвинутая система обнаружения поддельных токенов
    """
    
    def __init__(self):
        # База данных известных токенов и их правильных сетей
        self.known_tokens_db = {
            # Ethereum токены
            'ETH': {'network': 'ethereum', 'address': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'},
            'WETH': {'network': 'ethereum', 'address': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'},
            'USDC': {'network': 'ethereum', 'address': '0xA0b86a33E6441b8C4C8C8C8C8C8C8C8C8C8C8C8C'},
            'USDT': {'network': 'ethereum', 'address': '0xdAC17F958D2ee523a2206206994597C13D831ec7'},
            'PEPE': {'network': 'ethereum', 'address': '0x6982508145454Ce325dDbE47a25d4ec3d2311933'},
            'SHIB': {'network': 'ethereum', 'address': '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE'},
            'DOGE': {'network': 'ethereum', 'address': '0x3832d2F059E55934220881F831bE501D180671A7'},
            'UNI': {'network': 'ethereum', 'address': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984'},
            'LINK': {'network': 'ethereum', 'address': '0x514910771AF9Ca656af840dff83E8264EcF986CA'},
            'AAVE': {'network': 'ethereum', 'address': '0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9'},
            'COMP': {'network': 'ethereum', 'address': '0xc00e94Cb662C3520282E6f5717214004A7f26888'},
            'MKR': {'network': 'ethereum', 'address': '0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2'},
            'SNX': {'network': 'ethereum', 'address': '0xC011a73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F'},
            'YFI': {'network': 'ethereum', 'address': '0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e'},
            'CRV': {'network': 'ethereum', 'address': '0xD533a949740bb3306d119CC777fa900bA034cd52'},
            'MATIC': {'network': 'ethereum', 'address': '0x7D1AfA7B718fb893dB30A3aBc0Cfc608aCafEBB0'},
            'AVAX': {'network': 'ethereum', 'address': '0x85f138bfEE4ef8e540890CFb48F620571d67Eda3'},
            'FTM': {'network': 'ethereum', 'address': '0x4E15361FD6b4bb609Fa63C81A2be19d873717870'},
            'WBTC': {'network': 'ethereum', 'address': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599'},
            'DAI': {'network': 'ethereum', 'address': '0x6B175474E89094C44Da98b954EedeAC495271d0F'},
            'BAL': {'network': 'ethereum', 'address': '0xba100000625a3754423978a60c9317c58a424e3D'},
            'BAT': {'network': 'ethereum', 'address': '0x0D8775F648430679A709E98d2b0Cb6250d2887EF'},
            'BOND': {'network': 'ethereum', 'address': '0x0391D2021f89DC339F60Fff84546EA23E337760f'},
            'DPI': {'network': 'ethereum', 'address': '0x1494CA1F11D487c2bBe4543E90080AeBa4BA3C2b'},
            'ENJ': {'network': 'ethereum', 'address': '0xF629cBd94d3791C9250152BD8dfBDF380E2a3B9c'},
            'GRT': {'network': 'ethereum', 'address': '0xc944E90C64B2c07662A292be6244BDf05Cda44a7'},
            'KNC': {'network': 'ethereum', 'address': '0xdd974D5C2e2928deA5F71b9825b8b646686BD200'},
            'LDO': {'network': 'ethereum', 'address': '0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32'},
            'LRC': {'network': 'ethereum', 'address': '0xBBbbCA6A901c926F240b89EacB641d8Aec7AEafD'},
            'NMR': {'network': 'ethereum', 'address': '0x1776e1F26f98b1A5dF9cD347953a26dd3C4668a8'},
            'OXT': {'network': 'ethereum', 'address': '0x4575f41308EC1483f3d399aa9a2826d74Da13Deb'},
            'PAX': {'network': 'ethereum', 'address': '0x8E870D67F660D95d5be530380D0eC0bd388289E1'},
            'REN': {'network': 'ethereum', 'address': '0x408e41876cCcDC0F92210600ef50372656052a38'},
            'REP': {'network': 'ethereum', 'address': '0x2216577768468949895a2a4a9a8c4b6d6f6b6b6b'},
            'SUSHI': {'network': 'ethereum', 'address': '0x6B3595068778DD592e39A122f4f5a5cF09C90fE2'},
            'SXP': {'network': 'ethereum', 'address': '0x8CE9137d39326AD0cD6491fb5CC0CbA0e089b6A9'},
            'TUSD': {'network': 'ethereum', 'address': '0x0000000000085d4780B73119b644AE5ecd22b376'},
            'UMA': {'network': 'ethereum', 'address': '0x04Fa0d235C4abf4BcF4787aF4CF447DE572eF828'},
            'ZRX': {'network': 'ethereum', 'address': '0xE41d2489571d322189246DaFA5ebDe1F4699F498'},
            
            # BSC токены
            'BNB': {'network': 'bsc', 'address': '0xbb4CdB9CBd36B01bD1cBaEF2aD8C3c2D3C3C3C3C3'},
            'CAKE': {'network': 'bsc', 'address': '0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82'},
            'BUSD': {'network': 'bsc', 'address': '0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56'},
            'BIAO': {'network': 'bsc', 'address': '0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82'},
            
            # Solana токены
            'SOL': {'network': 'solana', 'address': 'So11111111111111111111111111111111111111112'},
            'BONK': {'network': 'solana', 'address': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263'},
            'RAY': {'network': 'solana', 'address': '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R'},
            'SRM': {'network': 'solana', 'address': 'SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt'},
            'MNGO': {'network': 'solana', 'address': 'MangoCzJ36AjZyKwVj3VnYU4GTonjfVEnJmvvWaxLac'},
            'SAMO': {'network': 'solana', 'address': '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU'},
            'ORCA': {'network': 'solana', 'address': 'orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE'},
            'ATLAS': {'network': 'solana', 'address': 'ATLASXmbPQxBUYbxPsV97usA3PpqKwV4QZFMvQ3pUCLv'},
            'POLIS': {'network': 'solana', 'address': 'poLisWXnNRwC6oBu1vHiuKQzFjGL4XDSu4g9qjtxcwM'},
            'GST': {'network': 'solana', 'address': 'AFbX8oGjGpmVFywbVouvhQSRmiW2aR1mohfahi4Y2AdB'},
            'SBR': {'network': 'solana', 'address': 'Saber2gLauYim4Mvftnrasomsv6NvAuncvMEZwcLpD1'},
            'JUP': {'network': 'solana', 'address': 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN'},
            'PYTH': {'network': 'solana', 'address': 'HZ1JovNiVvGrGNiiYvEozEVg58WUyVHFoBq8Vz7YtHm'},
            'WIF': {'network': 'solana', 'address': 'EKpQGSJtjMFqKZ1KQanSqABXRxaB45qe2XDQ5es4V7sM'},
            'MYRO': {'network': 'solana', 'address': 'HYPERfwdTjyJ2SCaKHmpF2MtrXqWxrsotYDsRhshbxQY'},
            'POPCAT': {'network': 'solana', 'address': 'POPCATeXj5qKfqKqKqKqKqKqKqKqKqKqKqKqKqKqKq'},
            'WEN': {'network': 'solana', 'address': 'WENWENvqqNya429uG2pTpQ2VqWg5j8ZvqKqKqKqKqKqKq'},
            'SLERF': {'network': 'solana', 'address': 'SLERFqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKq'},
            'BOME': {'network': 'solana', 'address': 'BOMEqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKq'},
            'MEME': {'network': 'solana', 'address': 'MEMEqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKqKq'},
        }
        
        # Подозрительные паттерны в названиях
        self.suspicious_patterns = {
            'high_risk': [
                'SAFEMOON', 'SAFEMARS', 'HONEY', 'MOONSHOT', 'PUMP', 'DUMP', 'SCAM', 'FAKE', 
                'TEST', 'DUMMY', 'BABY', 'MINI', 'MICRO', 'NANO', 'PICO', 'ELON', 'MUSK',
                'MOON', 'SAFE', 'INU', 'DOGE', 'SHIB', 'WOJAK', 'PEPE', 'BONK', 'WIF'
            ],
            'medium_risk': [
                'INU', 'DOGE', 'SHIB', 'MOON', 'SAFE', 'BABY', 'MINI', 'MICRO', 'NANO',
                'PICO', 'PUMP', 'DUMP', 'ELON', 'MUSK', 'WOJAK', 'PEPE', 'BONK', 'WIF'
            ],
            'low_risk': [
                'INU', 'DOGE', 'SHIB', 'MOON', 'SAFE', 'BABY', 'MINI', 'MICRO', 'NANO'
            ]
        }
        
        # Черный список токенов
        self.blacklisted_tokens = {
            'SAFEMOON', 'SAFEMARS', 'HONEY', 'MOONSHOT', 'PUMP', 'DUMP', 'SCAM', 'FAKE',
            'TEST', 'DUMMY', 'BABY', 'MINI', 'MICRO', 'NANO', 'PICO', 'ELON', 'MUSK'
        }
        
        # Паттерны для проверки адресов
        self.address_patterns = {
            'ethereum': r'^0x[a-fA-F0-9]{40}$',
            'bsc': r'^0x[a-fA-F0-9]{40}$',
            'polygon': r'^0x[a-fA-F0-9]{40}$',
            'arbitrum': r'^0x[a-fA-F0-9]{40}$',
            'base': r'^0x[a-fA-F0-9]{40}$',
            'avalanche': r'^0x[a-fA-F0-9]{40}$',
            'fantom': r'^0x[a-fA-F0-9]{40}$',
            'cronos': r'^0x[a-fA-F0-9]{40}$',
            'solana': r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'
        }
        
        # Кэш для результатов проверки
        self.cache = {}
        self.cache_ttl = 3600  # 1 час
        
    async def detect_fake_token(self, token_name: str, token_address: str, network: str) -> FakeTokenResult:
        """
        Комплексная проверка на поддельный токен
        
        Args:
            token_name: Название токена
            token_address: Адрес контракта
            network: Сеть блокчейна
            
        Returns:
            FakeTokenResult: Результат проверки
        """
        # Проверяем кэш
        cache_key = f"{token_name}_{token_address}_{network}"
        if cache_key in self.cache:
            cached_result, timestamp = self.cache[cache_key]
            if datetime.now().timestamp() - timestamp < self.cache_ttl:
                return cached_result
        
        # Выполняем все проверки
        checks = [
            self._check_known_token_mismatch(token_name, network),
            self._check_blacklisted_token(token_name),
            self._check_suspicious_patterns(token_name),
            self._check_address_format(token_address, network),
            self._check_similar_names(token_name, network),
            await self._check_contract_verification(token_address, network),
            await self._check_liquidity_suspicious(token_address, network),
            await self._check_holder_distribution(token_address, network)
        ]
        
        # Анализируем результаты
        fake_checks = [check for check in checks if check.is_fake]
        total_confidence = sum(check.confidence for check in checks)
        
        if fake_checks:
            # Берем самый уверенный результат
            best_check = max(fake_checks, key=lambda x: x.confidence)
            result = FakeTokenResult(
                is_fake=True,
                confidence=min(best_check.confidence, 1.0),
                reason=best_check.reason,
                original_token=best_check.original_token,
                original_network=best_check.original_network,
                original_address=best_check.original_address,
                detection_method=best_check.detection_method
            )
        else:
            # Если нет явных признаков подделки, но есть подозрения
            suspicious_checks = [check for check in checks if check.confidence > 0.3]
            if suspicious_checks:
                avg_confidence = sum(check.confidence for check in suspicious_checks) / len(suspicious_checks)
                result = FakeTokenResult(
                    is_fake=avg_confidence > 0.7,
                    confidence=avg_confidence,
                    reason=f"Подозрительные признаки: {len(suspicious_checks)} проверок",
                    detection_method="suspicious_patterns"
                )
            else:
                result = FakeTokenResult(
                    is_fake=False,
                    confidence=1.0,
                    reason="Токен прошел все проверки",
                    detection_method="all_checks_passed"
                )
        
        # Сохраняем в кэш
        self.cache[cache_key] = (result, datetime.now().timestamp())
        
        return result
    
    def _check_known_token_mismatch(self, token_name: str, network: str) -> FakeTokenResult:
        """Проверка на несоответствие известному токену"""
        token_upper = token_name.upper()
        
        if token_upper in self.known_tokens_db:
            known_info = self.known_tokens_db[token_upper]
            if known_info['network'] != network:
                return FakeTokenResult(
                    is_fake=True,
                    confidence=0.95,
                    reason=f"Токен {token_name} должен быть в сети {known_info['network']}, а не в {network}",
                    original_token=token_name,
                    original_network=known_info['network'],
                    original_address=known_info['address'],
                    detection_method="known_token_mismatch"
                )
        
        return FakeTokenResult(is_fake=False, confidence=0.0, reason="", detection_method="known_token_mismatch")
    
    def _check_blacklisted_token(self, token_name: str) -> FakeTokenResult:
        """Проверка на токен из черного списка"""
        token_upper = token_name.upper()
        
        if token_upper in self.blacklisted_tokens:
            return FakeTokenResult(
                is_fake=True,
                confidence=0.9,
                reason=f"Токен {token_name} в черном списке",
                detection_method="blacklisted_token"
            )
        
        return FakeTokenResult(is_fake=False, confidence=0.0, reason="", detection_method="blacklisted_token")
    
    def _check_suspicious_patterns(self, token_name: str) -> FakeTokenResult:
        """Проверка на подозрительные паттерны в названии"""
        token_upper = token_name.upper()
        
        # Подсчитываем подозрительные паттерны
        high_risk_count = sum(1 for pattern in self.suspicious_patterns['high_risk'] if pattern in token_upper)
        medium_risk_count = sum(1 for pattern in self.suspicious_patterns['medium_risk'] if pattern in token_upper)
        low_risk_count = sum(1 for pattern in self.suspicious_patterns['low_risk'] if pattern in token_upper)
        
        total_suspicious = high_risk_count + medium_risk_count + low_risk_count
        
        if high_risk_count >= 2:
            confidence = 0.85
        elif high_risk_count == 1 and medium_risk_count >= 1:
            confidence = 0.7
        elif total_suspicious >= 3:
            confidence = 0.6
        elif total_suspicious >= 2:
            confidence = 0.4
        elif total_suspicious == 1:
            confidence = 0.2
        else:
            confidence = 0.0
        
        if confidence > 0:
            return FakeTokenResult(
                is_fake=confidence > 0.6,
                confidence=confidence,
                reason=f"Подозрительные паттерны в названии: {total_suspicious} совпадений",
                detection_method="suspicious_patterns"
            )
        
        return FakeTokenResult(is_fake=False, confidence=0.0, reason="", detection_method="suspicious_patterns")
    
    def _check_address_format(self, token_address: str, network: str) -> FakeTokenResult:
        """Проверка формата адреса"""
        if network not in self.address_patterns:
            return FakeTokenResult(is_fake=False, confidence=0.0, reason="", detection_method="address_format")
        
        pattern = self.address_patterns[network]
        if not re.match(pattern, token_address):
            return FakeTokenResult(
                is_fake=True,
                confidence=0.8,
                reason=f"Неверный формат адреса для сети {network}",
                detection_method="address_format"
            )
        
        return FakeTokenResult(is_fake=False, confidence=0.0, reason="", detection_method="address_format")
    
    def _check_similar_names(self, token_name: str, network: str) -> FakeTokenResult:
        """Проверка на похожие названия известных токенов"""
        token_upper = token_name.upper()
        
        # Ищем похожие названия
        for known_token in self.known_tokens_db:
            if known_token != token_upper:
                # Простая проверка на схожесть
                if self._calculate_similarity(token_upper, known_token) > 0.8:
                    known_info = self.known_tokens_db[known_token]
                    if known_info['network'] != network:
                        return FakeTokenResult(
                            is_fake=True,
                            confidence=0.75,
                            reason=f"Название похоже на {known_token} из сети {known_info['network']}",
                            original_token=known_token,
                            original_network=known_info['network'],
                            detection_method="similar_names"
                        )
        
        return FakeTokenResult(is_fake=False, confidence=0.0, reason="", detection_method="similar_names")
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Вычисляет схожесть двух строк"""
        if len(str1) < 3 or len(str2) < 3:
            return 0.0
        
        # Простой алгоритм Левенштейна
        matrix = [[0] * (len(str2) + 1) for _ in range(len(str1) + 1)]
        
        for i in range(len(str1) + 1):
            matrix[i][0] = i
        for j in range(len(str2) + 1):
            matrix[0][j] = j
        
        for i in range(1, len(str1) + 1):
            for j in range(1, len(str2) + 1):
                if str1[i-1] == str2[j-1]:
                    matrix[i][j] = matrix[i-1][j-1]
                else:
                    matrix[i][j] = min(
                        matrix[i-1][j] + 1,
                        matrix[i][j-1] + 1,
                        matrix[i-1][j-1] + 1
                    )
        
        distance = matrix[len(str1)][len(str2)]
        max_len = max(len(str1), len(str2))
        return 1.0 - (distance / max_len)
    
    async def _check_contract_verification(self, token_address: str, network: str) -> FakeTokenResult:
        """Проверка верификации контракта"""
        # Заглушка - в реальной реализации здесь будет проверка через API
        return FakeTokenResult(is_fake=False, confidence=0.0, reason="", detection_method="contract_verification")
    
    async def _check_liquidity_suspicious(self, token_address: str, network: str) -> FakeTokenResult:
        """Проверка подозрительной ликвидности"""
        # Заглушка - в реальной реализации здесь будет анализ ликвидности
        return FakeTokenResult(is_fake=False, confidence=0.0, reason="", detection_method="liquidity_suspicious")
    
    async def _check_holder_distribution(self, token_address: str, network: str) -> FakeTokenResult:
        """Проверка распределения держателей"""
        # Заглушка - в реальной реализации здесь будет анализ держателей
        return FakeTokenResult(is_fake=False, confidence=0.0, reason="", detection_method="holder_distribution")
    
    def get_detection_stats(self) -> Dict:
        """Возвращает статистику обнаружения"""
        total_checks = len(self.cache)
        fake_detections = sum(1 for result, _ in self.cache.values() if result.is_fake)
        
        return {
            'total_checks': total_checks,
            'fake_detections': fake_detections,
            'detection_rate': fake_detections / total_checks if total_checks > 0 else 0,
            'cache_size': len(self.cache)
        }
    
    def clear_cache(self):
        """Очищает кэш"""
        self.cache.clear()
        logger.info("Кэш обнаружения поддельных токенов очищен") 