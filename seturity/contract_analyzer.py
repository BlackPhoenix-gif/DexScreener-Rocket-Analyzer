import re
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from web3 import Web3
from models import ContractAnalysis, ScamPattern
from config import Config

class ContractAnalyzer:
    def __init__(self):
        self.config = Config()
        self.web3 = Web3(Web3.HTTPProvider(self.config.ETHEREUM_RPC))
        self.scam_patterns: List[ScamPattern] = []
        self.load_scam_patterns()
    
    def load_scam_patterns(self):
        """Загрузка паттернов скам-контрактов"""
        self.scam_patterns = [
            ScamPattern(
                pattern_id="honeypot_gas_manipulation",
                pattern_type="honeypot",
                source_regex=r'require\(tx\.gasprice\s*[<>]=?\s*\d+\)',
                severity_score=9,
                false_positive_rate=0.1
            ),
            ScamPattern(
                pattern_id="honeypot_hidden_fees",
                pattern_type="honeypot",
                source_regex=r'_fee\s*=\s*(?:99|100)',
                severity_score=8,
                false_positive_rate=0.15
            ),
            ScamPattern(
                pattern_id="rug_pull_drain",
                pattern_type="rug_pull",
                source_regex=r'withdraw.*balance|emergency.*withdraw',
                severity_score=10,
                false_positive_rate=0.05
            ),
            ScamPattern(
                pattern_id="unlimited_mint",
                pattern_type="rug_pull",
                source_regex=r'function\s+mint.*onlyOwner.*unlimited',
                severity_score=9,
                false_positive_rate=0.1
            )
        ]
    
    async def analyze_contract(self, token_address: str) -> ContractAnalysis:
        """Основной метод анализа контракта"""
        analysis = ContractAnalysis()
        
        try:
            # Получение данных контракта
            contract_data = await self.get_contract_data(token_address)
            if not contract_data:
                return analysis
            
            analysis.verified = contract_data.get('verified', False)
            analysis.source_code = contract_data.get('source_code')
            analysis.bytecode = contract_data.get('bytecode')
            analysis.abi = contract_data.get('abi')
            
            # Анализ исходного кода
            if analysis.source_code:
                await self.analyze_source_code(analysis)
            
            # Анализ байткода
            if analysis.bytecode:
                await self.analyze_bytecode(analysis)
            
            # Проверка на honeypot
            analysis.honeypot_probability = await self.check_honeypot(token_address)
            
        except Exception as e:
            print(f"Error analyzing contract {token_address}: {e}")
        
        return analysis
    
    async def get_contract_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Получение данных контракта с Etherscan"""
        if not self.config.ETHERSCAN_API_KEY:
            return None
        
        url = f"https://api.etherscan.io/api"
        params = {
            'module': 'contract',
            'action': 'getsourcecode',
            'address': token_address,
            'apikey': self.config.ETHERSCAN_API_KEY
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['status'] == '1' and data['result']:
                            result = data['result'][0]
                            return {
                                'verified': result['SourceCode'] != '',
                                'source_code': result['SourceCode'],
                                'bytecode': result['Bytecode'],
                                'abi': result['ABI'] if result['ABI'] != '[]' else None
                            }
        except Exception as e:
            print(f"Error fetching contract data: {e}")
        
        return None
    
    async def analyze_source_code(self, analysis: ContractAnalysis):
        """Анализ исходного кода на опасные паттерны"""
        if not analysis.source_code:
            return
        
        source_code = analysis.source_code.lower()
        
        # Проверка паттернов
        for pattern in self.scam_patterns:
            if pattern.source_regex:
                matches = re.findall(pattern.source_regex, source_code, re.IGNORECASE)
                if matches:
                    analysis.dangerous_functions.append({
                        'pattern_id': pattern.pattern_id,
                        'pattern_type': pattern.pattern_type,
                        'severity_score': pattern.severity_score,
                        'matches': len(matches),
                        'description': self.get_pattern_description(pattern.pattern_id)
                    })
        
        # Проверка специфических паттернов
        self.check_specific_patterns(analysis, source_code)
    
    async def analyze_bytecode(self, analysis: ContractAnalysis):
        """Анализ байткода для неверифицированных контрактов"""
        if not analysis.bytecode:
            return
        
        bytecode = analysis.bytecode.lower()
        
        # Проверка известных сигнатур
        dangerous_signatures = [
            'a9059cbb',  # transfer(address,uint256)
            '23b872dd',  # transferFrom(address,address,uint256)
            '40c10f19',  # mint(address,uint256)
            '9dc29fac',  # burn(address,uint256)
        ]
        
        for sig in dangerous_signatures:
            if sig in bytecode:
                analysis.dangerous_functions.append({
                    'pattern_id': f'bytecode_{sig}',
                    'pattern_type': 'suspicious_function',
                    'severity_score': 5,
                    'matches': 1,
                    'description': f'Found suspicious function signature: {sig}'
                })
    
    def check_specific_patterns(self, analysis: ContractAnalysis, source_code: str):
        """Проверка специфических паттернов"""
        # Проверка на fake renounce
        if 'renounceownership' in source_code and 'owner' in source_code:
            if re.search(r'owner\s*=\s*msg\.sender', source_code):
                analysis.dangerous_functions.append({
                    'pattern_id': 'fake_renounce',
                    'pattern_type': 'honeypot',
                    'severity_score': 8,
                    'matches': 1,
                    'description': 'Fake renounceOwnership detected'
                })
        
        # Проверка на hidden fees
        fee_patterns = [
            r'transferfee\s*=\s*\d+',
            r'burnfee\s*=\s*\d+',
            r'reflectionfee\s*=\s*\d+'
        ]
        
        for pattern in fee_patterns:
            matches = re.findall(pattern, source_code, re.IGNORECASE)
            if matches:
                for match in matches:
                    fee_value = re.search(r'\d+', match)
                    if fee_value and int(fee_value.group()) > 10:
                        analysis.dangerous_functions.append({
                            'pattern_id': 'high_fees',
                            'pattern_type': 'rug_pull',
                            'severity_score': 7,
                            'matches': 1,
                            'description': f'High fees detected: {match}'
                        })
    
    async def check_honeypot(self, token_address: str) -> float:
        """Проверка на honeypot через внешние API"""
        honeypot_probability = 0.0
        
        try:
            # Проверка через Honeypot.is API
            url = "https://api.honeypot.is/v2/IsHoneypot"
            params = {'address': token_address}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('IsHoneypot'):
                            honeypot_probability = 0.9
                        elif data.get('IsHoneypot') is False:
                            honeypot_probability = 0.1
        except Exception as e:
            print(f"Error checking honeypot: {e}")
        
        return honeypot_probability
    
    def get_pattern_description(self, pattern_id: str) -> str:
        """Получение описания паттерна"""
        descriptions = {
            'honeypot_gas_manipulation': 'Gas price manipulation detected',
            'honeypot_hidden_fees': 'Hidden fees detected',
            'rug_pull_drain': 'Drain function detected',
            'unlimited_mint': 'Unlimited mint function detected',
            'fake_renounce': 'Fake renounceOwnership detected',
            'high_fees': 'High transaction fees detected'
        }
        return descriptions.get(pattern_id, 'Unknown pattern')
    
    def calculate_audit_score(self, analysis: ContractAnalysis) -> Dict[str, int]:
        """Расчет аудита на основе найденных проблем"""
        critical = 0
        high = 0
        medium = 0
        low = 0
        
        for func in analysis.dangerous_functions:
            severity = func['severity_score']
            if severity >= 9:
                critical += 1
            elif severity >= 7:
                high += 1
            elif severity >= 5:
                medium += 1
            else:
                low += 1
        
        return {
            'critical': critical,
            'high': high,
            'medium': medium,
            'low': low
        }
