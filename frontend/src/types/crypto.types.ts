export interface CryptoCurrency {
  id: string
  symbol: string
  name: string
  currentPrice: number
  priceChange24h?: number
  priceChangePercent24h?: number
  imageUrl?: string
}

