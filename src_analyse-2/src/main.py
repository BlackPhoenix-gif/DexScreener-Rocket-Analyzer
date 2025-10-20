import argparse
import os
import json
from datetime import datetime
from token_analyzer import TokenAnalyzer
from colorama import init, Fore, Style

# Инициализация colorama для цветного вывода
init()

def main():
    """Основная функция запуска анализатора"""
    # Создаем парсер аргументов командной строки
    parser = argparse.ArgumentParser(description='Анализатор криптовалютных токенов Raket')
    
    # Группа для основных действий
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--analyze', '-a', help='Путь к JSON-файлу для анализа')
    action_group.add_argument('--filter', '-f', help='Применить фильтры к ранее загруженным токенам', action='store_true')
    action_group.add_argument('--config', '-c', help='Обновить конфигурацию анализатора', action='store_true')
    
    # Аргументы для фильтрации
    filter_group = parser.add_argument_group('Параметры фильтрации')
    filter_group.add_argument('--min-age', type=float, help='Минимальный возраст токена (часы)')
    filter_group.add_argument('--max-age', type=float, help='Максимальный возраст токена (часы)')
    filter_group.add_argument('--min-price-change', type=float, help='Минимальное изменение цены (%%)')
    filter_group.add_argument('--max-price-change', type=float, help='Максимальное изменение цены (%%)')
    filter_group.add_argument('--min-liquidity', type=float, help='Минимальная ликвидность (USD)')
    filter_group.add_argument('--max-liquidity', type=float, help='Максимальная ликвидность (USD)')
    filter_group.add_argument('--networks', nargs='+', help='Фильтр по сетям (список)')
    filter_group.add_argument('--include-scam', action='store_true', help='Включать скам-токены в результаты')
    
    # Общие аргументы
    parser.add_argument('--output-dir', '-o', help='Директория для сохранения отчетов')
    
    # Парсим аргументы
    args = parser.parse_args()
    
    # Создаем экземпляр анализатора
    raket = TokenAnalyzer()
    
    # Обработка команд
    if args.analyze:
        # Запускаем полный анализ
        print(f"{Fore.CYAN}Анализ файла: {args.analyze}{Style.RESET_ALL}")
        
        if not os.path.exists(args.analyze):
            print(f"{Fore.RED}Ошибка: Файл '{args.analyze}' не найден{Style.RESET_ALL}")
            return
        
        try:
            # Создаем директорию для отчетов
            output_dir = args.output_dir or raket.config.get("output_dir", "reports")
            os.makedirs(output_dir, exist_ok=True)
            
            # Загружаем и анализируем токены
            raket.load_from_json(args.analyze)
            
            # Используем асинхронный анализ с верификацией
            import asyncio
            asyncio.run(raket.analyze_all_tokens())
            
            # Определяем базовое имя файла
            base_filename = os.path.basename(args.analyze).split('.')[0]
            
            # Экспорт рекомендованных токенов в JSON (после анализа безопасности)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            recommended_json_path = os.path.join(output_dir, f"{base_filename}_recommended_{timestamp}.json")
            raket.export_recommended_to_json(recommended_json_path)
            
            # Генерируем объединенный отчет
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Объединенный отчет (включает безопасность и все категории)
            unified_report_path = os.path.join(output_dir, f"{base_filename}_unified_{timestamp}.txt")
            raket.generate_unified_report(unified_report_path)
            
            # Экспорт в CSV (для дополнительного анализа)
            csv_path = os.path.join(output_dir, f"{base_filename}_analysis_{timestamp}.csv")
            raket.export_to_csv(csv_path)
            
            print(f"\n{Fore.GREEN}Анализ успешно завершен{Style.RESET_ALL}")
            print(f"Всего токенов: {len(raket.tokens)}")
            print(f"Распределение по рискам:")
            print(f"- Скам: {len(raket.scam_tokens)}")
            print(f"- Высокий риск: {len(raket.high_risk_tokens)}")
            print(f"- Средний риск: {len(raket.medium_risk_tokens)}")
            print(f"- Низкий риск: {len(raket.low_risk_tokens)}")
            # Получаем рекомендованные токены для статистики
            recommended_tokens = raket.get_top_tokens_by_growth(
                limit=None,
                min_liquidity=raket.config.get("min_liquidity", 50000),
                min_age=24
            )
            print(f"- Рекомендовано: {len(recommended_tokens)}")
            
            print(f"\n{Fore.CYAN}Созданы следующие отчеты:{Style.RESET_ALL}")
            print(f"- Объединенный отчет: {unified_report_path}")
            print(f"- CSV-экспорт: {csv_path}")
            print(f"- JSON с рекомендациями: {recommended_json_path}")
            
        except Exception as e:
            print(f"{Fore.RED}Ошибка при анализе: {str(e)}{Style.RESET_ALL}")
    
    elif args.filter:
        # Применяем фильтры к ранее загруженным токенам
        print(f"{Fore.CYAN}Применение фильтров к токенам{Style.RESET_ALL}")
        
        if not raket.tokens:
            print(f"{Fore.RED}Ошибка: Сначала необходимо загрузить токены с помощью команды --analyze{Style.RESET_ALL}")
            return
        
        filters = {}
        if args.min_age is not None:
            filters["min_age"] = args.min_age
        if args.max_age is not None:
            filters["max_age"] = args.max_age
        if args.min_price_change is not None:
            filters["min_price_change"] = args.min_price_change
        if args.max_price_change is not None:
            filters["max_price_change"] = args.max_price_change
        if args.min_liquidity is not None:
            filters["min_liquidity"] = args.min_liquidity
        if args.max_liquidity is not None:
            filters["max_liquidity"] = args.max_liquidity
        if args.networks:
            filters["networks"] = args.networks
        if args.include_scam:
            filters["exclude_scam"] = False
        
        try:
            # Создаем директорию для отчетов
            output_dir = args.output_dir or raket.config.get("output_dir", "reports")
            os.makedirs(output_dir, exist_ok=True)
            
            # Применяем фильтры
            filtered_tokens = raket.filter_tokens(filters)
            
            if not filtered_tokens:
                print(f"{Fore.YELLOW}Нет токенов, соответствующих заданным критериям{Style.RESET_ALL}")
                return
            
            # Генерируем отчеты
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Детальный отчет
            report_path = os.path.join(output_dir, f"filtered_report_{timestamp}.txt")
            raket.generate_text_report(report_path, tokens_list=filtered_tokens, detailed=True)
            
            # Экспорт в CSV
            csv_path = os.path.join(output_dir, f"filtered_tokens_{timestamp}.csv")
            raket.export_to_csv(csv_path, tokens_list=filtered_tokens)
            
            print(f"\n{Fore.GREEN}Фильтрация успешно завершена{Style.RESET_ALL}")
            print(f"Отфильтровано токенов: {len(filtered_tokens)}")
            print(f"Создан отчет: {report_path}")
            print(f"CSV-экспорт: {csv_path}")
            
        except Exception as e:
            print(f"{Fore.RED}Ошибка при фильтрации: {str(e)}{Style.RESET_ALL}")
    
    elif args.config:
        # Обновляем конфигурацию
        print(f"{Fore.CYAN}Обновление конфигурации{Style.RESET_ALL}")
        
        # Загружаем текущую конфигурацию
        current_config = raket.config
        
        print(f"\n{Fore.YELLOW}Текущая конфигурация:{Style.RESET_ALL}")
        for key, value in current_config.items():
            print(f"- {key}: {value}")
        
        # Запрашиваем новые значения
        print(f"\n{Fore.CYAN}Введите новые значения (или нажмите Enter, чтобы оставить текущее):{Style.RESET_ALL}")
        
        new_config = {}
        new_config["min_price_change"] = input(f"Минимальное изменение цены [{current_config.get('min_price_change', 5)}]: ")
        new_config["max_price_change"] = input(f"Максимальное изменение цены [{current_config.get('max_price_change', 1000)}]: ")
        new_config["min_liquidity"] = input(f"Минимальная ликвидность [{current_config.get('min_liquidity', 250)}]: ")
        new_config["min_volume"] = input(f"Минимальный объем [{current_config.get('min_volume', 100)}]: ")
        new_config["max_token_age_hours"] = input(f"Максимальный возраст токена (часы) [{current_config.get('max_token_age_hours', 72)}]: ")
        
        networks_str = input(f"Сети (через запятую) [{','.join(current_config.get('networks', []))}]: ")
        if networks_str:
            new_config["networks"] = [n.strip() for n in networks_str.split(',')]
        
        exclude_scam_str = input(f"Исключать скам-токены (yes/no) [{'yes' if current_config.get('exclude_scam', True) else 'no'}]: ")
        if exclude_scam_str.lower() in ['yes', 'no']:
            new_config["exclude_scam"] = exclude_scam_str.lower() == 'yes'
        
        output_dir = input(f"Директория для отчетов [{current_config.get('output_dir', 'reports')}]: ")
        if output_dir:
            new_config["output_dir"] = output_dir
        
        # Обновляем конфигурацию
        for key, value in new_config.items():
            if value:  # Если значение не пустое
                try:
                    # Пытаемся преобразовать числовые значения
                    if key in ["min_price_change", "max_price_change", "min_liquidity", "min_volume", "max_token_age_hours"]:
                        current_config[key] = float(value)
                    else:
                        current_config[key] = value
                except:
                    print(f"{Fore.RED}Ошибка: Некорректное значение для {key}: {value}{Style.RESET_ALL}")
        
        # Сохраняем обновленную конфигурацию
        with open("config.json", 'w', encoding='utf-8') as f:
            json.dump(current_config, f, indent=2)
        
        print(f"\n{Fore.GREEN}Конфигурация успешно обновлена и сохранена в файл config.json{Style.RESET_ALL}")

if __name__ == "__main__":
    main() 