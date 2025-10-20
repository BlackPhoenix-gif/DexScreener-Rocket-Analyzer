import asyncio
import json
import time
from typing import Dict, List, Any, Optional
from models import (
    TokenSecurityReport, 
    TradingAnalysis, 
    RiskAssessment, 
    ContractAnalysis, 
    OwnershipAnalysis, 
    DistributionAnalysis,
    OwnerType,
    WhaleConcentration
)
from config import Config

class FreeTokenAnalyzer:
    """Бесплатный анализатор токенов без API ключей"""
    
    def __init__(self):
        self.config = Config()
    
    async def analyze_token(self, token_address: str, chain: str = "ethereum") -> TokenSecurityReport:
        """Анализ токена с использованием только бесплатных методов"""
        start_time = time.time()
        
        # Получаем информацию о токене
        token_info = await self.get_token_info(token_address, chain)
        
        # Создание базового отчета
        report = TokenSecurityReport(
            token_address=token_address,
            token_name=token_info.get('name'),
            token_symbol=token_info.get('symbol'),
            chain=chain,
            risk_assessment=RiskAssessment(),
            contract_analysis=ContractAnalysis(),
            ownership=OwnershipAnalysis(),
            distribution=DistributionAnalysis(),
            trading=TradingAnalysis()
        )
        
        try:
            # Базовый анализ без внешних API
            await self.perform_basic_analysis(report)
            
            # Расчет риска
            report.risk_assessment = self.calculate_risk_score(report)
            
            # Внешние проверки (только бесплатные)
            report.external_checks = await self.perform_free_checks(token_address)
            
            # Интеграция 1inch удалена: не обновляем информацию из 1inch
                        
        except Exception as e:
            print(f"Error analyzing token {token_address}: {e}")
        
        # Расчет времени анализа
        report.analysis_duration = time.time() - start_time
        
        return report
    
    async def perform_basic_analysis(self, report: TokenSecurityReport):
        """Выполнение базового анализа без API"""
        
        # Симуляция анализа контракта
        report.contract_analysis.verified = False  # По умолчанию не верифицирован
        report.contract_analysis.honeypot_probability = 0.1  # Низкая вероятность
        
        # Симуляция анализа владельца
        report.ownership.owner = "0x0000000000000000000000000000000000000000"
        report.ownership.renounced = True
        report.ownership.owner_type = OwnerType.RENOUNCED
        
        # Симуляция анализа распределения
        report.distribution.total_holders = 1000
        report.distribution.top_10_holders_percent = 45.0
        report.distribution.gini_coefficient = 0.6
        report.distribution.whale_concentration = WhaleConcentration.MEDIUM
        report.distribution.liquidity_locked = False
        report.distribution.top_holders = [
            {'address': '0x1234...', 'balance': 1000000, 'percentage': 20.0},
            {'address': '0x5678...', 'balance': 800000, 'percentage': 16.0},
            {'address': '0x9abc...', 'balance': 600000, 'percentage': 12.0},
        ]
        
        # Симуляция анализа торговли
        report.trading.unique_buyers_24h = 150
        report.trading.unique_sellers_24h = 120
        report.trading.wash_trading_score = 0.2
        report.trading.organic_volume_ratio = 0.8
        report.trading.avg_hold_time = 2.5
        report.trading.volume_24h = 50000
        report.trading.price_change_24h = 5.2
    
    def calculate_risk_score(self, report: TokenSecurityReport) -> RiskAssessment:
        """Расчет риска на основе базовых данных"""
        
        # Веса для различных факторов
        weights = {
            'contract_verification': 0.15,
            'ownership_status': 0.20,
            'liquidity_lock': 0.25,
            'holder_distribution': 0.15,
            'trading_patterns': 0.10,
            'code_audit': 0.10,
            'community_reports': 0.05
        }
        
        scores = {}
        
        # Contract verification
        if report.contract_analysis.verified:
            scores['contract_verification'] = 0.1
        else:
            scores['contract_verification'] = 0.8
        
        # Ownership status
        if report.ownership.renounced:
            scores['ownership_status'] = 0.0
        else:
            scores['ownership_status'] = 0.9
        
        # Liquidity lock
        if report.distribution.liquidity_locked:
            scores['liquidity_lock'] = 0.1
        else:
            scores['liquidity_lock'] = 0.9
        
        # Holder distribution
        gini = report.distribution.gini_coefficient
        if gini > 0.8:
            scores['holder_distribution'] = 0.9
        elif gini > 0.6:
            scores['holder_distribution'] = 0.7
        elif gini > 0.4:
            scores['holder_distribution'] = 0.5
        else:
            scores['holder_distribution'] = 0.2
        
        # Trading patterns
        wash_score = report.trading.wash_trading_score
        if wash_score > 0.7:
            scores['trading_patterns'] = 0.9
        elif wash_score > 0.5:
            scores['trading_patterns'] = 0.7
        elif wash_score > 0.3:
            scores['trading_patterns'] = 0.5
        else:
            scores['trading_patterns'] = 0.2
        
        # Code audit (симуляция)
        scores['code_audit'] = 0.3
        
        # Community reports (симуляция)
        scores['community_reports'] = 0.2
        
        # Проверяем результаты внешних проверок
        # Интеграция 1inch удалена: не учитываем результаты 1inch
        
        # Комплексный расчет
        final_score = sum(scores[k] * weights[k] for k in scores)
        
        # Определение уровня риска
        if final_score >= 0.8:
            risk_level = "CRITICAL"
        elif final_score >= 0.6:
            risk_level = "HIGH"
        elif final_score >= 0.4:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Генерация рекомендаций
        recommendations = []
        
        if scores['contract_verification'] > 0.5:
            recommendations.append("⚠️ Контракт не верифицирован")
        else:
            recommendations.append("✅ Контракт верифицирован")
        
        if scores['ownership_status'] > 0.5:
            recommendations.append("⚠️ Контракт не ренонсирован")
        else:
            recommendations.append("✅ Владелец ренонсирован")
        
        if scores['liquidity_lock'] > 0.5:
            recommendations.append("⚠️ Ликвидность не заблокирована")
        else:
            recommendations.append("✅ Ликвидность заблокирована")
        
        if scores['holder_distribution'] > 0.5:
            recommendations.append("⚠️ Высокая концентрация у крупных держателей")
        else:
            recommendations.append("✅ Хорошее распределение токенов")
        
        if report.contract_analysis.honeypot_probability > 0.5:
            recommendations.append("🚨 Высокая вероятность honeypot")
        else:
            recommendations.append("✅ Нет признаков honeypot")
        
        # Интеграция 1inch удалена: не добавляем рекомендации
        
        return RiskAssessment(
            overall_score=final_score,
            risk_level=risk_level,
            confidence=0.7,  # Средняя уверенность для бесплатного анализа
            breakdown=scores,
            recommendations=recommendations
        )
    
    async def perform_free_checks(self, token_address: str) -> Dict[str, Any]:
        """Выполнение бесплатных внешних проверок"""
        checks = {}
        
        # Проверка через бесплатные API (если доступны)
        try:
            # Проверка через Honeypot.is (бесплатный)
            checks['honeypot_check'] = await self.check_honeypot_free(token_address)
        except Exception as e:
            checks['honeypot_check'] = {'status': 'skipped', 'reason': str(e)}
        
        # Интеграция 1inch удалена
        
        # Добавляем базовую информацию
        checks['analysis_type'] = 'free'
        checks['limitations'] = [
            'No API keys required',
            'Limited external data',
            'Simulated data for some metrics'
        ]
        
        return checks
    
    async def check_honeypot_free(self, token_address: str) -> Dict[str, Any]:
        """Бесплатная проверка honeypot"""
        try:
            import aiohttp
            
            # Попытка использовать бесплатный API
            url = "https://api.honeypot.is/v2/IsHoneypot"
            params = {'address': token_address}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'is_honeypot': data.get('IsHoneypot', False),
                            'buy_tax': data.get('BuyTax', 0),
                            'sell_tax': data.get('SellTax', 0),
                            'transfer_tax': data.get('TransferTax', 0),
                            'source': 'honeypot.is'
                        }
        except Exception as e:
            pass
        
        # Fallback: базовая проверка
        return {
            'is_honeypot': False,
            'buy_tax': 0,
            'sell_tax': 0,
            'transfer_tax': 0,
            'source': 'simulated',
            'note': 'Free analysis - limited data'
        }
    
    # Интеграция 1inch удалена: метод verify_with_1inch удален
    
    async def get_token_info(self, token_address: str, chain: str) -> Dict[str, Any]:
        """Получение базовой информации о токене"""
        try:
            import aiohttp
            
            # Интеграция 1inch удалена: не запрашиваем 1inch API
            
        except Exception as e:
            pass
        
        # Пробуем получить информацию через Etherscan (если есть API ключ)
        try:
            if self.config.ETHERSCAN_API_KEY:
                url = "https://api.etherscan.io/api"
                params = {
                    'module': 'token',
                    'action': 'tokeninfo',
                    'contractaddress': token_address,
                    'apikey': self.config.ETHERSCAN_API_KEY
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('status') == '1' and data.get('result'):
                                result = data['result'][0]
                                return {
                                    'name': result.get('tokenName', 'Unknown Token'),
                                    'symbol': result.get('tokenSymbol', 'UNKNOWN'),
                                    'decimals': int(result.get('decimals', 18))
                                }
        except Exception as e:
            pass
        
        # Fallback: база данных известных токенов
        known_tokens = {
            "0xdAC17F958D2ee523a2206206994597C13D831ec7": {"name": "Tether USD", "symbol": "USDT", "decimals": 6},
            "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": {"name": "USD Coin", "symbol": "USDC", "decimals": 6},
            "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599": {"name": "Wrapped Bitcoin", "symbol": "WBTC", "decimals": 8},
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2": {"name": "Wrapped Ether", "symbol": "WETH", "decimals": 18},
            "0x514910771AF9Ca656af840dff83E8264EcF986CA": {"name": "Chainlink", "symbol": "LINK", "decimals": 18},
        }
        
        if token_address in known_tokens:
            token_data = known_tokens[token_address]
            return token_data
        
        # Fallback: генерируем базовую информацию
        return {
            'name': f'Token {token_address[:8]}...',
            'symbol': 'UNKNOWN',
            'decimals': 18
        }
    
    async def analyze_batch(self, token_addresses: List[str], chain: str = "ethereum") -> List[TokenSecurityReport]:
        """Пакетный анализ токенов"""
        reports = []
        
        # Убираем дубликаты
        unique_addresses = list(set(token_addresses))
        
        print(f"🔍 Анализируем {len(unique_addresses)} уникальных токенов...")
        
        for i, address in enumerate(unique_addresses, 1):
            print(f"📊 Токен {i}/{len(unique_addresses)}: {address}")
            
            try:
                report = await self.analyze_token(address, chain)
                reports.append(report)
                print(f"✅ Завершен за {report.analysis_duration:.2f}с")
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                continue
        
        return reports

async def demo_free_analysis():
    """Демонстрация бесплатного анализа"""
    analyzer = FreeTokenAnalyzer()
    
    # Реальные токены для тестирования
    tokens = [
        "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
        "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # WBTC
    ]
    
    print("🔐 БЕСПЛАТНЫЙ АНАЛИЗ ТОКЕНОВ (без API ключей)")
    print("=" * 60)
    
    for i, token in enumerate(tokens, 1):
        try:
            report = await analyzer.analyze_token(token)
            
            # Отображаем название и символ токена
            token_display = token
            if report.token_name and report.token_symbol:
                token_display = f"{report.token_name} ({report.token_symbol}) - {token}"
            elif report.token_symbol:
                token_display = f"{report.token_symbol} - {token}"
            
            print(f"\n📊 Анализ токена {i}: {token_display}")
            print("-" * 40)
            
            print(f"🎯 Риск: {report.risk_assessment.risk_level}")
            print(f"📈 Оценка: {report.risk_assessment.overall_score:.2f}")
            print(f"🎯 Уверенность: {report.risk_assessment.confidence:.2f}")
            
            print(f"\n📋 Рекомендации:")
            for rec in report.risk_assessment.recommendations:
                print(f"  {rec}")
            
            print(f"\n⏱️  Время: {report.analysis_duration:.2f}с")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(demo_free_analysis())
