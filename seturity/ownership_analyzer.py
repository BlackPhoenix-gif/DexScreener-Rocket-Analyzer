import re
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from web3 import Web3
from models import OwnershipAnalysis, OwnerType
from config import Config

class OwnershipAnalyzer:
    def __init__(self):
        self.config = Config()
        self.web3 = Web3(Web3.HTTPProvider(self.config.ETHEREUM_RPC))
        
        # Известные адреса
        self.known_addresses = {
            'multisig': [
                '0x0000000000000000000000000000000000000000',  # Zero address
            ],
            'timelock': [
                # Известные timelock контракты
            ],
            'dex_pools': [
                '0x7a250d5630b4cf539739df2c5dacb4c659f2488d',  # Uniswap V2 Router
                '0xe592427a0aece92de3edee1f18e0157c05861564',  # Uniswap V3 Router
            ]
        }
    
    async def analyze_ownership(self, token_address: str, abi: Optional[List[Dict[str, Any]]] = None) -> OwnershipAnalysis:
        """Основной метод анализа владельца"""
        analysis = OwnershipAnalysis()
        
        try:
            # Получение владельца
            owner = await self.get_owner(token_address, abi)
            analysis.owner = owner
            
            # Определение типа владельца
            analysis.owner_type = await self.determine_owner_type(owner)
            
            # Проверка ренонса
            analysis.renounced = self.is_renounced(owner)
            
            # Анализ административных функций
            if abi:
                admin_analysis = self.analyze_admin_functions(abi)
                analysis.admin_functions = admin_analysis['admin_functions']
                analysis.risk_score = admin_analysis['risk_score']
            
        except Exception as e:
            print(f"Error analyzing ownership for {token_address}: {e}")
        
        return analysis
    
    async def get_owner(self, token_address: str, abi: Optional[List[Dict[str, Any]]] = None) -> str:
        """Получение адреса владельца"""
        try:
            # Попытка получить владельца через стандартные методы
            owner_methods = ['owner', 'getOwner', 'owner()']
            
            for method in owner_methods:
                try:
                    # Создание контракта
                    contract = self.web3.eth.contract(
                        address=Web3.to_checksum_address(token_address),
                        abi=abi or self.get_minimal_abi()
                    )
                    
                    # Вызов метода
                    if hasattr(contract.functions, method):
                        owner = getattr(contract.functions, method)().call()
                        if owner and owner != '0x0000000000000000000000000000000000000000':
                            return owner
                except Exception:
                    continue
            
            # Если не удалось получить через методы, попробуем через storage
            return await self.get_owner_from_storage(token_address)
            
        except Exception as e:
            print(f"Error getting owner: {e}")
            return '0x0000000000000000000000000000000000000000'
    
    async def get_owner_from_storage(self, token_address: str) -> str:
        """Получение владельца из storage контракта"""
        try:
            # Стандартные слоты для хранения владельца
            owner_slots = [
                '0x8da5cb5b',  # owner() selector
                '0x0000000000000000000000000000000000000000000000000000000000000000',  # slot 0
                '0x0000000000000000000000000000000000000000000000000000000000000001',  # slot 1
            ]
            
            for slot in owner_slots:
                try:
                    storage_value = self.web3.eth.get_storage_at(
                        Web3.to_checksum_address(token_address),
                        slot
                    )
                    
                    # Проверяем, что это валидный адрес
                    if storage_value and storage_value != b'\x00' * 32:
                        # Извлекаем адрес из storage
                        owner = '0x' + storage_value[-20:].hex()
                        if self.web3.is_address(owner):
                            return owner
                except Exception:
                    continue
            
            return '0x0000000000000000000000000000000000000000'
            
        except Exception as e:
            print(f"Error getting owner from storage: {e}")
            return '0x0000000000000000000000000000000000000000'
    
    async def determine_owner_type(self, owner: str) -> OwnerType:
        """Определение типа владельца"""
        if not owner or owner == '0x0000000000000000000000000000000000000000':
            return OwnerType.RENOUNCED
        
        # Проверка на multisig
        if await self.is_multisig(owner):
            return OwnerType.MULTISIG
        
        # Проверка на timelock
        if await self.is_timelock(owner):
            return OwnerType.TIMELOCK
        
        # Проверка на известные адреса
        if owner.lower() in [addr.lower() for addr in self.known_addresses['multisig']]:
            return OwnerType.MULTISIG
        
        if owner.lower() in [addr.lower() for addr in self.known_addresses['timelock']]:
            return OwnerType.TIMELOCK
        
        return OwnerType.EOA
    
    async def is_multisig(self, address: str) -> bool:
        """Проверка, является ли адрес multisig контрактом"""
        try:
            # Проверка кода контракта
            code = self.web3.eth.get_code(Web3.to_checksum_address(address))
            if code == b'':
                return False
            
            # Проверка на известные multisig паттерны
            multisig_patterns = [
                '0x6a761202',  # execute
                '0x8d1fdf2f',  # submitTransaction
                '0x2f54bf6e',  # owner
            ]
            
            for pattern in multisig_patterns:
                if pattern in code.hex():
                    return True
            
            return False
            
        except Exception:
            return False
    
    async def is_timelock(self, address: str) -> bool:
        """Проверка, является ли адрес timelock контрактом"""
        try:
            code = self.web3.eth.get_code(Web3.to_checksum_address(address))
            if code == b'':
                return False
            
            # Проверка на известные timelock паттерны
            timelock_patterns = [
                '0x2a6a4d77',  # execute
                '0x8f283970',  # schedule
                '0x1cff79cd',  # executeBatch
            ]
            
            for pattern in timelock_patterns:
                if pattern in code.hex():
                    return True
            
            return False
            
        except Exception:
            return False
    
    def is_renounced(self, owner: str) -> bool:
        """Проверка, ренонсирован ли контракт"""
        return (
            not owner or 
            owner == '0x0000000000000000000000000000000000000000' or
            owner == '0x000000000000000000000000000000000000dead'
        )
    
    def analyze_admin_functions(self, abi: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Анализ административных функций"""
        admin_functions = []
        risk_score = 0.0
        
        critical_functions = [
            'pause', 'unpause', 'blacklist', 'whitelist',
            'setFee', 'setMaxTx', 'mint', 'burn', 'withdraw',
            'emergency', 'drain', 'sweep'
        ]
        
        for func in abi:
            if func.get('type') == 'function':
                func_name = func.get('name', '').lower()
                
                # Проверка на onlyOwner модификатор
                has_owner_modifier = False
                if 'stateMutability' in func:
                    # Проверяем в inputs и outputs на наличие модификаторов
                    pass
                
                # Проверка на критические функции
                for critical in critical_functions:
                    if critical in func_name:
                        severity = self.config.RISK_WEIGHTS.get(critical, 0.5)
                        risk_score += severity
                        
                        admin_functions.append({
                            'name': func.get('name'),
                            'risk_level': self.get_risk_level(severity),
                            'type': critical,
                            'severity': severity,
                            'has_owner_modifier': has_owner_modifier
                        })
        
        return {
            'admin_functions': admin_functions,
            'risk_score': min(risk_score, 1.0),
            'recommendation': self.get_recommendation(risk_score)
        }
    
    def get_risk_level(self, severity: float) -> str:
        """Получение уровня риска"""
        if severity >= 0.8:
            return 'HIGH'
        elif severity >= 0.5:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def get_recommendation(self, risk_score: float) -> str:
        """Получение рекомендации на основе риска"""
        if risk_score >= 0.8:
            return "Критический риск: Контракт имеет множество административных функций"
        elif risk_score >= 0.5:
            return "Высокий риск: Обнаружены подозрительные административные функции"
        elif risk_score >= 0.2:
            return "Средний риск: Некоторые административные функции требуют внимания"
        else:
            return "Низкий риск: Административные функции в норме"
    
    def get_minimal_abi(self) -> List[Dict[str, Any]]:
        """Минимальный ABI для базовых операций"""
        return [
            {
                "constant": True,
                "inputs": [],
                "name": "owner",
                "outputs": [{"name": "", "type": "address"}],
                "payable": False,
                "stateMutability": "view",
                "type": "function"
            }
        ]
