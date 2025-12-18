import { useState } from 'react'

import styles from './CryptoIcon.module.scss'

interface CryptoIconProps {
  symbol: string
  name?: string
  size?: number
  className?: string
  imageUrl?: string  // URL image from API (primary source)
}

/**
 * Mapping of cryptocurrency symbols to CoinGecko ID
 * 
 * CoinGecko uses ID as a string (e.g., "bitcoin", "ethereum")
 * 
 * How to find ID for a new coin:
 * 1. Open https://www.coingecko.com
 * 2. Find the coin through search
 * 3. Open the coin page
 * 4. ID can be found in the URL: https://www.coingecko.com/en/coins/bitcoin → ID = "bitcoin"
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

  // Form a list of URLs in order of priority
  const allUrls: string[] = []
  
  // 1. imageUrl from API (primary source, if passed)
  if (imageUrl) {
    allUrls.push(imageUrl)
  }
  
  // 2. CoinGecko CDN (if there is ID) - use the format from the API response
  // CoinGecko returns image URL directly in the API, so this fallback is used rarely
  
  // 3. CryptoIcons CDN (fallback - works by symbols)
  allUrls.push(`https://cryptoicons.org/api/icon/${lowerSymbol}/200`)
  allUrls.push(`https://cryptoicons.org/api/icon/${lowerSymbol}/100`)

  const currentUrl = allUrls[currentUrlIndex] || null

  const handleError = () => {
    if (currentUrlIndex < allUrls.length - 1) {
      setCurrentUrlIndex(currentUrlIndex + 1)
    } else {
      setHasError(true)
    }
  }

  if (hasError || !currentUrl) {
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

