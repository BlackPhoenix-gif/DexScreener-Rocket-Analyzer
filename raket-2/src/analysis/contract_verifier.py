import asyncio
import aiohttp
import time
import json
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
import logging
from tqdm.asyncio import tqdm
from ..config import GOPLUS_BATCH_SIZE, GOPLUS_CONCURRENCY, GOPLUS_RATE_LIMIT, ETHERSCAN_RATE_LIMIT, BSCSCAN_RATE_LIMIT, RPC_CONCURRENCY

logger = logging.getLogger(__name__)

@dataclass
class ContractVerificationResult:
    """Результат верификации контракта"""
    is_verified: bool = False
    is_honeypot: bool = False
    buy_tax: str = "0"
    sell_tax: str = "0"
    owner_address: str = ""
    can_take_back_ownership: bool = False
    is_open_source: bool = False
    has_mint_function: bool = False
    has_blacklist: bool = False
    is_proxy: bool = False
    verification_source: str = ""
    error_message: str = ""
    raw_data: Dict = None

class ContractVerifier:
    """
    Универсальный верификатор контрактов через публичные API
    Поддерживает GoPlus Security, публичные RPC и Etherscan/BscScan
    """
    
    def __init__(self):
        self.session = None
        self.cache = {}
        self.cache_ttl = 3600  # 1 час
        
        # Семафоры для ограничения параллелизма
        self.goplus_semaphore = asyncio.Semaphore(GOPLUS_CONCURRENCY)
        self.etherscan_semaphore = asyncio.Semaphore(1)  # Очень ограниченно
        self.bscscan_semaphore = asyncio.Semaphore(1)    # Очень ограниченно
        self.rpc_semaphore = asyncio.Semaphore(RPC_CONCURRENCY)
        
        # Rate limiting
        self.request_delays = {
            'goplus': 60.0 / GOPLUS_RATE_LIMIT,      # Запросов в минуту
            'etherscan': 60.0 / ETHERSCAN_RATE_LIMIT, # Запросов в минуту
            'bscscan': 60.0 / BSCSCAN_RATE_LIMIT,     # Запросов в минуту
            'rpc': 0.1                               # 10 запросов/секунду
        }
        self.last_request_time = {}
        self.request_counters = {
            'goplus': 0,
            'etherscan': 0,
            'bscscan': 0,
            'rpc': 0
        }
        self.counter_reset_time = time.time()
        
        # Chain ID mapping для GoPlus
        self.chain_id_mapping = {
            'ethereum': 1,
            'bsc': 56,
            'polygon': 137,
            'arbitrum': 42161,
            'avalanche': 43114,
            'fantom': 250,
            'optimism': 10,
            'base': 8453,
            'linea': 59144,
            'cronos': 25,
            'solana': None,  # Solana использует отдельный API endpoint
            # Специальные сети, не поддерживаемые GoPlus
            'ton': None,
            'sonic': None
        }
        
        logger.info("[CONTRACT_VERIFIER] Инициализация верификатора контрактов")
    
    async def __aenter__(self):
        """Асинхронный контекст менеджер"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'Raket-Scanner/1.0'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()
    
    async def verify_contracts_batch(self, contracts: List[tuple], show_progress: bool = True) -> Dict[str, ContractVerificationResult]:
        """
        Batch верификация контрактов для максимальной производительности с прогресс-баром
        """
        if not contracts:
            return {}
        
        logger.info(f"[CONTRACT_VERIFIER] Начало batch верификации {len(contracts)} контрактов")
        
        # Группируем контракты по сети для batch-запросов
        contracts_by_chain = {}
        for contract_address, chain in contracts:
            if chain not in contracts_by_chain:
                contracts_by_chain[chain] = []
            contracts_by_chain[chain].append(contract_address)
        
        results = {}
        total_batches = 0
        
        # Подсчитываем общее количество batch'ей
        for chain, addresses in contracts_by_chain.items():
            batches_count = len([addresses[i:i + GOPLUS_BATCH_SIZE] for i in range(0, len(addresses), GOPLUS_BATCH_SIZE)])
            total_batches += batches_count
        
        # Создаем прогресс-бар
        progress_bar = None
        if show_progress:
            progress_bar = tqdm(
                total=total_batches,
                desc="🔍 Верификация контрактов",
                unit="batch",
                ncols=100,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
            )
        
        try:
            # Обрабатываем каждую сеть отдельно
            for chain, addresses in contracts_by_chain.items():
                logger.info(f"[CONTRACT_VERIFIER] Обработка {len(addresses)} контрактов в сети {chain}")
                
                # Разбиваем на batch'и для GoPlus
                batches = [addresses[i:i + GOPLUS_BATCH_SIZE] for i in range(0, len(addresses), GOPLUS_BATCH_SIZE)]
                
                # Создаем задачи для batch-запросов с прогресс-баром
                tasks = []
                for batch in batches:
                    task = self._process_batch_with_progress(batch, chain, progress_bar)
                    tasks.append(task)
                
                # Выполняем batch-запросы параллельно
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Обрабатываем результаты
                for batch_result in batch_results:
                    if isinstance(batch_result, dict):
                        results.update(batch_result)
        finally:
            if progress_bar:
                progress_bar.close()
        
        # Выводим статистику
        verified_count = sum(1 for result in results.values() if result.is_verified)
        honeypot_count = sum(1 for result in results.values() if result.is_honeypot)
        
        stats = {
            'total_contracts_checked': len(results),
            'verified_contracts': verified_count,
            'honeypot_contracts': honeypot_count,
            'verification_rate': (verified_count / len(results) * 100) if results else 0,
            'cache_size': len(self.cache)
        }
        
        logger.info(f"[CONTRACT_VERIFIER] Batch верификация завершена. Статистика: {stats}")
        return results
    
    async def _process_batch_with_progress(self, addresses: List[str], chain: str, progress_bar) -> Dict[str, ContractVerificationResult]:
        """Обработка batch'а с обновлением прогресс-бара"""
        try:
            result = await self._process_batch_goplus(addresses, chain)
            if progress_bar:
                progress_bar.update(1)
                # Обновляем описание с информацией о текущем batch'е
                verified_count = sum(1 for r in result.values() if r.is_verified)
                honeypot_count = sum(1 for r in result.values() if r.is_honeypot)
                progress_bar.set_postfix({
                    'сеть': chain[:6],
                    'верифицировано': verified_count,
                    'honeypot': honeypot_count
                })
            return result
        except Exception as e:
            if progress_bar:
                progress_bar.update(1)
                progress_bar.set_postfix({'ошибка': str(e)[:20]})
            logger.error(f"[CONTRACT_VERIFIER] Ошибка в batch {chain}: {str(e)}")
            return {}
    
    async def _process_batch_goplus(self, addresses: List[str], chain: str) -> Dict[str, ContractVerificationResult]:
        """Обработка batch'а адресов через GoPlus API"""
        async with self.goplus_semaphore:
            await self._respect_rate_limit('goplus')
            
            chain_id = self.chain_id_mapping.get(chain)
            if chain_id is None:
                logger.debug(f"[CONTRACT_VERIFIER] GoPlus не поддерживает сеть {chain}, используем fallback")
                return await self._process_batch_fallback(addresses, chain)
            
            url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}"
            params = {'contract_addresses': ','.join(addresses)}
            
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        results = {}
                        # Проверяем успешность ответа GoPlus
                        if data.get('code') == 1 and 'result' in data and data['result']:
                            goplus_result = data['result']
                            
                            for address in addresses:
                                if address.lower() in goplus_result:
                                    token_info = goplus_result[address.lower()]
                                    
                                    result = ContractVerificationResult()
                                    result.is_honeypot = token_info.get('is_honeypot', '0') == '1'
                                    result.is_verified = token_info.get('is_open_source', '0') == '1'
                                    result.buy_tax = token_info.get('buy_tax', '0') or '0'
                                    result.sell_tax = token_info.get('sell_tax', '0') or '0'
                                    result.owner_address = token_info.get('creator_address', '') or token_info.get('owner_address', '')
                                    result.can_take_back_ownership = token_info.get('can_take_back_ownership', '0') == '1'
                                    result.has_mint_function = token_info.get('is_mintable', '0') == '1'
                                    result.has_blacklist = token_info.get('is_blacklisted', '0') == '1'
                                    result.is_proxy = token_info.get('is_proxy', '0') == '1'
                                    result.verification_source = "GoPlus Security"
                                    result.raw_data = token_info
                                    
                                    results[address] = result
                                    
                                    # Кешируем результат
                                    cache_key = f"{chain}_{address.lower()}"
                                    self.cache[cache_key] = (time.time(), result)
                                    
                                    logger.info(f"[CONTRACT_VERIFIER] ✅ GoPlus: {address[:10]}... honeypot={result.is_honeypot}, verified={result.is_verified}, tax={result.buy_tax}/{result.sell_tax}, owner={result.owner_address[:10] if result.owner_address else 'None'}...")
                                else:
                                    # Создаем пустой результат для не найденных токенов
                                    result = ContractVerificationResult()
                                    result.verification_source = "GoPlus Security (не найден)"
                                    results[address] = result
                                    logger.info(f"[CONTRACT_VERIFIER] ⚠️  GoPlus: токен {address[:10]}... не найден в базе данных")
                        else:
                            logger.warning(f"[CONTRACT_VERIFIER] GoPlus неуспешный ответ: code={data.get('code')}, message={data.get('message')}")
                            # Создаем пустые результаты для всех токенов
                            for address in addresses:
                                result = ContractVerificationResult()
                                result.verification_source = "GoPlus Security (ошибка API)"
                                results[address] = result
                        
                        logger.info(f"[CONTRACT_VERIFIER] GoPlus batch: обработано {len(results)} из {len(addresses)} токенов")
                        return results
                    else:
                        logger.warning(f"[CONTRACT_VERIFIER] GoPlus API ошибка: {response.status}")
                        return {}
                        
            except Exception as e:
                logger.error(f"[CONTRACT_VERIFIER] GoPlus batch API исключение: {str(e)}")
                return {}
    
    async def _process_batch_fallback(self, addresses: List[str], chain: str) -> Dict[str, ContractVerificationResult]:
        """Fallback обработка для неподдерживаемых GoPlus сетей"""
        results = {}
        
        for address in addresses:
            result = ContractVerificationResult()
            
            # Специальная логика для разных сетей
            if chain == 'solana':
                # Для Solana используем базовую проверку существования токена
                solana_result = await self._check_solana_token_basic(address)
                if solana_result:
                    result = solana_result
                    result.verification_source = "Solana Token Registry"
                else:
                    result.verification_source = "Solana (не найден)"
            elif chain == 'ton':
                # Для TON создаем базовый результат
                result.is_verified = True  # Считаем все TON токены верифицированными
                result.verification_source = "TON Network"
            elif chain == 'sonic':
                # Для Sonic создаем базовый результат
                result.is_verified = True  # Считаем все Sonic токены верифицированными
                result.verification_source = "Sonic Network"
            else:
                # Для остальных сетей пытаемся использовать публичные API
                fallback_result = await self._check_fallback_sources(address, chain)
                if fallback_result:
                    result = fallback_result
                else:
                    result.verification_source = f"{chain} (не поддерживается)"
            
            results[address] = result
            
            # Кешируем результат
            cache_key = f"{chain}_{address.lower()}"
            self.cache[cache_key] = (time.time(), result)
        
        logger.info(f"[CONTRACT_VERIFIER] Fallback обработка {chain}: {len(results)} токенов")
        return results
    
    async def _check_solana_goplus(self, token_address: str) -> Optional[ContractVerificationResult]:
        """Проверка Solana токена через GoPlus Solana API"""
        try:
            url = "https://api.gopluslabs.io/api/v1/solana_token_security"
            params = {'contract_addresses': token_address}
            
            await self._respect_rate_limit('goplus')
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('code') == 1 and 'result' in data and data['result']:
                        if token_address in data['result'] and data['result'][token_address]:
                            token_info = data['result'][token_address]
                            
                            result = ContractVerificationResult()
                            result.is_honeypot = token_info.get('is_honeypot', '0') == '1'
                            result.is_verified = True  # Solana токены считаем верифицированными
                            result.buy_tax = token_info.get('buy_tax', '0')
                            result.sell_tax = token_info.get('sell_tax', '0')
                            result.owner_address = token_info.get('creator_address', '')
                            result.has_mint_function = token_info.get('is_mintable', '0') == '1'
                            result.has_blacklist = token_info.get('is_blacklisted', '0') == '1'
                            result.is_proxy = False  # Solana не использует proxy контракты
                            result.verification_source = "GoPlus Solana Security"
                            result.raw_data = token_info
                            
                            logger.info(f"[CONTRACT_VERIFIER] GoPlus Solana {token_address}: honeypot={result.is_honeypot}, "
                                       f"tax={result.buy_tax}/{result.sell_tax}, mint={result.has_mint_function}")
                            
                            return result
                    else:
                        logger.debug(f"[CONTRACT_VERIFIER] GoPlus Solana: токен {token_address} не найден")
                        return None
                else:
                    logger.warning(f"[CONTRACT_VERIFIER] GoPlus Solana API ошибка: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"[CONTRACT_VERIFIER] Ошибка при запросе к GoPlus Solana: {str(e)}")
            return None

    async def _check_solana_token_basic(self, token_address: str) -> Optional[ContractVerificationResult]:
        """Базовая проверка Solana токена через публичные API"""
        await self._respect_rate_limit('rpc')
        
        # Пробуем Jupiter API для получения информации о токене
        try:
            url = f"https://token.jup.ag/strict"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Ищем токен в списке
                    for token in data:
                        if token.get('address') == token_address:
                            result = ContractVerificationResult()
                            result.is_verified = True
                            result.verification_source = "Jupiter Token List"
                            result.raw_data = token
                            
                            logger.info(f"[CONTRACT_VERIFIER] Solana токен найден в Jupiter: {token.get('symbol', 'Unknown')}")
                            return result
        except Exception as e:
            logger.debug(f"[CONTRACT_VERIFIER] Jupiter API ошибка: {str(e)}")
        
        # Fallback: проверяем через Solana RPC
        return await self._check_solana_contract(token_address)
    
    async def verify_contract_multi_source(self, contract_address: str, chain: str) -> ContractVerificationResult:
        """
        Верификация контракта через несколько источников (для обратной совместимости)
        """
        # Проверяем кеш
        cache_key = f"{chain}_{contract_address.lower()}"
        if cache_key in self.cache:
            cached_time, cached_result = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug(f"[CONTRACT_VERIFIER] Используем кешированный результат для {contract_address}")
                return cached_result
        
        result = ContractVerificationResult()
        
        try:
            # 1. GoPlus Security API (основной источник)
            goplus_result = await self._check_goplus_security(contract_address, chain)
            if goplus_result:
                result = goplus_result
                result.verification_source = "GoPlus Security"
            
            # 2. Fallback проверки для специфических сетей
            if not result.is_verified or chain in ['ethereum', 'bsc']:
                fallback_result = await self._check_fallback_sources(contract_address, chain)
                if fallback_result:
                    result.is_verified = result.is_verified or fallback_result.is_verified
                    if not result.verification_source:
                        result.verification_source = fallback_result.verification_source
            
            # 3. Специальная проверка для Solana
            if chain == 'solana':
                solana_result = await self._check_solana_contract(contract_address)
                if solana_result:
                    result.is_verified = solana_result.is_verified
                    result.verification_source = "Solana RPC"
            
        except Exception as e:
            error_msg = f"Ошибка верификации {contract_address}: {str(e)}"
            logger.error(f"[CONTRACT_VERIFIER] {error_msg}")
            result.error_message = error_msg
        
        # Кешируем результат
        self.cache[cache_key] = (time.time(), result)
        
        return result
    
    async def _check_goplus_security(self, contract_address: str, chain: str) -> Optional[ContractVerificationResult]:
        """Проверка через GoPlus Security API"""
        chain_id = self.chain_id_mapping.get(chain)
        if chain_id is None:
            logger.debug(f"[CONTRACT_VERIFIER] GoPlus не поддерживает сеть {chain}")
            return None
        
        await self._respect_rate_limit('goplus')
        
        url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}"
        params = {'contract_addresses': contract_address}
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('code') == 1 and 'result' in data and data['result'] and contract_address.lower() in data['result']:
                        token_info = data['result'][contract_address.lower()]
                        
                        result = ContractVerificationResult()
                        result.is_honeypot = token_info.get('is_honeypot', '0') == '1'
                        result.is_verified = token_info.get('is_open_source', '0') == '1'
                        result.buy_tax = token_info.get('buy_tax', '0') or '0'
                        result.sell_tax = token_info.get('sell_tax', '0') or '0'
                        result.owner_address = token_info.get('creator_address', '') or token_info.get('owner_address', '')
                        result.can_take_back_ownership = token_info.get('can_take_back_ownership', '0') == '1'
                        result.has_mint_function = token_info.get('is_mintable', '0') == '1'
                        result.has_blacklist = token_info.get('is_blacklisted', '0') == '1'
                        result.is_proxy = token_info.get('is_proxy', '0') == '1'
                        result.raw_data = token_info
                        
                        logger.info(f"[CONTRACT_VERIFIER] GoPlus: honeypot={result.is_honeypot}, "
                                   f"tax={result.buy_tax}/{result.sell_tax}, owner={result.owner_address[:10]}...")
                        
                        return result
                    else:
                        logger.warning(f"[CONTRACT_VERIFIER] GoPlus: токен {contract_address} не найден или API ошибка")
                else:
                    logger.warning(f"[CONTRACT_VERIFIER] GoPlus API ошибка: {response.status}")
                    
        except Exception as e:
            logger.error(f"[CONTRACT_VERIFIER] GoPlus API исключение: {str(e)}")
        
        return None
    
    async def _check_fallback_sources(self, contract_address: str, chain: str) -> Optional[ContractVerificationResult]:
        """Fallback проверки для Ethereum и BSC"""
        if chain == 'ethereum':
            return await self._check_etherscan_public(contract_address)
        elif chain == 'bsc':
            return await self._check_bscscan_public(contract_address)
        
        return None
    
    async def _check_etherscan_public(self, contract_address: str) -> Optional[ContractVerificationResult]:
        """Проверка через публичный Etherscan API"""
        await self._respect_rate_limit('etherscan')
        
        url = "https://api.etherscan.io/api"
        params = {
            'module': 'contract',
            'action': 'getsourcecode',
            'address': contract_address
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('status') == '1' and data.get('result'):
                        contract_info = data['result'][0]
                        
                        result = ContractVerificationResult()
                        result.is_verified = contract_info.get('SourceCode', '').strip() != ''
                        result.owner_address = contract_info.get('ContractCreator', '')
                        result.raw_data = contract_info
                        
                        logger.info(f"[CONTRACT_VERIFIER] Etherscan: верифицирован={result.is_verified}")
                        return result
                        
        except Exception as e:
            logger.error(f"[CONTRACT_VERIFIER] Etherscan API исключение: {str(e)}")
        
        return None
    
    async def _check_bscscan_public(self, contract_address: str) -> Optional[ContractVerificationResult]:
        """Проверка через публичный BscScan API"""
        await self._respect_rate_limit('bscscan')
        
        url = "https://api.bscscan.com/api"
        params = {
            'module': 'contract',
            'action': 'getsourcecode',
            'address': contract_address
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('status') == '1' and data.get('result'):
                        contract_info = data['result'][0]
                        
                        result = ContractVerificationResult()
                        result.is_verified = contract_info.get('SourceCode', '').strip() != ''
                        result.owner_address = contract_info.get('ContractCreator', '')
                        result.raw_data = contract_info
                        
                        logger.info(f"[CONTRACT_VERIFIER] BscScan: верифицирован={result.is_verified}")
                        return result
                        
        except Exception as e:
            logger.error(f"[CONTRACT_VERIFIER] BscScan API исключение: {str(e)}")
        
        return None
    
    async def _check_solana_contract(self, contract_address: str) -> Optional[ContractVerificationResult]:
        """Специальная проверка для Solana контрактов"""
        await self._respect_rate_limit('rpc')
        
        # Пробуем несколько RPC endpoints
        rpc_endpoints = [
            "https://api.mainnet-beta.solana.com",
            "https://solana-api.projectserum.com",
            "https://rpc.ankr.com/solana"
        ]
        
        for endpoint in rpc_endpoints:
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getAccountInfo",
                    "params": [contract_address, {"encoding": "base64"}]
                }
                
                async with self.session.post(endpoint, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if 'result' in data and data['result']:
                            result = ContractVerificationResult()
                            result.is_verified = True  # Если аккаунт существует, считаем верифицированным
                            result.raw_data = data
                            
                            logger.info(f"[CONTRACT_VERIFIER] Solana RPC ({endpoint}): аккаунт найден")
                            return result
                            
            except Exception as e:
                logger.warning(f"[CONTRACT_VERIFIER] Solana RPC {endpoint} ошибка: {str(e)}")
                continue
        
        return None
    
    async def _respect_rate_limit(self, api_type: str):
        """Соблюдение лимитов запросов с улучшенным контролем"""
        current_time = time.time()
        
        # Сброс счетчиков каждую минуту
        if current_time - self.counter_reset_time > 60:
            self.request_counters = {k: 0 for k in self.request_counters}
            self.counter_reset_time = current_time
        
        # Проверяем лимиты
        if api_type == 'goplus' and self.request_counters[api_type] >= GOPLUS_RATE_LIMIT:
            wait_time = 60 - (current_time - self.counter_reset_time)
            if wait_time > 0:
                logger.debug(f"[CONTRACT_VERIFIER] Rate limit для {api_type}, ожидание {wait_time:.1f}с")
                await asyncio.sleep(wait_time)
                self.request_counters[api_type] = 0
                self.counter_reset_time = time.time()
        
        # Обычная задержка между запросами
        if api_type in self.last_request_time:
            delay_needed = self.request_delays[api_type]
            time_since_last = current_time - self.last_request_time[api_type]
            
            if time_since_last < delay_needed:
                sleep_time = delay_needed - time_since_last
                logger.debug(f"[CONTRACT_VERIFIER] Ожидание {sleep_time:.2f}с для {api_type}")
                await asyncio.sleep(sleep_time)
        
        self.last_request_time[api_type] = current_time
        self.request_counters[api_type] += 1
    
    def get_verification_stats(self) -> Dict[str, Any]:
        """Получение статистики верификации"""
        total_requests = len(self.cache)
        verified_count = sum(1 for _, (_, result) in self.cache.items() if result.is_verified)
        honeypot_count = sum(1 for _, (_, result) in self.cache.items() if result.is_honeypot)
        
        return {
            'total_contracts_checked': total_requests,
            'verified_contracts': verified_count,
            'honeypot_contracts': honeypot_count,
            'verification_rate': (verified_count / total_requests * 100) if total_requests > 0 else 0,
            'cache_size': len(self.cache)
        }
    
    def clear_cache(self):
        """Очистка кеша"""
        self.cache.clear()
        logger.info("[CONTRACT_VERIFIER] Кеш очищен")
