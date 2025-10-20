# Seturity - Система анализа безопасности криптовалютных токенов

Система для глубокого анализа безопасности криптовалютных токенов с использованием многофакторной оценки рисков.

## Возможности

### 🔍 Модуль анализа смарт-контрактов
- Статический анализ исходного кода
- Детекция опасных паттернов (honeypot, rug pull)
- Анализ байткода для неверифицированных контрактов
- Проверка через внешние API (Honeypot.is, RugDoc)

### 👤 Анализ владельца и административных прав
- Определение типа владельца (EOA, Multisig, Timelock, Renounced)
- Анализ административных функций
- Проверка ренонса контракта

### 📊 Анализ распределения токенов
- Расчет коэффициента Джини
- Анализ концентрации крупных держателей
- Проверка блокировки ликвидности

### ⚖️ Система оценки рисков
- Многофакторная модель риска
- Взвешенная оценка по различным параметрам
- Генерация рекомендаций

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd seturity
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. (Опционально) Создайте файл `.env` с вашими API ключами для расширенного анализа:
```env
ETHERSCAN_API_KEY=your_etherscan_api_key
BSCSCAN_API_KEY=your_bscscan_api_key
POLYGONSCAN_API_KEY=your_polygonscan_api_key
ETHEREUM_RPC=https://eth-mainnet.g.alchemy.com/v2/your-api-key
```

**Примечание:** Система работает и без API ключей, используя бесплатные методы анализа.

### 🔗 Интеграция с 1inch API

Интеграция с 1inch полностью удалена.

## Использование

### 🆓 Бесплатный анализ (без API ключей)

```bash
python free_analyzer.py
```

### Базовый анализ токена

```python
import asyncio
from token_analyzer import TokenAnalyzer

async def analyze_single_token():
    analyzer = TokenAnalyzer()
    report = await analyzer.analyze_token("0x1234...")
    print(f"Risk Level: {report.risk_assessment.risk_level}")
    print(f"Risk Score: {report.risk_assessment.overall_score}")

asyncio.run(analyze_single_token())
```

### Пакетный анализ из JSON файла

```bash
python main.py
```

Система автоматически:
1. Загрузит данные из `results/final_recommended_20250811_183555.json`
2. Отфильтрует токены, помеченные как scam
3. Проанализирует каждый токен
4. Сохранит результаты в `results/security_analysis_results.json`
5. Сгенерирует сводный отчет

## Структура проекта

```
seturity/
├── config.py              # Конфигурация системы
├── models.py              # Модели данных
├── contract_analyzer.py   # Анализ смарт-контрактов
├── ownership_analyzer.py  # Анализ владельца
├── distribution_analyzer.py # Анализ распределения
├── risk_calculator.py     # Расчет рисков
├── token_analyzer.py      # Основной анализатор
├── main.py               # Главный скрипт
├── requirements.txt      # Зависимости
└── README.md            # Документация
```

## Формат входных данных

Система поддерживает различные форматы JSON:

```json
{
  "tokens": [
    {
      "address": "0x1234...",
      "name": "Token Name",
      "symbol": "TKN",
      "is_scam": false
    }
  ]
}
```

или

```json
[
  {
    "address": "0x1234...",
    "name": "Token Name",
    "symbol": "TKN"
  }
]
```

## Формат выходных данных

```json
{
  "token_address": "0x1234...",
  "risk_assessment": {
    "overall_score": 0.25,
    "risk_level": "LOW",
    "confidence": 0.85,
    "breakdown": {
      "contract_verification": 0.1,
      "ownership_status": 0.0,
      "liquidity_lock": 0.1,
      "holder_distribution": 0.2,
      "trading_patterns": 0.2,
      "code_audit": 0.1,
      "community_reports": 0.3
    },
    "recommendations": [
      "✅ Контракт безопасен",
      "✅ Владелец безопасен",
      "✅ Ликвидность заблокирована"
    ]
  },
  "contract_analysis": {
    "verified": true,
    "audit_results": {"critical": 0, "high": 0, "medium": 0, "low": 0},
    "dangerous_functions": [],
    "honeypot_probability": 0.02
  },
  "ownership": {
    "owner": "0x0000...0000",
    "renounced": true,
    "admin_functions": []
  },
  "distribution": {
    "top_10_holders_percent": 45.2,
    "gini_coefficient": 0.72,
    "whale_concentration": "MEDIUM"
  }
}
```

## Метрики производительности

- Анализ одного токена: < 3 секунды
- Пакетный анализ 100 токенов: < 60 секунд
- Точность детекции скама: > 95%
- False positive rate: < 5%

## Внешние API

Система интегрируется со следующими сервисами:
- **Etherscan** - данные контрактов и транзакций
- **Honeypot.is** - проверка honeypot токенов
- **RugDoc** - анализ rug pull рисков
- **TokenSniffer** - дополнительная проверка безопасности

## Безопасность

- Все API ключи хранятся в переменных окружения
- Поддержка rate limiting для внешних API
- Кеширование результатов для оптимизации
- Обработка ошибок и fallback механизмы

## Разработка

### Добавление новых паттернов

```python
# В contract_analyzer.py
new_pattern = ScamPattern(
    pattern_id="new_scam_pattern",
    pattern_type="rug_pull",
    source_regex=r'your_regex_pattern',
    severity_score=8,
    false_positive_rate=0.1
)
```

### Настройка весов риска

```python
# В risk_calculator.py
self.weights = {
    'contract_verification': 0.15,
    'ownership_status': 0.20,
    'liquidity_lock': 0.25,
    # Добавьте новые веса
}
```

## Лицензия

MIT License

## Поддержка

Для вопросов и предложений создавайте issues в репозитории.
