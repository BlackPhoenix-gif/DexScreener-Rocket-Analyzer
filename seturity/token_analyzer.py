import json
import asyncio
import time
from typing import Dict, List, Any, Optional
from models import (
    TokenSecurityReport, 
    TradingAnalysis, 
    RiskAssessment, 
    ContractAnalysis, 
    OwnershipAnalysis, 
    DistributionAnalysis
)
from contract_analyzer import ContractAnalyzer
from ownership_analyzer import OwnershipAnalyzer
from distribution_analyzer import DistributionAnalyzer
from risk_calculator import RiskScoreCalculator
from config import Config

class TokenAnalyzer:
    def __init__(self):
        self.config = Config()
        self.contract_analyzer = ContractAnalyzer()
        self.ownership_analyzer = OwnershipAnalyzer()
        self.distribution_analyzer = DistributionAnalyzer()
        self.risk_calculator = RiskScoreCalculator()
    
    async def analyze_token(self, token_address: str, chain: str = "ethereum") -> TokenSecurityReport:
        """Основной метод анализа токена"""
        start_time = time.time()
        
        # Создание базового отчета
        report = TokenSecurityReport(
            token_address=token_address,
            chain=chain,
            risk_assessment=RiskAssessment(),
            contract_analysis=ContractAnalysis(),
            ownership=OwnershipAnalysis(),
            distribution=DistributionAnalysis(),
            trading=TradingAnalysis()
        )
        
        try:
            # Параллельный анализ всех компонентов
            tasks = [
                self.contract_analyzer.analyze_contract(token_address),
                self.ownership_analyzer.analyze_ownership(token_address),
                self.distribution_analyzer.analyze_distribution(token_address),
                self.analyze_trading_patterns(token_address)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обработка результатов
            if not isinstance(results[0], Exception):
                report.contract_analysis = results[0]
            
            if not isinstance(results[1], Exception):
                report.ownership = results[1]
            
            if not isinstance(results[2], Exception):
                report.distribution = results[2]
            
            if not isinstance(results[3], Exception):
                report.trading = results[3]
            
            # Расчет общего риска
            report.risk_assessment = self.risk_calculator.calculate_risk_score(report)
            
            # Внешние проверки
            report.external_checks = await self.perform_external_checks(token_address)
            
        except Exception as e:
            print(f"Error analyzing token {token_address}: {e}")
        
        # Расчет времени анализа
        report.analysis_duration = time.time() - start_time
        
        return report
    
    async def analyze_trading_patterns(self, token_address: str) -> TradingAnalysis:
        """Анализ торговых паттернов"""
        analysis = TradingAnalysis()
        
        try:
            # Симуляция данных торговли для демонстрации
            analysis.unique_buyers_24h = 150
            analysis.unique_sellers_24h = 120
            analysis.wash_trading_score = 0.2
            analysis.organic_volume_ratio = 0.8
            analysis.avg_hold_time = 2.5
            analysis.volume_24h = 50000
            analysis.price_change_24h = 5.2
            
        except Exception as e:
            print(f"Error analyzing trading patterns: {e}")
        
        return analysis
    
    async def perform_external_checks(self, token_address: str) -> Dict[str, Any]:
        """Выполнение внешних проверок"""
        checks = {}
        
        try:
            # Проверка через различные API
            checks['honeypot_check'] = await self.check_honeypot_external(token_address)
            checks['rugdoc_check'] = await self.check_rugdoc(token_address)
            checks['tokensniffer_check'] = await self.check_tokensniffer(token_address)
            
        except Exception as e:
            print(f"Error performing external checks: {e}")
        
        return checks
    
    async def check_honeypot_external(self, token_address: str) -> Dict[str, Any]:
        """Проверка через Honeypot.is API"""
        try:
            import aiohttp
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
                            'transfer_tax': data.get('TransferTax', 0)
                        }
        except Exception as e:
            print(f"Error checking honeypot: {e}")
        
        return {'status': 'skipped', 'reason': 'API unavailable'}
    
    async def check_rugdoc(self, token_address: str) -> Dict[str, Any]:
        """Проверка через RugDoc API"""
        try:
            import aiohttp
            url = f"https://rugdoc.io/api/check/{token_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
        except Exception as e:
            print(f"Error checking rugdoc: {e}")
        
        return {'status': 'skipped', 'reason': 'API unavailable'}
    
    async def check_tokensniffer(self, token_address: str) -> Dict[str, Any]:
        """Проверка через TokenSniffer API"""
        try:
            import aiohttp
            url = f"https://tokensniffer.com/api/v2/tokens/{token_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
        except Exception as e:
            print(f"Error checking tokensniffer: {e}")
        
        return {'status': 'skipped', 'reason': 'API unavailable'}
    
    async def analyze_batch(self, token_addresses: List[str], chain: str = "ethereum") -> List[TokenSecurityReport]:
        """Пакетный анализ токенов"""
        reports = []
        
        # Ограничиваем количество одновременных запросов
        semaphore = asyncio.Semaphore(5)
        
        async def analyze_with_semaphore(address: str) -> TokenSecurityReport:
            async with semaphore:
                return await self.analyze_token(address, chain)
        
        tasks = [analyze_with_semaphore(addr) for addr in token_addresses]
        reports = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Фильтруем ошибки
        valid_reports = [r for r in reports if not isinstance(r, Exception)]
        
        return valid_reports
    
    def save_report(self, report: TokenSecurityReport, filename: str):
        """Сохранение отчета в файл"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report.dict(), f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving report: {e}")
    
    def load_report(self, filename: str) -> Optional[TokenSecurityReport]:
        """Загрузка отчета из файла"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return TokenSecurityReport(**data)
        except Exception as e:
            print(f"Error loading report: {e}")
            return None
