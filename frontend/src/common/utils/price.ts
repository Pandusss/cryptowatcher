/**
 * Утилиты для работы с ценами криптовалют
 */

/**
 * Определяет количество знаков после запятой на основе цены
 * @param price - Цена криптовалюты
 * @param cachedDecimals - Опциональное кэшированное значение из API
 * @returns Количество знаков после запятой (от 2 до 10)
 */
export const getPriceDecimals = (price: number, cachedDecimals?: number): number => {
  // Если есть кэшированное значение из API, используем его
  if (cachedDecimals !== undefined) {
    return cachedDecimals
  }
  
  // Иначе вычисляем локально на основе цены
  if (price >= 1) return 2
  if (price >= 0.1) return 3
  if (price >= 0.01) return 4
  if (price >= 0.001) return 5
  if (price >= 0.0001) return 6
  if (price >= 0.00001) return 7
  if (price >= 0.000001) return 8
  if (price >= 0.0000001) return 9
  return 10
}

