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
import { getPriceDecimals } from '@utils'

import styles from './ChooseCoinPage.module.scss'

export const ChooseCoinPage = () => {
  const navigate = useNavigate()
  const [coins, setCoins] = useState<CoinListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const hasFetchedRef = useRef(false)

  // Управление кнопкой "Назад" в Telegram Mini App
  useTelegramBackButton()

  useEffect(() => {
    // Защита от повторных запросов в StrictMode
    if (hasFetchedRef.current) {
      return
    }
    hasFetchedRef.current = true

    const fetchCoins = async () => {
      try {
        setLoading(true)
        
        // Загружаем все данные из кэша (статика + цены) - быстро
        // Цены обновляются каждые 10 секунд в фоновом режиме, поэтому всегда актуальны
        const coins = await apiService.getCoinsListStatic(100, 1)
        setCoins(coins)
        setLoading(false) // Показываем список сразу
      } catch (error) {
        console.error('Failed to fetch coins:', error)
        setLoading(false)
      }
    }

    fetchCoins()
  }, [])

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

  // Фильтрация монет по поисковому запросу
  const filteredCoins = useMemo(() => {
    if (!searchQuery.trim()) {
      return coins
    }
    
    const query = searchQuery.toLowerCase().trim()
    return coins.filter((coin) => {
      const nameMatch = coin.name.toLowerCase().includes(query)
      const symbolMatch = coin.symbol.toLowerCase().includes(query)
      return nameMatch || symbolMatch
    })
  }, [coins, searchQuery])

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
            {filteredCoins.map((coin) => (
              <GroupItem
                key={coin.id}
                before={<CryptoIcon symbol={coin.symbol} name={coin.name} size={40} imageUrl={coin.imageUrl} />}
                text={coin.name}
                description={coin.symbol}
                after={
                  <Text type="text" color="secondary">
                    {coin.quote.USD.price > 0 
                      ? `$${formatPrice(coin.quote.USD.price, coin)}`
                      : '...'
                    }
                  </Text>
                }
                chevron
                onClick={() => handleSelectCoin(coin)}
              />
            ))}
          </Group>
        )}
      </Block>
    </PageLayout>
  )
}

