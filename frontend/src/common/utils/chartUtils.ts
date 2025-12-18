/**
 * Utilities for working with cryptocurrency charts
 */

import { ChartPeriod } from '../../types/chart.types'
import { ChartDataPoint } from '../../services/api'

import { 
  formatDateForAxis, 
  formatDateForTooltip, 
  getXAxisTicks 
} from './chartTimeUtils'

/**
 * Determines the color of the chart based on the trend
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
 * Calculates a uniform range for the Y axis
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
  
  // If there are trigger levels, consider them in the range calculation
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
  
  // Use percentage relationship for all coins:
  // For 1D timeframe, use a smaller percentage (8%), for the rest - 15%
  const relativeRangePercent = avgPrice > 0 ? range / avgPrice : 0
  const targetPercent = period === '1d' ? 0.08 : 0.15 // 8% for 1D, 15% for the rest
  
  let adjustedMin = minPrice
  let adjustedMax = maxPrice
  
  if (avgPrice > 0 && relativeRangePercent < targetPercent) {
    // Expand the range to targetPercent from the average price for better visibility
    const targetRange = avgPrice * targetPercent
    
    // Calculate how much data is offset from the center
    const dataCenter = avgPrice
    const dataRange = range
    
    // Expand proportionally: expand more in the direction where there is more data
    const expansionNeeded = targetRange - dataRange
    
    if (expansionNeeded > 0) {
      // Calculate the offset of data from the center of the range
      const rangeCenter = (minPrice + maxPrice) / 2
      const offsetFromCenter = dataCenter - rangeCenter
      
      // Expand more in the direction of the data offset
      const expansionDown = expansionNeeded * (0.5 + Math.max(0, -offsetFromCenter) / dataRange)
      const expansionUp = expansionNeeded * (0.5 + Math.max(0, offsetFromCenter) / dataRange)
      
      adjustedMin = Math.max(0, minPrice - expansionDown)
      adjustedMax = maxPrice + expansionUp
    }
  } else {
    // If the range is already large enough, use standard padding
    const padding = Math.max(range * 0.05, minPrice * 0.01)
    adjustedMin = Math.max(0, minPrice - padding)
    adjustedMax = maxPrice + padding
  }
  
  // Determine the rounding step based on the range
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
  
  // Round to the nearest value with the step
  adjustedMin = Math.floor(adjustedMin / step) * step
  adjustedMax = Math.ceil(adjustedMax / step) * step
  
  // Make sure min < max
  if (adjustedMin >= adjustedMax) {
    adjustedMax = adjustedMin + step * 2
  }
  
  return [adjustedMin, adjustedMax]
}

/**
 * Generates ticks for the Y axis
 */
export const getYAxisTicks = (domain: [number, number], tickCount: number = 5): number[] | undefined => {
  const [min, max] = domain
  const range = max - min
  
  if (range === 0) return undefined
  
  // Determine the number of significant digits for rounding based on the range
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
  
  // Remove duplicates
  const uniqueTicks = Array.from(new Set(ticks))
  
  return uniqueTicks.length > 0 ? uniqueTicks : undefined
}

/**
 * Calculates the domain for volumes - limit their height to 30% of the chart
 */
export const getVolumeDomain = (data: ChartDataPoint[]): [number, number] => {
  if (data.length === 0) return [0, 1]
  
  const volumes = data.map(item => item.volume || 0).filter(v => v > 0)
  if (volumes.length === 0) return [0, 1]
  
  const maxVolume = Math.max(...volumes)
  // Increase the maximum value by 2 times, so that volumes occupy only ~30% of the height
  return [0, maxVolume * 2]
}

/**
 * Formatting the volume
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
 * Formatting the price for the Y axis (with K for thousands, M for millions)
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
  // For large values, add dots for thousands
  const parts = value.toFixed(0).split('.')
  const integerPart = parts[0]
  const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return `$${formattedInteger}`
}

/**
 * Formatting the price for tooltip (with K for thousands, M for millions)
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
 * Calculates all necessary values for the chart
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

// Export functions for working with dates for backward compatibility
export { 
  formatDateForAxis, 
  formatDateForTooltip, 
  getXAxisTicks 
} from './chartTimeUtils'