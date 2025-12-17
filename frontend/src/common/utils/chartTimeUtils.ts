import { ChartPeriod } from '../../types/chart.types'
import { ChartDataPoint } from '../../services/api'

/**
 * Конвертирует дату сервера (UTC+3) в локальное время пользователя
 */
export const convertServerDateToLocal = (serverDateStr: string): string => {
  // Сервер отдает "YYYY-MM-DD HH:MM" в неизвестном часовом поясе
  const [datePart, timePart] = serverDateStr.split(' ')
  if (!datePart || !timePart) return serverDateStr
  
  const [year, month, day] = datePart.split('-').map(Number)
  const [hours, minutes] = timePart.split(':').map(Number)
  
  // Шаг 1: Создаем дату в предположении, что это локальное время
  // (браузер интерпретирует как локальное время)
  const localDate = new Date(year, month - 1, day, hours, minutes, 0)
  
  // Шаг 2: Форматируем как локальное время (оно уже локальное)
  const localYear = localDate.getFullYear()
  const localMonth = String(localDate.getMonth() + 1).padStart(2, '0')
  const localDay = String(localDate.getDate()).padStart(2, '0')
  const localHours = String(localDate.getHours()).padStart(2, '0')
  const localMinutes = String(localDate.getMinutes()).padStart(2, '0')
  
  return `${localYear}-${localMonth}-${localDay} ${localHours}:${localMinutes}`
}

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
 * Форматирует дату для оси X в зависимости от периода (работает с локальным временем)
 */
export const formatDateForAxis = (dateStr: string, period: ChartPeriod): string => {
  try {
    // dateStr в локальном времени пользователя: "YYYY-MM-DD HH:MM"
    const [datePart, timePart] = dateStr.split(' ')
    if (!datePart || !timePart) return dateStr
    
    const [year, month, day] = datePart.split('-').map(Number)
    const [hours, minutes] = timePart.split(':').map(Number)
    
    const date = new Date(year, month - 1, day, hours, minutes, 0)
    
    switch (period) {
      case '1d':
        // Часы:минуты (например: "15:30")
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
        
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
        return `${day} ${months[month - 1]}`
        
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
    // dateStr в локальном времени пользователя: "YYYY-MM-DD HH:MM"
    const [datePart, timePart] = dateStr.split(' ')
    if (!datePart || !timePart) return dateStr
    
    const [year, month, day] = datePart.split('-').map(Number)
    const [hours, minutes] = timePart.split(':').map(Number)
    
    const date = new Date(year, month - 1, day, hours, minutes, 0)
    
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
    const dates = data.map(point => {
      const [datePart, timePart] = point.date.split(' ')
      const [year, month, day] = datePart.split('-').map(Number)
      const [hours, minutes] = timePart.split(':').map(Number)
      return new Date(year, month - 1, day, hours, minutes, 0)
    })
    
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
    
    return ticks.length > 0 ? ticks.sort() : undefined
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