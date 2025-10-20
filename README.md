[![GitHub release](https://img.shields.io/github/v/release/BlackPhoenix-gif/DexScreener-Rocket-Analyzer)](https://github.com/BlackPhoenix-gif/DexScreener-Rocket-Analyzer/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Made with Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

Languages: [🇬🇧 English](README.en.md) | [🇷🇺 Русский](README.ru.md)


# Raket — поиск ракет + анализ безопасности

Комплексный пайплайн:
- Поиск перспективных токенов (`raket-2`)
- Анализ безопасности и генерация отчетов (`src_analyse-2` + `seturity`)
- Глобальный запуск одним скриптом `./run_global.sh`

## Быстрый старт

```bash
# 1) Поиск токенов
cd raket-2
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
./run_scanner.sh

# 2) Анализ безопасности
cd ../src_analyse-2
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
./run_analysis.sh

# 3) Глобально (в корне)
cd ..
chmod +x run_global.sh
./run_global.sh
```

## Структура

```
github_export/
├── run_global.sh
├── raket-2/
│   ├── main.py
│   ├── run_scanner.sh
│   ├── requirements.txt
│   └── src/...
├── src_analyse-2/
│   ├── run_analysis.sh
│   ├── requirements.txt
│   └── src/...
├── seturity/
│   ├── main.py
│   ├── requirements.txt
│   └── *.py (analyzers)
└── examples/
    └── финальные отчеты (txt/csv/json)
```

## Примеры отчетов

Смотрите `examples/` (например, `final_unified_*.txt`, `final_analysis_*.csv`, `final_recommended_*.json`).

## Лицензия

MIT
