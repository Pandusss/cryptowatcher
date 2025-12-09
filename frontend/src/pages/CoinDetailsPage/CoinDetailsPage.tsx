import {
    Block,
    Button,
    CryptoIcon,
    PageLayout,
    Text,
  } from '@components'
  import { useEffect, useState } from 'react'
  import { useLocation, useNavigate, useParams } from 'react-router-dom'
  import {
    Area,
    Bar,
    ComposedChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
  } from 'recharts'
  
  import { ROUTES_NAME } from '../../constants/routes'
  import type { CryptoCurrency } from '@types'
  import { apiService } from '../../services/api'
  import { useTelegramBackButton } from '@hooks'
  
  import styles from './CoinDetailsPage.module.scss'
  
  // Генерируем даты для текущего дня
  const getTodayDate = () => {
    const today = new Date()
    return today.toISOString().split('T')[0] // YYYY-MM-DD
  }

  // Mock data for chart - более детальные данные для плавного графика с объемом
  const MOCK_CHART_DATA = {
    '1d': (() => {
      const today = getTodayDate()
      return [
        { date: `${today} 00:00`, price: 11270, volume: 45000000000 },
        { date: `${today} 01:00`, price: 11272, volume: 43000000000 },
        { date: `${today} 02:00`, price: 11275, volume: 42000000000 },
        { date: `${today} 03:00`, price: 11273, volume: 44000000000 },
        { date: `${today} 04:00`, price: 11280, volume: 48000000000 },
        { date: `${today} 05:00`, price: 11278, volume: 46000000000 },
        { date: `${today} 06:00`, price: 11272, volume: 44000000000 },
        { date: `${today} 07:00`, price: 11274, volume: 45000000000 },
        { date: `${today} 08:00`, price: 11278, volume: 46000000000 },
        { date: `${today} 09:00`, price: 11280, volume: 47000000000 },
        { date: `${today} 10:00`, price: 11285, volume: 50000000000 },
        { date: `${today} 11:00`, price: 11283, volume: 48000000000 },
        { date: `${today} 12:00`, price: 11282, volume: 47000000000 },
        { date: `${today} 13:00`, price: 11284, volume: 47500000000 },
        { date: `${today} 14:00`, price: 11288, volume: 49000000000 },
        { date: `${today} 15:00`, price: 11287, volume: 48500000000 },
        { date: `${today} 16:00`, price: 11290, volume: 51000000000 },
        { date: `${today} 17:00`, price: 11289, volume: 49500000000 },
        { date: `${today} 18:00`, price: 11287, volume: 48000000000 },
        { date: `${today} 19:00`, price: 11289, volume: 49000000000 },
        { date: `${today} 20:00`, price: 11292, volume: 52000000000 },
        { date: `${today} 21:00`, price: 11293, volume: 51000000000 },
        { date: `${today} 22:00`, price: 11295, volume: 50000000000 },
        { date: `${today} 23:00`, price: 11297, volume: 49500000000 },
        { date: `${today} 23:59`, price: 11298, volume: 49000000000 },
      ]
    })(),
    '7d': (() => {
      const dates: string[] = []
      const today = new Date()
      for (let i = 6; i >= 0; i--) {
        const date = new Date(today)
        date.setDate(date.getDate() - i)
        const dateStr = date.toISOString().split('T')[0]
        dates.push(`${dateStr} 00:00`, `${dateStr} 04:00`, `${dateStr} 08:00`, `${dateStr} 12:00`, `${dateStr} 16:00`, `${dateStr} 20:00`)
      }
      const prices = [11250, 11252, 11254, 11255, 11257, 11259, 11260, 11259, 11258, 11258, 11257, 11256, 11255, 11256, 11257, 11257, 11258, 11259, 11270, 11271, 11272, 11272, 11273, 11274, 11275, 11276, 11277, 11277, 11278, 11279, 11280, 11281, 11282, 11282, 11283, 11284, 11290, 11291, 11292, 11292, 11293, 11294]
      const volumes = [45000000000, 45200000000, 45400000000, 46000000000, 45800000000, 46200000000, 46000000000, 45900000000, 45800000000, 45500000000, 45600000000, 45700000000, 44000000000, 44200000000, 44400000000, 44500000000, 44600000000, 44700000000, 48000000000, 48200000000, 48400000000, 48500000000, 48600000000, 48700000000, 47000000000, 47200000000, 47400000000, 47500000000, 47600000000, 47700000000, 49000000000, 49200000000, 49400000000, 49500000000, 49600000000, 49700000000, 50000000000, 50200000000, 50400000000, 50500000000, 50600000000, 50700000000]
      return dates.map((date, index) => ({
        date,
        price: prices[index] || 11250,
        volume: volumes[index] || 45000000000,
      }))
    })(),
    '30d': (() => {
      const dates: string[] = []
      const today = new Date()
      for (let i = 29; i >= 0; i--) {
        const date = new Date(today)
        date.setDate(date.getDate() - i)
        const dateStr = date.toISOString().split('T')[0]
        dates.push(`${dateStr} 00:00`)
      }
      const prices = [11200, 11205, 11210, 11208, 11212, 11215, 11218, 11220, 11222, 11225, 11228, 11230, 11232, 11235, 11238, 11240, 11242, 11245, 11248, 11250, 11252, 11255, 11258, 11260, 11262, 11265, 11268, 11270, 11272, 11275]
      const volumes = [45000000000, 45200000000, 45400000000, 45300000000, 45600000000, 45800000000, 46000000000, 46000000000, 46200000000, 46400000000, 46600000000, 46800000000, 47000000000, 47200000000, 47400000000, 47600000000, 47800000000, 48000000000, 48200000000, 48400000000, 48600000000, 48800000000, 49000000000, 49200000000, 49400000000, 49600000000, 49800000000, 50000000000, 50200000000, 50400000000]
      return dates.map((date, index) => ({
        date,
        price: prices[index] || 11200,
        volume: volumes[index] || 45000000000,
      }))
    })(),
    '1y': (() => {
      const dates: string[] = []
      const today = new Date()
      const currentYear = today.getFullYear()
      
      // Генерируем даты каждые пол месяца за последний год
      for (let month = 0; month < 12; month++) {
        const date1 = new Date(currentYear, month, 1)
        const date2 = new Date(currentYear, month, 15)
        dates.push(
          `${date1.toISOString().split('T')[0]} 00:00`,
          `${date2.toISOString().split('T')[0]} 00:00`
        )
      }
      
      const prices = [11000, 11025, 11050, 11075, 11100, 11090, 11080, 11100, 11120, 11135, 11150, 11165, 11180, 11190, 11200, 11210, 11220, 11230, 11240, 11250, 11260, 11270, 11280, 11290]
      const volumes = [40000000000, 40500000000, 41000000000, 41250000000, 42000000000, 41750000000, 41500000000, 42000000000, 42500000000, 42750000000, 43000000000, 43250000000, 43500000000, 43750000000, 44000000000, 44250000000, 44500000000, 44750000000, 45000000000, 45250000000, 45500000000, 45750000000, 46000000000, 46250000000]
      
      return dates.map((date, index) => ({
        date,
        price: prices[index] || 11000,
        volume: volumes[index] || 40000000000,
      }))
    })(),
  }
  
  const PERIOD_OPTIONS = [
    { label: '1D', value: '1d' },
    { label: '7D', value: '7d' },
    { label: '30D', value: '30d' },
    { label: '1Y', value: '1y' },
  ]
  
  export const CoinDetailsPage = () => {
    const navigate = useNavigate()
    const location = useLocation()
    const { id } = useParams<{ id: string }>()
  
    const [coin, setCoin] = useState<CryptoCurrency | null>(null)
    const [chartData, setChartData] = useState<any[]>([])
    const [selectedPeriod, setSelectedPeriod] = useState('7d')

    // Управление кнопкой "Назад" в Telegram Mini App
    useTelegramBackButton()
  
    useEffect(() => {
      const fetchCoinData = async () => {
        // Check if coin is passed via location state
        const coinFromState = location.state?.coin || location.state?.selectedCoin
        
        if (coinFromState) {
          // Convert from ChooseCoinPage format to CryptoCurrency format
          const cryptoCurrency: CryptoCurrency = {
            id: coinFromState.id || id || '',
            symbol: coinFromState.symbol || '',
            name: coinFromState.name || '',
            currentPrice: coinFromState.price || coinFromState.currentPrice || 0,
            priceChange24h: coinFromState.priceChange24h,
            priceChangePercent24h: coinFromState.priceChangePercent24h,
            imageUrl: coinFromState.imageUrl,
            priceDecimals: coinFromState.priceDecimals,  // Используем кэшированное значение из API
          }
          setCoin(cryptoCurrency)
        } else if (id) {
          // Fetch coin details by ID from API
          try {
            const coinDetails = await apiService.getCoinDetails(id)
            if (coinDetails) {
              setCoin({
                id: coinDetails.id || id,
                symbol: coinDetails.symbol || '',
                name: coinDetails.name || '',
                currentPrice: coinDetails.currentPrice || 0,
                priceChange24h: coinDetails.priceChange24h,
                priceChangePercent24h: coinDetails.priceChangePercent24h,
                imageUrl: coinDetails.imageUrl,
                priceDecimals: coinDetails.priceDecimals,  // Используем кэшированное значение из API
              })
            }
          } catch (error) {
            console.error('Failed to fetch coin details:', error)
            // Fallback to mock data
            setCoin({
              id: id,
              symbol: 'BTC',
              name: 'Bitcoin',
              currentPrice: 11273540.23,
            })
          }
        }
      }
      
      fetchCoinData()
    }, [location.state, id])
  
    useEffect(() => {
      if (coin && coin.id) {
        const fetchChartData = async () => {
          try {
            // Пытаемся получить данные из API
            const apiData = await apiService.getCoinChart(coin.id, selectedPeriod)
            
            if (apiData && apiData.length > 0) {
              // Если API вернул данные, используем их
              setChartData(apiData)
            } else {
              // Если API не вернул данные (CoinMarketCap бесплатный план не предоставляет историю),
              // используем mock данные, масштабированные относительно текущей цены
              const baseData = MOCK_CHART_DATA[selectedPeriod as keyof typeof MOCK_CHART_DATA] || []
              const scaledData = baseData.map((item) => ({
                ...item,
                price: (item.price / 11290) * coin.currentPrice,
                volume: item.volume || 0,
              }))
              setChartData(scaledData)
            }
          } catch (error) {
            console.error('Error fetching chart data:', error)
            // В случае ошибки используем mock данные
            const baseData = MOCK_CHART_DATA[selectedPeriod as keyof typeof MOCK_CHART_DATA] || []
            const scaledData = baseData.map((item) => ({
              ...item,
              price: (item.price / 11290) * coin.currentPrice,
              volume: item.volume || 0,
            }))
            setChartData(scaledData)
          }
        }
        
        fetchChartData()
      }
    }, [coin, selectedPeriod])
  
    const handleChooseCoin = () => {
      if (coin) {
        // Проверяем, есть ли информация о режиме редактирования в location state
        const isEditMode = location.state?.isEditMode === true
        const notificationId = location.state?.notificationId
        
        navigate(ROUTES_NAME.CREATE_NOTIFICATION, {
          state: { 
            selectedCoin: coin,
            ...(isEditMode && notificationId ? { isEditMode: true, notificationId } : {}),
          },
        })
      }
    }
  
    // Определяем количество знаков после запятой на основе цены
    // Используем кэшированное значение из API, если есть, иначе вычисляем локально
    const getPriceDecimals = (price: number): number => {
      // Если есть кэшированное значение из API, используем его
      if (coin?.priceDecimals !== undefined) {
        return coin.priceDecimals
      }
      // Иначе вычисляем локально
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

    const formatPrice = (price: number) => {
      const decimals = coin ? getPriceDecimals(coin.currentPrice) : 2
      // Форматируем с точками для тысяч и запятой для десятичных (например: 89.357,00)
      const parts = price.toFixed(decimals).split('.')
      const integerPart = parts[0]
      const decimalPart = parts[1] || '0'.repeat(decimals)
      
      // Добавляем точки для разделения тысяч
      const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
      
      return `${formattedInteger},${decimalPart}`
    }
  
    const currentPrice = coin ? `$${formatPrice(coin.currentPrice)}` : '-'
    const priceChange = coin?.priceChangePercent24h ?? 5.23 // Mock value if not available
    const isPriceRising = priceChange >= 0
    
    // Определяем цвет графика на основе тренда (сравниваем первую и последнюю цену)
    const getChartColor = () => {
      if (chartData.length < 2) {
        return isPriceRising ? 'var(--color-state-success)' : 'var(--color-state-destructive)'
      }
      const firstPrice = chartData[0]?.price || 0
      const lastPrice = chartData[chartData.length - 1]?.price || 0
      return lastPrice >= firstPrice ? 'var(--color-state-success)' : 'var(--color-state-destructive)'
    }
    
    const chartColor = getChartColor()
    
    // Рассчитываем равномерный диапазон для Y-axis
    const getYAxisDomain = () => {
      if (chartData.length === 0) return ['dataMin', 'dataMax']
      
      const prices = chartData.map(item => item.price).filter(p => p > 0)
      if (prices.length === 0) return ['dataMin', 'dataMax']
      
      const minPrice = Math.min(...prices)
      const maxPrice = Math.max(...prices)
      const range = maxPrice - minPrice
      const avgPrice = (minPrice + maxPrice) / 2
      
      // Используем процентное соотношение для всех монет:
      // Для 1D таймфрейма используем меньший процент (8%), для остальных - 15%
      // Это предотвращает создание слишком большого пустого пространства на 1D
      const relativeRangePercent = avgPrice > 0 ? range / avgPrice : 0
      const targetPercent = selectedPeriod === '1d' ? 0.08 : 0.15 // 8% для 1D, 15% для остальных
      
      let adjustedMin = minPrice
      let adjustedMax = maxPrice
      
      if (avgPrice > 0 && relativeRangePercent < targetPercent) {
        // Расширяем диапазон до targetPercent от средней цены для лучшей видимости
        // Но учитываем реальное распределение данных - расширяем больше там, где есть данные
        const targetRange = avgPrice * targetPercent
        
        // Вычисляем, насколько данные смещены от центра
        const dataCenter = avgPrice
        const dataRange = range
        
        // Расширяем пропорционально: больше расширяем в сторону, где больше данных
        // Если данные ближе к минимуму, расширяем больше вниз
        // Если данные ближе к максимуму, расширяем больше вверх
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
    
    // Генерируем тики для оси Y
    const getYAxisTicks = () => {
      if (chartData.length === 0) return undefined
      
      const domain = getYAxisDomain()
      if (typeof domain[0] === 'string' || typeof domain[1] === 'string') {
        return undefined
      }
      
      const min = domain[0] as number
      const max = domain[1] as number
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
      
      const tickCount = 5
      const step = range / (tickCount - 1)
      const significantDigits = getSignificantDigits(range)
      const multiplier = Math.pow(10, significantDigits)
      
      const ticks: number[] = []
      
      // Генерируем тики равномерно распределенные
      for (let i = 0; i < tickCount; i++) {
        const tickValue = min + (step * i)
        const roundedTick = Math.round(tickValue * multiplier) / multiplier
        ticks.push(roundedTick)
      }
      
      // Убираем дубликаты
      const uniqueTicks = Array.from(new Set(ticks))
      
      // Если после удаления дубликатов осталось меньше 3 тиков, возвращаем все без округления
      if (uniqueTicks.length < 3) {
        const simpleTicks: number[] = []
        for (let i = 0; i < tickCount; i++) {
          const tickValue = min + (step * i)
          simpleTicks.push(tickValue)
        }
        return simpleTicks
      }
      
      return uniqueTicks.length > 0 ? uniqueTicks : undefined
    }
    
    const yAxisDomain = getYAxisDomain()
    
    // Рассчитываем домен для объемов - ограничиваем их высоту до 30% от графика
    const getVolumeDomain = (): [number, number] => {
      if (chartData.length === 0) return [0, 1]
      
      const volumes = chartData.map(item => item.volume || 0).filter(v => v > 0)
      if (volumes.length === 0) return [0, 1]
      
      const maxVolume = Math.max(...volumes)
      // Увеличиваем максимальное значение в 3 раза, чтобы объемы занимали только ~30% высоты
      return [0, maxVolume * 2]
    }
    
    const volumeDomain = getVolumeDomain()
    
    // Рассчитываем оптимальное количество меток на основе периода
    // Учитываем минимальную ширину метки (~40-50px) и доступное пространство
    const getOptimalTickCount = () => {
      // Примерная ширина графика: ~300-400px (с учетом отступов)
      // Минимальная ширина для метки: ~40-50px
      // Оптимальное количество: 5-8 меток
      switch (selectedPeriod) {
        case '1d':
          // Для 1D показываем каждый час (24 метки)
          return 24
        case '7d':
          return 7 // Раз в день
        case '30d':
          return 6 // Каждые 5 дней
        case '1y':
          return 6 // Каждые 2 месяца
        default:
          return 6
      }
    }
    
    // Округляем дату до четного времени
    const roundDateToEvenTime = (dateStr: string, period: string): string => {
      try {
        const [datePart, timePart] = dateStr.split(' ')
        if (!datePart || !timePart) return dateStr
        
        const [year, month, day] = datePart.split('-').map(Number)
        const timeParts = timePart.split(':')
        const hours = Number(timeParts[0]) || 0
        const minutes = Number(timeParts[1]) || 0
        
        const roundedTime = roundTime(hours, minutes, period)
        
        // Формируем новую дату с округленным временем
        let roundedHours = roundedTime.h
        let roundedMinutes = roundedTime.m
        let roundedDay = day
        let roundedMonth = month
        let roundedYear = year
        
        // Если минуты переполнились (60), увеличиваем часы
        if (roundedMinutes >= 60) {
          roundedHours += 1
          roundedMinutes = 0
        }
        
        // Если часы переполнились (24), увеличиваем день
        if (roundedHours >= 24) {
          roundedHours = 0
          roundedDay += 1
          // Простая проверка на конец месяца (не учитываем разные длины месяцев, но это для округления достаточно)
          if (roundedDay > 31) {
            roundedDay = 1
            roundedMonth += 1
            if (roundedMonth > 12) {
              roundedMonth = 1
              roundedYear += 1
            }
          }
        }
        
        return `${String(roundedYear).padStart(4, '0')}-${String(roundedMonth).padStart(2, '0')}-${String(roundedDay).padStart(2, '0')} ${String(roundedHours).padStart(2, '0')}:${String(roundedMinutes).padStart(2, '0')}:00`
      } catch {
        return dateStr
      }
    }
    
    // Получаем тики для оси X в зависимости от периода
    // Равномерно распределяем метки по всей оси (используем реальные даты из данных)
    const getXAxisTicks = () => {
      if (chartData.length === 0) return undefined
      
      const optimalCount = getOptimalTickCount()
      const totalPoints = chartData.length
      
      // Если точек меньше или равно оптимальному количеству, показываем все
      if (totalPoints <= optimalCount) {
        return chartData.map(item => item.date)
      }
      
      // Рассчитываем шаг для равномерного распределения
      // Всегда включаем первую и последнюю точку
      const step = Math.floor((totalPoints - 1) / (optimalCount - 1))
      const ticks: string[] = []
      
      // Добавляем первую точку
      ticks.push(chartData[0].date)
      
      // Добавляем промежуточные точки с равномерным шагом
      for (let i = step; i < totalPoints - 1; i += step) {
        if (ticks.length < optimalCount - 1) {
          ticks.push(chartData[i].date)
        }
      }
      
      // Добавляем последнюю точку (если еще не добавлена)
      const lastDate = chartData[totalPoints - 1].date
      if (ticks[ticks.length - 1] !== lastDate) {
        if (ticks.length >= optimalCount) {
          ticks[ticks.length - 1] = lastDate
        } else {
          ticks.push(lastDate)
        }
      }
      
      return ticks.length > 0 ? ticks : undefined
    }
    
    // Получаем интервал для отображения тиков на оси X
    const getXAxisInterval = (): number | 'preserveStartEnd' => {
      // Используем 0 чтобы показывать только указанные тики
      return 0
    }
    
    // Кастомный рендеринг тиков для смещения крайних меток
    const renderCustomTick = (props: any) => {
      const { x, y, payload, index } = props
      const ticks = getXAxisTicks()
      const isFirst = index === 0
      const isLast = ticks && index === ticks.length - 1
      
      // Смещение: первая метка вправо на 8px, последняя влево на 8px
      const offsetX = isFirst ? 8 : isLast ? -8 : 0
      
      return (
        <text
          x={x + offsetX}
          y={y}
          fill="var(--color-foreground-tertiary)"
          fontSize={10}
          textAnchor="middle"
        >
          {formatDateForAxis(payload.value)}
        </text>
      )
    }
    
    // Форматирование объема
    const formatVolume = (volume: number) => {
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
    
    // Форматирование цены для tooltip (с K для тысяч)
    const formatPriceForTooltip = (price: number) => {
      const decimals = coin ? getPriceDecimals(coin.currentPrice) : 2
      if (price >= 1000000) {
        const value = (price / 1000000).toFixed(2)
        return `$${value.replace('.', ',')}M`
      }
      if (price >= 1000) {
        const value = (price / 1000).toFixed(2)
        return `$${value.replace('.', ',')}K`
      }
      const value = price.toFixed(decimals)
      return `$${value.replace('.', ',')}`
    }
    
    // Округляем время до ближайшего получаса или часа
    const roundTime = (hours: number, minutes: number, period: string) => {
      if (period === '1d') {
        // Для 1d округляем до часа (0 минут)
        return { h: hours, m: 0 }
      } else if (period === '7d') {
        // Для 7d округляем до часа (0 минут)
        return { h: hours, m: 0 }
      }
      return { h: hours, m: minutes }
    }
    
    // Форматирование даты для отображения на оси X
    const formatDateForAxis = (dateStr: string) => {
      try {
        // Парсим дату в формате "YYYY-MM-DD HH:MM" или "YYYY-MM-DD HH:MM:SS"
        const [datePart, timePart] = dateStr.split(' ')
        if (!datePart || !timePart) return dateStr
        
        // Парсим дату
        const [year, month, day] = datePart.split('-').map(Number)
        const timeParts = timePart.split(':')
        const hours = Number(timeParts[0]) || 0
        const minutes = Number(timeParts[1]) || 0
        
        if (isNaN(year) || isNaN(month) || isNaN(day)) return dateStr
        
        // Округляем время до четных значений
        const roundedTime = roundTime(hours, minutes, selectedPeriod)
        
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        const monthShort = monthNames[month - 1]
        
        switch (selectedPeriod) {
          case '1d':
            // Показываем только час (HH:00)
            return `${String(roundedTime.h).padStart(2, '0')}:00`
          case '7d':
            // Показываем только месяц и день (MMM DD) - короткий формат
            return `${monthShort} ${day}`
          case '30d':
            // Показываем только месяц и день (MMM DD) - короткий формат
            return `${monthShort} ${day}`
          case '1y':
            // Показываем только месяц и день (MMM DD) - короткий формат
            return `${monthShort} ${day}`
          default:
            return dateStr
        }
      } catch {
        // Fallback: пытаемся извлечь хотя бы время или дату
        try {
          const parts = dateStr.split(' ')
          if (parts.length >= 2) {
            const timePart = parts[1]
            if (timePart && timePart.includes(':')) {
              const [hours, minutes] = timePart.split(':').map(Number)
              const roundedTime = roundTime(hours || 0, minutes || 0, selectedPeriod)
              if (selectedPeriod === '1d') {
                return `${String(roundedTime.h).padStart(2, '0')}:00`
              }
              return `${String(roundedTime.h).padStart(2, '0')}:${String(roundedTime.m).padStart(2, '0')}`
            }
          }
          return dateStr.substring(0, 10) // Первые 10 символов
        } catch {
          return dateStr
        }
      }
    }
    
    // Форматирование даты для tooltip
    const formatDateForTooltip = (dateStr: string) => {
      try {
        const [date, time] = dateStr.split(' ')
        if (!date || !time) return dateStr
        
        // Парсим время
        const timeParts = time.split(':')
        let hours = Number(timeParts[0]) || 0
        let minutes = Number(timeParts[1]) || 0
        
        // Для периода 7D округляем до часа (убираем минуты)
        if (selectedPeriod === '7d') {
          minutes = 0
        }
        
        // Создаем объект даты с округленным временем
        const [year, month, day] = date.split('-').map(Number)
        const dateObj = new Date(year, month - 1, day, hours, minutes)
        if (isNaN(dateObj.getTime())) return dateStr
        
        const formattedDate = dateObj.toLocaleDateString('en-US', { 
          month: 'short', 
          day: 'numeric',
          year: 'numeric'
        })
        
        // Для периода 7D показываем только часы (без минут)
        if (selectedPeriod === '7d') {
          const formattedTime = dateObj.toLocaleTimeString('en-US', {
            hour: '2-digit',
            hour12: true
          })
          return `${formattedDate} ${formattedTime}`
        }
        
        // Для остальных периодов показываем часы и минуты
        const formattedTime = dateObj.toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: true
        })
        
        return `${formattedDate} ${formattedTime}`
      } catch {
        return dateStr
      }
    }
  
    return (
      <PageLayout>
        <Block margin="top" marginValue={16} align="center">
          {coin && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <CryptoIcon symbol={coin.symbol} name={coin.name} size={40} imageUrl={coin.imageUrl} />
              <Text type="title1" weight="bold">
                {coin.name}
              </Text>
            </div>
          )}
          <Text type="title" color="primary">
            {currentPrice}
          </Text>
          <span style={{ color: isPriceRising ? 'var(--color-state-success)' : undefined }}>
            <Text type="text" color={isPriceRising ? undefined : 'danger'}>
              {isPriceRising ? '+' : ''}{priceChange.toFixed(2)}%
            </Text>
          </span>
        </Block>
  
        <Block margin="top" marginValue={44}>
          <div className={styles.chartContainer}>
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart
                data={chartData}
                margin={{ 
                  top: 10, 
                  right: 5, 
                  left: 5, 
                  bottom: 5
                }}
              >
                <defs>
                  <linearGradient id="colorGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={chartColor} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={chartColor} stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <XAxis 
                  dataKey="date" 
                  axisLine={{ stroke: 'var(--color-border-separator)' }}
                  tickLine={{ stroke: 'transparent' }}
                  height={40}
                  ticks={getXAxisTicks()}
                  interval={getXAxisInterval()}
                  angle={0}
                  tick={renderCustomTick}
                  minTickGap={selectedPeriod === '1d' ? 8 : selectedPeriod === '30d' || selectedPeriod === '1y' ? 8 : 6}
                />
                <YAxis 
                  yAxisId="price"
                  orientation="right"
                  domain={yAxisDomain}
                  tick={{ fill: 'var(--color-foreground-tertiary)', fontSize: 10 }}
                  axisLine={{ stroke: 'transparent' }}
                  tickLine={{ stroke: 'transparent' }}
                  width={45}
                  ticks={getYAxisTicks()}
                  allowDecimals={true}
                  tickFormatter={(value: number) => {
                    const decimals = coin ? getPriceDecimals(coin.currentPrice) : 2
                    // Форматируем значение с точками для тысяч и запятой для десятичных
                    if (value >= 1000000) {
                      const formatted = (value / 1000000).toFixed(1).replace('.', ',')
                      return `$${formatted}M`
                    }
                    if (value >= 1000) {
                      const formatted = (value / 1000).toFixed(1).replace('.', ',')
                      return `$${formatted}K`
                    }
                    // Для значений меньше 1000
                    if (value < 1) {
                      return `$${value.toFixed(decimals).replace('.', ',')}`
                    }
                    if (value < 10) {
                      return `$${value.toFixed(decimals).replace('.', ',')}`
                    }
                    if (value < 100) {
                      return `$${value.toFixed(Math.min(decimals, 1)).replace('.', ',')}`
                    }
                    // Для больших значений добавляем точки для тысяч
                    const parts = value.toFixed(0).split('.')
                    const integerPart = parts[0]
                    const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
                    return `$${formattedInteger}`
                  }}
                />
                <YAxis 
                  yAxisId="volume"
                  orientation="left"
                  hide
                  domain={volumeDomain}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--color-background-modal)',
                    borderColor: 'var(--color-border-separator)',
                    borderRadius: '8px',
                    padding: '8px 12px',
                  }}
                  labelStyle={{ 
                    color: 'var(--color-foreground-primary)',
                    fontSize: '12px',
                    marginBottom: '4px',
                  }}
                  itemStyle={{ 
                    color: 'var(--color-foreground-primary)',
                    fontSize: '12px',
                  }}
                  formatter={(value: number, name: string) => {
                    if (name === 'price') {
                      return [formatPriceForTooltip(value), 'Price']
                    }
                    if (name === 'volume') {
                      return [formatVolume(value), 'Vol 24h']
                    }
                    return value
                  }}
                  labelFormatter={(label) => formatDateForTooltip(label as string)}
                  cursor={{ stroke: chartColor, strokeWidth: 1, strokeDasharray: '3 3' }}
                />
                <Area
                  yAxisId="price"
                  type="monotone"
                  dataKey="price"
                  stroke={chartColor}
                  strokeWidth={2}
                  fill="url(#colorGradient)"
                  dot={false}
                  activeDot={{ r: 4, fill: chartColor, strokeWidth: 2, stroke: 'var(--color-background-primary)' }}
                  connectNulls={false}
                />
                <Bar
                  yAxisId="volume"
                  dataKey="volume"
                  fill="var(--color-foreground-tertiary)"
                  opacity={0.3}
                  radius={[2, 2, 0, 0]}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Block>
  
        <Block margin="top" marginValue={24} row justify="center" gap={8}>
          {PERIOD_OPTIONS.map((option) => (
            <Button
              key={option.value}
              type={selectedPeriod === option.value ? 'primary' : 'secondary'}
              onClick={() => setSelectedPeriod(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </Block>
  
        <Block margin="top" marginValue={32} fixed="bottom">
          <Button type="primary" onClick={handleChooseCoin}>
            Choose
          </Button>
        </Block>
      </PageLayout>
    )
  }
  