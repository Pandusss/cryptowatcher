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
import { getTelegramUserId, getPriceDecimals } from '@utils'
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
    { label: 'Price', value: 'price' },
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

  // Manage Telegram Mini App back button
  useTelegramBackButton()

  // Form state
  const [crypto, setCrypto] = useState<{ id: string; symbol: string; name: string; price: number; imageUrl?: string; priceDecimals?: number } | null>(null)
  const [direction, setDirection] = useState<NotificationDirection>('rise')
  const [trigger, setTrigger] = useState<NotificationTrigger>('stop-loss')
  const [valueType, setValueType] = useState<NotificationValueType>('price')
  const [value, setValue] = useState<string>('')
  const [expireTime, setExpireTime] = useState<number | null>(null) // null = no expiration
  const [isLoading, setIsLoading] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chartData, setChartData] = useState<ChartDataPoint[]>([])
  const [chartLoading, setChartLoading] = useState(false)
  const [selectedPeriod, setSelectedPeriod] = useState('7d') // Chart timeframe
  const [priceUpdated, setPriceUpdated] = useState(false) // Flag for price update animation
  const [priceDirection, setPriceDirection] = useState<'up' | 'down' | 'neutral' | null>(null) // Price change direction

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

  // Filter options based on current selections
  const filteredDirectionOptions = DIRECTION_OPTIONS.filter(opt => {
    // If valueType is 'price', hide 'both' option
    if (valueType === 'price' && opt.value === 'both') {
      return false
    }
    return true
  })

  const filteredValueTypeOptions = VALUE_TYPE_OPTIONS.filter(opt => {
    // If direction is 'both', hide 'price' option
    if (direction === 'both' && opt.value === 'price') {
      return false
    }
    return true
  })

  // Auto-correct incompatible combinations
  useEffect(() => {
    // If direction is 'both' and valueType is 'price', change valueType to 'percent'
    if (direction === 'both' && valueType === 'price') {
      setValueType('percent')
    }
  }, [valueType, direction])

  // Auto-set direction based on price comparison when valueType is 'price'
  useEffect(() => {
    if (valueType === 'price' && crypto && value) {
      const numValue = parseFloat(value)
      if (!isNaN(numValue)) {
        // If entered price > current price → rise, else → fall
        const newDirection = numValue > crypto.price ? 'rise' : 'fall'
        if (newDirection !== direction) {
          setDirection(newDirection)
        }
      }
    }
  }, [valueType, value, crypto?.price, direction])

  // Calculate calculated value based on value type
  const calculatedValue = (() => {
    if (!crypto || !value) return null
    
    const numValue = parseFloat(value)
    if (isNaN(numValue)) return null

    if (valueType === 'percent') {
      // If percent, show absolute value in USD
      return (crypto.price * numValue) / 100
    } else if (valueType === 'absolute') {
      // If absolute value, show percent
      return (numValue / crypto.price) * 100
    } else {
      // If price, show difference in percent and absolute value
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
          
          // Get current price and imageUrl from API in parallel
          let imageUrl: string | undefined
          let currentPrice = notification.current_price || 0
          let priceDecimals: number | undefined
          
          // Run requests in parallel for faster loading
          const [coinsListResult, coinDetailsResult] = await Promise.allSettled([
            apiService.getCoinsList(250, 1),
            apiService.getCoinDetails(notification.crypto_id),
          ])
          
          // Process coin list result
          if (coinsListResult.status === 'fulfilled') {
            const coin = coinsListResult.value.find(c => c.id === notification.crypto_id)
            if (coin?.imageUrl) {
              imageUrl = coin.imageUrl
            }
            if (coin?.priceDecimals !== undefined) {
              priceDecimals = coin.priceDecimals
            }
          } else {
          }
          
          // Process coin details result
          if (coinDetailsResult.status === 'fulfilled' && coinDetailsResult.value) {
            currentPrice = coinDetailsResult.value.currentPrice
            // If imageUrl wasn't obtained from list, use from details
            if (!imageUrl && coinDetailsResult.value.imageUrl) {
              imageUrl = coinDetailsResult.value.imageUrl
            }
            // Use priceDecimals from details if not obtained from list
            if (priceDecimals === undefined && coinDetailsResult.value.priceDecimals !== undefined) {
              priceDecimals = coinDetailsResult.value.priceDecimals
            }
          } else {
            // Use saved price if couldn't get current one
          }
          
          // Fill form with notification data
          setCrypto({
            id: notification.crypto_id,
            symbol: notification.crypto_symbol,
            name: notification.crypto_name,
            price: currentPrice,
            imageUrl,
            priceDecimals,  // Use cached value from API
          })
          setDirection(notification.direction)
          setTrigger(notification.trigger)
          setValueType(notification.value_type)
          setValue(notification.value.toString())
          setExpireTime(notification.expire_time_hours ?? null)
        } catch {
          setError('Failed to load notification. Please try again.')
          setIsLoading(false)
        }
      }
      
      loadNotification()
      return
    }

    // Get selected cryptocurrency from navigation state
    const selectedCoin = location.state?.selectedCoin as
      | { id: string; symbol: string; name: string; price?: number; currentPrice?: number; imageUrl?: string; priceDecimals?: number }
      | undefined

    // Check if we came back via the Back button
    const isReturningBack = location.state?.fromBackButton === true

    if (selectedCoin) {
      // Use selected cryptocurrency
      // Support both formats: price and currentPrice
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
      // If cryptocurrency not selected and this is not back button return and not edit mode,
      // redirect to selection (only on first create page open)
      // Use replace instead of navigate to not add to history
      navigate(ROUTES_NAME.CHOOSE_COIN, { replace: true })
    }
    // If isReturningBack === true and no selectedCoin, just show the page
    // without automatic redirect to avoid a loop
  }, [id, isEditMode, location.state?.selectedCoin, location.state?.fromBackButton, navigate])

  // Load chart data when crypto is available (both for create and edit modes)
  useEffect(() => {
    if (crypto?.id) {
      const loadChartData = async () => {
        try {
          setChartLoading(true)
          const data = await apiService.getCoinChart(crypto.id, selectedPeriod)
          setChartData(data)
        } catch {
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

  // Update price every 5 seconds from Redis cache
  useEffect(() => {
    if (!crypto?.id) {
      return
    }

    const coinId = crypto.id // Save ID to local variable for use in closure

    // Function to update price and last chart point
    const updatePrice = async () => {
      try {
        const coinDetails = await apiService.getCoinDetails(coinId)
        if (coinDetails && coinDetails.currentPrice) {
          const newPrice = coinDetails.currentPrice
          
          setCrypto(prevCrypto => {
            if (!prevCrypto || prevCrypto.id !== coinId) {
              return prevCrypto
            }
            
            // Trigger highlight animation
            if (prevCrypto.price !== newPrice) {
              setPriceDirection(newPrice > prevCrypto.price ? 'up' : 'down')
            } else {
              setPriceDirection('neutral')
            }
            setPriceUpdated(true)
            setTimeout(() => {
              setPriceUpdated(false)
              setPriceDirection(null)
            }, 800)
            
            return {
              ...prevCrypto,
              price: newPrice,
              priceDecimals: coinDetails.priceDecimals || prevCrypto.priceDecimals,
            }
          })

          // Update only the last chart point
          setChartData(prevData => {
            if (prevData.length === 0) {
              return prevData
            }
            
            const updatedData = [...prevData]
            const lastIndex = updatedData.length - 1
            
            const now = new Date()
            const year = now.getFullYear()
            const month = String(now.getMonth() + 1).padStart(2, '0')
            const day = String(now.getDate()).padStart(2, '0')
            const hours = String(now.getHours()).padStart(2, '0')
            const minutes = String(now.getMinutes()).padStart(2, '0')
            const formattedDate = `${year}-${month}-${day} ${hours}:${minutes}`
            
            updatedData[lastIndex] = {
              ...updatedData[lastIndex],
              price: newPrice,
              date: formattedDate,
            }
            
            return updatedData
          })
        }
      } catch {
        // Price update failed, will retry
      }
    }

    // Update price immediately on mount
    updatePrice()

    // Update price every 5 seconds
    const intervalId = setInterval(updatePrice, 5000)

    return () => {
      clearInterval(intervalId)
    }
  }, [crypto?.id])

  const handleCreate = async () => {
    if (!crypto || !value) return

    const userId = getTelegramUserId()
    if (!userId) {
      setError('Could not get user ID from Telegram')
      return
    }

    const numValue = parseFloat(value)
    if (isNaN(numValue) || numValue <= 0) {
      setError('Please enter a valid value')
      return
    }

    setIsSaving(true)
    setError(null)

    try {
      if (isEditMode && id) {
        // Update existing notification
        await apiService.updateNotification(parseInt(id), {
          direction,
          trigger,
          value_type: valueType,
          value: numValue,
          expire_time_hours: expireTime,
        })
      } else {
        // Create new notification
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

      // Successfully created/updated
      // Use replace: true to clear history and refresh list on main page
      navigate(ROUTES_NAME.MAIN, { replace: true })
    } catch {
      setError('Failed to save notification. Please try again.')
      setIsSaving(false)
    }
  }

  const handleRemove = async () => {
    if (!isEditMode || !id) return

    setIsDeleting(true)
    setError(null)

    try {
      await apiService.deleteNotification(parseInt(id))
      // Successfully deleted
      navigate(ROUTES_NAME.MAIN, { replace: true })
    } catch {
      setError('Failed to delete notification. Please try again.')
      setIsDeleting(false)
    }
  }

  // Format number with comma for decimals (no thousands separator)
  const formatPrice = (price: number) => {
    const decimals = crypto ? getPriceDecimals(crypto.price, crypto.priceDecimals) : 2
    // Format with comma for decimals only (e.g.: 89357,00)
    const parts = price.toFixed(decimals).split('.')
    const integerPart = parts[0]
    const decimalPart = parts[1] || '0'.repeat(decimals)
    
    return `${integerPart},${decimalPart}`
  }

  const formatCalculatedValue = (val: number) => {
    const decimals = crypto ? getPriceDecimals(crypto.price, crypto.priceDecimals) : 2
    // Format: comma for decimals, no thousands separator
    const parts = val.toFixed(decimals).split('.')
    const integerPart = parts[0]
    const decimalPart = parts[1] || '0'.repeat(decimals)
    return `${integerPart},${decimalPart}`
  }

  // Calculate trigger level for chart display
  // Line position depends only on Direction and Value, Trigger is just a label
  const getTriggerLevel = (): number | null => {
    if (!crypto || !value) return null

    const numValue = parseFloat(value)
    if (isNaN(numValue) || numValue <= 0) return null

    const currentPrice = crypto.price

    if (valueType === 'percent') {
      // If percent, calculate absolute value
      if (direction === 'rise') {
        // Rise: price above current by X%
        return currentPrice * (1 + numValue / 100)
      } else if (direction === 'fall') {
        // Fall: price below current by X%
        return currentPrice * (1 - numValue / 100)
      } else {
        // Both: show both lines (above and below)
        // For simplicity, show only upper line
        return currentPrice * (1 + numValue / 100)
      }
    } else {
      // If absolute value
      if (direction === 'rise') {
        // Rise: price above current by X USD
        return currentPrice + numValue
      } else if (direction === 'fall') {
        // Fall: price below current by X USD
        return currentPrice - numValue
      } else {
        // Both: show both lines (above and below)
        // For simplicity, show only upper line
        return currentPrice + numValue
      }
    }
  }

  // For Both show two lines (above and below)
  const getTriggerLevels = (): { upper: number | null; lower: number | null } => {
    if (!crypto || !value) return { upper: null, lower: null }

    const numValue = parseFloat(value)
    if (isNaN(numValue) || numValue <= 0) return { upper: null, lower: null }

    const currentPrice = crypto.price

    // If type is "price", use specified price for both directions
    if (valueType === 'price') {
      if (direction === 'rise') {
        return { upper: numValue, lower: null }
      } else if (direction === 'fall') {
        return { upper: null, lower: numValue }
      } else {
        // Both: show one line at specified price
        return { upper: numValue, lower: numValue }
      }
    }

    if (direction === 'both') {
      // Both: show both lines
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
      // For Rise or Fall show only one line
      const singleLevel = getTriggerLevel()
      return {
        upper: direction === 'rise' ? singleLevel : null,
        lower: direction === 'fall' ? singleLevel : null,
      }
    }
  }

  const triggerLevel = getTriggerLevel()
  const triggerLevels = getTriggerLevels()


  // Determine chart color based on trend (like in CoinDetailsPage)
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

  // Calculate uniform range for Y-axis
  const getYAxisDomain = () => {
    if (chartData.length === 0) return ['dataMin', 'dataMax']
    
    const prices = chartData.map(item => item.price).filter(p => p > 0)
    if (prices.length === 0) return ['dataMin', 'dataMax']
    
    const minPrice = Math.min(...prices)
    const maxPrice = Math.max(...prices)
    const range = maxPrice - minPrice
    const avgPrice = (minPrice + maxPrice) / 2
    
    // If trigger levels exist, include them in range calculation
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
    
    // Use percentage ratio for all coins:
    // For 1D timeframe use smaller percent (8%), for others - 15%
    // This prevents creating too much empty space on 1D
    const relativeRangePercent = effectiveAvg > 0 ? effectiveRange / effectiveAvg : 0
    const targetPercent = selectedPeriod === '1d' ? 0.08 : 0.15 // 8% for 1D, 15% for others
    
    let adjustedMin = effectiveMin
    let adjustedMax = effectiveMax
    
    if (effectiveAvg > 0 && relativeRangePercent < targetPercent) {
      // Expand range to targetPercent of average price for better visibility
      // But consider real data distribution - expand more where data exists
      const targetRange = effectiveAvg * targetPercent
      
      // Calculate how much data is offset from center
      const dataCenter = effectiveAvg
      const dataRange = effectiveRange
      
      // Expand proportionally: expand more towards where more data exists
      // If data is closer to minimum, expand more downward
      // If data is closer to maximum, expand more upward
      const expansionNeeded = targetRange - dataRange
      
      if (expansionNeeded > 0) {
        // Calculate data offset from range center
        const rangeCenter = (effectiveMin + effectiveMax) / 2
        const offsetFromCenter = dataCenter - rangeCenter
        
        // Expand more towards data offset direction
        const expansionDown = expansionNeeded * (0.5 + Math.max(0, -offsetFromCenter) / dataRange)
        const expansionUp = expansionNeeded * (0.5 + Math.max(0, offsetFromCenter) / dataRange)
        
        adjustedMin = Math.max(0, effectiveMin - expansionDown)
        adjustedMax = effectiveMax + expansionUp
      }
    } else {
      // If range is already large enough, use standard padding
      const padding = Math.max(effectiveRange * 0.05, effectiveMin * 0.01)
      adjustedMin = Math.max(0, effectiveMin - padding)
      adjustedMax = effectiveMax + padding
    }
    
    // Determine rounding step based on range
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
    
    // Round to nearest value considering the step
    adjustedMin = Math.floor(adjustedMin / step) * step
    adjustedMax = Math.ceil(adjustedMax / step) * step
    
    // Ensure min < max
    if (adjustedMin >= adjustedMax) {
      adjustedMax = adjustedMin + step * 2
    }
    
    return [adjustedMin, adjustedMax]
  }

  // Generate ticks for Y axis
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
    
    // Determine number of significant digits for rounding based on range
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
    
    // Remove duplicates
    const uniqueTicks = Array.from(new Set(ticks))
    
    return uniqueTicks.length > 0 ? uniqueTicks : undefined
  }

  // Format price for Y axis (like in CoinDetailsPage)
  const formatPriceForYAxis = (value: number) => {
    const decimals = crypto ? getPriceDecimals(crypto.price, crypto.priceDecimals) : 2
    
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

  // Format date for tooltip (like in CoinDetailsPage)
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

  // Calculate domain for volumes - limit their height to 30% of chart
  const getVolumeDomain = (): [number, number] => {
    if (chartData.length === 0) return [0, 1]
    
    const volumes = chartData.map(item => item.volume || 0).filter(v => v > 0)
    if (volumes.length === 0) return [0, 1]
    
    const maxVolume = Math.max(...volumes)
    // Double max value so volumes take only ~30% of height
    return [0, maxVolume * 2]
  }

  const volumeDomain = getVolumeDomain()

  // Format volume
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

  // Get ticks for X axis
  const getXAxisTicks = () => {
    if (chartData.length === 0) return undefined
    
    // For 1D timeframe show fixed time labels every 3 hours
    if (selectedPeriod === '1d') {
      if (chartData.length === 0) return undefined
      
      const ticks: string[] = []
      const threeHoursInMs = 3 * 60 * 60 * 1000 // 3 hours in milliseconds
      
      const firstDate = new Date(chartData[0].date)
      const lastDate = new Date(chartData[chartData.length - 1].date)
      const firstTime = firstDate.getTime()
      const lastTime = lastDate.getTime()
      
      // Find first hour divisible by 3 that is >= first date
      const firstHour = firstDate.getHours()
      const firstRoundedHour = Math.floor(firstHour / 3) * 3
      const startTick = new Date(firstDate)
      startTick.setHours(firstRoundedHour, 0, 0, 0)
      
      // If rounded hour is less than current hour, add 3 hours
      if (startTick.getTime() < firstTime) {
        startTick.setHours(startTick.getHours() + 3)
      }
      
      // Generate fixed time labels every 3 hours
      let currentTick = startTick.getTime()
      
      while (currentTick <= lastTime) {
        // Find closest data point to current tick
        let closestIndex = 0
        let minDiff = Math.abs(new Date(chartData[0].date).getTime() - currentTick)
        
        for (let i = 1; i < chartData.length; i++) {
          const diff = Math.abs(new Date(chartData[i].date).getTime() - currentTick)
          if (diff < minDiff) {
            minDiff = diff
            closestIndex = i
          }
        }
        
        // Add tick if not already added
        const tickDate = chartData[closestIndex].date
        if (!ticks.includes(tickDate)) {
          ticks.push(tickDate)
        }
        
        // Move to next 3-hour interval
        currentTick += threeHoursInMs
      }
      
      return ticks.length > 0 ? ticks : undefined
    }
    
    // For other timeframes use standard logic
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

  // Render custom tick for X axis
  const renderCustomTick = (props: any) => {
    const { x, y, payload } = props
    
    // For 1D timeframe show fixed time (HH:00)
    if (selectedPeriod === '1d') {
      try {
        const date = new Date(payload.value)
        const hours = date.getHours()
        const minutes = date.getMinutes()
        
        // Calculate fixed label time: round to nearest hour divisible by 3
        // If current time is 17:00, show 15:00 (round down)
        // If current time is 18:30, show 18:00 (round up)
        let roundedHour = Math.floor(hours / 3) * 3
        
        // If we passed more than half of interval (>= 1.5 hours), show next hour
        const remainder = hours % 3
        if (remainder >= 2 || (remainder === 1 && minutes >= 30)) {
          roundedHour = (Math.floor(hours / 3) + 1) * 3
        }
        
        // Handle midnight transition
        roundedHour = roundedHour % 24
        
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
    
    // For other timeframes show date
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
              // When editing, pass current cryptocurrency in state
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
              <Text 
                type="text" 
                color="primary"
                className={priceUpdated ? (
                  priceDirection === 'up' ? styles.priceUpdatedUp : 
                  priceDirection === 'down' ? styles.priceUpdatedDown : 
                  styles.priceUpdatedNeutral
                ) : ''}
              >
                {crypto ? `$${formatPrice(crypto.price)}` : '-'}
              </Text>
            }
            disabled
          />
        </Group>
      </Block>

      {/* Second island: Value Type and Value */}
      <Block margin="top" marginValue={12}>
        <Group>
          <div ref={valueTypeRef}>
            <GroupItem
              text="Value Type"
              after={
                <Text type="text" color="accent">
                  {VALUE_TYPE_OPTIONS.find((opt) => opt.value === valueType)?.label || 'Price'}
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
                  crypto ? crypto.price.toFixed(getPriceDecimals(crypto.price, crypto.priceDecimals)).replace('.', ',') : '0'
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
                ? `$${formatCalculatedValue(parseFloat(value))} ≈ ${(calculatedValue as number).toFixed(2).replace('.', ',')}%`
                : typeof calculatedValue === 'object' && calculatedValue !== null && 'priceDiff' in calculatedValue
                ? `$${formatCalculatedValue(parseFloat(value))} (${calculatedValue.priceDiff >= 0 ? '+' : ''}${calculatedValue.priceDiff.toFixed(crypto ? getPriceDecimals(crypto.price, crypto.priceDecimals) : 2).replace('.', ',')} USD, ${calculatedValue.percentDiff >= 0 ? '+' : ''}${calculatedValue.percentDiff.toFixed(2).replace('.', ',')}%)`
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

      {/* Third island: Direction and Trigger */}
      <Block margin="top" marginValue={12}>
        <Group>
          <div ref={directionRef}>
            <GroupItem
              text="Direction"
              after={
                <Text type="text" color={valueType === 'price' ? 'secondary' : 'accent'}>
                  {filteredDirectionOptions.find((opt) => opt.value === direction)?.label || 'Rise'}
                </Text>
              }
              chevron={valueType !== 'price'}
              chevronType="double"
              disabled={valueType === 'price'}
              onClick={() => {
                if (valueType !== 'price') {
                  setDirectionDropdownOpen(!directionDropdownOpen)
                }
              }}
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
        options={filteredDirectionOptions}
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
        options={filteredValueTypeOptions}
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

      {/* Chart with trigger line (show when coin is selected) */}
      {crypto && chartData.length > 0 && (
        <Block margin="top" marginValue={24}>
          {/* Timeframe selector */}
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
                  left: 15,  // Increase left margin for Stop-loss/Take-profit label
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
                {/* Current price line */}
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
                {/* Display lines depending on Direction, color depends on Trigger */}
                {triggerLevels.upper !== null && (
                  <>
                    {/* Main line with label on the left (Stop-loss/Take-profit) */}
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
                          // Get color from CSS variables
                          const root = document.documentElement
                          const color = trigger === 'stop-loss' 
                            ? getComputedStyle(root).getPropertyValue('--color-state-destructive').trim() || '#ff3b30'
                            : getComputedStyle(root).getPropertyValue('--color-state-success').trim() || '#34c759'
                          const text = trigger === 'stop-loss' ? 'Stop-loss' : 'Take-profit'
                          const textWidth = text.length * 7 + 8
                          // Position rectangle to the left of line, but inside chart area
                          // viewBox.x is the coordinate of point on line relative to chart start
                          // Account for left chart margin (70px), so label should be at position 0-60px
                          const rectX = Math.max(0, viewBox.x - textWidth - 4) // Don't go beyond left border (0)
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
                    {/* Invisible line with price on the right */}
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
                    {/* Main line with label on the left (Stop-loss/Take-profit) */}
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
                          // Get color from CSS variables
                          const root = document.documentElement
                          const color = trigger === 'stop-loss' 
                            ? getComputedStyle(root).getPropertyValue('--color-state-destructive').trim() || '#ff3b30'
                            : getComputedStyle(root).getPropertyValue('--color-state-success').trim() || '#34c759'
                          const text = trigger === 'stop-loss' ? 'Stop-loss' : 'Take-profit'
                          const textWidth = text.length * 7 + 8
                          // Position rectangle to the left of line, but inside chart area
                          // viewBox.x is the coordinate of point on line relative to chart start
                          // Account for left chart margin (70px), so label should be at position 0-60px
                          const rectX = Math.max(0, viewBox.x - textWidth - 4) // Don't go beyond left border (0)
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
                    {/* Invisible line with price on the right */}
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

