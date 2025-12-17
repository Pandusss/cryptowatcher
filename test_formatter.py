#!/usr/bin/env python3
import sys
sys.path.insert(0, 'backend')

from datetime import datetime, timezone
from app.utils.formatters import format_chart_date

print('Тестирование новой функции format_chart_date:')

# Создаем дату в UTC
test_date = datetime(2025, 12, 17, 18, 12, 12, tzinfo=timezone.utc)
print(f'Исходная дата (UTC): {test_date.isoformat()}')

# Тестируем для разных периодов
for period in ['1d', '7d', '30d', '1y']:
    result = format_chart_date(test_date, period)
    print(f'Период {period}: {result}')
    
# Тест без часового пояса
test_date_no_tz = datetime(2025, 12, 17, 18, 12, 12)
print(f'\nДата без часового пояса: {test_date_no_tz}')
for period in ['1d', '7d']:
    result = format_chart_date(test_date_no_tz, period)
    print(f'Период {period}: {result}')

# Проверка, что результат содержит 'T' и '+00:00' (ISO формат с часовым поясом)
print('\nПроверка формата:')
for period in ['1d', '7d', '30d', '1y']:
    result = format_chart_date(test_date, period)
    has_t = 'T' in result
    has_timezone = '+00:00' in result
    print(f'Период {period}: содержит "T"={has_t}, содержит "+00:00"={has_timezone}, результат={result}')