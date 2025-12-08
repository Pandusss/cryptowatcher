import {
  Block,
  Button,
  CryptoIcon,
  Dropdown,
  Group,
  GroupItem,
  ListInput,
  PageLayout,
  Text,
} from '@components'
import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  Area,
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
import { apiService } from '@services'
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

export const CreateNotificationPage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { id } = useParams<{ id?: string }>()
  const isEditMode = !!id

  // Управление кнопкой "Назад" в Telegram Mini App
  useTelegramBackButton()

  // Form state
  const [crypto, setCrypto] = useState<{ id: string; symbol: string; name: string; price: number; imageUrl?: string } | null>(null)
  const [direction, setDirection] = useState<NotificationDirection>('rise')
  const [trigger, setTrigger] = useState<NotificationTrigger>('stop-loss')
  const [valueType, setValueType] = useState<NotificationValueType>('percent')
  const [value, setValue] = useState<string>('')
  const [expireTime, setExpireTime] = useState<number | null>(null) // null = без времени
  const [isLoading, setIsLoading] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chartData, setChartData] = useState<{ date: string; price: number }[]>([])
  const [chartLoading, setChartLoading] = useState(false)

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
    } else {
      // Если абсолютное значение, показываем процент
      return (numValue / crypto.price) * 100
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
            console.log('[CreateNotificationPage] Loaded coin details:', {
              crypto_id: notification.crypto_id,
              imageUrl,
              currentPrice,
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
      | { id: string; symbol: string; name: string; price?: number; currentPrice?: number; imageUrl?: string }
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

  // Загружаем данные графика когда есть crypto и в режиме редактирования
  useEffect(() => {
    if (isEditMode && crypto?.id) {
      const loadChartData = async () => {
        try {
          setChartLoading(true)
          const data = await apiService.getCoinChart(crypto.id, '7d')
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
  }, [isEditMode, crypto?.id])

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

  // Format number with spaces for thousands and comma for decimals
  const formatPrice = (price: number) => {
    // Форматируем с точками для тысяч и запятой для десятичных (например: 89.357,00)
    const parts = price.toFixed(2).split('.')
    const integerPart = parts[0]
    const decimalPart = parts[1] || '00'
    
    // Добавляем точки для разделения тысяч
    const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
    
    return `${formattedInteger},${decimalPart}`
  }

  const formatCalculatedValue = (val: number) => {
    // Format: replace dot with comma, keep spaces for thousands
    return val.toLocaleString('ru-RU', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).replace(/,/g, ' ').replace('.', ',')
  }

  // Вычисляем уровень триггера для отображения на графике
  const getTriggerLevel = (): number | null => {
    if (!crypto || !value) return null

    const numValue = parseFloat(value)
    if (isNaN(numValue) || numValue <= 0) return null

    const currentPrice = crypto.price

    if (valueType === 'percent') {
      // Если процент, вычисляем абсолютное значение
      if (trigger === 'stop-loss') {
        // Stop-loss: цена ниже текущей на X%
        return currentPrice * (1 - numValue / 100)
      } else {
        // Take-profit: цена выше текущей на X%
        return currentPrice * (1 + numValue / 100)
      }
    } else {
      // Если абсолютное значение
      if (trigger === 'stop-loss') {
        // Stop-loss: цена ниже текущей на X USD
        return currentPrice - numValue
      } else {
        // Take-profit: цена выше текущей на X USD
        return currentPrice + numValue
      }
    }
  }

  const triggerLevel = getTriggerLevel()


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

  // Рассчитываем равномерный диапазон для Y-axis (как в CoinDetailsPage)
  const getYAxisDomain = () => {
    if (chartData.length === 0) return ['dataMin', 'dataMax']
    
    const prices = chartData.map(item => item.price).filter(p => p > 0)
    if (prices.length === 0) return ['dataMin', 'dataMax']
    
    const minPrice = Math.min(...prices)
    const maxPrice = Math.max(...prices)
    const range = maxPrice - minPrice
    
    // Добавляем небольшой отступ сверху и снизу (5% от диапазона, но не меньше 1% от цены)
    const padding = Math.max(range * 0.05, minPrice * 0.01)
    let adjustedMin = Math.max(0, minPrice - padding)
    let adjustedMax = maxPrice + padding
    
    // Если есть уровень триггера, учитываем его
    if (triggerLevel !== null) {
      adjustedMin = Math.min(adjustedMin, triggerLevel)
      adjustedMax = Math.max(adjustedMax, triggerLevel)
    }
    
    // Определяем шаг округления на основе диапазона
    let step: number
    if (range >= 10000) {
      step = 2000
    } else if (range >= 1000) {
      step = 200
    } else if (range >= 100) {
      step = 20
    } else if (range >= 10) {
      step = 2
    } else if (range >= 1) {
      step = 0.2
    } else {
      step = 0.02
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

  // Генерируем тики для оси Y (как в CoinDetailsPage)
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
    
    const tickCount = 5
    const step = range / (tickCount - 1)
    
    const ticks: number[] = []
    
    for (let i = 0; i < tickCount; i++) {
      const tickValue = min + (step * i)
      let roundedTick: number
      if (tickValue >= 1000) {
        roundedTick = Math.round(tickValue)
      } else if (tickValue >= 100) {
        roundedTick = Math.round(tickValue * 10) / 10
      } else if (tickValue >= 10) {
        roundedTick = Math.round(tickValue * 10) / 10
      } else if (tickValue >= 1) {
        roundedTick = Math.round(tickValue * 100) / 100
      } else {
        roundedTick = Math.round(tickValue * 1000) / 1000
      }
      ticks.push(roundedTick)
    }
    
    return ticks.length > 0 ? ticks : undefined
  }

  // Форматирование цены для Y оси (как в CoinDetailsPage)
  const formatPriceForYAxis = (value: number) => {
    if (value >= 1000000) {
      const formatted = (value / 1000000).toFixed(1).replace('.', ',')
      return `$${formatted}M`
    }
    if (value >= 1000) {
      const formatted = (value / 1000).toFixed(1).replace('.', ',')
      return `$${formatted}K`
    }
    if (value < 1) {
      return `$${value.toFixed(2).replace('.', ',')}`
    }
    if (value < 10) {
      return `$${value.toFixed(2).replace('.', ',')}`
    }
    if (value < 100) {
      return `$${value.toFixed(1).replace('.', ',')}`
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

  // Получаем тики для оси X
  const getXAxisTicks = () => {
    if (chartData.length === 0) return undefined
    
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

  // Рендер кастомного тика для X оси (как в CoinDetailsPage)
  const renderCustomTick = (props: any) => {
    const { x, y, payload } = props
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
        {!isEditMode && (
          <div style={{ fontSize: '64px', marginBottom: '16px' }}>💰</div>
        )}
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
              <ListInput
                value={value}
                onChange={setValue}
                type="number"
                inputMode="decimal"
                placeholder={valueType === 'percent' ? '5%' : '100'}
                className={styles.valueInput}
                inputRef={valueInputRef}
              />
            }
          />
        </Group>
        {value && calculatedValue !== null && (
          <Block margin="top" marginValue={6} padding="left" paddingValue={16}>
            <Text type="caption" color="secondary">
              {valueType === 'percent' 
                ? `${value}% ≈ $${formatCalculatedValue(calculatedValue)}`
                : `$${formatCalculatedValue(parseFloat(value))} ≈ ${calculatedValue.toFixed(2)}%`
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

      {/* График с линией триггера (только в режиме редактирования) */}
      {isEditMode && crypto && chartData.length > 0 && (
        <Block margin="top" marginValue={24}>
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
                  formatter={(value: number) => {
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
                {triggerLevel !== null && (
                  <ReferenceLine
                    yAxisId="price"
                    y={triggerLevel}
                    stroke={trigger === 'stop-loss' ? 'var(--color-state-destructive)' : 'var(--color-state-success)'}
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    label={{
                      value: `${trigger === 'stop-loss' ? 'Stop-loss' : 'Take-profit'}: ${formatPriceForYAxis(triggerLevel)}`,
                      position: 'right',
                      fill: trigger === 'stop-loss' ? 'var(--color-state-destructive)' : 'var(--color-state-success)',
                      fontSize: 11,
                      fontWeight: 'bold',
                    }}
                  />
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

