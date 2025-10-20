import re
import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Any
from web3 import Web3
try:
    from ..models.security_models import (
        ContractAnalysis, OwnershipAnalysis, DistributionAnalysis, 
        TradingAnalysis, RiskAssessment, TokenSecurityReport, 
        ScamPattern, SecurityCheckResult, RiskLevel, OwnerType
    )
except ImportError:
    # Fallback для прямого импорта
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'models'))
    from security_models import (
        ContractAnalysis, OwnershipAnalysis, DistributionAnalysis, 
        TradingAnalysis, RiskAssessment, TokenSecurityReport, 
        ScamPattern, SecurityCheckResult, RiskLevel, OwnerType
    )

class SecurityAnalyzer:
    def __init__(self, config: Dict):
        self.config = config
        self.web3 = None
        self.scam_patterns: List[ScamPattern] = []
        self.load_scam_patterns()
        self.setup_web3()
    
    def setup_web3(self):
        """Настройка Web3 подключения с API ключом"""
        try:
            rpc_url = self.config.get('ethereum_rpc', 'https://eth.llamarpc.com')
            api_key = self.config.get('ethereum_rpc_api_key', '')
            
            # Добавляем API ключ к URL если он есть
            if api_key:
                if '?' in rpc_url:
                    rpc_url += f"&api_key={api_key}"
                else:
                    rpc_url += f"?api_key={api_key}"
            
            self.web3 = Web3(Web3.HTTPProvider(rpc_url))
            
            # Проверяем подключение
            if self.web3.is_connected():
                print(f"✅ Web3 подключен к {rpc_url.split('?')[0]}")
            else:
                print(f"⚠️ Не удалось подключиться к {rpc_url.split('?')[0]}")
                
        except Exception as e:
            print(f"⚠️ Ошибка настройки Web3: {e}")
    
    async def rate_limited_request(self, func, *args, **kwargs):
        """Выполнение запроса с ограничением скорости"""
        try:
            # Получаем настройки ограничения
            delay = self.config.get('rate_limiting', {}).get('delay_between_requests', 0.2)
            
            # Выполняем запрос
            result = await func(*args, **kwargs)
            
            # Ждем указанное время
            await asyncio.sleep(delay)
            
            return result
        except Exception as e:
            print(f"⚠️ Ошибка в rate_limited_request: {e}")
            return None
    
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
            ),
            ScamPattern(
                pattern_id="fake_renounce",
                pattern_type="honeypot",
                source_regex=r'renounceownership.*owner.*msg\.sender',
                severity_score=8,
                false_positive_rate=0.1
            ),
            ScamPattern(
                pattern_id="high_fees",
                pattern_type="rug_pull",
                source_regex=r'(transferfee|burnfee|reflectionfee)\s*=\s*\d{2,}',
                severity_score=7,
                false_positive_rate=0.15
            )
        ]
    
    async def analyze_token_security(self, token_data: Dict) -> TokenSecurityReport:
        """Основной метод анализа безопасности токена"""
        start_time = asyncio.get_event_loop().time()
        
        # Создаем базовый отчет с инициализацией всех обязательных полей
        report = TokenSecurityReport(
            token_address=token_data.get('address', ''),
            token_name=token_data.get('name', ''),
            token_symbol=token_data.get('symbol', ''),
            chain=token_data.get('chainId', 'ethereum'),
            risk_assessment=RiskAssessment(),
            contract_analysis=ContractAnalysis(),
            ownership=OwnershipAnalysis(),
            distribution=DistributionAnalysis(),
            trading=TradingAnalysis()
        )
        
        try:
            # Анализ контракта
            report.contract_analysis = await self.analyze_contract(token_data.get('address', ''))
            
            # Анализ владельца
            report.ownership = await self.analyze_ownership(token_data.get('address', ''))
            
            # Анализ распределения
            report.distribution = await self.analyze_distribution(token_data)
            
            # Анализ торговли
            report.trading = await self.analyze_trading(token_data)
            
            # Внешние проверки
            report.external_checks = await self.perform_external_checks(token_data.get('address', ''), token_data)
            
            # Расчет общего риска
            report.risk_assessment = self.calculate_overall_risk(report)
            
        except Exception as e:
            print(f"⚠️ Ошибка анализа безопасности для {token_data.get('address', '')}: {e}")
        
        report.analysis_duration = asyncio.get_event_loop().time() - start_time
        return report
    
    async def analyze_contract(self, token_address: str) -> ContractAnalysis:
        """Анализ контракта"""
        analysis = ContractAnalysis()
        
        try:
            # Получение данных контракта
            contract_data = await self.get_contract_data(token_address)
            if contract_data:
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
            
            # Расчет security score
            analysis.security_score = self.calculate_contract_security_score(analysis)
            
        except Exception as e:
            print(f"⚠️ Ошибка анализа контракта {token_address}: {e}")
        
        return analysis
    
    async def get_contract_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Получение данных контракта с Etherscan"""
        api_key = self.config.get('etherscan_api_key')
        if not api_key:
            # Возвращаем базовые данные без API ключа
            return {
                'verified': False,
                'source_code': None,
                'bytecode': None,
                'abi': None
            }
        
        url = "https://api.etherscan.io/api"
        params = {
            'module': 'contract',
            'action': 'getsourcecode',
            'address': token_address,
            'apikey': api_key
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
            print(f"⚠️ Ошибка получения данных контракта: {e}")
        
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
                    analysis.security_issues.append(f"Обнаружен паттерн: {pattern.pattern_id}")
        
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
                    'description': f'Найдена подозрительная сигнатура функции: {sig}'
                })
                analysis.security_issues.append(f"Подозрительная сигнатура: {sig}")
    
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
                    'description': 'Обнаружен fake renounceOwnership'
                })
                analysis.security_issues.append("Fake renounceOwnership обнаружен")
        
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
                            'description': f'Высокие комиссии: {match}'
                        })
                        analysis.security_issues.append(f"Высокие комиссии: {match}")
    
    async def check_honeypot(self, token_address: str) -> float:
        """Проверка на honeypot через внешние API"""
        honeypot_probability = 0.0
        
        try:
            # Проверка через Honeypot.is API (работает без ключа)
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
                    else:
                        # Если API недоступен, используем базовую оценку
                        honeypot_probability = 0.3
        except Exception as e:
            print(f"⚠️ Ошибка проверки honeypot: {e}")
            # При ошибке используем базовую оценку
            honeypot_probability = 0.3
        
        return honeypot_probability
    
    async def analyze_ownership(self, token_address: str) -> OwnershipAnalysis:
        """Анализ владельца"""
        analysis = OwnershipAnalysis()
        
        try:
            # Получение владельца
            owner = await self.get_owner(token_address)
            analysis.owner = owner
            
            # Определение типа владельца
            analysis.owner_type = await self.determine_owner_type(owner)
            
            # Проверка ренонса
            analysis.renounced = self.is_renounced(owner)
            
            # Анализ административных функций
            contract_data = await self.get_contract_data(token_address)
            if contract_data and contract_data.get('abi'):
                admin_analysis = self.analyze_admin_functions(contract_data['abi'])
                analysis.admin_functions = admin_analysis['admin_functions']
                analysis.risk_score = admin_analysis['risk_score']
            
            # Расчет security score
            analysis.security_score = self.calculate_ownership_security_score(analysis)
            
        except Exception as e:
            print(f"⚠️ Ошибка анализа владельца для {token_address}: {e}")
        
        return analysis
    
    async def get_owner(self, token_address: str) -> str:
        """Получение адреса владельца"""
        try:
            if not self.web3:
                return '0x0000000000000000000000000000000000000000'
            
            # Попытка получить владельца через стандартные методы
            owner_methods = ['owner', 'getOwner', 'owner()']
            
            for method in owner_methods:
                try:
                    # Создание контракта
                    contract = self.web3.eth.contract(
                        address=Web3.to_checksum_address(token_address),
                        abi=self.get_minimal_abi()
                    )
                    
                    # Вызов метода
                    if hasattr(contract.functions, method):
                        owner = getattr(contract.functions, method)().call()
                        if owner and owner != '0x0000000000000000000000000000000000000000':
                            return owner
                except Exception:
                    continue
            
            return '0x0000000000000000000000000000000000000000'
            
        except Exception as e:
            print(f"⚠️ Ошибка получения владельца: {e}")
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
        
        return OwnerType.EOA
    
    async def is_multisig(self, address: str) -> bool:
        """Проверка, является ли адрес multisig контрактом"""
        try:
            if not self.web3:
                return False
            
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
            if not self.web3:
                return False
            
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
                
                # Проверка на критические функции
                for critical in critical_functions:
                    if critical in func_name:
                        severity = 0.5  # Базовая серьезность
                        risk_score += severity
                        
                        admin_functions.append({
                            'name': func.get('name'),
                            'risk_level': self.get_risk_level(severity),
                            'type': critical,
                            'severity': severity,
                            'has_owner_modifier': True  # Упрощенная проверка
                        })
        
        return {
            'admin_functions': admin_functions,
            'risk_score': min(risk_score, 1.0)
        }
    
    async def analyze_distribution(self, token_data: Dict) -> DistributionAnalysis:
        """Анализ распределения токенов"""
        analysis = DistributionAnalysis()
        
        try:
            # Базовая информация о распределении
            # Здесь можно добавить логику получения данных о держателях
            analysis.total_holders = token_data.get('total_holders', 0)
            analysis.top_10_holders_percent = token_data.get('top_10_percent', 0.0)
            
            # Расчет коэффициента Джини (упрощенный)
            analysis.gini_coefficient = self.calculate_gini_coefficient(token_data)
            
            # Определение концентрации китов
            if analysis.top_10_holders_percent > 80:
                analysis.whale_concentration = 'HIGH'
            elif analysis.top_10_holders_percent > 60:
                analysis.whale_concentration = 'MEDIUM'
            else:
                analysis.whale_concentration = 'LOW'
            
            # Проверка блокировки ликвидности
            analysis.liquidity_locked = token_data.get('liquidity_locked', False)
            analysis.liquidity_lock_period = token_data.get('liquidity_lock_period')
            
            # Расчет security score
            analysis.security_score = self.calculate_distribution_security_score(analysis)
            
        except Exception as e:
            print(f"⚠️ Ошибка анализа распределения: {e}")
        
        return analysis
    
    async def analyze_trading(self, token_data: Dict) -> TradingAnalysis:
        """Анализ торговых паттернов"""
        analysis = TradingAnalysis()
        
        try:
            # Базовая информация о торговле
            analysis.volume_24h = token_data.get('volume_24h', 0.0)
            analysis.price_change_24h = token_data.get('price_change_24h', 0.0)
            
            # Расчет wash trading score (упрощенный)
            analysis.wash_trading_score = self.calculate_wash_trading_score(token_data)
            
            # Расчет organic volume ratio
            analysis.organic_volume_ratio = self.calculate_organic_volume_ratio(token_data)
            
            # Расчет security score
            analysis.security_score = self.calculate_trading_security_score(analysis)
            
        except Exception as e:
            print(f"⚠️ Ошибка анализа торговли: {e}")
        
        return analysis
    
    async def perform_external_checks(self, token_address: str, token_data: Dict = None) -> Dict[str, Any]:
        """Выполнение внешних проверок"""
        checks = {}
        
        try:
            # Проверка через различные API
            checks['honeypot_check'] = await self.check_honeypot(token_address)
            checks['contract_verification'] = await self.check_contract_verification(token_address)
            # DEXScreener сигналы
            try:
                from ..api.dexscreener import DexScreenerAPI
            except ImportError:
                try:
                    from src.api.dexscreener import DexScreenerAPI
                except ImportError:
                    # Создаем заглушку если модуль недоступен
                    class DexScreenerAPI:
                        def __init__(self, test_mode=False):
                            pass
                        def get_token_profile(self, chain, address):
                            return {}
                        def derive_signals_from_pair(self, profile):
                            return {"found": False}

            chain = (token_data or {}).get('chainId', 'ethereum')
            ds = DexScreenerAPI(test_mode=False)
            # пытаемся синхронно получить лучший профиль
            profile = ds.get_token_profile(chain, token_address)
            ds_signals = ds.derive_signals_from_pair(profile) if profile else {"found": False}
            checks['dexscreener'] = ds_signals

            # UniversalTokenChecker (бесплатные подтверждения)
            try:
                from ..api.universal_token_checker import UniversalTokenChecker
            except ImportError:
                try:
                    from src.api.universal_token_checker import UniversalTokenChecker
                except ImportError:
                    # Создаем заглушку если модуль недоступен
                    class UniversalTokenChecker:
                        def __init__(self):
                            pass
                        def check_token(self, address, chain):
                            return {"sources": [], "trust_level": "unknown", "risk_score": 0.5}
            utc = UniversalTokenChecker()
            checks['universal_checks'] = utc.check_token(token_address, chain)
            
        except Exception as e:
            print(f"⚠️ Ошибка внешних проверок: {e}")
        
        return checks
    
    def calculate_overall_risk(self, report: TokenSecurityReport) -> RiskAssessment:
        """Расчет общего риска"""
        weights = {
            'contract_verification': 0.15,
            'ownership_status': 0.20,
            'liquidity_lock': 0.20,
            'holder_distribution': 0.13,
            'trading_patterns': 0.10,
            'code_audit': 0.10,
            'community_reports': 0.05,
            'dexscreener': 0.07
        }
        
        scores = {}
        
        # Contract verification
        scores['contract_verification'] = self.calculate_verification_score(report)
        
        # Ownership status
        scores['ownership_status'] = self.calculate_ownership_score(report)
        
        # Liquidity lock
        scores['liquidity_lock'] = self.calculate_liquidity_score(report)
        
        # Holder distribution
        scores['holder_distribution'] = self.calculate_distribution_score(report)
        
        # Trading patterns
        scores['trading_patterns'] = self.calculate_trading_score(report)

        # DEXScreener (новые сигналы)
        scores['dexscreener'] = self.calculate_dexscreener_score(report)
        
        # Code audit
        scores['code_audit'] = self.calculate_audit_score(report)
        
        # Community reports
        scores['community_reports'] = 0.3  # Базовая оценка
        
        # Комплексный расчет
        final_score = sum(scores[k] * weights[k] for k in scores)
        
        return RiskAssessment(
            overall_score=final_score,
            risk_level=self.get_risk_level(final_score),
            confidence=self.calculate_confidence(scores),
            breakdown=scores,
            recommendations=self.generate_recommendations(scores, report),
            security_checks=self.generate_security_checks(report)
        )

    def calculate_dexscreener_score(self, report: TokenSecurityReport) -> float:
        """Расчет риска по сигналам DEXScreener (0..1, выше = риск)."""
        try:
            ds = (getattr(report, 'external_checks', {}) or {}).get('dexscreener') or {}
            if not ds or not ds.get('found'):
                return 0.6  # неизвестно — умеренный риск

            scores = ds.get('scores', {}) or {}
            metrics = ds.get('metrics', {}) or {}
            warnings = ds.get('warnings', []) or []

            # Базовый «безопасный» скор: агрегируем позитивные показатели
            positive = [
                float(scores.get('dex_trust', 0)),
                float(scores.get('liquidity_score', 0)),
                float(scores.get('volume_score', 0)),
                float(scores.get('stability_score', 0)),
                float(scores.get('age_score', 0)),
                float(scores.get('metadata_score', 0)),
            ]
            safe_score = sum(positive) / max(1, len(positive))
            risk = max(0.0, 1.0 - safe_score)  # чем больше safe, тем ниже риск

            # Наказания за предупреждения/критерии
            liquidity_usd = float(metrics.get('liquidity_usd', 0) or 0)
            vol_liq_ratio = float(metrics.get('vol_liq_ratio', 0) or 0)
            h24 = float(metrics.get('price_change_h24', 0) or 0)

            if liquidity_usd < 25000:
                risk += 0.2
            elif liquidity_usd < 100000:
                risk += 0.1

            if h24 > 300 or h24 < -50:
                risk += 0.1

            if vol_liq_ratio > 2 or (0 < vol_liq_ratio < 0.05):
                risk += 0.1

            risk += min(0.2, 0.03 * len(warnings))

            return min(1.0, max(0.0, risk))
        except Exception:
            return 0.6
    
    def calculate_verification_score(self, report: TokenSecurityReport) -> float:
        """Расчет риска верификации контракта"""
        if not report.contract_analysis.verified:
            return 0.8
        
        audit_results = report.contract_analysis.audit_results
        if audit_results['critical'] > 0:
            return 0.9
        elif audit_results['high'] > 0:
            return 0.7
        elif audit_results['medium'] > 0:
            return 0.4
        else:
            return 0.1
    
    def calculate_ownership_score(self, report: TokenSecurityReport) -> float:
        """Расчет риска владельца"""
        if report.ownership.renounced:
            return 0.0
        elif report.ownership.owner_type == OwnerType.TIMELOCK:
            return 0.2
        elif report.ownership.owner_type == OwnerType.MULTISIG:
            return 0.4
        else:
            return 0.9
    
    def calculate_liquidity_score(self, report: TokenSecurityReport) -> float:
        """Расчет риска ликвидности"""
        if report.distribution.liquidity_locked:
            if report.distribution.liquidity_lock_period and report.distribution.liquidity_lock_period > 365:
                return 0.1
            elif report.distribution.liquidity_lock_period and report.distribution.liquidity_lock_period > 180:
                return 0.3
            else:
                return 0.5
        else:
            return 0.9
    
    def calculate_distribution_score(self, report: TokenSecurityReport) -> float:
        """Расчет риска распределения"""
        gini = report.distribution.gini_coefficient
        top_10_percent = report.distribution.top_10_holders_percent
        
        if gini > 0.8 or top_10_percent > 80:
            return 0.9
        elif gini > 0.6 or top_10_percent > 60:
            return 0.7
        elif gini > 0.4 or top_10_percent > 40:
            return 0.5
        else:
            return 0.2
    
    def calculate_trading_score(self, report: TokenSecurityReport) -> float:
        """Расчет риска торговых паттернов"""
        wash_score = report.trading.wash_trading_score
        organic_ratio = report.trading.organic_volume_ratio
        
        if wash_score > 0.7 or organic_ratio < 0.3:
            return 0.9
        elif wash_score > 0.5 or organic_ratio < 0.5:
            return 0.7
        elif wash_score > 0.3 or organic_ratio < 0.7:
            return 0.5
        else:
            return 0.2
    
    def calculate_audit_score(self, report: TokenSecurityReport) -> float:
        """Расчет риска аудита кода"""
        dangerous_funcs = report.contract_analysis.dangerous_functions
        honeypot_prob = report.contract_analysis.honeypot_probability
        
        if honeypot_prob > 0.8:
            return 0.9
        elif honeypot_prob > 0.5:
            return 0.7
        elif len(dangerous_funcs) > 5:
            return 0.6
        elif len(dangerous_funcs) > 2:
            return 0.4
        else:
            return 0.1
    
    def get_risk_level(self, score: float) -> RiskLevel:
        """Определение уровня риска"""
        if score >= 0.8:
            return RiskLevel.CRITICAL
        elif score >= 0.6:
            return RiskLevel.HIGH
        elif score >= 0.4:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def calculate_confidence(self, scores: Dict[str, float]) -> float:
        """Расчет уверенности в оценке"""
        confidence = 0.5  # Базовая уверенность
        
        for score in scores.values():
            if score >= 0:
                confidence += 0.1
        
        return min(confidence, 1.0)
    
    def generate_recommendations(self, scores: Dict[str, float], report: TokenSecurityReport) -> List[str]:
        """Генерация рекомендаций"""
        recommendations = []
        
        # Контракт
        if scores['contract_verification'] > 0.5:
            if not report.contract_analysis.verified:
                recommendations.append("⚠️ Контракт не верифицирован")
            else:
                recommendations.append("⚠️ Обнаружены проблемы в коде контракта")
        else:
            recommendations.append("✅ Контракт безопасен")
        
        # Владелец
        if scores['ownership_status'] > 0.5:
            if not report.ownership.renounced:
                recommendations.append("⚠️ Контракт не ренонсирован")
            else:
                recommendations.append("⚠️ Подозрительный владелец")
        else:
            recommendations.append("✅ Владелец безопасен")
        
        # Ликвидность
        if scores['liquidity_lock'] > 0.5:
            if not report.distribution.liquidity_locked:
                recommendations.append("⚠️ Ликвидность не заблокирована")
            else:
                recommendations.append("⚠️ Короткий период блокировки ликвидности")
        else:
            recommendations.append("✅ Ликвидность заблокирована")
        
        # Распределение
        if scores['holder_distribution'] > 0.5:
            recommendations.append("⚠️ Высокая концентрация у крупных держателей")
        else:
            recommendations.append("✅ Хорошее распределение токенов")
        
        # Honeypot
        if report.contract_analysis.honeypot_probability > 0.5:
            recommendations.append("🚨 Высокая вероятность honeypot")
        else:
            recommendations.append("✅ Нет признаков honeypot")
        
        return recommendations
    
    def generate_security_checks(self, report: TokenSecurityReport) -> Dict[str, Dict[str, Any]]:
        """Генерация детальных проверок безопасности"""
        checks = {}
        
        # Проверка контракта
        checks['contract_verification'] = {
            'passed': report.contract_analysis.verified,
            'score': report.contract_analysis.security_score,
            'issues': report.contract_analysis.security_issues,
            'dangerous_functions_count': len(report.contract_analysis.dangerous_functions),
            'honeypot_probability': report.contract_analysis.honeypot_probability
        }
        
        # Проверка владельца
        checks['ownership'] = {
            'passed': report.ownership.renounced or report.ownership.owner_type in [OwnerType.MULTISIG, OwnerType.TIMELOCK],
            'score': report.ownership.security_score,
            'issues': report.ownership.security_issues,
            'owner_type': report.ownership.owner_type.name if hasattr(report.ownership.owner_type, 'name') else str(report.ownership.owner_type),
            'renounced': report.ownership.renounced,
            'admin_functions_count': len(report.ownership.admin_functions)
        }
        
        # Проверка распределения
        checks['distribution'] = {
            'passed': report.distribution.liquidity_locked and report.distribution.whale_concentration != 'HIGH',
            'score': report.distribution.security_score,
            'issues': report.distribution.security_issues,
            'liquidity_locked': report.distribution.liquidity_locked,
            'whale_concentration': report.distribution.whale_concentration.name if hasattr(report.distribution.whale_concentration, 'name') else str(report.distribution.whale_concentration)
        }
        
        # Проверка торговли
        checks['trading'] = {
            'passed': report.trading.wash_trading_score < 0.5 and report.trading.organic_volume_ratio > 0.5,
            'score': report.trading.security_score,
            'issues': report.trading.security_issues,
            'wash_trading_score': report.trading.wash_trading_score,
            'organic_volume_ratio': report.trading.organic_volume_ratio
        }

        # Проверка DEXScreener
        ds = (getattr(report, 'external_checks', {}) or {}).get('dexscreener') or {}
        if ds:
            metrics = ds.get('metrics', {}) or {}
            checks['dexscreener'] = {
                'passed': bool(ds.get('found', False)) and float(metrics.get('liquidity_usd', 0) or 0) >= 25000,
                'score': 1.0 - float(self.calculate_dexscreener_score(report)),
                'warnings': ds.get('warnings', []),
                'pair_url': ds.get('pair_url'),
                'liquidity_usd': metrics.get('liquidity_usd'),
                'volume_24h': metrics.get('volume_24h'),
                'price_change_h24': metrics.get('price_change_h24'),
                'age_hours': metrics.get('age_hours'),
                'vol_liq_ratio': metrics.get('vol_liq_ratio'),
                'dex_id': metrics.get('dex_id')
            }
        
        return checks
    
    def calculate_contract_security_score(self, analysis: ContractAnalysis) -> float:
        """Расчет security score для контракта"""
        score = 1.0
        
        # Штраф за неверифицированный контракт
        if not analysis.verified:
            score -= 0.3
        
        # Штраф за опасные функции
        for func in analysis.dangerous_functions:
            score -= func['severity_score'] * 0.1
        
        # Штраф за honeypot
        score -= analysis.honeypot_probability * 0.5
        
        return max(score, 0.0)
    
    def calculate_ownership_security_score(self, analysis: OwnershipAnalysis) -> float:
        """Расчет security score для владельца"""
        score = 1.0
        
        # Бонус за ренонс
        if analysis.renounced:
            score += 0.2
        else:
            score -= 0.3
        
        # Бонус за multisig/timelock
        if analysis.owner_type in [OwnerType.MULTISIG, OwnerType.TIMELOCK]:
            score += 0.1
        
        # Штраф за административные функции
        score -= analysis.risk_score * 0.5
        
        return max(score, 0.0)
    
    def calculate_distribution_security_score(self, analysis: DistributionAnalysis) -> float:
        """Расчет security score для распределения"""
        score = 1.0
        
        # Бонус за блокировку ликвидности
        if analysis.liquidity_locked:
            score += 0.2
            if analysis.liquidity_lock_period and analysis.liquidity_lock_period > 365:
                score += 0.1
        else:
            score -= 0.4
        
        # Штраф за концентрацию китов
        if analysis.whale_concentration == 'HIGH':
            score -= 0.3
        elif analysis.whale_concentration == 'MEDIUM':
            score -= 0.1
        
        return max(score, 0.0)
    
    def calculate_trading_security_score(self, analysis: TradingAnalysis) -> float:
        """Расчет security score для торговли"""
        score = 1.0
        
        # Штраф за wash trading
        score -= analysis.wash_trading_score * 0.4
        
        # Штраф за низкий organic volume
        score -= (1.0 - analysis.organic_volume_ratio) * 0.3
        
        return max(score, 0.0)
    
    def calculate_gini_coefficient(self, token_data: Dict) -> float:
        """Расчет коэффициента Джини (упрощенный)"""
        # Упрощенный расчет на основе top 10 holders
        top_10_percent = token_data.get('top_10_percent', 0.0)
        return min(top_10_percent / 100.0, 1.0)
    
    def calculate_wash_trading_score(self, token_data: Dict) -> float:
        """Расчет wash trading score (упрощенный)"""
        # Упрощенный расчет на основе соотношения покупок/продаж
        buys = token_data.get('buys_24h', 0)
        sells = token_data.get('sells_24h', 0)
        
        if buys + sells == 0:
            return 0.0
        
        ratio = sells / (buys + sells)
        return min(ratio, 1.0)
    
    def calculate_organic_volume_ratio(self, token_data: Dict) -> float:
        """Расчет organic volume ratio (упрощенный)"""
        # Упрощенный расчет
        volume_24h = token_data.get('volume_24h', 0.0)
        market_cap = token_data.get('market_cap', 1.0)
        
        if market_cap == 0:
            return 0.0
        
        ratio = volume_24h / market_cap
        return min(ratio, 1.0)
    
    async def check_contract_verification(self, token_address: str) -> bool:
        """Проверка верификации контракта"""
        contract_data = await self.get_contract_data(token_address)
        return contract_data.get('verified', False) if contract_data else False
    
    
    
    def get_pattern_description(self, pattern_id: str) -> str:
        """Получение описания паттерна"""
        descriptions = {
            'honeypot_gas_manipulation': 'Обнаружена манипуляция с gas price',
            'honeypot_hidden_fees': 'Обнаружены скрытые комиссии',
            'rug_pull_drain': 'Обнаружена функция drain',
            'unlimited_mint': 'Обнаружена неограниченная функция mint',
            'fake_renounce': 'Обнаружен fake renounceOwnership',
            'high_fees': 'Обнаружены высокие комиссии транзакций'
        }
        return descriptions.get(pattern_id, 'Неизвестный паттерн')
    
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
