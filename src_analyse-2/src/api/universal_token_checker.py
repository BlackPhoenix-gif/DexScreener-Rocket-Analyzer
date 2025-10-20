import requests
import random
from typing import Dict, Any, Optional


class UniversalTokenChecker:
    """
    Бесплатные проверки токена из нескольких источников:
    - DEXScreener интегрируем отдельно (из dexscreener.py)
    - Uniswap v3 (The Graph)
    - Jupiter (Solana)
    - CoinGecko (для известных токенов по адресу контракта)
    """

    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Mozilla/5.0 (X11; Linux x86_64)'
    ]

    PLATFORM_MAP = {
        'ethereum': 'ethereum',
        'bsc': 'binance-smart-chain',
        'polygon': 'polygon-pos',
        'arbitrum': 'arbitrum-one',
        'optimism': 'optimistic-ethereum',
        'base': 'base',
    }

    def _headers(self) -> Dict[str, str]:
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'application/json'
        }

    def check_via_uniswap(self, token_address: str) -> Dict[str, Any]:
        """Проверка наличия токена в Uniswap v3 (The Graph)."""
        url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
        query = f"""
        {{
          token(id: "{token_address.lower()}") {{
            symbol
            name
            decimals
            totalValueLockedUSD
          }}
        }}
        """
        try:
            resp = requests.post(url, json={'query': query}, headers=self._headers(), timeout=10)
            data = resp.json() if resp.ok else {}
            token = (data.get('data') or {}).get('token')
            if token:
                return {
                    'found': True,
                    'source': 'uniswap_v3_graph',
                    'info': token
                }
        except Exception:
            pass
        return {'found': False, 'source': 'uniswap_v3_graph'}

    def check_solana_jupiter(self, mint: str) -> Dict[str, Any]:
        """Проверка токена в Jupiter (Solana)."""
        try:
            url = "https://token.jup.ag/all"
            resp = requests.get(url, headers=self._headers(), timeout=8, stream=True)
            if resp.status_code == 200:
                tokens = resp.json()
                for t in tokens:
                    if t.get('address') == mint:
                        return {'found': True, 'source': 'jupiter_all', 'verified': True, 'info': t}
        except Exception:
            pass

        try:
            url = f"https://token.jup.ag/strict/{mint}"
            resp = requests.get(url, headers=self._headers(), timeout=6)
            if resp.status_code == 200:
                return {'found': True, 'source': 'jupiter_strict', 'strict': True}
        except Exception:
            pass

        return {'found': False, 'source': 'jupiter'}

    def check_coingecko(self, chain: str, token_address: str) -> Dict[str, Any]:
        """Проверка токена на CoinGecko по контракту (без ключа)."""
        platform = self.PLATFORM_MAP.get(chain.lower())
        if not platform:
            return {'found': False, 'source': 'coingecko'}
        url = f"https://api.coingecko.com/api/v3/coins/{platform}/contract/{token_address}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'found': True,
                    'source': 'coingecko',
                    'name': (data.get('name') or ''),
                    'symbol': (data.get('symbol') or '').upper(),
                    'categories': data.get('categories') or []
                }
        except Exception:
            pass
        return {'found': False, 'source': 'coingecko'}

    def check_token(self, address: str, chain: str) -> Dict[str, Any]:
        """Комбинированная бесплатная проверка без KYC."""
        results: Dict[str, Any] = {
            'found': False,
            'sources': [],
            'liquidity': 0,
            'risk_score': 100,
            'trust_level': 'low'
        }

        # CoinGecko — высокий приоритет доверия
        cg = self.check_coingecko(chain, address)
        if cg.get('found'):
            results['found'] = True
            results['sources'].append('coingecko')
            results['risk_score'] -= 40
            results['coingecko'] = cg

        # Uniswap v3 (для EVM)
        if chain.lower() in {'ethereum', 'bsc', 'polygon', 'arbitrum', 'optimism', 'base'}:
            uni = self.check_via_uniswap(address) if chain.lower() == 'ethereum' else {'found': False}
            if uni.get('found'):
                results['found'] = True
                results['sources'].append('uniswap')
                results['risk_score'] -= 30
                results['uniswap'] = uni

        # Solana — Jupiter
        if chain.lower() == 'solana':
            jup = self.check_solana_jupiter(address)
            if jup.get('found'):
                results['found'] = True
                results['sources'].append('jupiter')
                results['risk_score'] -= 20
                results['jupiter'] = jup

        # Trust level
        if len(results['sources']) >= 2:
            results['trust_level'] = 'high'
        elif results.get('liquidity', 0) > 100000:
            results['trust_level'] = 'medium'
        else:
            results['trust_level'] = 'low'

        return results


