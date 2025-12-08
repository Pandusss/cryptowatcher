export interface CryptoCurrency {
  priceDecimals?: number  // Количество знаков после запятой (кэшируется в Redis на 1 день)
  id: string
  symbol: string
  name: string
  currentPrice: number
  priceChange24h?: number
  priceChangePercent24h?: number
  imageUrl?: string
}

