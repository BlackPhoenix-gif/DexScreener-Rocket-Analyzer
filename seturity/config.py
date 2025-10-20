import os
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Web3 providers (бесплатные альтернативы)
    ETHEREUM_RPC = os.getenv("ETHEREUM_RPC", "https://eth.llamarpc.com")
    BSC_RPC = os.getenv("BSC_RPC", "https://bsc-dataseed1.binance.org/")
    POLYGON_RPC = os.getenv("POLYGON_RPC", "https://polygon-rpc.com/")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/seturity")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # API Keys
    ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
    BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
    POLYGONSCAN_API_KEY = os.getenv("POLYGONSCAN_API_KEY")
    
    # Risk weights
    RISK_WEIGHTS = {
        'pause': 0.8,
        'unpause': 0.8,
        'blacklist': 0.9,
        'whitelist': 0.7,
        'setFee': 0.6,
        'setMaxTx': 0.5,
        'mint': 0.9,
        'burn': 0.4
    }
    
    # Dangerous patterns
    DANGEROUS_PATTERNS = {
        'honeypot': {
            'gas_manipulation': r'require\(tx\.gasprice\s*[<>]=?\s*\d+\)',
            'hidden_fees': r'_fee\s*=\s*(?:99|100)',
            'fake_renounce': r'function\s+renounceOwnership.*owner\s*=\s*msg\.sender'
        },
        'rug_pull': {
            'drain_functions': r'withdraw.*balance|emergency.*withdraw',
            'unlimited_mint': r'function\s+mint.*onlyOwner.*unlimited'
        }
    }
    
    # External APIs
    EXTERNAL_APIS = {
        'honeypot': [
            'https://api.honeypot.is/v2/IsHoneypot',
            'https://rugdoc.io/api/check'
        ],
        'dex_data': {
            'uniswap': 'https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3',
            'pancake': 'https://bsc.streamingfast.io/subgraphs/name/pancakeswap/exchange-v2'
        },
        'threat_intel': [
            'https://raw.githubusercontent.com/CryptoScamDB/blacklist/master/data/urls.json',
            'https://tokensniffer.com/api/v2/tokens'
        ]
    }
    
    # Cache TTL (seconds)
    CACHE_TTL = {
        'dynamic': 3600,  # 1 hour
        'static': 86400   # 24 hours
    }
    
    # Performance thresholds
    PERFORMANCE = {
        'single_token_timeout': 3,  # seconds
        'batch_timeout': 60,        # seconds
        'min_accuracy': 0.95,
        'max_false_positive': 0.05
    }
