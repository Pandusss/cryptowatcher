import {
  Block,
  CryptoIcon,
  Group,
  GroupItem,
  ListInput,
  PageLayout,
  Text,
} from '@components'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ROUTES_NAME } from '../../constants/routes'
import { apiService, type CoinListItem } from '../../services/api'
import { useTelegramBackButton } from '@hooks'
import { getPriceDecimals, getFavoriteTokens, toggleFavoriteToken } from '@utils'

import styles from './ChooseCoinPage.module.scss'

export const ChooseCoinPage = () => {
  const navigate = useNavigate()
  const [coins, setCoins] = useState<CoinListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const hasFetchedRef = useRef(false)
  // State for price animations: Map<coinId, 'up' | 'down' | 'neutral' | null>
  const [priceAnimations, setPriceAnimations] = useState<Map<string, 'up' | 'down' | 'neutral' | null>>(new Map())
  // Ref for storing current coin list (to avoid dependency issues)
  const coinsRef = useRef<CoinListItem[]>([])
  // State for favorite tokens
  const [favoriteTokens, setFavoriteTokens] = useState<Set<string>>(new Set())

  // Manage Telegram Mini App back button
  useTelegramBackButton()

  useEffect(() => {
    // Prevent duplicate requests in StrictMode
    if (hasFetchedRef.current) {
      return
    }
    hasFetchedRef.current = true

    const fetchData = async () => {
      try {
        setLoading(true)
        
        // Load coins and favorites in parallel
        const [coins, favorites] = await Promise.all([
          apiService.getCoinsListStatic(100, 1),
          getFavoriteTokens(),
        ])
        
        setCoins(coins)
        coinsRef.current = coins // Update ref
        setFavoriteTokens(new Set(favorites))
        setLoading(false) // Show list immediately
      } catch {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // Update prices every 5 seconds
  useEffect(() => {
    if (coins.length === 0 || loading) {
      return
    }

    const updatePrices = async () => {
      try {
        // Use current coin list from ref
        const currentCoins = coinsRef.current
        if (currentCoins.length === 0) {
          return
        }

        // Get all coin IDs
        const coinIds = currentCoins.map((coin) => coin.id)

        // Make one batch request to get all prices
        const pricesData = await apiService.getCoinsListPrices(coinIds)

        // Update prices for all coins
        const updatedCoins = currentCoins.map((coin) => {
          const priceData = pricesData[coin.id]
          if (priceData && priceData.price !== undefined && priceData.price > 0) {
            const newPrice = priceData.price
            const oldPrice = coin.quote.USD.price

            // Determine price change direction (account for float precision)
            let direction: 'up' | 'down' | 'neutral' | null = null
            const priceDiff = Math.abs(oldPrice - newPrice)
            // For prices > 1 use threshold 0.01, for smaller - relative
            const threshold = oldPrice >= 1 ? 0.01 : oldPrice * 0.0001
            
            if (priceDiff > threshold) {
              direction = newPrice > oldPrice ? 'up' : 'down'
            } else {
              direction = 'neutral'
            }

            // ALWAYS trigger animation (even if neutral)
            setPriceAnimations((prev) => {
              const newMap = new Map(prev)
              newMap.set(coin.id, direction)
              return newMap
            })

            // Remove animation after 800ms
            setTimeout(() => {
              setPriceAnimations((prev) => {
                const newMap = new Map(prev)
                newMap.set(coin.id, null)
                return newMap
              })
            }, 800)

            // Return updated coin
            return {
              ...coin,
              quote: {
                ...coin.quote,
                USD: {
                  ...coin.quote.USD,
                  price: newPrice,
                  percent_change_24h: priceData.percent_change_24h ?? coin.quote.USD.percent_change_24h,
                },
              },
              priceDecimals: priceData.priceDecimals ?? coin.priceDecimals,
            }
          }
          return coin
        })

        // Update state and ref once after all updates
        setCoins(updatedCoins)
        coinsRef.current = updatedCoins
      } catch {
        // Price update failed, will retry on next interval
      }
    }

    // Первое обновление через 1 секунду после загрузки, затем каждые 5 секунд
    const initialTimeout = setTimeout(() => {
      updatePrices()
    }, 1000)

    const intervalId = setInterval(updatePrices, 5000)

    return () => {
      clearTimeout(initialTimeout)
      clearInterval(intervalId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]) // Запускаем только когда загрузка завершилась

  // Format price with spaces for thousands and comma for decimals
  const formatPrice = (price: number, coin?: CoinListItem) => {
    const decimals = getPriceDecimals(price, coin?.priceDecimals)
    // Форматируем с точками для тысяч и запятой для десятичных (например: 89.357,00)
    const parts = price.toFixed(decimals).split('.')
    const integerPart = parts[0]
    const decimalPart = parts[1] || '0'.repeat(decimals)
    
    // Добавляем точки для разделения тысяч
    const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
    
    return `${formattedInteger},${decimalPart}`
  }

  // Фильтрация и сортировка монет: избранные первыми, затем по поисковому запросу
  const filteredCoins = useMemo(() => {
    let filtered = coins
    
    // Фильтрация по поисковому запросу
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim()
      filtered = coins.filter((coin) => {
        const nameMatch = coin.name.toLowerCase().includes(query)
        const symbolMatch = coin.symbol.toLowerCase().includes(query)
        return nameMatch || symbolMatch
      })
    }
    
    // Сортировка: избранные первыми
    return [...filtered].sort((a, b) => {
      const aIsFavorite = favoriteTokens.has(a.id)
      const bIsFavorite = favoriteTokens.has(b.id)
      
      if (aIsFavorite && !bIsFavorite) return -1
      if (!aIsFavorite && bIsFavorite) return 1
      return 0
    })
  }, [coins, searchQuery, favoriteTokens])

  const handleSelectCoin = (coin: CoinListItem) => {
    // Возвращаемся на страницу создания уведомления с выбранной монетой
    const coinData = {
      id: coin.id,  // id уже строка
      symbol: coin.symbol,
      name: coin.name,
      price: coin.quote.USD.price,
      currentPrice: coin.quote.USD.price,
      priceChangePercent24h: coin.quote.USD.percent_change_24h,
      imageUrl: coin.imageUrl,
      priceDecimals: coin.priceDecimals,  // Кэшированное значение из API
    }
    navigate(ROUTES_NAME.CREATE_NOTIFICATION, {
      state: { selectedCoin: coinData },
    })
  }

  const handleClearSearch = () => {
    setSearchQuery('')
  }

  const handleToggleFavorite = async (e: React.MouseEvent, coinId: string) => {
    e.stopPropagation() // Предотвращаем клик на GroupItem
    const currentFavorites = Array.from(favoriteTokens)
    const updatedFavorites = await toggleFavoriteToken(coinId, currentFavorites)
    setFavoriteTokens(new Set(updatedFavorites))
  }

  return (
    <PageLayout>
      <Block margin="top" marginValue={16}>
        <Text type="title1" align="center">
          Choose Coin
        </Text>
      </Block>

      {/* Поисковая строка */}
      <Block margin="top" marginValue={16}>
        <Group>
          <div className={styles.searchItem}>
            <div className={styles.searchIcon}>
              <svg
                width="20"
                height="20"
                viewBox="0 0 20 20"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M9 17C13.4183 17 17 13.4183 17 9C17 4.58172 13.4183 1 9 1C4.58172 1 1 4.58172 1 9C1 13.4183 4.58172 17 9 17Z"
                  stroke="var(--color-foreground-tertiary)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M19 19L14.65 14.65"
                  stroke="var(--color-foreground-tertiary)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <ListInput
              type="text"
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search..."
              inputMode="search"
              autoComplete="off"
              className={styles.searchInput}
            />
            <button
              className={styles.closeButton}
              onClick={handleClearSearch}
              aria-label="Clear search"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M12 4L4 12M4 4L12 12"
                  stroke="var(--color-foreground-tertiary)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
        </Group>
      </Block>

      <Block margin="top" marginValue={32}>
        {loading ? (
          <Text type="text" align="center" color="secondary">
            Loading...
          </Text>
        ) : filteredCoins.length === 0 ? (
          <Text type="text" align="center" color="secondary">
            {searchQuery ? 'No coins found' : 'No coins available'}
          </Text>
        ) : (
          <Group>
            {filteredCoins.map((coin) => {
              const isFavorite = favoriteTokens.has(coin.id)
              return (
                <GroupItem
                  key={coin.id}
                  before={<CryptoIcon symbol={coin.symbol} name={coin.name} size={40} imageUrl={coin.imageUrl} />}
                  text={
                    <div className={styles.coinNameContainer}>
                      <span>{coin.name}</span>
                      <button
                        className={styles.favoriteButton}
                        onClick={(e) => handleToggleFavorite(e, coin.id)}
                        aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
                      >
                        <svg
                          width="20"
                          height="20"
                          viewBox="0 0 16 16"
                          fill={isFavorite ? 'currentColor' : 'none'}
                          stroke="currentColor"
                          strokeWidth="1.5"
                          xmlns="http://www.w3.org/2000/svg"
                          className={isFavorite ? styles.favoriteIconActive : styles.favoriteIcon}
                        >
                          <path
                            d="M8 2L9.09 5.26L12.5 5.61L10 8.14L10.82 11.5L8 9.77L5.18 11.5L6 8.14L3.5 5.61L6.91 5.26L8 2Z"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </button>
                    </div>
                  }
                  description={coin.symbol}
                  after={
                    <Text 
                      type="text" 
                      color="secondary"
                      className={
                        priceAnimations.get(coin.id)
                          ? priceAnimations.get(coin.id) === 'up'
                            ? styles.priceUpdatedUp
                            : priceAnimations.get(coin.id) === 'down'
                            ? styles.priceUpdatedDown
                            : styles.priceUpdatedNeutral
                          : ''
                      }
                    >
                      {coin.quote.USD.price > 0 
                        ? `$${formatPrice(coin.quote.USD.price, coin)}`
                        : '...'
                      }
                    </Text>
                  }
                  chevron
                  onClick={() => handleSelectCoin(coin)}
                />
              )
            })}
          </Group>
        )}
      </Block>
    </PageLayout>
  )
}

