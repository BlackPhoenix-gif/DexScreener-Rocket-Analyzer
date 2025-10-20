#!/usr/bin/env python3
import asyncio
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd

# Добавление директории проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from src.utils.logger import get_logger
from src.utils.report import ReportGenerator
from src.api.dexscreener import DexScreenerAPI
from src.analysis.filter import RocketFilter
from src.blockchain.contract import ContractAnalyzer

logger = get_logger()

class RaketApp:
    """
    Основной класс приложения для поиска и анализа "ракет".
    """
    
    def __init__(self):
        """
        Инициализация приложения и его компонентов.
        """
        logger.info(f"[SYSTEM] Запуск системы поиска ракет v1.0")
        
        # Инициализация компонентов
        self.api = DexScreenerAPI()
        self.filter = RocketFilter()
        self.contract_analyzer = ContractAnalyzer()
        self.report_generator = ReportGenerator()
        
        # Путь для сохранения отчетов
        self.reports_dir = config.REPORTS_DIR
        self.reports_dir.mkdir(exist_ok=True)
    
    async def scan_for_rockets(self, max_age_hours: int = None) -> None:
        """
        Основной метод сканирования и поиска "ракет".
        
        Args:
            max_age_hours: Максимальный возраст токена в часах
        """
        # Используем значение из конфига, если не указано явно
        if max_age_hours is None:
            max_age_hours = config.MAX_TOKEN_AGE_HOURS
        
        logger.info(f"[SYSTEM] Начало сканирования токенов (макс. возраст: {max_age_hours}ч)")
        
        try:
            # Получение токенов через API
            logger.info(f"[SYSTEM] Получение данных о токенах с DEXScreener")
            tokens = await self.api.find_rocket_tokens(max_age_hours=max_age_hours)
            logger.info(f"[SYSTEM] Получено {len(tokens)} токенов")
            
            # Фильтрация "ракет"
            logger.info(f"[SYSTEM] Фильтрация потенциальных ракет")
            rockets = self.filter.filter_rockets(tokens)
            logger.info(f"[SYSTEM] Найдено {len(rockets)} потенциальных ракет")
            
            # Сортировка "ракет" по потенциалу
            logger.info(f"[SYSTEM] Сортировка ракет по потенциалу")
            sorted_rockets = self.filter.sort_rockets_by_potential(rockets)
            
            # Простая заглушка для скам-проверки
            # В будущем здесь будет полноценный анализ
            for rocket in sorted_rockets:
                rocket.scam_check_result = {
                    'risk_level': 'unknown',
                    'indicators': [],
                    'notes': 'Проверка на скам не реализована в текущей версии'
                }
                
                # Добавляем ссылку на контракт в блокчейн-сканере
                if rocket.chain_id:
                    contract_link = await self.contract_analyzer.get_contract_link(rocket.address, rocket.chain_id)
                    rocket.scam_check_result['contract_link'] = contract_link
            
            # Формирование отчета
            await self.generate_report(sorted_rockets)
            
        except Exception as e:
            logger.error(f"[SYSTEM] Ошибка при сканировании: {str(e)}")
            raise
    
    async def generate_report(self, rockets: list, report_format: str = 'all') -> None:
        """
        Генерирует отчет о найденных "ракетах".
        
        Args:
            rockets: Список "ракет" для отчета
            report_format: Формат отчета ('json', 'csv', 'html' или 'all')
        """
        logger.info(f"[SYSTEM] Формирование отчета о {len(rockets)} ракетах (формат: {report_format})")
        
        try:
            # Генерация отчетов через специализированный генератор отчетов
            report_files = self.report_generator.generate_report(rockets, format_type=report_format)
            
            # Вывод информации о созданных отчетах
            for report_type, report_path in report_files.items():
                logger.info(f"[SYSTEM] Отчет ({report_type}): {report_path}")
            
            # Если найдены ракеты, выводим краткую сводку
            if rockets:
                logger.info(f"[SYSTEM] Топ-5 потенциальных ракет:")
                for i, rocket in enumerate(rockets[:5], 1):
                    logger.info(f"[SYSTEM] {i}. {rocket.symbol} ({rocket.name}): "
                               f"+{rocket.max_price_change_24h:.1f}% (24ч), "
                               f"ликв. ${rocket.total_liquidity_usd:.1f}, "
                               f"возраст {rocket.age_hours:.1f}ч")
            else:
                logger.info(f"[SYSTEM] Не найдено потенциальных ракет, соответствующих критериям")
            
        except Exception as e:
            logger.error(f"[SYSTEM] Ошибка при создании отчета: {str(e)}")
    
    async def run(self, args) -> None:
        """
        Запускает процесс сканирования с указанными параметрами.
        
        Args:
            args: Аргументы командной строки
        """
        # Переопределение параметров из аргументов командной строки
        if args.min_growth_1h is not None:
            self.filter.min_price_growth_1h = args.min_growth_1h
            logger.info(f"[SYSTEM] Установлен параметр мин. рост 1ч: {args.min_growth_1h}%")
        
        if args.min_growth_24h is not None:
            self.filter.min_price_growth_24h = args.min_growth_24h
            logger.info(f"[SYSTEM] Установлен параметр мин. рост 24ч: {args.min_growth_24h}%")
        
        if args.min_liquidity is not None:
            self.filter.min_liquidity = args.min_liquidity
            logger.info(f"[SYSTEM] Установлен параметр мин. ликвидность: ${args.min_liquidity}")
        
        if args.min_volume is not None:
            self.filter.min_volume_24h = args.min_volume
            logger.info(f"[SYSTEM] Установлен параметр мин. объем 24ч: ${args.min_volume}")
        
        max_age = args.max_age if args.max_age is not None else config.MAX_TOKEN_AGE_HOURS
        logger.info(f"[SYSTEM] Установлен параметр макс. возраст: {max_age}ч")
        
        # Формат отчета
        report_format = args.report_format if args.report_format else 'all'
        logger.info(f"[SYSTEM] Формат отчета: {report_format}")
        
        # Запуск сканирования
        await self.scan_for_rockets(max_age_hours=max_age)
        
        logger.info(f"[SYSTEM] Завершение работы системы")


def parse_arguments():
    """
    Парсинг аргументов командной строки.
    
    Returns:
        argparse.Namespace: Объект с аргументами
    """
    parser = argparse.ArgumentParser(description='Система поиска и анализа высокодоходных токенов')
    
    parser.add_argument('--min-growth-1h', type=float, help='Минимальный рост цены за 1 час (%)')
    parser.add_argument('--min-growth-24h', type=float, help='Минимальный рост цены за 24 часа (%)')
    parser.add_argument('--min-liquidity', type=float, help='Минимальная ликвидность пула ($)')
    parser.add_argument('--min-volume', type=float, help='Минимальный объем торгов за 24 часа ($)')
    parser.add_argument('--max-age', type=int, help='Максимальный возраст токена (часы)')
    parser.add_argument('--report-format', type=str, choices=['json', 'csv', 'html', 'all'], 
                        help='Формат отчета (json, csv, html или all)')
    
    return parser.parse_args()


async def main():
    """
    Основная функция приложения.
    """
    args = parse_arguments()
    app = RaketApp()
    await app.run(args)


if __name__ == "__main__":
    asyncio.run(main()) 