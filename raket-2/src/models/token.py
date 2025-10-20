from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

@dataclass
class TokenPair:
    """Класс для хранения информации о торговой паре токена"""
    pair_address: str
    base_token: 'Token'
    quote_token: 'Token'
    price_usd: float
    price_native: float
    volume_24h: float
    liquidity_usd: float
    liquidity_native: float
    price_change_1h: float
    price_change_24h: float
    created_at: datetime
    dex_id: str
    chain_id: str
    
    @classmethod
    def from_dexscreener(cls, data: Dict[str, Any]) -> 'TokenPair':
        """Создает объект TokenPair из данных DEXScreener"""
        base_token = Token.from_dexscreener(data.get('baseToken', {}))
        quote_token = Token.from_dexscreener(data.get('quoteToken', {}))
        
        # Получаем данные о ценах и объемах из вложенных объектов
        price_data = data.get('priceUsd', 0)
        volume_data = data.get('volume', {}).get('h24', 0)
        liquidity_data = data.get('liquidity', {})
        price_change_data = data.get('priceChange', {})
        
        return cls(
            pair_address=data.get('pairAddress', ''),
            base_token=base_token,
            quote_token=quote_token,
            price_usd=float(price_data),
            price_native=float(data.get('priceNative', 0)),
            volume_24h=float(volume_data),
            liquidity_usd=float(liquidity_data.get('usd', 0)),
            liquidity_native=float(liquidity_data.get('native', 0)),
            price_change_1h=float(price_change_data.get('h1', 0)),
            price_change_24h=float(price_change_data.get('h24', 0)),
            created_at=datetime.fromtimestamp(int(data.get('pairCreatedAt', 0)) / 1000),
            dex_id=data.get('dexId', ''),
            chain_id=data.get('chainId', '')
        )
    
    @property
    def dex_link(self) -> str:
        """Возвращает ссылку на DEX для просмотра графика и данных"""
        if self.dex_id == 'pancakeswap':
            return f'https://pancakeswap.finance/swap?outputCurrency={self.base_token.address}'
        elif self.dex_id == 'uniswap':
            return f'https://app.uniswap.org/#/swap?outputCurrency={self.pair_address}'
        else:
            return f'https://dexscreener.com/{self.chain_id}/{self.pair_address}'

@dataclass
class Token:
    """Класс для хранения информации о токене"""
    address: str
    name: str
    symbol: str
    chain_id: str
    pairs: List[TokenPair] = field(default_factory=list)
    risk_level: str = 'unknown'
    risks: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    contract_info: dict = field(default_factory=dict)
    
    def __init__(self, address: str, name: str, symbol: str, chain_id: str = None, pairs: List[TokenPair] = None):
        self.address = address
        self.name = name
        self.symbol = symbol
        self.chain_id = chain_id
        self.pairs = pairs or []
        self.risk_level = "Низкий"
        self.risks = []
        self.warnings = []
        self.contract_info = {}
    
    @classmethod
    def from_dexscreener(cls, data: dict) -> 'Token':
        """Создает объект Token из данных DEXScreener"""
        return cls(
            address=data.get('address', ''),
            name=data.get('name', ''),
            symbol=data.get('symbol', ''),
            chain_id=data.get('chainId', '')
        )
    
    @property
    def max_pair_by_liquidity(self) -> Optional[TokenPair]:
        """Возвращает пару с максимальной ликвидностью"""
        if not self.pairs:
            return None
        return max(self.pairs, key=lambda p: p.liquidity_usd or 0)
    
    @property
    def created_at(self) -> Optional[datetime]:
        """Возвращает время создания токена"""
        if not self.pairs:
            return None
        return min(p.created_at for p in self.pairs if p.created_at)
    
    @property
    def age_hours(self) -> float:
        """Возвращает возраст токена в часах"""
        if not self.created_at:
            return float('inf')
        return (datetime.now() - self.created_at).total_seconds() / 3600
    
    @property
    def max_price_change_1h(self) -> float:
        """Возвращает максимальное изменение цены за 1 час"""
        if not self.pairs:
            return 0
        return max(pair.price_change_1h for pair in self.pairs)
    
    @property
    def max_price_change_24h(self) -> float:
        """Возвращает максимальное изменение цены за 24 часа"""
        if not self.pairs:
            return 0
        return max(pair.price_change_24h for pair in self.pairs)
    
    @property
    def total_liquidity_usd(self) -> float:
        """Возвращает общую ликвидность в USD"""
        return sum(pair.liquidity_usd for pair in self.pairs)
    
    @property
    def total_volume_24h(self) -> float:
        """Возвращает общий объем торгов за 24 часа в USD"""
        return sum(pair.volume_24h for pair in self.pairs)
    
    @property
    def best_dex_link(self) -> str:
        """Возвращает ссылку на лучший DEX для просмотра графика и данных"""
        if not self.pairs:
            return f'https://dexscreener.com/{self.chain_id}/{self.address}'
        
        # Выбираем пару с наибольшей ликвидностью
        best_pair = max(self.pairs, key=lambda x: x.liquidity_usd)
        return best_pair.dex_link
    
    @property
    def chart_links(self) -> Dict[str, str]:
        """Возвращает словарь с ссылками на различные графики и данные"""
        links = {
            'DEXScreener': f'https://dexscreener.com/{self.chain_id}/{self.pair_address}'
        }
        
        # Добавляем Poocoin для BSC токенов
        if self.chain_id == 'bsc':
            links['Poocoin'] = f'https://poocoin.app/tokens/{self.base_token.address}'
        
        # Добавляем ссылку на DEX
        if self.dex_id == 'pancakeswap':
            links['PancakeSwap'] = f'https://pancakeswap.finance/swap?outputCurrency={self.base_token.address}'
        elif self.dex_id == 'uniswap':
            links['Uniswap'] = f'https://app.uniswap.org/#/swap?outputCurrency={self.pair_address}'
        
        return links
    
    def update_risk_info(self, risk_level: str, risks: List[str], warnings: List[str], contract_info: dict):
        """Обновляет информацию о рисках токена"""
        self.risk_level = risk_level
        self.risks = risks
        self.warnings = warnings
        self.contract_info = contract_info
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует токен в словарь для сериализации
        
        Returns:
            Dict[str, Any]: Токен в виде словаря
        """
        return {
            'address': self.address,
            'name': self.name,
            'symbol': self.symbol,
            'age_hours': self.age_hours,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'chain_id': self.chain_id,
            'risk_level': self.risk_level,
            'risks': self.risks,
            'warnings': self.warnings,
            'contract_info': self.contract_info,
            'pairs': [
                {
                    'address': pair.pair_address,
                    'dex': pair.dex_id,
                    'chain_id': pair.chain_id,
                    'price_usd': pair.price_usd,
                    'price_change_1h': pair.price_change_1h,
                    'price_change_24h': pair.price_change_24h,
                    'liquidity_usd': pair.liquidity_usd,
                    'volume_24h': pair.volume_24h,
                    'created_at': pair.created_at.isoformat(),
                    'dex_link': pair.dex_link
                }
                for pair in self.pairs
            ]
        }
    
    def to_json(self) -> str:
        """
        Преобразует токен в JSON-строку
        
        Returns:
            str: JSON-представление токена
        """
        def json_serial(obj):
            """Сериализация объектов datetime в ISO-формат"""
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        return json.dumps(self.to_dict(), default=json_serial, ensure_ascii=False) 