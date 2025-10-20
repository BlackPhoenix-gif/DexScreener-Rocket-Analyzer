import os
import json
import csv
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import config
from src.models.token import Token
from src.utils.logger import get_logger

logger = get_logger()

class ReportGenerator:
    """
    Класс для генерации отчетов о найденных "ракетах".
    Поддерживает форматы JSON, CSV и HTML.
    """
    
    def __init__(self, reports_dir: Optional[Path] = None):
        """
        Инициализация генератора отчетов.
        
        Args:
            reports_dir: Директория для сохранения отчетов (если None, используется config.REPORTS_DIR)
        """
        self.reports_dir = reports_dir or config.REPORTS_DIR
        self.reports_dir.mkdir(exist_ok=True)
        
        logger.info(f"[REPORT] Инициализация генератора отчетов (директория: {self.reports_dir})")
    
    def generate_report(self, rockets: List[Token], format_type: str = 'all') -> Dict[str, Path]:
        """
        Генерирует отчет о найденных "ракетах" в указанном формате.
        
        Args:
            rockets: Список "ракет" для отчета
            format_type: Формат отчета ('json', 'csv', 'html', 'txt' или 'all')
            
        Returns:
            Dict[str, Path]: Словарь с путями к созданным файлам отчетов
        """
        logger.info(f"[REPORT] Формирование отчета о {len(rockets)} ракетах (формат: {format_type})")
        
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        
        report_files = {}
        
        # Определение форматов для генерации
        formats_to_generate = []
        if format_type.lower() == 'all':
            formats_to_generate = ['json', 'csv', 'html', 'txt']
        else:
            formats_to_generate = [format_type.lower()]
        
        try:
            # Подготовка данных для отчетов
            if 'json' in formats_to_generate:
                # Создание JSON отчета
                json_report_path = self.reports_dir / f"rockets_report_{timestamp}.json"
                self._generate_json_report(rockets, json_report_path)
                report_files['json'] = json_report_path
            
            if 'csv' in formats_to_generate:
                # Создание CSV отчета
                csv_report_path = self.reports_dir / f"rockets_report_{timestamp}.csv"
                self._generate_csv_report(rockets, csv_report_path)
                report_files['csv'] = csv_report_path
            
            if 'html' in formats_to_generate:
                # Создание HTML отчета
                html_report_path = self.reports_dir / f"rockets_report_{timestamp}.html"
                self._generate_html_report(rockets, html_report_path)
                report_files['html'] = html_report_path
                
            if 'txt' in formats_to_generate:
                # Создание текстового отчета
                txt_report_path = self.reports_dir / f"rockets_report_{timestamp}.txt"
                self._generate_txt_report(rockets, txt_report_path)
                report_files['txt'] = txt_report_path
            
        except Exception as e:
            logger.error(f"[REPORT] Ошибка при создании отчета: {str(e)}")
            raise
        
        logger.info(f"[REPORT] Отчеты успешно сформированы: {', '.join(report_files.keys())}")
        return report_files
    
    def _generate_json_report(self, rockets: List[Token], output_path: Path) -> None:
        """
        Генерирует отчет в формате JSON.
        
        Args:
            rockets: Список "ракет" для отчета
            output_path: Путь для сохранения отчета
        """
        logger.info(f"[REPORT] Создание JSON отчета: {output_path}")
        
        # Преобразование токенов в словари
        rockets_data = [rocket.to_dict() for rocket in rockets]
        
        # Запись в файл
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(rockets_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[REPORT] JSON отчет успешно создан: {output_path}")
    
    def _generate_csv_report(self, rockets: List[Token], output_path: Path) -> None:
        """
        Генерирует отчет в формате CSV.
        
        Args:
            rockets: Список "ракет" для отчета
            output_path: Путь для сохранения отчета
        """
        logger.info(f"[REPORT] Создание CSV отчета: {output_path}")
        
        if not rockets:
            logger.warning(f"[REPORT] Нет данных для создания CSV отчета")
            return
        
        # Подготовка данных для CSV
        csv_data = []
        for rocket in rockets:
            # Берем пару с максимальной ликвидностью
            main_pair = rocket.max_pair_by_liquidity
            
            row = {
                'Символ': rocket.symbol,
                'Название': rocket.name,
                'Адрес': rocket.address,
                'Возраст (ч)': round(rocket.age_hours, 2),
                'Сеть': rocket.chain_id,
                'Рост 1ч (%)': round(rocket.max_price_change_1h, 2),
                'Рост 24ч (%)': round(rocket.max_price_change_24h, 2),
                'Ликвидность ($)': round(rocket.total_liquidity_usd, 2),
                'Объем 24ч ($)': round(rocket.total_volume_24h, 2),
                'DEX': main_pair.dex_id if main_pair else '',
                'Цена ($)': main_pair.price_usd if main_pair else 0,
                'Пара': f"{main_pair.base_token.symbol}/{main_pair.quote_token.symbol}" if main_pair else '',
                'Уровень риска': rocket.scam_check_result.get('risk_level', 'unknown'),
                'Ссылка на контракт': rocket.scam_check_result.get('contract_link', '')
            }
            csv_data.append(row)
        
        # Создание DataFrame и сохранение в CSV
        df = pd.DataFrame(csv_data)
        df.to_csv(output_path, index=False, encoding='utf-8')
        
        logger.info(f"[REPORT] CSV отчет успешно создан: {output_path}")
    
    def _generate_html_report(self, rockets: List[Token], output_path: Path) -> None:
        """
        Генерирует отчет в формате HTML.
        
        Args:
            rockets: Список "ракет" для отчета
            output_path: Путь для сохранения отчета
        """
        logger.info(f"[REPORT] Создание HTML отчета: {output_path}")
        
        if not rockets:
            logger.warning(f"[REPORT] Нет данных для создания HTML отчета")
            return
        
        # Создание DataFrame для HTML-таблицы
        data = []
        for rocket in rockets:
            main_pair = rocket.max_pair_by_liquidity
            
            row = {
                'Символ': rocket.symbol,
                'Название': rocket.name,
                'Адрес': f'<a href="{rocket.scam_check_result.get("contract_link", "#")}" target="_blank">{rocket.address[:8]}...{rocket.address[-6:]}</a>',
                'Возраст (ч)': round(rocket.age_hours, 2),
                'Сеть': rocket.chain_id,
                'Рост 1ч (%)': round(rocket.max_price_change_1h, 2),
                'Рост 24ч (%)': round(rocket.max_price_change_24h, 2),
                'Ликвидность ($)': f"{rocket.total_liquidity_usd:,.2f}",
                'Объем 24ч ($)': f"{rocket.total_volume_24h:,.2f}",
                'DEX': main_pair.dex_id if main_pair else '',
                'Цена ($)': f"{main_pair.price_usd:.10f}" if main_pair else "0",
                'Риск': rocket.scam_check_result.get('risk_level', 'unknown')
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Создание стилизованной HTML-таблицы
        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчет о потенциальных ракетах</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            text-align: center;
        }}
        .report-info {{
            text-align: center;
            margin-bottom: 20px;
            color: #666;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background-color: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f1f1f1;
        }}
        a {{
            color: #2196F3;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .positive {{
            color: green;
            font-weight: bold;
        }}
        .risk-low {{
            color: green;
        }}
        .risk-medium {{
            color: orange;
        }}
        .risk-high {{
            color: red;
        }}
        .risk-unknown {{
            color: gray;
        }}
        .footer {{
            margin-top: 30px;
            text-align: center;
            color: #666;
            font-size: 0.8em;
        }}
    </style>
</head>
<body>
    <h1>Отчет о потенциальных ракетах</h1>
    <div class="report-info">
        <p>Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
        <p>Всего найдено ракет: {len(rockets)}</p>
    </div>
    
    {df.to_html(index=False, escape=False, classes='data-table')}
    
    <div class="footer">
        <p>Отчет сгенерирован системой поиска и анализа высокодоходных токенов Raket</p>
        <p>Обратите внимание: данная информация не является инвестиционной рекомендацией</p>
    </div>
</body>
</html>"""
        
        # Запись в файл
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"[REPORT] HTML отчет успешно создан: {output_path}")

    def _generate_txt_report(self, rockets: List[Token], output_path: Path) -> None:
        """
        Генерирует отчет в текстовом формате.
        
        Args:
            rockets: Список "ракет" для отчета
            output_path: Путь для сохранения отчета
        """
        logger.info(f"[REPORT] Создание текстового отчета: {output_path}")
        
        if not rockets:
            logger.warning(f"[REPORT] Нет данных для создания текстового отчета")
            return
        
        # Формирование текстового отчета
        report_text = f"""Отчет о потенциальных ракетах
Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
Всего найдено ракет: {len(rockets)}

"""
        
        for i, rocket in enumerate(rockets, 1):
            main_pair = rocket.max_pair_by_liquidity
            
            # Форматирование цены
            price = main_pair.price_usd if main_pair else 0
            price_str = f"${price:.10f}" if price > 0 else "Н/Д"
            
            # Форматирование пары
            pair_str = f"{main_pair.base_token.symbol}/{main_pair.quote_token.symbol}" if main_pair else "Н/Д"
            
            report_text += f"""Ракета #{i}
------------------------
Символ: {rocket.symbol}
Название: {rocket.name}
Адрес: {rocket.address}
Сеть: {rocket.chain_id}
Возраст: {rocket.age_hours:.2f} часов

Показатели:
- Рост цены (1ч): {rocket.max_price_change_1h:.2f}%
- Рост цены (24ч): {rocket.max_price_change_24h:.2f}%
- Ликвидность: ${rocket.total_liquidity_usd:,.2f}
- Объем торгов (24ч): ${rocket.total_volume_24h:,.2f}

Основная пара:
- DEX: {main_pair.dex_id if main_pair else 'Н/Д'}
- Пара: {pair_str}
- Цена: {price_str}

Ссылки:
- DEXScreener: {main_pair.chart_links.get('DEXScreener', 'Н/Д') if main_pair else 'Н/Д'}
"""
            # Добавляем дополнительные ссылки, если они доступны
            if main_pair and main_pair.chart_links:
                for name, link in main_pair.chart_links.items():
                    if name != 'DEXScreener':  # DEXScreener уже добавлен выше
                        report_text += f"- {name}: {link}\n"
            
            report_text += f"""
Риск:
- Уровень: {rocket.scam_check_result.get('risk_level', 'unknown')}
- Ссылка на контракт: {rocket.scam_check_result.get('contract_link', 'Н/Д')}

"""
        
        report_text += f"""
Примечание: Данная информация не является инвестиционной рекомендацией.
Отчет сгенерирован системой поиска и анализа высокодоходных токенов Raket.
"""
        
        # Запись в файл
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        logger.info(f"[REPORT] Текстовый отчет успешно создан: {output_path}")


if __name__ == "__main__":
    # Пример использования
    from src.models.token import Token, TokenPair
    from datetime import datetime, timedelta
    
    # Создание тестовых данных
    now = datetime.now()
    
    # Создание тестовой пары
    pair1 = TokenPair(
        pair_address="0x1234567890abcdef",
        dex_id="uniswap",
        base_token={"address": "0xabc", "name": "Test Token", "symbol": "TEST"},
        quote_token={"address": "0xdef", "name": "Ethereum", "symbol": "ETH"},
        price_usd=0.000005,
        price_change={"5m": 5, "1h": 35, "6h": 70, "24h": 120, "7d": 200},
        liquidity_usd=10000,
        volume_usd_24h=5000,
        created_at=now - timedelta(hours=24)
    )
    
    # Создание тестового токена
    token1 = Token(
        address="0xabc123def456",
        name="Test Token",
        symbol="TEST",
        pairs=[pair1],
        chain_id="ethereum"
    )
    
    # Добавление информации о проверке на скам
    token1.scam_check_result = {
        'risk_level': 'low',
        'indicators': [],
        'contract_link': 'https://etherscan.io/address/0xabc123def456'
    }
    
    # Создание генератора отчетов и формирование отчетов
    report_generator = ReportGenerator()
    report_files = report_generator.generate_report([token1], format_type='all')
    
    print(f"Созданы отчеты: {report_files}") 