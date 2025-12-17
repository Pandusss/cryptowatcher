import { ChartPeriod } from '../../types/chart.types'
import { ChartDataPoint } from '../../services/api'

/**
 * Конвертирует UTC дату с сервера в локальное время пользователя
 * Сервер отдает: "2025-12-17T18:12:12+00:00" (ISO формат с часовым поясом)
 */
/**
 * Конвертирует дату сервера (UTC) в локальное время пользователя
 */
// chartTimeUtils.ts
export const convertServerDateToLocal = (serverDateStr: string): string => {
  try {
    // Если это ISO формат с часовым поясом
    if (serverDateStr.includes('T')) {
      const date = new Date(serverDateStr);
      return formatLocalDateTime(date);
    }
    
    // Старый формат "YYYY-MM-DD HH:MM" - предполагаем UTC
    const [datePart, timePart] = serverDateStr.split(' ');
    if (!datePart || !timePart) return serverDateStr;
    
    const [year, month, day] = datePart.split('-').map(Number);
    const [hours, minutes] = timePart.split(':').map(Number);
    
    // Создаем дату в UTC
    const utcDate = new Date(Date.UTC(year, month - 1, day, hours, minutes, 0));
    
    // Конвертируем в локальное время
    return formatLocalDateTime(utcDate);
  } catch (error) {
    console.error('Error converting date:', error, serverDateStr);
    return serverDateStr;
  }
};

const formatLocalDateTime = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  
  return `${year}-${month}-${day} ${hours}:${minutes}`;
};

/**
 * Получает текущее время для последней точки (в локальном времени пользователя)
 */
export const getCurrentLocalTime = (): string => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const hours = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

/**
 * Парсит дату из любого формата в объект Date
 * Поддерживает:
 * - "YYYY-MM-DD HH:MM" (локальное время после конвертации через convertServerDateToLocal)
 * - ISO формат "2025-12-17T18:12:12+00:00" (с часовым поясом)
 */
export const parseDateString = (dateStr: string): Date => {
  try {
    // Если это ISO формат с часовым поясом
    if (dateStr.includes('T')) {
      return new Date(dateStr)
    }
    
    // Если это "YYYY-MM-DD HH:MM" (локальное время после конвертации)
    const [datePart, timePart] = dateStr.split(' ')
    if (!datePart || !timePart) {
      return new Date(dateStr) // пробуем стандартный парсинг
    }
    
    const [year, month, day] = datePart.split('-').map(Number)
    const [hours, minutes] = timePart.split(':').map(Number)
    
    // Создаем дату в локальном времени
    // Важно: после convertServerDateToLocal даты уже в локальном времени
    return new Date(year, month - 1, day, hours, minutes, 0)
  } catch (error) {
    console.error('Error parsing date string:', error, dateStr)
    return new Date(dateStr)
  }
}

/**
 * Форматирует дату для оси X в зависимости от периода
 */
export const formatDateForAxis = (dateStr: string, period: ChartPeriod): string => {
  try {
    const date = parseDateString(dateStr)
    
    switch (period) {
      case '1d':
        // Часы:минуты (например: "15:30")
        const hours = String(date.getHours()).padStart(2, '0')
        const minutes = String(date.getMinutes()).padStart(2, '0')
        return `${hours}:${minutes}`
        
      case '7d':
        // День недели (например: "Пн", "Вт")
        const weekdays = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']
        return weekdays[date.getDay()]
        
      case '30d':
      case '1y':
        // Дата в формате "17 дек"
        const months = [
          'янв', 'фев', 'мар', 'апр', 'май', 'июн',
          'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'
        ]
        const day = date.getDate()
        const monthIndex = date.getMonth()
        return `${day} ${months[monthIndex]}`
        
      default:
        return dateStr
    }
  } catch (error) {
    console.error('Error formatting date:', error, dateStr)
    return dateStr
  }
}

/**
 * Форматирует дату для тултипа в локальном времени
 */
export const formatDateForTooltip = (dateStr: string, period: ChartPeriod): string => {
  try {
    const date = parseDateString(dateStr)
    
    // Форматируем полную дату и время
    const formattedDate = date.toLocaleString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    })
    
    return formattedDate
  } catch (error) {
    console.error('Error formatting tooltip date:', error, dateStr)
    return dateStr
  }
}

/**
 * Получает тики для оси X с учетом локального времени
 */
export const getXAxisTicks = (data: ChartDataPoint[], period: ChartPeriod): string[] | undefined => {
  if (data.length === 0) return undefined
  
  // Для 1D показываем каждые 3 часа в локальном времени
  if (period === '1d') {
    const ticks: string[] = []
    
    // Преобразуем все даты в объекты Date
    const dates = data.map(point => parseDateString(point.date))
    
    // Находим минимальный и максимальный час в локальном времени
    const minHour = Math.min(...dates.map(d => d.getHours()))
    const maxHour = Math.max(...dates.map(d => d.getHours()))
    
    // Генерируем часы, кратные 3
    const startHour = Math.floor(minHour / 3) * 3
    const endHour = Math.ceil(maxHour / 3) * 3
    
    for (let hour = startHour; hour <= endHour; hour += 3) {
      // Находим ближайшую точку к этому часу
      let closestIndex = 0
      let minDiff = Infinity
      
      dates.forEach((date, index) => {
        const diff = Math.abs(date.getHours() - hour)
        if (diff < minDiff) {
          minDiff = diff
          closestIndex = index
        }
      })
      
      if (closestIndex >= 0 && !ticks.includes(data[closestIndex].date)) {
        ticks.push(data[closestIndex].date)
      }
    }
    
    // Сортируем тики по дате
    return ticks.length > 0 ? ticks.sort((a, b) => {
      const dateA = parseDateString(a).getTime()
      const dateB = parseDateString(b).getTime()
      return dateA - dateB
    }) : undefined
  }
  
  // Для остальных периодов стандартная логика
  const optimalCount = period === '7d' ? 7 : 6
  const totalPoints = data.length
  
  if (totalPoints <= optimalCount) {
    return data.map(item => item.date)
  }
  
  const step = Math.floor((totalPoints - 1) / (optimalCount - 1))
  const ticks: string[] = []
  
  ticks.push(data[0].date)
  
  for (let i = step; i < totalPoints - 1; i += step) {
    if (ticks.length < optimalCount - 1) {
      ticks.push(data[i].date)
    }
  }
  
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