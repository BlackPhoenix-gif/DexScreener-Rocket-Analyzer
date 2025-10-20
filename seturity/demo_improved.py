import asyncio
import json
from token_analyzer import TokenAnalyzer

async def demo_single_token():
    """Демонстрация анализа одного токена"""
    analyzer = TokenAnalyzer()
    
    # Примеры реальных токенов для анализа (уникальные)
    test_tokens = [
        "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
        "0xA0b86a33E6441b8c4C8C1C1B9C9C9C9C9C9C9C9C",  # Тестовый токен
    ]
    
    print("🔍 ДЕМОНСТРАЦИЯ АНАЛИЗА БЕЗОПАСНОСТИ ТОКЕНОВ")
    print("=" * 60)
    
    for i, token_address in enumerate(test_tokens, 1):
        print(f"\n📊 Анализ токена {i}: {token_address}")
        print("-" * 40)
        
        try:
            # Анализ токена
            report = await analyzer.analyze_token(token_address)
            
            # Вывод результатов
            print(f"🎯 Общий риск: {report.risk_assessment.risk_level.value}")
            print(f"📈 Оценка риска: {report.risk_assessment.overall_score:.2f}")
            print(f"🎯 Уверенность: {report.risk_assessment.confidence:.2f}")
            
            print(f"\n📋 Рекомендации:")
            for rec in report.risk_assessment.recommendations:
                print(f"  {rec}")
            
            print(f"\n🔧 Детали анализа:")
            print(f"  • Контракт верифицирован: {'✅' if report.contract_analysis.verified else '❌'}")
            print(f"  • Владелец ренонсирован: {'✅' if report.ownership.renounced else '❌'}")
            print(f"  • Ликвидность заблокирована: {'✅' if report.distribution.liquidity_locked else '❌'}")
            print(f"  • Концентрация китов: {report.distribution.whale_concentration.value}")
            print(f"  • Вероятность honeypot: {report.contract_analysis.honeypot_probability:.2f}")
            
            print(f"\n⏱️  Время анализа: {report.analysis_duration:.2f}с")
            
        except Exception as e:
            print(f"❌ Ошибка анализа: {e}")
        
        print("\n" + "=" * 60)

async def demo_batch_analysis():
    """Демонстрация пакетного анализа"""
    analyzer = TokenAnalyzer()
    
    # Список токенов для анализа (уникальные адреса)
    tokens = [
        "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
        "0xA0b86a33E6441b8c4C8C1C1B9C9C9C9C9C9C9C9C",  # Тестовый 1
        "0xB1b86a33E6441b8c4C8C1C1B9C9C9C9C9C9C9C9C",  # Тестовый 2
    ]
    
    # Убираем дубликаты
    tokens = list(set(tokens))
    
    print("\n🚀 ПАКЕТНЫЙ АНАЛИЗ ТОКЕНОВ")
    print("=" * 60)
    print(f"📝 Анализируем {len(tokens)} уникальных токенов...")
    
    try:
        reports = await analyzer.analyze_batch(tokens)
        
        print(f"✅ Проанализировано токенов: {len(reports)}")
        
        # Статистика
        risk_counts = {}
        total_time = 0
        verified_count = 0
        renounced_count = 0
        locked_count = 0
        
        for report in reports:
            risk_level = report.risk_assessment.risk_level.value
            risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1
            total_time += report.analysis_duration
            
            if report.contract_analysis.verified:
                verified_count += 1
            if report.ownership.renounced:
                renounced_count += 1
            if report.distribution.liquidity_locked:
                locked_count += 1
        
        print(f"\n📊 Статистика рисков:")
        for risk, count in risk_counts.items():
            percentage = (count / len(reports)) * 100
            print(f"  {risk}: {count} токенов ({percentage:.1f}%)")
        
        print(f"\n🔧 Дополнительная статистика:")
        print(f"  • Верифицированных контрактов: {verified_count}/{len(reports)}")
        print(f"  • Ренонсированных контрактов: {renounced_count}/{len(reports)}")
        print(f"  • Заблокированной ликвидности: {locked_count}/{len(reports)}")
        
        print(f"\n⏱️  Общее время анализа: {total_time:.2f}с")
        print(f"📈 Среднее время на токен: {total_time/len(reports):.2f}с")
        
    except Exception as e:
        print(f"❌ Ошибка пакетного анализа: {e}")

async def demo_with_real_data():
    """Демонстрация с реальными данными из файла"""
    print("\n📁 ДЕМОНСТРАЦИЯ С РЕАЛЬНЫМИ ДАННЫМИ")
    print("=" * 60)
    
    try:
        # Импортируем основной процессор
        from main import TokenSecurityProcessor
        
        processor = TokenSecurityProcessor()
        
        # Путь к файлу с данными
        input_file = "results/final_recommended_20250811_183555.json"
        output_file = "results/demo_analysis_results.json"
        
        print(f"📂 Обрабатываем файл: {input_file}")
        
        # Обработка токенов
        await processor.process_tokens_file(input_file, output_file)
        
        print(f"✅ Результаты сохранены в: {output_file}")
        
    except Exception as e:
        print(f"❌ Ошибка обработки файла: {e}")

async def main():
    """Основная функция демонстрации"""
    print("🔐 SETURITY - Система анализа безопасности криптовалютных токенов")
    print("=" * 70)
    
    # Демонстрация анализа одного токена
    await demo_single_token()
    
    # Демонстрация пакетного анализа
    await demo_batch_analysis()
    
    # Демонстрация с реальными данными
    await demo_with_real_data()
    
    print("\n🎉 Демонстрация завершена!")
    print("\n💡 Для анализа ваших данных:")
    print("   1. Поместите JSON файл с токенами в папку results/")
    print("   2. Запустите: python main.py")
    print("   3. Результаты будут сохранены в results/security_analysis_results.json")
    print("\n🔧 Для настройки API ключей:")
    print("   1. Скопируйте env.example в .env")
    print("   2. Добавьте ваши API ключи в .env файл")

if __name__ == "__main__":
    asyncio.run(main())
