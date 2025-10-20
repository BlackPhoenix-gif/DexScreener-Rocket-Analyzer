from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class OwnerType(str, Enum):
    EOA = "EOA"
    MULTISIG = "MULTISIG"
    TIMELOCK = "TIMELOCK"
    RENOUNCED = "RENOUNCED"
    UNKNOWN = "UNKNOWN"

class WhaleConcentration(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class ContractAnalysis(BaseModel):
    verified: bool = False
    audit_results: Dict[str, int] = Field(default_factory=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0})
    dangerous_functions: List[Dict[str, Any]] = Field(default_factory=list)
    honeypot_probability: float = 0.0
    source_code: Optional[str] = None
    bytecode: Optional[str] = None
    abi: Optional[List[Dict[str, Any]]] = None

class OwnershipAnalysis(BaseModel):
    owner: str = "0x0000000000000000000000000000000000000000"
    owner_type: OwnerType = OwnerType.UNKNOWN
    renounced: bool = False
    admin_functions: List[Dict[str, Any]] = Field(default_factory=list)
    risk_score: float = 0.0

class DistributionAnalysis(BaseModel):
    top_10_holders_percent: float = 0.0
    gini_coefficient: float = 0.0
    whale_concentration: WhaleConcentration = WhaleConcentration.LOW
    total_holders: int = 0
    top_holders: List[Dict[str, Any]] = Field(default_factory=list)
    liquidity_locked: bool = False
    liquidity_lock_period: Optional[int] = None

class TradingAnalysis(BaseModel):
    unique_buyers_24h: int = 0
    unique_sellers_24h: int = 0
    wash_trading_score: float = 0.0
    organic_volume_ratio: float = 0.0
    avg_hold_time: float = 0.0
    volume_24h: float = 0.0
    price_change_24h: float = 0.0

class RiskAssessment(BaseModel):
    overall_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    confidence: float = 0.0
    breakdown: Dict[str, float] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)

class TokenSecurityReport(BaseModel):
    token_address: str
    token_name: Optional[str] = None
    token_symbol: Optional[str] = None
    chain: str = "ethereum"
    risk_assessment: RiskAssessment
    contract_analysis: ContractAnalysis
    ownership: OwnershipAnalysis
    distribution: DistributionAnalysis
    trading: TradingAnalysis
    external_checks: Dict[str, Any] = Field(default_factory=dict)
    analysis_timestamp: datetime = Field(default_factory=datetime.now)
    analysis_duration: float = 0.0

class ScamPattern(BaseModel):
    pattern_id: str
    pattern_type: str
    bytecode_signature: Optional[str] = None
    source_regex: Optional[str] = None
    severity_score: int = Field(ge=1, le=10)
    false_positive_rate: float = Field(ge=0.0, le=1.0)
    last_updated: datetime = Field(default_factory=datetime.now)
    detection_count: int = 0

class DetectedScam(BaseModel):
    token_address: str
    pattern_id: str
    detection_timestamp: datetime = Field(default_factory=datetime.now)
    confidence_score: float = Field(ge=0.0, le=1.0)
