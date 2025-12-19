import { ChartPeriod } from '../../types/chart.types'
import { ChartDataPoint } from '../../services/api'

// Cached constants for date formatting
const WEEKDAYS = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']
const MONTHS = [
  'янв', 'фев', 'мар', 'апр', 'май', 'июн',
  'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'
] 

/**
 * Formats a Date object to string
 * @param date - Date object to format
 * @param format - 'full' returns "YYYY-MM-DD HH:MM", 'time-only' returns "HH:MM"
 */
const formatDateTime = (date: Date, format: 'full' | 'time-only' = 'full'): string => {
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  
  if (format === 'time-only') {
    return `${hours}:${minutes}`
  }
  
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

/**
 * Converts the server date (UTC) to the local time of the user
 */
export const convertServerDateToLocal = (serverDateStr: string): string => {
  try {
    // If this is an ISO format with a time zone
    if (serverDateStr.includes('T')) {
      const date = new Date(serverDateStr)
      return formatDateTime(date)
    }
    
    const [datePart, timePart] = serverDateStr.split(' ')
    if (!datePart || !timePart) return serverDateStr
    
    const [year, month, day] = datePart.split('-').map(Number)
    const [hours, minutes] = timePart.split(':').map(Number)
    
    // Create a date in UTC (explicit to ensure cross-browser compatibility)
    const utcDate = new Date(Date.UTC(year, month - 1, day, hours, minutes, 0))
    
    // Convert to local time
    return formatDateTime(utcDate)
  } catch (error) {
    console.error('Error converting date:', error, serverDateStr)
    return serverDateStr
  }
}

/**
 * Gets the current time for the last point (in the local time of the user)
 */
export const getCurrentLocalTime = (): string => {
  return formatDateTime(new Date())
}

/**
 * Parses a date from any format into a Date object
 * Supports:
 * - "YYYY-MM-DD HH:MM" (local time after conversion via convertServerDateToLocal)
 * - ISO format "2025-12-17T18:12:12+00:00" (with a time zone)
 */
export const parseDateString = (dateStr: string): Date => {
  try {
    // If this is an ISO format with a time zone
    if (dateStr.includes('T')) {
      return new Date(dateStr)
    }
    
    // If this is "YYYY-MM-DD HH:MM" (local time after conversion)
    const [datePart, timePart] = dateStr.split(' ')
    if (!datePart || !timePart) {
      return new Date(dateStr) // try standard parsing
    }
    
    const [year, month, day] = datePart.split('-').map(Number)
    const [hours, minutes] = timePart.split(':').map(Number)
    
    // Create a date in local time
    // Important: after convertServerDateToLocal, dates are already in local time
    return new Date(year, month - 1, day, hours, minutes, 0)
  } catch (error) {
    console.error('Error parsing date string:', error, dateStr)
    return new Date(dateStr)
  }
}

/**
 * Formats the date for the X axis depending on the period
 */
export const formatDateForAxis = (dateStr: string, period: ChartPeriod): string => {
  try {
    const date = parseDateString(dateStr)
    
    switch (period) {
      case '1d':
        // Hours:minutes (e.g. "15:30")
        return formatDateTime(date, 'time-only')
        
      case '7d':
        // Day of the week (e.g. "Mon", "Tue")
        return WEEKDAYS[date.getDay()]
        
      case '30d':
      case '1y':
        // Date in the format "17 dec"
        return `${date.getDate()} ${MONTHS[date.getMonth()]}`
        
      default:
        return dateStr
    }
  } catch (error) {
    console.error('Error formatting date:', error, dateStr)
    return dateStr
  }
}

/**
 * Formats the date for the tooltip in local time
 */
export const formatDateForTooltip = (dateStr: string, period: ChartPeriod): string => {
  try {
    const date = parseDateString(dateStr)
    
    // Format the full date and time
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
 * Gets ticks for the X axis taking into account local time
 */
export const getXAxisTicks = (data: ChartDataPoint[], period: ChartPeriod): string[] | undefined => {
  if (data.length === 0) return undefined
  
  // For 1D, show every 3 hours in local time
  if (period === '1d') {
    const ticks: string[] = []
    
    // Convert all dates to Date objects
    const dates = data.map(point => parseDateString(point.date))
    
    // Find the minimum and maximum hour in local time
    const minHour = Math.min(...dates.map(d => d.getHours()))
    const maxHour = Math.max(...dates.map(d => d.getHours()))
    
    // Generate hours, multiple of 3
    const startHour = Math.floor(minHour / 3) * 3
    const endHour = Math.ceil(maxHour / 3) * 3
    
    for (let hour = startHour; hour <= endHour; hour += 3) {
      // Find the closest point to this hour
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
    
    // Sort ticks by date
    return ticks.length > 0 ? ticks.sort((a, b) => {
      const dateA = parseDateString(a).getTime()
      const dateB = parseDateString(b).getTime()
      return dateA - dateB
    }) : undefined
  }
  
  // For the rest of the periods, the standard logic
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