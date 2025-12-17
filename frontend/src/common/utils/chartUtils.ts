/**
 * Утилиты для работы с графиками криптовалют
 */

import { ChartPeriod } from '../../types/chart.types'
import { ChartDataPoint } from '../../services/api'

/**
 * Определяет цвет графика на основе тренда
 */
export const getChartColor = (data: ChartDataPoint[]): string => {
  if (data.length < 2) {
    return 'var(--color-state-success)'
  }
  const firstPrice = data[0]?.price || 0
  const lastPrice = data[data.length - 1]?.price || 0
  return lastPrice >= firstPrice 
    ? 'var(--color-state-success)' 
    : 'var(--color-state-destructive)'
}

/**
 * Рассчитывает равномерный диапазон для оси Y
 */
export const getYAxisDomain = (
  data: ChartDataPoint[], 
  period: ChartPeriod,
  triggerLevels?: { upper?: number; lower?: number }
): [number, number] => {
  if (data.length === 0) return [0, 1]
  
  const prices = data.map(item => item.price).filter(p => p > 0)
  if (prices.length === 0) return [0, 1]
  
  let minPrice = Math.min(...prices)
  let maxPrice = Math.max(...prices)
  
  // Если есть уровни триггеров, учитываем их в расчете диапазона
  if (triggerLevels) {
    if (triggerLevels.upper !== undefined) {
      minPrice = Math.min(minPrice, triggerLevels.upper)
      maxPrice = Math.max(maxPrice, triggerLevels.upper)
    }
    if (triggerLevels.lower !== undefined) {
      minPrice = Math.min(minPrice, triggerLevels.lower)
      maxPrice = Math.max(maxPrice, triggerLevels.lower)
    }
  }
  
  const range = maxPrice - minPrice
  const avgPrice = (minPrice + maxPrice) / 2
  
  // Используем процентное соотношение для всех монет:
  // Для 1D таймфрейма используем меньший процент (8%), для остальных - 15%
  const relativeRangePercent = avgPrice > 0 ? range / avgPrice : 0
  const targetPercent = period === '1d' ? 0.08 : 0.15 // 8% для 1D, 15% для остальных
  
  let adjustedMin = minPrice
  let adjustedMax = maxPrice
  
  if (avgPrice > 0 && relativeRangePercent < targetPercent) {
    // Расширяем диапазон до targetPercent от средней цены для лучшей видимости
    const targetRange = avgPrice * targetPercent
    
    // Вычисляем, насколько данные смещены от центра
    const dataCenter = avgPrice
    const dataRange = range
    
    // Расширяем пропорционально: больше расширяем в сторону, где больше данных
    const expansionNeeded = targetRange - dataRange
    
    if (expansionNeeded > 0) {
      // Вычисляем смещение данных от центра диапазона
      const rangeCenter = (minPrice + maxPrice) / 2
      const offsetFromCenter = dataCenter - rangeCenter
      
      // Расширяем больше в сторону смещения данных
      const expansionDown = expansionNeeded * (0.5 + Math.max(0, -offsetFromCenter) / dataRange)
      const expansionUp = expansionNeeded * (0.5 + Math.max(0, offsetFromCenter) / dataRange)
      
      adjustedMin = Math.max(0, minPrice - expansionDown)
      adjustedMax = maxPrice + expansionUp
    }
  } else {
    // Если диапазон уже достаточно большой, используем стандартный padding
    const padding = Math.max(range * 0.05, minPrice * 0.01)
    adjustedMin = Math.max(0, minPrice - padding)
    adjustedMax = maxPrice + padding
  }
  
  // Определяем шаг округления на основе диапазона
  const finalRange = adjustedMax - adjustedMin
  let step: number
  if (finalRange >= 10000) {
    step = 2000
  } else if (finalRange >= 1000) {
    step = 200
  } else if (finalRange >= 100) {
    step = 20
  } else if (finalRange >= 10) {
    step = 2
  } else if (finalRange >= 1) {
    step = 0.2
  } else if (finalRange >= 0.1) {
    step = 0.02
  } else if (finalRange >= 0.01) {
    step = 0.002
  } else if (finalRange >= 0.001) {
    step = 0.0002
  } else if (finalRange >= 0.0001) {
    step = 0.00002
  } else if (finalRange >= 0.00001) {
    step = 0.000002
  } else if (finalRange >= 0.000001) {
    step = 0.0000002
  } else {
    step = 0.00000002
  }
  
  // Округляем до ближайшего значения с учетом шага
  adjustedMin = Math.floor(adjustedMin / step) * step
  adjustedMax = Math.ceil(adjustedMax / step) * step
  
  // Убеждаемся, что min < max
  if (adjustedMin >= adjustedMax) {
    adjustedMax = adjustedMin + step * 2
  }
  
  return [adjustedMin, adjustedMax]
}

/**
 * Генерирует тики для оси Y
 */
export const getYAxisTicks = (domain: [number, number], tickCount: number = 5): number[] | undefined => {
  const [min, max] = domain
  const range = max - min
  
  if (range === 0) return undefined
  
  // Определяем количество значащих цифр для округления на основе диапазона
  const getSignificantDigits = (val: number): number => {
    if (val >= 1000) return 0
    if (val >= 100) return 1
    if (val >= 10) return 1
    if (val >= 1) return 2
    if (val >= 0.1) return 3
    if (val >= 0.01) return 4
    if (val >= 0.001) return 5
    if (val >= 0.0001) return 6
    if (val >= 0.00001) return 7
    if (val >= 0.000001) return 8
    return 9
  }
  
  const step = range / (tickCount - 1)
  const significantDigits = getSignificantDigits(range)
  const multiplier = Math.pow(10, significantDigits)
  
  const ticks: number[] = []
  
  for (let i = 0; i < tickCount; i++) {
    const tickValue = min + (step * i)
    const roundedTick = Math.round(tickValue * multiplier) / multiplier
    ticks.push(roundedTick)
  }
  
  // Убираем дубликаты
  const uniqueTicks = Array.from(new Set(ticks))
  
  return uniqueTicks.length > 0 ? uniqueTicks : undefined
}

/**
 * Рассчитывает домен для объемов - ограничиваем их высоту до 30% от графика
 */
export const getVolumeDomain = (data: ChartDataPoint[]): [number, number] => {
  if (data.length === 0) return [0, 1]
  
  const volumes = data.map(item => item.volume || 0).filter(v => v > 0)
  if (volumes.length === 0) return [0, 1]
  
  const maxVolume = Math.max(...volumes)
  // Увеличиваем максимальное значение в 2 раза, чтобы объемы занимали только ~30% высоты
  return [0, maxVolume * 2]
}

/**
 * Форматирование объема
 */
export const formatVolume = (volume: number): string => {
  if (volume >= 1000000000) {
    return `$${(volume / 1000000000).toFixed(2)}B`
  }
  if (volume >= 1000000) {
    return `$${(volume / 1000000).toFixed(2)}M`
  }
  if (volume >= 1000) {
    return `$${(volume / 1000).toFixed(2)}K`
  }
  return `$${volume.toFixed(2)}`
}

/**
 * Форматирование цены для оси Y (с K для тысяч, M для миллионов)
 */
export const formatPriceForYAxis = (value: number, priceDecimals: number = 2): string => {
  if (value >= 1000000) {
    const formatted = (value / 1000000).toFixed(1).replace('.', ',')
    return `$${formatted}M`
  }
  if (value >= 1000) {
    const formatted = (value / 1000).toFixed(1).replace('.', ',')
    return `$${formatted}K`
  }
  if (value < 1) {
    return `$${value.toFixed(priceDecimals).replace('.', ',')}`
  }
  if (value < 10) {
    return `$${value.toFixed(priceDecimals).replace('.', ',')}`
  }
  if (value < 100) {
    return `$${value.toFixed(Math.min(priceDecimals, 1)).replace('.', ',')}`
  }
  // Для больших значений добавляем точки для тысяч
  const parts = value.toFixed(0).split('.')
  const integerPart = parts[0]
  const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return `$${formattedInteger}`
}

/**
 * Форматирование цены для tooltip (с K для тысяч, M для миллионов)
 */
export const formatPriceForTooltip = (price: number, priceDecimals: number = 2): string => {
  if (price >= 1000000) {
    const value = (price / 1000000).toFixed(2)
    return `$${value.replace('.', ',')}M`
  }
  if (price >= 1000) {
    const value = (price / 1000).toFixed(2)
    return `$${value.replace('.', ',')}K`
  }
  const value = price.toFixed(priceDecimals)
  return `$${value.replace('.', ',')}`
}

/**
 * Форматирование даты для оси X в зависимости от периода
 */
export const formatDateForAxis = (dateStr: string, period: ChartPeriod): string => {
  try {
    const [datePart, timePart] = dateStr.split(' ')
    if (!datePart || !timePart) return dateStr
    
    const [year, month, day] = datePart.split('-').map(Number)
    const timeParts = timePart.split(':')
    const hours = Number(timeParts[0]) || 0
    const minutes = Number(timeParts[1]) || 0
    
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const monthShort = monthNames[month - 1]
    
    switch (period) {
      case '1d':
        // Для 1D показываем фиксированное время (HH:00) - округленное до часа, кратного 3
        let roundedHour = Math.floor(hours / 3) * 3
        
        // Если мы прошли больше половины интервала (>= 1.5 часа), показываем следующий час
        const remainder = hours % 3
        if (remainder >= 2 || (remainder === 1 && minutes >= 30)) {
          roundedHour = (Math.floor(hours / 3) + 1) * 3
        }
        
        // Обрабатываем переход через полночь
        roundedHour = roundedHour % 24
        
        return `${String(roundedHour).padStart(2, '0')}:00`
      case '7d':
      case '30d':
      case '1y':
        // Показываем только месяц и день (MMM DD) - короткий формат
        return `${monthShort} ${day}`
      default:
        return dateStr
    }
  } catch {
    return dateStr
  }
}

/**
 * Форматирование даты для tooltip
 */
export const formatDateForTooltip = (dateStr: string, period: ChartPeriod): string => {
  try {
    const date = new Date(dateStr)
    const day = date.getDate()
    const month = date.toLocaleDateString('en-US', { month: 'short' })
    const hours = date.getHours()
    const minutes = date.getMinutes()
    
    if (period === '7d') {
      // Для периода 7D показываем только часы (без минут)
      const formattedTime = date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        hour12: true
      })
      return `${day} ${month} ${formattedTime}`
    }
    
    // Для остальных периодов показываем часы и минуты
    const formattedTime = date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    })
    
    return `${day} ${month} ${formattedTime}`
  } catch {
    return dateStr
  }
}

/**
 * Получает тики для оси X в зависимости от периода
 */
export const getXAxisTicks = (data: ChartDataPoint[], period: ChartPeriod): string[] | undefined => {
  if (data.length === 0) return undefined
  
  // Для 1D таймфрейма показываем фиксированные временные метки каждые 3 часа
  if (period === '1d') {
    const ticks: string[] = []
    const threeHoursInMs = 3 * 60 * 60 * 1000 // 3 часа в миллисекундах
    
    const firstDate = new Date(data[0].date)
    const lastDate = new Date(data[data.length - 1].date)
    const firstTime = firstDate.getTime()
    const lastTime = lastDate.getTime()
    
    // Находим первый час, кратный 3, который >= первой даты
    const firstHour = firstDate.getHours()
    const firstRoundedHour = Math.floor(firstHour / 3) * 3
    const startTick = new Date(firstDate)
    startTick.setHours(firstRoundedHour, 0, 0, 0)
    
    // Если округленный час меньше текущего часа, добавляем 3 часа
    if (startTick.getTime() < firstTime) {
      startTick.setHours(startTick.getHours() + 3)
    }
    
    // Генерируем фиксированные временные метки каждые 3 часа
    let currentTick = startTick.getTime()
    
    while (currentTick <= lastTime) {
      // Находим ближайшую точку данных к текущему тику
      let closestIndex = 0
      let minDiff = Math.abs(new Date(data[0].date).getTime() - currentTick)
      
      for (let i = 1; i < data.length; i++) {
        const diff = Math.abs(new Date(data[i].date).getTime() - currentTick)
        if (diff < minDiff) {
          minDiff = diff
          closestIndex = i
        }
      }
      
      // Добавляем тик, если он еще не добавлен
      const tickDate = data[closestIndex].date
      if (!ticks.includes(tickDate)) {
        ticks.push(tickDate)
      }
      
      // Переходим к следующему 3-часовому интервалу
      currentTick += threeHoursInMs
    }
    
    return ticks.length > 0 ? ticks : undefined
  }
  
  // Для остальных таймфреймов используем стандартную логику
  const optimalCount = period === '7d' ? 7 : 6
  const totalPoints = data.length
  
  // Если точек меньше или равно оптимальному количеству, показываем все
  if (totalPoints <= optimalCount) {
    return data.map(item => item.date)
  }
  
  // Рассчитываем шаг для равномерного распределения
  // Всегда включаем первую и последнюю точку
  const step = Math.floor((totalPoints - 1) / (optimalCount - 1))
  const ticks: string[] = []
  
  // Добавляем первую точку
  ticks.push(data[0].date)
  
  // Добавляем промежуточные точки с равномерным шагом
  for (let i = step; i < totalPoints - 1; i += step) {
    if (ticks.length < optimalCount - 1) {
      ticks.push(data[i].date)
    }
  }
  
  // Добавляем последнюю точку (если еще не добавлена)
  const lastDate = data[totalPoints - 1].date
  if (ticks[ticks.length - 1] !== lastDate) {
    if (ticks.length >= optimalCount) {
      ticks[ticks.length - 1] = lastDate
    } else {
      ticks.push(lastDate)
    }
  }
  
  return ticks.length > 0 ? ticks : undefined
}

/**
 * Рассчитывает все необходимые значения для графика
 */
export const calculateChartValues = (
  data: ChartDataPoint[],
  period: ChartPeriod,
  priceDecimals: number = 2,
  triggerLevels?: { upper?: number; lower?: number }
) => {
  const chartColor = getChartColor(data)
  const yAxisDomain = getYAxisDomain(data, period, triggerLevels)
  const yAxisTicks = getYAxisTicks(yAxisDomain)
  const volumeDomain = getVolumeDomain(data)
  const xAxisTicks = getXAxisTicks(data, period)
  
  return {
    chartColor,
    yAxisDomain,
    yAxisTicks,
    volumeDomain,
    xAxisTicks,
    minPrice: data.length > 0 ? Math.min(...data.map(d => d.price)) : 0,
    maxPrice: data.length > 0 ? Math.max(...data.map(d => d.price)) : 0,
    minVolume: data.length > 0 ? Math.min(...data.map(d => d.volume || 0)) : 0,
    maxVolume: data.length > 0 ? Math.max(...data.map(d => d.volume || 0)) : 0,
  }
}