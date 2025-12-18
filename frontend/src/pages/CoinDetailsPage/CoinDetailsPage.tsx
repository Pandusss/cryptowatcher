import {
  Block,
  Button,
  CryptoIcon,
  PageLayout,
  Text,
  CryptoChart,
} from '@components'
import { useEffect, useState, useMemo } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import { ROUTES_NAME } from '../../constants/routes'
import type { CryptoCurrency } from '@types'
import { apiService } from '../../services/api'
import { useTelegramBackButton, useLiveChartData } from '@hooks'
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
  const [selectedPeriod, setSelectedPeriod] = useState<'1d' | '7d' | '30d' | '1y'>('7d')

  // Use hook to manage chart data
  const {
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
  } = useLiveChartData({
    coinId: coin?.id || '',
    initialPeriod: selectedPeriod,
    updateInterval: 5000,
    autoUpdateChart: true,
  })

  // Manage Telegram Mini App back button
  useTelegramBackButton()

  useEffect(() => {
    const fetchCoinData = async () => {
      // Check if coin is passed via location state
      const coinFromState = location.state?.coin || location.state?.selectedCoin
      
      if (coinFromState) {
        // Convert from ChooseCoinPage format to CoinListItem format
        const cryptoCurrency: CryptoCurrency = {
          id: coinFromState.id || id || '',
          symbol: coinFromState.symbol || '',
          name: coinFromState.name || '',
          currentPrice: coinFromState.price || coinFromState.currentPrice || 0,
          priceChange24h: coinFromState.priceChange24h,
          priceChangePercent24h: coinFromState.priceChangePercent24h,
          imageUrl: coinFromState.imageUrl,
          priceDecimals: coinFromState.priceDecimals,  // Use cached value from API
        }
        setCoin(cryptoCurrency)
        setCurrentPrice(cryptoCurrency.currentPrice)
      } else if (id) {
        // Fetch coin details by ID from API
        try {
          const coinDetails = await apiService.getCoinDetails(id)
          if (coinDetails) {
            const cryptoCurrency = {
              id: coinDetails.id || id,
              symbol: coinDetails.symbol || '',
              name: coinDetails.name || '',
              currentPrice: coinDetails.currentPrice || 0,
              priceChange24h: coinDetails.priceChange24h,
              priceChangePercent24h: coinDetails.priceChangePercent24h,
              imageUrl: coinDetails.imageUrl,
              priceDecimals: coinDetails.priceDecimals,  // Use cached value from API
            }
            setCoin(cryptoCurrency)
            setCurrentPrice(cryptoCurrency.currentPrice)
          }
        } catch (error) {
          console.error('Failed to fetch coin details:', error)
        }
      }
    }
    
    fetchCoinData()
  }, [location.state, id, setCurrentPrice])

  // Load chart data when period changes
  useEffect(() => {
    if (coin?.id) {
      loadChartData(selectedPeriod)
    }
  }, [coin?.id, selectedPeriod, loadChartData])

  const handleChooseCoin = () => {
    if (coin) {
      // Check if there is information about edit mode in location state
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
    // Format with dots for thousands and comma for decimals (e.g.: 89.357,00)
    const parts = price.toFixed(decimals).split('.')
    const integerPart = parts[0]
    const decimalPart = parts[1] || '0'.repeat(decimals)
    
    // Add dots for thousands separation
    const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
    
    return `${formattedInteger},${decimalPart}`
  }

  // Use useMemo to recalculate when coin.currentPrice changes
  const formattedPrice = useMemo(() => {
    return coin ? `$${formatPrice(coin.currentPrice)}` : '-'
  }, [coin?.currentPrice, coin?.priceDecimals])
  
  const priceChange = coin?.priceChangePercent24h ?? 0
  const isPriceRising = priceChange >= 0
  
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
          className={priceUpdated ? (
            priceDirection === 'up' ? styles.priceUpdatedUp : 
            priceDirection === 'down' ? styles.priceUpdatedDown : 
            styles.priceUpdatedNeutral
          ) : ''}
        >
          {formattedPrice}
        </Text>
        <span style={{ color: isPriceRising ? 'var(--color-state-success)' : undefined }}>
          <Text type="text" color={isPriceRising ? undefined : 'danger'}>
            {isPriceRising ? '+' : ''}{priceChange.toFixed(2)}%
          </Text>
        </span>
      </Block>

      <Block margin="top" marginValue={44}>
        <CryptoChart
          data={chartData}
          period={selectedPeriod}
          currentPrice={coin?.currentPrice}
          options={{
            showVolume: true,
            showPriceAnimation: true,
            height: 280,
            margin: { top: 10, right: 5, left: 5, bottom: 5 },
            showCurrentPriceLine: true,
          }}
          isLoading={chartLoading}
          error={error}
          priceDecimals={coin?.priceDecimals}
        />
      </Block>

      <Block margin="top" marginValue={24} row justify="center" gap={8}>
        {PERIOD_OPTIONS.map((option) => (
          <Button
            key={option.value}
            type={selectedPeriod === option.value ? 'primary' : 'secondary'}
            onClick={() => setSelectedPeriod(option.value as any)}
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