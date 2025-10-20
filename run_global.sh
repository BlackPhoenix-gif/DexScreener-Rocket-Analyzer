#!/bin/bash

echo "=== Начало глобального запуска ==="

# Активация виртуального окружения
echo "Активация виртуального окружения..."
if [ -f "raket-2/venv/bin/activate" ]; then
    source raket-2/venv/bin/activate
    echo "✓ Виртуальное окружение активировано"
else
    echo "⚠️ Виртуальное окружение не найдено в raket-2/venv/"
    echo "Создание виртуального окружения..."
    cd raket-2
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
    echo "✓ Виртуальное окружение создано и зависимости установлены"
fi

# Очистка всех необходимых каталогов и файлов
echo "Очистка каталогов и файлов..."
rm -rf results/*
rm -f results/final.json
rm -rf src_analyse-2/reports/*
rm -f src_analyse-2/tokens/Final/final.json

# 2. Запуск run_scanner.sh
echo "Запуск run_scanner.sh..."
cd raket-2
./run_scanner.sh
cd ..

# 3. Копирование нового final.json
echo "Копирование нового final.json..."
cp raket-2/results/final.json src_analyse-2/tokens/Final/final.json

# 4. Запуск скрипта анализа
echo "Запуск скрипта анализа..."
cd src_analyse-2
./run_analysis.sh
cd ..

# 5. Копирование отчетов
echo "Копирование отчетов..."
cp -r src_analyse-2/reports/* results/

echo "=== Глобальный запуск завершен ===" 