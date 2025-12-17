// Тест конвертации времени
const { convertServerDateToLocal, parseDateString, formatDateForAxis } = require('./frontend/src/common/utils/chartTimeUtils.ts');

// Мокаем импорты
const mockChartPeriod = {
  '1d': '1d',
  '7d': '7d',
  '30d': '30d',
  '1y': '1y'
};

// Тестовые данные
console.log('Текущее время пользователя (UTC+3):', new Date().toString());
console.log('Текущее время UTC:', new Date().toISOString());

// Тест 1: ISO формат с часовым поясом UTC
const isoUTC = '2025-12-17T18:12:12+00:00'; // 18:12 UTC
console.log('\nТест 1: ISO формат UTC');
console.log('Вход:', isoUTC);
const local1 = convertServerDateToLocal(isoUTC);
console.log('Локальное время:', local1);
const parsed1 = parseDateString(local1);
console.log('Парсинг обратно:', parsed1.toString());
console.log('Часы локальные:', parsed1.getHours());

// Тест 2: Старый формат "YYYY-MM-DD HH:MM" (предполагается UTC)
const oldFormatUTC = '2025-12-17 18:12'; // 18:12 UTC
console.log('\nТест 2: Старый формат UTC');
console.log('Вход:', oldFormatUTC);
const local2 = convertServerDateToLocal(oldFormatUTC);
console.log('Локальное время:', local2);
const parsed2 = parseDateString(local2);
console.log('Парсинг обратно:', parsed2.toString());
console.log('Часы локальные:', parsed2.getHours());

// Тест 3: Форматирование для оси X
console.log('\nТест 3: Форматирование для оси X');
console.log('Для 1d:', formatDateForAxis(local1, '1d'));
console.log('Для 7d:', formatDateForAxis(local1, '7d'));
console.log('Для 30d:', formatDateForAxis(local1, '30d'));

// Тест 4: Разница во времени
const utcDate = new Date('2025-12-17T18:12:12Z');
const localDate = new Date(utcDate);
console.log('\nТест 4: Проверка смещения часового пояса');
console.log('UTC время:', utcDate.toISOString());
console.log('Локальное время JS:', localDate.toString());
console.log('Часы UTC:', utcDate.getUTCHours());
console.log('Часы локальные:', localDate.getHours());
console.log('Разница часов:', localDate.getHours() - utcDate.getUTCHours());