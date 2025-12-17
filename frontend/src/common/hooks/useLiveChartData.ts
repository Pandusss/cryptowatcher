import { useState, useEffect, useCallback, useRef } from 'react'
import { apiService, type ChartDataPoint } from '../../services/api'
import { ChartPeriod } from '../../types/chart.types'
import { convertServerDateToLocal, getCurrentLocalTime } from '../../common/utils/chartTimeUtils'

interface UseLiveChartDataOptions {
  /** ID криптовалюты */
  coinId: string
  /** Начальный период графика */
  initialPeriod?: ChartPeriod
  /** Интервал обновления цены в миллисекундах (по умолчанию 5000) */
  updateInterval?: number
  /** Автоматически обновлять данные графика при изменении периода */
  autoUpdateChart?: boolean
}

interface UseLiveChartDataReturn {
  /** Данные графика */
  chartData: ChartDataPoint[]
  /** Текущая цена */
  currentPrice: number | null
  /** Направление изменения цены (up/down/neutral) */
  priceDirection: 'up' | 'down' | 'neutral' | null
  /** Флаг обновления цены для анимации */
  priceUpdated: boolean
  /** Флаг загрузки данных графика */
  chartLoading: boolean
  /** Ошибка загрузки */
  error: string | null
  /** Функция загрузки данных графика */
  loadChartData: (period: ChartPeriod) => Promise<void>
  /** Функция обновления текущей цены */
  updatePrice: () => Promise<void>
  /** Установить данные графика (например, из кэша) */
  setChartData: (data: ChartDataPoint[]) => void
  /** Установить текущую цену */
  setCurrentPrice: (price: number) => void
}

/**
 * Хук для управления данными графика криптовалюты с live-обновлением цены
 */
export const useLiveChartData = ({
  coinId,
  initialPeriod = '7d',
  updateInterval = 5000,
  autoUpdateChart = true,
}: UseLiveChartDataOptions): UseLiveChartDataReturn => {
  const [chartData, setChartData] = useState<ChartDataPoint[]>([])
  const [currentPrice, setCurrentPrice] = useState<number | null>(null)
  const [priceDirection, setPriceDirection] = useState<'up' | 'down' | 'neutral' | null>(null)
  const [priceUpdated, setPriceUpdated] = useState(false)
  const [chartLoading, setChartLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [period, setPeriod] = useState<ChartPeriod>(initialPeriod)
  
  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const previousPriceRef = useRef<number | null>(null)

  /**
   * Загрузка данных графика
   */
  const loadChartData = useCallback(async (newPeriod: ChartPeriod) => {
    if (!coinId) return
    
    try {
      setChartLoading(true)
      setError(null)
      const data = await apiService.getCoinChart(coinId, newPeriod)
      
      // КОНВЕРТИРУЕМ ВСЕ ДАННЫЕ в локальное время пользователя
      const convertedData = data.map(point => ({
        ...point,
        date: convertServerDateToLocal(point.date)
      }))
      
      setChartData(convertedData)
      setPeriod(newPeriod)
      
      // Если есть данные, устанавливаем последнюю цену как текущую
      if (convertedData.length > 0) {
        const lastPrice = convertedData[convertedData.length - 1].price
        setCurrentPrice(lastPrice)
        previousPriceRef.current = lastPrice
      }
    } catch (err) {
      console.error('Failed to load chart data:', err)
      setError('Не удалось загрузить данные графика')
      setChartData([])
    } finally {
      setChartLoading(false)
    }
  }, [coinId])

  /**
   * Обновление текущей цены
   */
/**
 * Обновление текущей цены (упрощенная версия)
 */
    const updatePrice = useCallback(async () => {
    if (!coinId) return
    
    try {
        const coinDetails = await apiService.getCoinDetails(coinId)
        if (coinDetails && coinDetails.currentPrice) {
        const newPrice = coinDetails.currentPrice
        
        // Определяем направление изменения цены
        if (previousPriceRef.current !== null) {
            if (newPrice > previousPriceRef.current) {
            setPriceDirection('up')
            } else if (newPrice < previousPriceRef.current) {
            setPriceDirection('down')
            } else {
            setPriceDirection('neutral')
            }
        }
        
        // Запускаем анимацию обновления
        setPriceUpdated(true)
        setTimeout(() => {
            setPriceUpdated(false)
            setPriceDirection(null)
        }, 800)
        
        // Обновляем текущую цену
        setCurrentPrice(newPrice)
        previousPriceRef.current = newPrice
        
        // Просто обновляем цену, не трогая время
        setChartData(prev => {
            if (prev.length === 0) return prev
            
            const updatedData = [...prev]
            const lastIndex = updatedData.length - 1
            
            updatedData[lastIndex] = {
            ...updatedData[lastIndex],
            price: newPrice,
            // Время оставляем как есть
            }
            
            return updatedData
        })
        }
    } catch (err) {
        console.error('Failed to update price:', err)
    }
    }, [coinId]) // <-- Только coinId

  /**
   * Инициализация: загрузка данных графика
   */
  useEffect(() => {
    if (coinId && autoUpdateChart) {
      loadChartData(period)
    }
  }, [coinId, period, loadChartData, autoUpdateChart])

  /**
   * Настройка интервала обновления цены
   */
  useEffect(() => {
    if (!coinId) return
    
    // Обновляем цену сразу при монтировании
    updatePrice()
    
    // Настраиваем интервал обновления
    intervalRef.current = setInterval(() => {
      updatePrice()
    }, updateInterval)
    
    // Очистка интервала при размонтировании
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [coinId, updateInterval, updatePrice])

  return {
    chartData,
    currentPrice,
    priceDirection,
    priceUpdated,
    chartLoading,
    error,
    loadChartData,
    updatePrice,
    setChartData,
    setCurrentPrice,
  }
}