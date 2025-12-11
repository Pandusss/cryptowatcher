import {
  Block,
  Button,
  CryptoIcon,
  PageLayout,
  Text,
} from '@components'
import { useEffect, useState, useMemo } from 'react'
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
import { getPriceDecimals } from '@utils'

import styles from './CoinDetailsPage.module.scss'

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
  const [priceUpdated, setPriceUpdated] = useState(false) // Флаг для анимации обновления цены
  const [priceDirection, setPriceDirection] = useState<'up' | 'down' | null>(null) // Направление изменения цены

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
        }
      }
    }
    
    fetchCoinData()
  }, [location.state, id])

  useEffect(() => {
    if (!coin || !coin.id) {
      console.log('[CoinDetailsPage] Монета не загружена, пропускаем инициализацию')
      return
    }

    const coinId = coin.id // Сохраняем ID в локальную переменную для использования в замыкании

    // Полная загрузка графика (при первой загрузке или смене периода)
    const fetchChartData = async () => {
      try {
        console.log(`[CoinDetailsPage] Загрузка полного графика для ${coinId}, период: ${selectedPeriod}`)
        const apiData = await apiService.getCoinChart(coinId, selectedPeriod)
        
        if (apiData && apiData.length > 0) {
          console.log(`[CoinDetailsPage] Загружено ${apiData.length} точек графика`)
          setChartData(apiData)
        } else {
          console.warn('[CoinDetailsPage] График пуст')
          setChartData([])
        }
      } catch (error) {
        console.error('[CoinDetailsPage] Ошибка загрузки графика:', error)
        setChartData([])
      }
    }

    // Обновление только последней точки графика и текущей цены
    const updateLastPoint = async () => {
      try {
        console.log(`[CoinDetailsPage] Обновление последней точки для ${coinId}...`)
        
        // Получаем текущую цену монеты
        const coinDetails = await apiService.getCoinDetails(coinId)
        if (coinDetails && coinDetails.currentPrice) {
          const newPrice = coinDetails.currentPrice
          console.log(`[CoinDetailsPage] Получена новая цена: $${newPrice}`)
          
          // Обновляем текущую цену монеты
          setCoin(prevCoin => {
            if (!prevCoin || prevCoin.id !== coinId) {
              console.warn(`[CoinDetailsPage] Пропуск обновления: prevCoin=${!!prevCoin}, id совпадает=${prevCoin?.id === coinId}`)
              return prevCoin
            }
            
            // Запускаем анимацию подсветки только если цена действительно изменилась
            if (prevCoin.currentPrice !== newPrice) {
              setPriceDirection(newPrice > prevCoin.currentPrice ? 'up' : 'down')
              setPriceUpdated(true)
              // Убираем класс через 800ms (длительность анимации)
              setTimeout(() => {
                setPriceUpdated(false)
                setPriceDirection(null)
              }, 800)
            }
            
            const updatedCoin = {
              ...prevCoin,
              currentPrice: newPrice,
              priceChange24h: coinDetails.priceChange24h,
              priceChangePercent24h: coinDetails.priceChangePercent24h,
              priceDecimals: coinDetails.priceDecimals || prevCoin.priceDecimals,
            }
            console.log(`[CoinDetailsPage] ✅ Обновлена цена монеты: $${prevCoin.currentPrice} → $${newPrice}`)
            return updatedCoin
          })

          // Обновляем только последнюю точку графика
          setChartData(prevData => {
            if (prevData.length === 0) {
              console.log('[CoinDetailsPage] Нет данных графика для обновления, загружаем полный график...')
              // Если данных нет, загружаем полный график
              fetchChartData()
              return prevData
            }
            
            const updatedData = [...prevData]
            const lastIndex = updatedData.length - 1
            
            // Форматируем дату в формате "YYYY-MM-DD HH:MM" (как в API)
            const now = new Date()
            const year = now.getFullYear()
            const month = String(now.getMonth() + 1).padStart(2, '0')
            const day = String(now.getDate()).padStart(2, '0')
            const hours = String(now.getHours()).padStart(2, '0')
            const minutes = String(now.getMinutes()).padStart(2, '0')
            const formattedDate = `${year}-${month}-${day} ${hours}:${minutes}`
            
            // Обновляем последнюю точку: цену, дату и объем (если есть)
            updatedData[lastIndex] = {
              ...updatedData[lastIndex],
              price: newPrice,
              date: formattedDate,
              // Объем оставляем как есть, так как его нельзя получить из getCoinDetails
            }
            
            console.log(`[CoinDetailsPage] ✅ Обновлена последняя точка графика: цена $${newPrice}`)
            return updatedData
          })
        } else {
          console.warn(`[CoinDetailsPage] Не удалось получить данные монеты ${coinId}`)
        }
      } catch (error) {
        console.error('[CoinDetailsPage] Ошибка обновления последней точки:', error)
      }
    }

    // Загружаем полный график сразу
    fetchChartData()

    // Обновляем последнюю точку и цену каждые 5 секунд из кэша Redis
    console.log(`[CoinDetailsPage] ✅ Запуск интервала обновления каждые 5 секунд для ${coinId}`)
    const intervalId = setInterval(() => {
      updateLastPoint()
    }, 5000) // 5000 мс = 5 секунд

    // Очищаем интервал при размонтировании или изменении зависимостей
    return () => {
      console.log(`[CoinDetailsPage] Очистка интервала обновления для ${coinId}`)
      clearInterval(intervalId)
    }
  }, [coin?.id, selectedPeriod])

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

  const formatPrice = (price: number) => {
    const decimals = coin ? getPriceDecimals(coin.currentPrice, coin.priceDecimals) : 2
    // Форматируем с точками для тысяч и запятой для десятичных (например: 89.357,00)
    const parts = price.toFixed(decimals).split('.')
    const integerPart = parts[0]
    const decimalPart = parts[1] || '0'.repeat(decimals)
    
    // Добавляем точки для разделения тысяч
    const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
    
    return `${formattedInteger},${decimalPart}`
  }

  // Используем useMemo для пересчета при изменении coin.currentPrice
  const currentPrice = useMemo(() => {
    return coin ? `$${formatPrice(coin.currentPrice)}` : '-'
  }, [coin?.currentPrice, coin?.priceDecimals])
  
  const priceChange = coin?.priceChangePercent24h ?? 0
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
    // Увеличиваем максимальное значение в 2 раза, чтобы объемы занимали только ~30% высоты
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
        return 6 // Каждые 3 часа
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
    
    // Для 1D таймфрейма показываем фиксированные временные метки каждые 3 часа
    if (selectedPeriod === '1d') {
      if (chartData.length === 0) return undefined
      
      const ticks: string[] = []
      const threeHoursInMs = 3 * 60 * 60 * 1000 // 3 часа в миллисекундах
      
      const firstDate = new Date(chartData[0].date)
      const lastDate = new Date(chartData[chartData.length - 1].date)
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
        let minDiff = Math.abs(new Date(chartData[0].date).getTime() - currentTick)
        
        for (let i = 1; i < chartData.length; i++) {
          const diff = Math.abs(new Date(chartData[i].date).getTime() - currentTick)
          if (diff < minDiff) {
            minDiff = diff
            closestIndex = i
          }
        }
        
        // Добавляем тик, если он еще не добавлен
        const tickDate = chartData[closestIndex].date
        if (!ticks.includes(tickDate)) {
          ticks.push(tickDate)
        }
        
        // Переходим к следующему 3-часовому интервалу
        currentTick += threeHoursInMs
      }
      
      return ticks.length > 0 ? ticks : undefined
    }
    
    // Для остальных таймфреймов используем стандартную логику
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
    const decimals = coin ? getPriceDecimals(coin.currentPrice, coin.priceDecimals) : 2
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
      // Для 1d округляем до получаса (0 или 30 минут)
      const roundedMinutes = minutes < 15 ? 0 : minutes < 45 ? 30 : 60
      if (roundedMinutes === 60) {
        return { h: hours + 1, m: 0 }
      }
      return { h: hours, m: roundedMinutes }
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
          // Показываем фиксированное время (HH:00) - округленное до часа, кратного 3 (0, 3, 6, 9, 12, 15, 18, 21)
          // Если текущее время 17:00, показываем 15:00 (округляем вниз)
          // Если текущее время 18:30, показываем 18:00 (округляем вверх)
          let roundedHour = Math.floor(roundedTime.h / 3) * 3
          
          // Если мы прошли больше половины интервала (>= 1.5 часа), показываем следующий час
          const remainder = roundedTime.h % 3
          if (remainder >= 2 || (remainder === 1 && roundedTime.m >= 30)) {
            roundedHour = (Math.floor(roundedTime.h / 3) + 1) * 3
          }
          
          // Обрабатываем переход через полночь
          roundedHour = roundedHour % 24
          
          return `${String(roundedHour).padStart(2, '0')}:00`
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
          <Text 
            type="title" 
            color="primary"
            className={priceUpdated ? (priceDirection === 'up' ? styles.priceUpdatedUp : styles.priceUpdatedDown) : ''}
          >
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
                  minTickGap={selectedPeriod === '1d' ? 12 : selectedPeriod === '30d' || selectedPeriod === '1y' ? 8 : 6}
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
                    const decimals = coin ? getPriceDecimals(coin.currentPrice, coin.priceDecimals) : 2
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
  