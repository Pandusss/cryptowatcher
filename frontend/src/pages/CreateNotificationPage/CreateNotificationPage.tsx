import {
  Block,
  Button,
  CryptoIcon,
  Dropdown,
  Group,
  GroupItem,
  ListInput,
  NumberInput,
  PageLayout,
  Text,
} from '@components'
import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  Area,
  Bar,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { ROUTES_NAME } from '../../constants/routes'
import type {
  NotificationDirection,
  NotificationTrigger,
  NotificationValueType,
} from '@types'
import { apiService, type ChartDataPoint } from '@services'
import { getTelegramUserId } from '@utils'
import { useTelegramBackButton } from '@hooks'

import styles from './CreateNotificationPage.module.scss'

const DIRECTION_OPTIONS: { label: string; value: NotificationDirection }[] = [
  { label: 'Rise', value: 'rise' },
  { label: 'Fall', value: 'fall' },
  { label: 'Both', value: 'both' },
]

const TRIGGER_OPTIONS: { label: string; value: NotificationTrigger }[] = [
  { label: 'Stop-loss', value: 'stop-loss' },
  { label: 'Take-profit', value: 'take-profit' },
]

const VALUE_TYPE_OPTIONS: { label: string; value: NotificationValueType }[] =
  [
    { label: 'Percent', value: 'percent' },
    { label: 'Absolute Value', value: 'absolute' },
    { label: 'Price', value: 'price' },
  ]

const EXPIRE_TIME_OPTIONS: { label: string; value: string }[] = [
  { label: 'No expiration', value: 'null' },
  { label: '1 hour', value: '1' },
  { label: '2 hours', value: '2' },
  { label: '4 hours', value: '4' },
  { label: '8 hours', value: '8' },
  { label: '12 hours', value: '12' },
  { label: '24 hours', value: '24' },
  { label: '48 hours', value: '48' },
  { label: '72 hours', value: '72' },
]

const PERIOD_OPTIONS = [
  { label: '1D', value: '1d' },
  { label: '7D', value: '7d' },
  { label: '30D', value: '30d' },
  { label: '1Y', value: '1y' },
]

export const CreateNotificationPage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { id } = useParams<{ id?: string }>()
  const isEditMode = !!id

  // Управление кнопкой "Назад" в Telegram Mini App
  useTelegramBackButton()

  // Form state
  const [crypto, setCrypto] = useState<{ id: string; symbol: string; name: string; price: number; imageUrl?: string; priceDecimals?: number } | null>(null)
  const [direction, setDirection] = useState<NotificationDirection>('rise')
  const [trigger, setTrigger] = useState<NotificationTrigger>('stop-loss')
  const [valueType, setValueType] = useState<NotificationValueType>('percent')
  const [value, setValue] = useState<string>('')
  const [expireTime, setExpireTime] = useState<number | null>(null) // null = без времени
  const [isLoading, setIsLoading] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chartData, setChartData] = useState<ChartDataPoint[]>([])
  const [chartLoading, setChartLoading] = useState(false)
  const [selectedPeriod, setSelectedPeriod] = useState('7d') // Таймфрейм для графика

  // Dropdown states
  const [directionDropdownOpen, setDirectionDropdownOpen] = useState(false)
  const [triggerDropdownOpen, setTriggerDropdownOpen] = useState(false)
  const [valueTypeDropdownOpen, setValueTypeDropdownOpen] = useState(false)
  const [expireTimeDropdownOpen, setExpireTimeDropdownOpen] = useState(false)

  const directionRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLDivElement>(null)
  const valueTypeRef = useRef<HTMLDivElement>(null)
  const expireTimeRef = useRef<HTMLDivElement>(null)
  const valueInputRef = useRef<HTMLInputElement>(null)

  // Calculate calculated value based on value type
  const calculatedValue = (() => {
    if (!crypto || !value) return null
    
    const numValue = parseFloat(value)
    if (isNaN(numValue)) return null

    if (valueType === 'percent') {
      // Если процент, показываем абсолютное значение в USD
      return (crypto.price * numValue) / 100
    } else if (valueType === 'absolute') {
      // Если абсолютное значение, показываем процент
      return (numValue / crypto.price) * 100
    } else {
      // Если цена, показываем разницу в процентах и абсолютном значении
      const priceDiff = numValue - crypto.price
      const percentDiff = (priceDiff / crypto.price) * 100
      return { priceDiff, percentDiff }
    }
  })()

  useEffect(() => {
    // Load notification data if editing
    if (isEditMode && id) {
      const loadNotification = async () => {
        try {
          setIsLoading(true)
          setError(null)
          const notification = await apiService.getNotification(parseInt(id))
          
          // Получаем актуальную цену и imageUrl из API параллельно
          let imageUrl: string | undefined
          let currentPrice = notification.current_price || 0
          let priceDecimals: number | undefined
          
          // Запускаем запросы параллельно для ускорения загрузки
          const [coinsListResult, coinDetailsResult] = await Promise.allSettled([
            apiService.getCoinsList(250, 1),
            apiService.getCoinDetails(notification.crypto_id),
          ])
          
          // Обрабатываем результат списка монет
          if (coinsListResult.status === 'fulfilled') {
            const coin = coinsListResult.value.find(c => c.id === notification.crypto_id)
            if (coin?.imageUrl) {
              imageUrl = coin.imageUrl
              console.log('[CreateNotificationPage] Found imageUrl from coins list:', imageUrl)
            }
            if (coin?.priceDecimals !== undefined) {
              priceDecimals = coin.priceDecimals
            }
          } else {
            console.warn('[CreateNotificationPage] Failed to fetch coins list for imageUrl:', coinsListResult.reason)
          }
          
          // Обрабатываем результат деталей монеты
          if (coinDetailsResult.status === 'fulfilled' && coinDetailsResult.value) {
            currentPrice = coinDetailsResult.value.currentPrice
            // Если imageUrl не был получен из списка, используем из деталей
            if (!imageUrl && coinDetailsResult.value.imageUrl) {
              imageUrl = coinDetailsResult.value.imageUrl
            }
            // Используем priceDecimals из деталей, если не был получен из списка
            if (priceDecimals === undefined && coinDetailsResult.value.priceDecimals !== undefined) {
              priceDecimals = coinDetailsResult.value.priceDecimals
            }
            console.log('[CreateNotificationPage] Loaded coin details:', {
              crypto_id: notification.crypto_id,
              imageUrl,
              currentPrice,
              priceDecimals,
            })
          } else {
            console.warn('[CreateNotificationPage] Failed to fetch coin details, using saved price:', coinDetailsResult.status === 'rejected' ? coinDetailsResult.reason : 'null result')
            // Используем сохраненную цену если не удалось получить актуальную
          }
          
          // Заполняем форму данными уведомления
          setCrypto({
            id: notification.crypto_id,
            symbol: notification.crypto_symbol,
            name: notification.crypto_name,
            price: currentPrice,
            imageUrl,
            priceDecimals,  // Используем кэшированное значение из API
          })
          setDirection(notification.direction)
          setTrigger(notification.trigger)
          setValueType(notification.value_type)
          setValue(notification.value.toString())
          setExpireTime(notification.expire_time_hours ?? null)
        } catch (error) {
          console.error('Failed to load notification:', error)
          setError('Не удалось загрузить уведомление. Попробуйте еще раз.')
          setIsLoading(false)
          // Не делаем автоматический редирект, показываем ошибку пользователю
        }
      }
      
      loadNotification()
      return
    }

    // Получаем выбранную криптовалюту из navigation state
    const selectedCoin = location.state?.selectedCoin as
      | { id: string; symbol: string; name: string; price?: number; currentPrice?: number; imageUrl?: string; priceDecimals?: number }
      | undefined

    // Проверяем, пришли ли мы по кнопке "Назад"
    const isReturningBack = location.state?.fromBackButton === true

    if (selectedCoin) {
      // Используем выбранную криптовалюту
      // Поддерживаем оба формата: price и currentPrice
      const price = selectedCoin.price ?? selectedCoin.currentPrice ?? 0
      setCrypto({
        id: selectedCoin.id,
        symbol: selectedCoin.symbol,
        name: selectedCoin.name,
        price: price,
        imageUrl: selectedCoin.imageUrl,
        priceDecimals: selectedCoin.priceDecimals,  // Используем кэшированное значение из API
      })
    } else if (!crypto && !isReturningBack && !isEditMode) {
      // Если криптовалюта не выбрана и это не возврат по кнопке "Назад" и не режим редактирования,
      // перенаправляем на выбор (только при первом открытии страницы создания)
      // Используем replace вместо navigate, чтобы не добавлять в историю
      navigate(ROUTES_NAME.CHOOSE_COIN, { replace: true })
    }
    // Если isReturningBack === true и нет selectedCoin, просто показываем страницу
    // без автоматического редиректа, чтобы избежать цикла
  }, [id, isEditMode, location.state?.selectedCoin, location.state?.fromBackButton, navigate])

  // Загружаем данные графика когда есть crypto (и при создании, и при редактировании)
  useEffect(() => {
    if (crypto?.id) {
      const loadChartData = async () => {
        try {
          setChartLoading(true)
          const data = await apiService.getCoinChart(crypto.id, selectedPeriod)
          setChartData(data)
        } catch (error) {
          console.error('Failed to load chart data:', error)
          setChartData([])
        } finally {
          setChartLoading(false)
        }
      }

      loadChartData()
    } else {
      setChartData([])
    }
  }, [crypto?.id, selectedPeriod])

  const handleCreate = async () => {
    if (!crypto || !value) return

    const userId = getTelegramUserId()
    if (!userId) {
      setError('Не удалось получить ID пользователя из Telegram')
      return
    }

    const numValue = parseFloat(value)
    if (isNaN(numValue) || numValue <= 0) {
      setError('Введите корректное значение')
      return
    }

    setIsSaving(true)
    setError(null)

    try {
      if (isEditMode && id) {
        // Обновление существующего уведомления
        await apiService.updateNotification(parseInt(id), {
          direction,
          trigger,
          value_type: valueType,
          value: numValue,
          expire_time_hours: expireTime,
        })
      } else {
        // Создание нового уведомления
        await apiService.createNotification({
          user_id: userId,
          crypto_id: crypto.id,
          crypto_symbol: crypto.symbol,
          crypto_name: crypto.name,
          direction,
          trigger,
          value_type: valueType,
          value: numValue,
          current_price: crypto.price,
          expire_time_hours: expireTime,
        })
      }

      // Успешно создано/обновлено
      // Используем replace: true чтобы очистить историю и обновить список на главной
      navigate(ROUTES_NAME.MAIN, { replace: true })
    } catch (error) {
      console.error('Failed to create/update notification:', error)
      setError('Не удалось сохранить уведомление. Попробуйте еще раз.')
      setIsSaving(false)
    }
  }

  const handleRemove = async () => {
    if (!isEditMode || !id) return

    setIsDeleting(true)
    setError(null)

    try {
      await apiService.deleteNotification(parseInt(id))
      // Успешно удалено
      navigate(ROUTES_NAME.MAIN, { replace: true })
    } catch (error) {
      console.error('Failed to delete notification:', error)
      setError('Не удалось удалить уведомление. Попробуйте еще раз.')
      setIsDeleting(false)
    }
  }

  // Определяем количество знаков после запятой на основе цены
  // Используем кэшированное значение из API, если есть, иначе вычисляем локально
  const getPriceDecimals = (price: number): number => {
    // Если есть кэшированное значение из API, используем его
    if (crypto?.priceDecimals !== undefined) {
      return crypto.priceDecimals
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

  // Format number with spaces for thousands and comma for decimals
  const formatPrice = (price: number) => {
    const decimals = crypto ? getPriceDecimals(crypto.price) : 2
    // Форматируем с точками для тысяч и запятой для десятичных (например: 89.357,00)
    const parts = price.toFixed(decimals).split('.')
    const integerPart = parts[0]
    const decimalPart = parts[1] || '0'.repeat(decimals)
    
    // Добавляем точки для разделения тысяч
    const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
    
    return `${formattedInteger},${decimalPart}`
  }

  const formatCalculatedValue = (val: number) => {
    const decimals = crypto ? getPriceDecimals(crypto.price) : 2
    // Format: replace dot with comma, keep spaces for thousands
    return val.toLocaleString('ru-RU', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).replace(/,/g, ' ').replace('.', ',')
  }

  // Вычисляем уровень триггера для отображения на графике
  // Позиция линии зависит только от Direction и Value, Trigger - это просто метка
  const getTriggerLevel = (): number | null => {
    if (!crypto || !value) return null

    const numValue = parseFloat(value)
    if (isNaN(numValue) || numValue <= 0) return null

    const currentPrice = crypto.price

    if (valueType === 'percent') {
      // Если процент, вычисляем абсолютное значение
      if (direction === 'rise') {
        // Rise: цена выше текущей на X%
        return currentPrice * (1 + numValue / 100)
      } else if (direction === 'fall') {
        // Fall: цена ниже текущей на X%
        return currentPrice * (1 - numValue / 100)
      } else {
        // Both: показываем обе линии (выше и ниже)
        // Для упрощения показываем только верхнюю линию
        return currentPrice * (1 + numValue / 100)
      }
    } else {
      // Если абсолютное значение
      if (direction === 'rise') {
        // Rise: цена выше текущей на X USD
        return currentPrice + numValue
      } else if (direction === 'fall') {
        // Fall: цена ниже текущей на X USD
        return currentPrice - numValue
      } else {
        // Both: показываем обе линии (выше и ниже)
        // Для упрощения показываем только верхнюю линию
        return currentPrice + numValue
      }
    }
  }

  // Для Both показываем две линии (выше и ниже)
  const getTriggerLevels = (): { upper: number | null; lower: number | null } => {
    if (!crypto || !value) return { upper: null, lower: null }

    const numValue = parseFloat(value)
    if (isNaN(numValue) || numValue <= 0) return { upper: null, lower: null }

    const currentPrice = crypto.price

    // Если тип "price", используем указанную цену для обоих направлений
    if (valueType === 'price') {
      if (direction === 'rise') {
        return { upper: numValue, lower: null }
      } else if (direction === 'fall') {
        return { upper: null, lower: numValue }
      } else {
        // Both: показываем одну линию на указанной цене
        return { upper: numValue, lower: numValue }
      }
    }

    if (direction === 'both') {
      // Both: показываем обе линии
      if (valueType === 'percent') {
        return {
          upper: currentPrice * (1 + numValue / 100),
          lower: currentPrice * (1 - numValue / 100),
        }
      } else {
        return {
          upper: currentPrice + numValue,
          lower: currentPrice - numValue,
        }
      }
    } else {
      // Для Rise или Fall показываем только одну линию
      const singleLevel = getTriggerLevel()
      return {
        upper: direction === 'rise' ? singleLevel : null,
        lower: direction === 'fall' ? singleLevel : null,
      }
    }
  }

  const triggerLevel = getTriggerLevel()
  const triggerLevels = getTriggerLevels()


  // Определяем цвет графика на основе тренда (как в CoinDetailsPage)
  const getChartColor = () => {
    if (chartData.length < 2) {
      return 'var(--color-state-success)'
    }
    const firstPrice = chartData[0]?.price || 0
    const lastPrice = chartData[chartData.length - 1]?.price || 0
    return lastPrice >= firstPrice 
      ? 'var(--color-state-success)' 
      : 'var(--color-state-destructive)'
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
    
    // Если есть уровни триггеров, учитываем их в расчете диапазона
    let effectiveMin = minPrice
    let effectiveMax = maxPrice
    
    if (triggerLevels.upper !== null) {
      effectiveMin = Math.min(effectiveMin, triggerLevels.upper)
      effectiveMax = Math.max(effectiveMax, triggerLevels.upper)
    }
    if (triggerLevels.lower !== null) {
      effectiveMin = Math.min(effectiveMin, triggerLevels.lower)
      effectiveMax = Math.max(effectiveMax, triggerLevels.lower)
    }
    
    const effectiveRange = effectiveMax - effectiveMin
    const effectiveAvg = (effectiveMin + effectiveMax) / 2
    
    // Используем процентное соотношение для всех монет:
    // Для 1D таймфрейма используем меньший процент (8%), для остальных - 15%
    // Это предотвращает создание слишком большого пустого пространства на 1D
    const relativeRangePercent = effectiveAvg > 0 ? effectiveRange / effectiveAvg : 0
    const targetPercent = selectedPeriod === '1d' ? 0.08 : 0.15 // 8% для 1D, 15% для остальных
    
    let adjustedMin = effectiveMin
    let adjustedMax = effectiveMax
    
    if (effectiveAvg > 0 && relativeRangePercent < targetPercent) {
      // Расширяем диапазон до targetPercent от средней цены для лучшей видимости
      // Но учитываем реальное распределение данных - расширяем больше там, где есть данные
      const targetRange = effectiveAvg * targetPercent
      
      // Вычисляем, насколько данные смещены от центра
      const dataCenter = effectiveAvg
      const dataRange = effectiveRange
      
      // Расширяем пропорционально: больше расширяем в сторону, где больше данных
      // Если данные ближе к минимуму, расширяем больше вниз
      // Если данные ближе к максимуму, расширяем больше вверх
      const expansionNeeded = targetRange - dataRange
      
      if (expansionNeeded > 0) {
        // Вычисляем смещение данных от центра диапазона
        const rangeCenter = (effectiveMin + effectiveMax) / 2
        const offsetFromCenter = dataCenter - rangeCenter
        
        // Расширяем больше в сторону смещения данных
        const expansionDown = expansionNeeded * (0.5 + Math.max(0, -offsetFromCenter) / dataRange)
        const expansionUp = expansionNeeded * (0.5 + Math.max(0, offsetFromCenter) / dataRange)
        
        adjustedMin = Math.max(0, effectiveMin - expansionDown)
        adjustedMax = effectiveMax + expansionUp
      }
    } else {
      // Если диапазон уже достаточно большой, используем стандартный padding
      const padding = Math.max(effectiveRange * 0.05, effectiveMin * 0.01)
      adjustedMin = Math.max(0, effectiveMin - padding)
      adjustedMax = effectiveMax + padding
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
    
    for (let i = 0; i < tickCount; i++) {
      const tickValue = min + (step * i)
      const roundedTick = Math.round(tickValue * multiplier) / multiplier
      ticks.push(roundedTick)
    }
    
    // Убираем дубликаты
    const uniqueTicks = Array.from(new Set(ticks))
    
    return uniqueTicks.length > 0 ? uniqueTicks : undefined
  }

  // Форматирование цены для Y оси (как в CoinDetailsPage)
  const formatPriceForYAxis = (value: number) => {
    const decimals = crypto ? getPriceDecimals(crypto.price) : 2
    
    if (value >= 1000000) {
      const formatted = (value / 1000000).toFixed(1).replace('.', ',')
      return `$${formatted}M`
    }
    if (value >= 1000) {
      const formatted = (value / 1000).toFixed(1).replace('.', ',')
      return `$${formatted}K`
    }
    if (value < 1) {
      return `$${value.toFixed(decimals).replace('.', ',')}`
    }
    if (value < 10) {
      return `$${value.toFixed(decimals).replace('.', ',')}`
    }
    if (value < 100) {
      return `$${value.toFixed(Math.min(decimals, 1)).replace('.', ',')}`
    }
    const parts = value.toFixed(0).split('.')
    const integerPart = parts[0]
    const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
    return `$${formattedInteger}`
  }

  // Форматирование даты для tooltip (как в CoinDetailsPage)
  const formatDateForTooltip = (dateStr: string) => {
    try {
      const date = new Date(dateStr)
      const day = date.getDate()
      const month = date.toLocaleDateString('en-US', { month: 'short' })
      const hours = date.getHours()
      const minutes = date.getMinutes()
      return `${day} ${month} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`
    } catch {
      return dateStr
    }
  }

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

  // Получаем тики для оси X
  const getXAxisTicks = () => {
    if (chartData.length === 0) return undefined
    
    // Для 1D таймфрейма выбираем точки каждые 4 часа
    if (selectedPeriod === '1d') {
      const ticks: string[] = []
      const fourHoursInMs = 4 * 60 * 60 * 1000 // 4 часа в миллисекундах
      
      if (chartData.length === 0) return undefined
      
      const firstDate = new Date(chartData[0].date)
      const lastDate = new Date(chartData[chartData.length - 1].date)
      
      // Округляем первую дату до ближайшего часа, кратного 4 (0, 4, 8, 12, 16, 20)
      const firstHour = firstDate.getHours()
      const roundedFirstHour = Math.floor(firstHour / 4) * 4
      const roundedFirstDate = new Date(firstDate)
      roundedFirstDate.setHours(roundedFirstHour, 0, 0, 0)
      
      // Находим ближайшую точку данных к округленной дате
      let currentTick = roundedFirstDate.getTime()
      
      while (currentTick <= lastDate.getTime()) {
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
        
        // Добавляем тик, если он еще не добавлен и достаточно далеко от предыдущего
        const tickDate = chartData[closestIndex].date
        const tickTime = new Date(tickDate).getTime()
        const twoHoursInMs = 2 * 60 * 60 * 1000 // 2 часа в миллисекундах
        
        if (!ticks.includes(tickDate)) {
          // Проверяем расстояние до последнего добавленного тика
          if (ticks.length === 0) {
            ticks.push(tickDate)
          } else {
            const lastTickTime = new Date(ticks[ticks.length - 1]).getTime()
            const timeDiff = Math.abs(tickTime - lastTickTime)
            
            // Добавляем только если расстояние больше 2 часов
            if (timeDiff > twoHoursInMs) {
              ticks.push(tickDate)
            }
          }
        }
        
        // Переходим к следующему 4-часовому интервалу
        currentTick += fourHoursInMs
      }
      
      // Добавляем последнюю точку только если она достаточно далеко от последнего тика
      const lastTick = chartData[chartData.length - 1].date
      const lastTickTime = new Date(lastTick).getTime()
      
      if (ticks.length > 0) {
        const lastAddedTickTime = new Date(ticks[ticks.length - 1]).getTime()
        const timeDiff = Math.abs(lastTickTime - lastAddedTickTime)
        const twoHoursInMs = 2 * 60 * 60 * 1000 // 2 часа в миллисекундах
        
        // Добавляем последнюю точку только если она достаточно далеко от последнего тика
        if (!ticks.includes(lastTick) && timeDiff > twoHoursInMs) {
          ticks.push(lastTick)
        }
      } else {
        // Если тиков нет, добавляем последнюю точку
        ticks.push(lastTick)
      }
      
      return ticks.length > 0 ? ticks : undefined
    }
    
    // Для остальных таймфреймов используем стандартную логику
    const optimalCount = 7
    const totalPoints = chartData.length
    
    if (totalPoints <= optimalCount) {
      return chartData.map(item => item.date)
    }
    
    const step = Math.floor((totalPoints - 1) / (optimalCount - 1))
    const ticks: string[] = []
    
    ticks.push(chartData[0].date)
    
    for (let i = step; i < totalPoints - 1; i += step) {
      if (ticks.length < optimalCount - 1) {
        ticks.push(chartData[i].date)
      }
    }
    
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

  // Рендер кастомного тика для X оси
  const renderCustomTick = (props: any) => {
    const { x, y, payload } = props
    
    // Для 1D таймфрейма показываем время (HH:MM)
    if (selectedPeriod === '1d') {
      try {
        const date = new Date(payload.value)
        const hours = date.getHours()
        const minutes = date.getMinutes()
        
        // Округляем до ближайшего часа, кратного 4 (0, 4, 8, 12, 16, 20)
        const roundedHour = Math.floor(hours / 4) * 4
        
        return (
          <g transform={`translate(${x},${y})`}>
            <text
              x={0}
              y={0}
              dy={16}
              textAnchor="middle"
              fill="var(--color-foreground-tertiary)"
              fontSize={10}
            >
              {`${String(roundedHour).padStart(2, '0')}:00`}
            </text>
          </g>
        )
      } catch {
        return null
      }
    }
    
    // Для остальных таймфреймов показываем дату
    const date = new Date(payload.value)
    const day = date.getDate()
    const month = date.toLocaleDateString('en-US', { month: 'short' })
    
    return (
      <g transform={`translate(${x},${y})`}>
        <text
          x={0}
          y={0}
          dy={16}
          textAnchor="middle"
          fill="var(--color-foreground-tertiary)"
          fontSize={10}
        >
          {`${day} ${month}`}
        </text>
      </g>
    )
  }

  return (
    <PageLayout>
      <Block margin="top" marginValue={16} align="center">
        <Text type="title1" align="center">
          {isEditMode ? 'Edit Notification' : 'Create Notification'}
        </Text>
      </Block>

      {/* First island: Crypto and Current Price */}
      <Block margin="top" marginValue={32}>
        <Group>
          <GroupItem
            text="Crypto"
            after={
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {crypto ? (
                  <>
                    <Text type="text" color="accent">
                      {crypto.symbol}
                    </Text>
                    <CryptoIcon symbol={crypto.symbol} name={crypto.name} size={24} imageUrl={crypto.imageUrl} />
                  </>
                ) : (
                  <Text type="text" color="accent">
                    Select
                  </Text>
                )}
              </div>
            }
            chevron
            onClick={() => {
              // При редактировании передаем текущую криптовалюту в state
              navigate(ROUTES_NAME.CHOOSE_COIN, {
                state: isEditMode && crypto ? {
                  selectedCoin: {
                    id: crypto.id,
                    symbol: crypto.symbol,
                    name: crypto.name,
                    price: crypto.price,
                    imageUrl: crypto.imageUrl,
                  },
                  isEditMode: true,
                  notificationId: id,
                } : undefined,
              })
            }}
          />
          <GroupItem
            text="Current Price"
            after={
              <Text type="text" color="primary">
                {crypto ? `$${formatPrice(crypto.price)}` : '-'}
              </Text>
            }
            disabled
          />
        </Group>
      </Block>

      {/* Second island: Direction and Trigger */}
      <Block margin="top" marginValue={12}>
        <Group>
          <div ref={directionRef}>
            <GroupItem
              text="Direction"
              after={
                <Text type="text" color="accent">
                  {DIRECTION_OPTIONS.find((opt) => opt.value === direction)?.label || 'Rise'}
                </Text>
              }
              chevron
              chevronType="double"
              onClick={() => setDirectionDropdownOpen(!directionDropdownOpen)}
            />
          </div>
          <div ref={triggerRef}>
            <GroupItem
              text="Trigger"
              after={
                <Text type="text" color="accent">
                  {TRIGGER_OPTIONS.find((opt) => opt.value === trigger)?.label || 'Stop-loss'}
                </Text>
              }
              chevron
              chevronType="double"
              onClick={() => setTriggerDropdownOpen(!triggerDropdownOpen)}
            />
          </div>
        </Group>
      </Block>

      {/* Third island: Value Type and Value */}
      <Block margin="top" marginValue={12}>
        <Group>
          <div ref={valueTypeRef}>
            <GroupItem
              text="Value Type"
              after={
                <Text type="text" color="accent">
                  {VALUE_TYPE_OPTIONS.find((opt) => opt.value === valueType)?.label || 'Percent'}
                </Text>
              }
              chevron
              chevronType="double"
              onClick={() => setValueTypeDropdownOpen(!valueTypeDropdownOpen)}
            />
          </div>
          <GroupItem
            text="Value"
            after={
              <NumberInput
                value={value}
                onChange={setValue}
                placeholder={
                  valueType === 'percent' ? '5%' : 
                  valueType === 'absolute' ? '100' : 
                  crypto ? crypto.price.toFixed(getPriceDecimals(crypto.price)) : '0'
                }
                className={styles.valueInput}
                inputRef={valueInputRef}
                min={0}
                step={1}
              />
            }
          />
        </Group>
        {value && calculatedValue !== null && (
          <Block margin="top" marginValue={6} padding="left" paddingValue={16}>
            <Text type="caption" color="secondary">
              {valueType === 'percent' 
                ? `${value}% ≈ $${formatCalculatedValue(calculatedValue as number)}`
                : valueType === 'absolute'
                ? `$${formatCalculatedValue(parseFloat(value))} ≈ ${(calculatedValue as number).toFixed(2)}%`
                : typeof calculatedValue === 'object' && calculatedValue !== null && 'priceDiff' in calculatedValue
                ? `$${formatCalculatedValue(parseFloat(value))} (${calculatedValue.priceDiff >= 0 ? '+' : ''}${calculatedValue.priceDiff.toFixed(crypto ? getPriceDecimals(crypto.price) : 2)} USD, ${calculatedValue.percentDiff >= 0 ? '+' : ''}${calculatedValue.percentDiff.toFixed(2)}%)`
                : null
              }
            </Text>
          </Block>
        )}
        {error && (
          <Block margin="top" marginValue={6} padding="left" paddingValue={16}>
            <Text type="caption" color="danger">
              {error}
            </Text>
          </Block>
        )}
      </Block>

      {/* Fourth island: Expire Time */}
      <Block margin="top" marginValue={12}>
        <Group>
          <div ref={expireTimeRef}>
            <GroupItem
              text="Expire Time"
              after={
                <Text type="text" color="accent">
                  {EXPIRE_TIME_OPTIONS.find((opt) => opt.value === (expireTime === null ? 'null' : String(expireTime)))?.label || 'No expiration'}
                </Text>
              }
              chevron
              chevronType="double"
              onClick={() => setExpireTimeDropdownOpen(!expireTimeDropdownOpen)}
            />
          </div>
        </Group>
      </Block>

      {/* Dropdowns */}
      <Dropdown
        options={DIRECTION_OPTIONS}
        active={directionDropdownOpen}
        selectedValue={direction}
        onSelect={(val) => {
          setDirection(val as NotificationDirection)
          setDirectionDropdownOpen(false)
        }}
        onClose={() => setDirectionDropdownOpen(false)}
        triggerRef={directionRef}
      />

      <Dropdown
        options={TRIGGER_OPTIONS}
        active={triggerDropdownOpen}
        selectedValue={trigger}
        onSelect={(val) => {
          setTrigger(val as NotificationTrigger)
          setTriggerDropdownOpen(false)
        }}
        onClose={() => setTriggerDropdownOpen(false)}
        triggerRef={triggerRef}
      />

      <Dropdown
        options={VALUE_TYPE_OPTIONS}
        active={valueTypeDropdownOpen}
        selectedValue={valueType}
        onSelect={(val) => {
          setValueType(val as NotificationValueType)
          setValueTypeDropdownOpen(false)
        }}
        onClose={() => setValueTypeDropdownOpen(false)}
        triggerRef={valueTypeRef}
      />
      <Dropdown
        options={EXPIRE_TIME_OPTIONS}
        active={expireTimeDropdownOpen}
        selectedValue={expireTime === null ? 'null' : String(expireTime)}
        onSelect={(val) => {
          setExpireTime(val === 'null' ? null : parseInt(val, 10))
          setExpireTimeDropdownOpen(false)
        }}
        onClose={() => setExpireTimeDropdownOpen(false)}
        triggerRef={expireTimeRef}
      />

      {/* График с линией триггера (показываем когда выбрана монета) */}
      {crypto && chartData.length > 0 && (
        <Block margin="top" marginValue={24}>
          {/* Селектор таймфреймов */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginBottom: '16px' }}>
            {PERIOD_OPTIONS.map((period) => (
              <button
                key={period.value}
                onClick={() => setSelectedPeriod(period.value)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: selectedPeriod === period.value 
                    ? 'var(--color-accentsBrandCommunity)' 
                    : 'var(--color-backgroundTertiary)',
                  color: selectedPeriod === period.value 
                    ? 'var(--tg-theme-button-text-color, white)' 
                    : 'var(--color-foreground-primary)',
                  fontSize: '14px',
                  fontWeight: selectedPeriod === period.value ? 600 : 400,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                {period.label}
              </button>
            ))}
          </div>
          <div className={styles.chartContainer}>
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart
                data={chartData}
                margin={{ 
                  top: 10, 
                  right: 5, 
                  left: 15,  // Увеличиваем отступ слева для метки Stop-loss/Take-profit
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
                  interval={0}
                  angle={0}
                  tick={renderCustomTick}
                  minTickGap={6}
                />
                <YAxis 
                  yAxisId="price"
                  orientation="right"
                  domain={getYAxisDomain()}
                  tick={{ fill: 'var(--color-foreground-tertiary)', fontSize: 10 }}
                  axisLine={{ stroke: 'transparent' }}
                  tickLine={{ stroke: 'transparent' }}
                  width={45}
                  ticks={getYAxisTicks()}
                  allowDecimals={true}
                  tickFormatter={formatPriceForYAxis}
                />
                <YAxis 
                  yAxisId="volume"
                  orientation="left"
                  domain={volumeDomain}
                  tick={{ fill: 'transparent', fontSize: 0 }}
                  axisLine={{ stroke: 'transparent' }}
                  tickLine={{ stroke: 'transparent' }}
                  width={0}
                  hide={true}
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
                    if (name === 'volume') {
                      return [formatVolume(value), 'Vol 24h']
                    }
                    return [formatPriceForYAxis(value), 'Price']
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
                {/* Линия текущей цены */}
                {crypto && (
                  <ReferenceLine
                    yAxisId="price"
                    y={crypto.price}
                    stroke="var(--color-foreground-secondary)"
                    strokeWidth={1}
                    strokeDasharray="3 3"
                    label={{
                      value: formatPriceForYAxis(crypto.price),
                      position: 'right',
                      fill: 'var(--color-foreground-secondary)',
                      fontSize: 10,
                      fontWeight: 'normal',
                    }}
                  />
                )}
                {/* Отображаем линии в зависимости от Direction, цвет зависит от Trigger */}
                {triggerLevels.upper !== null && (
                  <>
                    {/* Основная линия с меткой слева (Stop-loss/Take-profit) */}
                    <ReferenceLine
                      yAxisId="price"
                      y={triggerLevels.upper}
                      stroke={trigger === 'stop-loss' ? 'var(--color-state-destructive)' : 'var(--color-state-success)'}
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      label={{
                        value: trigger === 'stop-loss' ? 'Stop-loss' : 'Take-profit',
                        position: 'left',
                        content: ({ viewBox }: any) => {
                          if (!viewBox) return null
                          // Получаем цвет из CSS переменных
                          const root = document.documentElement
                          const color = trigger === 'stop-loss' 
                            ? getComputedStyle(root).getPropertyValue('--color-state-destructive').trim() || '#ff3b30'
                            : getComputedStyle(root).getPropertyValue('--color-state-success').trim() || '#34c759'
                          const text = trigger === 'stop-loss' ? 'Stop-loss' : 'Take-profit'
                          const textWidth = text.length * 7 + 8
                          // Позиционируем прямоугольник слева от линии, но внутри области графика
                          // viewBox.x - это координата точки на линии относительно начала графика
                          // Учитываем отступ слева графика (70px), поэтому метка должна быть на позиции 0-60px
                          const rectX = Math.max(0, viewBox.x - textWidth - 4) // Не выходим за левую границу (0)
                          return (
                            <g>
                              <rect
                                x={rectX}
                                y={viewBox.y - 9}
                                width={textWidth-12}
                                height={18}
                                fill={color}
                                rx={4}
                              />
                              <text
                                x={rectX + 4}
                                y={viewBox.y + 4}
                                fill="white"
                                fontSize={11}
                                fontWeight="bold"
                              >
                                {text}
                              </text>
                            </g>
                          )
                        },
                      }}
                    />
                    {/* Невидимая линия с ценой справа */}
                    <ReferenceLine
                      yAxisId="price"
                      y={triggerLevels.upper}
                      stroke="transparent"
                      strokeWidth={0}
                      label={{
                        value: formatPriceForYAxis(triggerLevels.upper),
                        position: 'right',
                        fill: trigger === 'stop-loss' ? 'var(--color-state-destructive)' : 'var(--color-state-success)',
                        fontSize: 11,
                        fontWeight: 'bold',
                      }}
                    />
                  </>
                )}
                {triggerLevels.lower !== null && (
                  <>
                    {/* Основная линия с меткой слева (Stop-loss/Take-profit) */}
                    <ReferenceLine
                      yAxisId="price"
                      y={triggerLevels.lower}
                      stroke={trigger === 'stop-loss' ? 'var(--color-state-destructive)' : 'var(--color-state-success)'}
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      label={{
                        value: trigger === 'stop-loss' ? 'Stop-loss' : 'Take-profit',
                        position: 'left',
                        content: ({ viewBox }: any) => {
                          if (!viewBox) return null
                          // Получаем цвет из CSS переменных
                          const root = document.documentElement
                          const color = trigger === 'stop-loss' 
                            ? getComputedStyle(root).getPropertyValue('--color-state-destructive').trim() || '#ff3b30'
                            : getComputedStyle(root).getPropertyValue('--color-state-success').trim() || '#34c759'
                          const text = trigger === 'stop-loss' ? 'Stop-loss' : 'Take-profit'
                          const textWidth = text.length * 7 + 8
                          // Позиционируем прямоугольник слева от линии, но внутри области графика
                          // viewBox.x - это координата точки на линии относительно начала графика
                          // Учитываем отступ слева графика (70px), поэтому метка должна быть на позиции 0-60px
                          const rectX = Math.max(0, viewBox.x - textWidth - 4) // Не выходим за левую границу (0)
                          return (
                            <g>
                              <rect
                                x={rectX}
                                y={viewBox.y - 9}
                                width={textWidth}
                                height={18}
                                fill={color}
                                rx={4}
                              />
                              <text
                                x={rectX + 4}
                                y={viewBox.y + 4}
                                fill="white"
                                fontSize={11}
                                fontWeight="bold"
                              >
                                {text}
                              </text>
                            </g>
                          )
                        },
                      }}
                    />
                    {/* Невидимая линия с ценой справа */}
                    <ReferenceLine
                      yAxisId="price"
                      y={triggerLevels.lower}
                      stroke="transparent"
                      strokeWidth={0}
                      label={{
                        value: formatPriceForYAxis(triggerLevels.lower),
                        position: 'right',
                        fill: trigger === 'stop-loss' ? 'var(--color-state-destructive)' : 'var(--color-state-success)',
                        fontSize: 11,
                        fontWeight: 'bold',
                      }}
                    />
                  </>
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Block>
      )}

      <Block margin="top" marginValue={32} fixed="bottom">
        {isEditMode && (
          <>
            <Block margin="bottom" marginValue={12}>
              <Button 
                type="danger" 
                onClick={handleRemove}
                disabled={isDeleting || isSaving}
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </Button>
            </Block>
            <Button
              type="primary"
              onClick={handleCreate}
              disabled={!crypto || !value || isDeleting || isSaving}
            >
              {isSaving ? 'Saving...' : 'Apply'}
            </Button>
          </>
        )}
        {!isEditMode && (
          <Button
            type="primary"
            onClick={handleCreate}
            disabled={!crypto || !value || isSaving}
          >
            {isSaving ? 'Creating...' : 'Create'}
          </Button>
        )}
      </Block>
    </PageLayout>
  )
}

