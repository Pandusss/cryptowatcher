export type NotificationDirection = 'rise' | 'fall' | 'both'
export type NotificationTrigger = 'stop-loss' | 'take-profit'
export type NotificationValueType = 'percent' | 'absolute' | 'price'
export type NotificationSource = 'binance' | 'coingecko' | 'coinmarketcap'

export interface Notification {
  id: string
  cryptoId: string
  cryptoSymbol: string
  cryptoName: string
  currentPrice: number
  direction: NotificationDirection
  trigger: NotificationTrigger
  valueType: NotificationValueType
  value: number
  source: NotificationSource
  isActive: boolean
  createdAt: string
  updatedAt: string
}

export interface CreateNotificationDto {
  cryptoId: string
  direction: NotificationDirection
  trigger: NotificationTrigger
  valueType: NotificationValueType
  value: number
  source: NotificationSource
}

export interface UpdateNotificationDto extends Partial<CreateNotificationDto> {
  isActive?: boolean
}

