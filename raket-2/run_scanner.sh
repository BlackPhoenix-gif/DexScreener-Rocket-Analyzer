#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧹 Очистка старых данных...${NC}"

# Активация виртуального окружения
echo -e "${BLUE}🔧 Активация виртуального окружения...${NC}"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✓ Виртуальное окружение активировано${NC}"
else
    echo -e "${YELLOW}⚠️ Виртуальное окружение не найдено в venv/${NC}"
    echo -e "${YELLOW}Попытка запуска без виртуального окружения...${NC}"
fi

# Очистка логов
if [ -d "logs" ]; then
    rm -rf logs/*
    echo -e "${GREEN}✓ Логи очищены${NC}"
fi

# Создание директории для логов если её нет
mkdir -p logs

# Очистка результатов
if [ -d "results" ]; then
    rm -f results/final.json results/final_hour.json
    echo -e "${GREEN}✓ Старые результаты удалены${NC}"
fi

# Создание директории для результатов если её нет
mkdir -p results

# Создание директории для кэша если её нет
mkdir -p cache

echo -e "${BLUE}🚀 Запуск сканера...${NC}"

# Установка PYTHONPATH и запуск сканера
export PYTHONPATH=$PYTHONPATH:.
python3 src/api/token_scanner.py

echo -e "${GREEN}✓ Сканирование завершено${NC}"
echo -e "${BLUE}📊 Результаты сохранены в:${NC}"
echo -e "${BLUE}- results/final.json (суточные результаты)${NC}"
echo -e "${BLUE}- results/final_hour.json (часовые результаты)${NC}" 