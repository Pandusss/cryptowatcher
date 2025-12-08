import { useState } from 'react'

import styles from './CryptoIcon.module.scss'

interface CryptoIconProps {
  symbol: string
  name?: string
  size?: number
  className?: string
  imageUrl?: string  // URL изображения из API (приоритетный источник)
}

/**
 * Маппинг символов криптовалют к CoinGecko ID
 * 
 * CoinGecko использует ID как строку (например, "bitcoin", "ethereum")
 * 
 * Как найти ID для новой монеты:
 * 1. Откройте https://www.coingecko.com
 * 2. Найдите монету через поиск
 * 3. Откройте страницу монеты
 * 4. ID можно найти в URL: https://www.coingecko.com/en/coins/bitcoin → ID = "bitcoin"
 */
const COINGECKO_IDS: Record<string, string> = {
  BTC: 'bitcoin',
  ETH: 'ethereum',
  USDT: 'tether',
  XRP: 'ripple',
  TON: 'the-open-network',
  TRX: 'tron',
  NOT: 'notcoin',
  BNB: 'binancecoin',
  SOL: 'solana',
  ADA: 'cardano',
  DOGE: 'dogecoin',
  MATIC: 'matic-network',
  DOT: 'polkadot',
  AVAX: 'avalanche-2',
  LTC: 'litecoin',
  UNI: 'uniswap',
  ATOM: 'cosmos',
  LINK: 'chainlink',
  ETC: 'ethereum-classic',
}

const getCoinGeckoId = (symbol: string): string | null => {
  return COINGECKO_IDS[symbol] || null
}

export const CryptoIcon = ({
  symbol,
  name,
  size = 40,
  className,
  imageUrl,
}: CryptoIconProps) => {
  const [currentUrlIndex, setCurrentUrlIndex] = useState(0)
  const [hasError, setHasError] = useState(false)

  const upperSymbol = symbol.toUpperCase()
  const lowerSymbol = symbol.toLowerCase()
  const cgId = getCoinGeckoId(upperSymbol)

  // Формируем список URL в порядке приоритета
  const allUrls: string[] = []
  
  // 1. imageUrl из API (приоритетный источник, если передан)
  if (imageUrl) {
    allUrls.push(imageUrl)
  }
  
  // 2. CoinGecko CDN (если есть ID) - используем формат из API ответа
  // CoinGecko возвращает image URL напрямую в API, поэтому этот fallback используется редко
  
  // 3. CryptoIcons CDN (fallback - работает по символам)
  allUrls.push(`https://cryptoicons.org/api/icon/${lowerSymbol}/200`)
  allUrls.push(`https://cryptoicons.org/api/icon/${lowerSymbol}/100`)

  const currentUrl = allUrls[currentUrlIndex] || null

  const handleError = () => {
    if (currentUrlIndex < allUrls.length - 1) {
      // Пробуем следующий URL
      setCurrentUrlIndex(currentUrlIndex + 1)
    } else {
      // Все URL не загрузились
      setHasError(true)
    }
  }

  if (hasError || !currentUrl) {
    // Fallback - показываем первую букву символа
    return (
      <div
        className={className}
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          backgroundColor: 'var(--color-fill-secondary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: size * 0.4,
          fontWeight: 'bold',
          color: 'var(--color-foreground-primary)',
          flexShrink: 0,
        }}
      >
        {symbol.charAt(0).toUpperCase()}
      </div>
    )
  }

  return (
    <img
      src={currentUrl}
      alt={name || symbol}
      width={size}
      height={size}
      className={className}
      style={{
        borderRadius: '50%',
        objectFit: 'cover',
        flexShrink: 0,
      }}
      onError={handleError}
    />
  )
}

