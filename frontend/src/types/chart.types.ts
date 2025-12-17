/**
 * Типы для компонентов графиков криптовалют
 */

import { ChartDataPoint } from '../services/api'

export type ChartPeriod = '1d' | '7d' | '30d' | '1y'

export interface ChartOptions {
  /** Показывать ли объемы */
  showVolume?: boolean
  /** Цвет графика (если не указан, будет определен автоматически) */
  color?: string
  /** Показывать ли анимацию обновления цены */
  showPriceAnimation?: boolean
  /** Высота графика в пикселях */
  height?: number
  /** Отступы графика */
  margin?: {
    top?: number
    right?: number
    left?: number
    bottom?: number
  }
  /** Показывать ли текущую цену как линию */
  showCurrentPriceLine?: boolean
  /** Показывать ли линии триггеров */
  showTriggerLines?: boolean
  /** Настройки линий триггеров */
  triggerLines?: {
    upper?: {
      value: number
      label: string
      color?: string
    }
    lower?: {
      value: number
      label: string
      color?: string
    }
  }
  /** Форматирование оси Y */
  yAxisFormatter?: (value: number) => string
  /** Форматирование тултипов */
  tooltipFormatter?: {
    price?: (value: number) => string
    volume?: (value: number) => string
    date?: (dateStr: string) => string
  }
}

export interface CryptoChartProps {
  /** Данные графика */
  data: ChartDataPoint[]
  /** Период графика */
  period: ChartPeriod
  /** Текущая цена (для анимации и линии) */
  currentPrice?: number
  /** Опции графика */
  options?: ChartOptions
  /** Коллбэк при изменении периода */
  onPeriodChange?: (period: ChartPeriod) => void
  /** Загрузка данных */
  isLoading?: boolean
  /** Ошибка загрузки */
  error?: string | null
  /** Количество знаков после запятой для форматирования цены */
  priceDecimals?: number
}

export interface ChartCalculations {
  /** Минимальное значение цены в данных */
  minPrice: number
  /** Максимальное значение цены в данных */
  maxPrice: number
  /** Минимальное значение объема в данных */
  minVolume: number
  /** Максимальное значение объема в данных */
  maxVolume: number
  /** Цвет графика на основе тренда */
  chartColor: string
  /** Домен оси Y */
  yAxisDomain: [number, number]
  /** Тики оси Y */
  yAxisTicks?: number[]
  /** Домен оси объемов */
  volumeDomain: [number, number]
  /** Тики оси X */
  xAxisTicks?: string[]
}