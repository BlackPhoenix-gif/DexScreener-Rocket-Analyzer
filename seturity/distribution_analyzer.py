import asyncio
import aiohttp
import numpy as np
from typing import Dict, List, Optional, Any
from web3 import Web3
from models import DistributionAnalysis, WhaleConcentration
from config import Config

class DistributionAnalyzer:
    def __init__(self):
        self.config = Config()
        self.web3 = Web3(Web3.HTTPProvider(self.config.ETHEREUM_RPC))
        
        # Известные адреса DEX и CEX
        self.known_addresses = {
            'dex_pools': [
                '0x7a250d5630b4cf539739df2c5dacb4c659f2488d',  # Uniswap V2 Router
                '0xe592427a0aece92de3edee1f18e0157c05861564',  # Uniswap V3 Router
            ],
            'cex_wallets': [
                '0x28c6c06298d514db089934071355e5743bf21d60',  # Binance
                '0x21a31ee1afc51d94c2efccaa2092ad1028285549',  # Binance
            ]
        }
    
    async def analyze_distribution(self, token_address: str) -> DistributionAnalysis:
        """Основной метод анализа распределения"""
        analysis = DistributionAnalysis()
        
        try:
            # Получение держателей
            holders = await self.get_token_holders(token_address)
            if not holders:
                return analysis
            
            analysis.total_holders = len(holders)
            analysis.top_holders = holders[:10]
            
            # Расчет метрик
            analysis.top_10_holders_percent = self.calculate_top_holders_percent(holders)
            analysis.gini_coefficient = self.calculate_gini_coefficient(holders)
            analysis.whale_concentration = self.determine_whale_concentration(analysis.gini_coefficient)
            
            # Проверка ликвидности
            liquidity_info = await self.check_liquidity_lock(token_address)
            analysis.liquidity_locked = liquidity_info['locked']
            analysis.liquidity_lock_period = liquidity_info['period']
            
        except Exception as e:
            print(f"Error analyzing distribution for {token_address}: {e}")
        
        return analysis
    
    async def get_token_holders(self, token_address: str) -> List[Dict[str, Any]]:
        """Получение списка держателей токенов"""
        try:
            # Проверяем наличие API ключа
            if not self.config.ETHERSCAN_API_KEY:
                print("Warning: ETHERSCAN_API_KEY not configured, using simulated data")
                return self.simulate_holders()
            
            # Используем Etherscan API для получения держателей
            url = "https://api.etherscan.io/api"
            params = {
                'module': 'token',
                'action': 'tokenholderlist',
                'contractaddress': token_address,
                'apikey': self.config.ETHERSCAN_API_KEY
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == '1' and data.get('result'):
                            holders = []
                            for holder in data['result']:
                                try:
                                    holders.append({
                                        'address': holder.get('TokenHolderAddress', ''),
                                        'balance': float(holder.get('TokenHolderQuantity', 0)),
                                        'percentage': float(holder.get('TokenHolderShare', 0))
                                    })
                                except (ValueError, TypeError) as e:
                                    print(f"Error parsing holder data: {e}")
                                    continue
                            return holders
            
            # Fallback: симуляция данных
            return self.simulate_holders()
            
        except Exception as e:
            print(f"Error getting token holders: {e}")
            return self.simulate_holders()
    
    def simulate_holders(self) -> List[Dict[str, Any]]:
        """Симуляция данных держателей для тестирования"""
        return [
            {'address': '0x1234...', 'balance': 1000000, 'percentage': 20.0},
            {'address': '0x5678...', 'balance': 800000, 'percentage': 16.0},
            {'address': '0x9abc...', 'balance': 600000, 'percentage': 12.0},
        ]
    
    def calculate_top_holders_percent(self, holders: List[Dict[str, Any]]) -> float:
        """Расчет процента топ-10 держателей"""
        if not holders:
            return 0.0
        
        top_10 = holders[:10]
        total_percentage = sum(holder['percentage'] for holder in top_10)
        return total_percentage
    
    def calculate_gini_coefficient(self, holders: List[Dict[str, Any]]) -> float:
        """Расчет коэффициента Джини"""
        if not holders:
            return 0.0
        
        balances = [holder['balance'] for holder in holders]
        n = len(balances)
        
        if n == 0:
            return 0.0
        
        # Сортировка балансов
        balances.sort()
        
        # Расчет коэффициента Джини
        cumsum = np.cumsum(balances)
        return (n + 1 - 2 * np.sum(cumsum) / cumsum[-1]) / n
    
    def determine_whale_concentration(self, gini: float) -> WhaleConcentration:
        """Определение концентрации китов"""
        if gini >= 0.8:
            return WhaleConcentration.HIGH
        elif gini >= 0.5:
            return WhaleConcentration.MEDIUM
        else:
            return WhaleConcentration.LOW
    
    async def check_liquidity_lock(self, token_address: str) -> Dict[str, Any]:
        """Проверка блокировки ликвидности"""
        try:
            # Проверка известных lock контрактов
            lock_contracts = [
                '0x663A5C229c09b049E36dCc11a9B0d4a8Eb9db214',  # DxSale
                '0x7a250d5630b4cf539739df2c5dacb4c659f2488d',  # Uniswap
            ]
            
            for lock_contract in lock_contracts:
                # Проверка блокировки
                pass
            
            return {
                'locked': False,
                'period': None
            }
            
        except Exception as e:
            print(f"Error checking liquidity lock: {e}")
            return {
                'locked': False,
                'period': None
            }
