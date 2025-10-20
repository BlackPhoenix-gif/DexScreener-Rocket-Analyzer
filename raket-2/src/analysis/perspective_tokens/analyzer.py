from typing import List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict

@dataclass
class TokenMetrics:
    """Класс для хранения метрик токена"""
    address: str
    symbol: str
    name: str
    chain_id: str
    price: float
    price_change_1h: float
    price_change_24h: float
    volume_24h: float
    liquidity: float
    market_cap: float
    holders: int
    created_at: datetime
    age_hours: float
    contract_verified: bool
    contract_link: str
    scam_check_result: Dict[str, Any]
    social_metrics: Dict[str, Any]
    technical_metrics: Dict[str, Any]
    risk_metrics: Dict[str, Any]

class PerspectiveTokenAnalyzer:
    """
    Класс для анализа перспективных токенов
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация анализатора
        
        Args:
            config: Конфигурация с параметрами анализа
        """
        self.config = config
    
    def analyze_tokens(self, tokens: List[Dict[str, Any]]) -> List[TokenMetrics]:
        """
        Анализирует список токенов и возвращает перспективные
        
        Args:
            tokens: Список токенов для анализа
            
        Returns:
            List[TokenMetrics]: Список перспективных токенов с метриками
        """
        perspective_tokens = []
        
        for token in tokens:
            # Создаем объект с метриками токена
            metrics = TokenMetrics(
                address=token.get('address'),
                symbol=token.get('symbol'),
                name=token.get('name'),
                chain_id=token.get('chain_id'),
                price=token.get('price', 0),
                price_change_1h=token.get('price_change_1h', 0),
                price_change_24h=token.get('price_change_24h', 0),
                volume_24h=token.get('volume_24h', 0),
                liquidity=token.get('liquidity', 0),
                market_cap=token.get('market_cap', 0),
                holders=token.get('holders', 0),
                created_at=datetime.fromisoformat(token.get('created_at', datetime.now().isoformat())),
                age_hours=token.get('age_hours', 0),
                contract_verified=token.get('contract_verified', False),
                contract_link=token.get('contract_link', ''),
                scam_check_result=token.get('scam_check_result', {}),
                social_metrics=token.get('social_metrics', {}),
                technical_metrics=token.get('technical_metrics', {}),
                risk_metrics=token.get('risk_metrics', {})
            )
            
            # Проверяем соответствие критериям
            if self._check_perspective_criteria(metrics):
                perspective_tokens.append(metrics)
        
        return perspective_tokens
    
    def _check_perspective_criteria(self, metrics: TokenMetrics) -> bool:
        """
        Проверяет соответствие токена критериям перспективности
        
        Args:
            metrics: Метрики токена
            
        Returns:
            bool: True если токен соответствует критериям
        """
        # Проверяем базовые критерии
        if metrics.price_change_1h < self.config.get('min_price_growth_1h', 30):
            return False
            
        if metrics.price_change_24h < self.config.get('min_price_growth_24h', 100):
            return False
            
        if metrics.liquidity < self.config.get('min_liquidity', 5000):
            return False
            
        if metrics.volume_24h < self.config.get('min_volume_24h', 1000):
            return False
            
        if metrics.age_hours > self.config.get('max_token_age_hours', 72):
            return False
        
        # Проверяем риск-метрики
        if metrics.risk_metrics.get('risk_level') == 'high':
            return False
            
        if not metrics.contract_verified:
            return False
        
        # Проверяем социальные метрики
        if metrics.social_metrics.get('community_size', 0) < self.config.get('min_community_size', 100):
            return False
        
        return True 