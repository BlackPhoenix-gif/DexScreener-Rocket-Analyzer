from typing import Dict, List, Any
from models import RiskAssessment, RiskLevel, TokenSecurityReport
from config import Config

class RiskScoreCalculator:
    def __init__(self):
        self.config = Config()
        self.weights = {
            'contract_verification': 0.15,
            'ownership_status': 0.20,
            'liquidity_lock': 0.25,
            'holder_distribution': 0.15,
            'trading_patterns': 0.10,
            'code_audit': 0.10,
            'community_reports': 0.05
        }
    
    def calculate_risk_score(self, token_data: TokenSecurityReport) -> RiskAssessment:
        """Расчет общего риска токена"""
        scores = {}
        
        # Contract verification
        scores['contract_verification'] = self.calculate_verification_score(token_data)
        
        # Ownership status
        scores['ownership_status'] = self.calculate_ownership_score(token_data)
        
        # Liquidity lock
        scores['liquidity_lock'] = self.calculate_liquidity_score(token_data)
        
        # Holder distribution
        scores['holder_distribution'] = self.calculate_distribution_score(token_data)
        
        # Trading patterns
        scores['trading_patterns'] = self.calculate_trading_score(token_data)
        
        # Code audit
        scores['code_audit'] = self.calculate_audit_score(token_data)
        
        # Community reports
        scores['community_reports'] = self.calculate_community_score(token_data)
        
        # Комплексный расчет
        final_score = sum(scores[k] * self.weights[k] for k in scores)
        
        return RiskAssessment(
            overall_score=final_score,
            risk_level=self.get_risk_level(final_score),
            confidence=self.calculate_confidence(scores),
            breakdown=scores,
            recommendations=self.generate_recommendations(scores, token_data)
        )
    
    def calculate_verification_score(self, token_data: TokenSecurityReport) -> float:
        """Расчет риска верификации контракта"""
        if not token_data.contract_analysis.verified:
            return 0.8
        
        # Проверка аудита
        audit_results = token_data.contract_analysis.audit_results
        if audit_results['critical'] > 0:
            return 0.9
        elif audit_results['high'] > 0:
            return 0.7
        elif audit_results['medium'] > 0:
            return 0.4
        else:
            return 0.1
    
    def calculate_ownership_score(self, token_data: TokenSecurityReport) -> float:
        """Расчет риска владельца"""
        if token_data.ownership.renounced:
            return 0.0
        elif token_data.ownership.owner_type.value == 'TIMELOCK':
            return 0.2
        elif token_data.ownership.owner_type.value == 'MULTISIG':
            return 0.4
        else:
            return 0.9
    
    def calculate_liquidity_score(self, token_data: TokenSecurityReport) -> float:
        """Расчет риска ликвидности"""
        if token_data.distribution.liquidity_locked:
            if token_data.distribution.liquidity_lock_period and token_data.distribution.liquidity_lock_period > 365:
                return 0.1
            elif token_data.distribution.liquidity_lock_period and token_data.distribution.liquidity_lock_period > 180:
                return 0.3
            else:
                return 0.5
        else:
            return 0.9
    
    def calculate_distribution_score(self, token_data: TokenSecurityReport) -> float:
        """Расчет риска распределения"""
        gini = token_data.distribution.gini_coefficient
        top_10_percent = token_data.distribution.top_10_holders_percent
        
        if gini > 0.8 or top_10_percent > 80:
            return 0.9
        elif gini > 0.6 or top_10_percent > 60:
            return 0.7
        elif gini > 0.4 or top_10_percent > 40:
            return 0.5
        else:
            return 0.2
    
    def calculate_trading_score(self, token_data: TokenSecurityReport) -> float:
        """Расчет риска торговых паттернов"""
        wash_score = token_data.trading.wash_trading_score
        organic_ratio = token_data.trading.organic_volume_ratio
        
        if wash_score > 0.7 or organic_ratio < 0.3:
            return 0.9
        elif wash_score > 0.5 or organic_ratio < 0.5:
            return 0.7
        elif wash_score > 0.3 or organic_ratio < 0.7:
            return 0.5
        else:
            return 0.2
    
    def calculate_audit_score(self, token_data: TokenSecurityReport) -> float:
        """Расчет риска аудита кода"""
        dangerous_funcs = token_data.contract_analysis.dangerous_functions
        honeypot_prob = token_data.contract_analysis.honeypot_probability
        
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
    
    def calculate_community_score(self, token_data: TokenSecurityReport) -> float:
        """Расчет риска на основе сообщества"""
        # Здесь можно добавить проверку внешних источников
        return 0.3  # Базовый риск
    
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
        # Чем больше данных, тем выше уверенность
        confidence = 0.5  # Базовая уверенность
        
        # Увеличиваем уверенность за каждый доступный показатель
        for score in scores.values():
            if score >= 0:
                confidence += 0.1
        
        return min(confidence, 1.0)
    
    def generate_recommendations(self, scores: Dict[str, float], token_data: TokenSecurityReport) -> List[str]:
        """Генерация рекомендаций"""
        recommendations = []
        
        # Контракт
        if scores['contract_verification'] > 0.5:
            if not token_data.contract_analysis.verified:
                recommendations.append("⚠️ Контракт не верифицирован")
            else:
                recommendations.append("⚠️ Обнаружены проблемы в коде контракта")
        else:
            recommendations.append("✅ Контракт безопасен")
        
        # Владелец
        if scores['ownership_status'] > 0.5:
            if not token_data.ownership.renounced:
                recommendations.append("⚠️ Контракт не ренонсирован")
            else:
                recommendations.append("⚠️ Подозрительный владелец")
        else:
            recommendations.append("✅ Владелец безопасен")
        
        # Ликвидность
        if scores['liquidity_lock'] > 0.5:
            if not token_data.distribution.liquidity_locked:
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
        if token_data.contract_analysis.honeypot_probability > 0.5:
            recommendations.append("🚨 Высокая вероятность honeypot")
        else:
            recommendations.append("✅ Нет признаков honeypot")
        
        return recommendations
