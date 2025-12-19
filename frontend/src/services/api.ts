// In development uses relative paths (Vite proxy)
// In production, same domain, so also relative paths
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

import type {
  Notification,
  NotificationDirection,
  NotificationTrigger,
  NotificationValueType,
} from '@types'

export interface ChartDataPoint {
  date: string
  price: number
  volume?: number
}

export interface ChartResponse {
  data: ChartDataPoint[]
}

export interface CoinDetailsResponse {
  data: {
    id: string
    symbol: string
    name: string
    currentPrice: number
    priceChange24h?: number
    priceChangePercent24h?: number
    imageUrl?: string
    priceDecimals?: number  // Number of decimal places (cached in Redis for 1 day)
  }
}

export interface CoinListItem {
  id: string  // Changed to string to match backend
  name: string
  symbol: string
  slug: string
  imageUrl?: string
  priceDecimals?: number  // Количество знаков после запятой (кэшируется в Redis на 1 день)
  quote: {
    USD: {
      price: number
      percent_change_24h?: number
      volume_24h?: number
    }
  }
}

export interface CoinsListResponse {
  data: CoinListItem[]
}

// Backend uses snake_case, so we create interfaces for API
export interface CreateNotificationRequest {
  user_id: number
  crypto_id: string
  crypto_symbol: string
  crypto_name: string
  direction: NotificationDirection
  trigger: NotificationTrigger
  value_type: NotificationValueType
  value: number
  current_price: number
  expire_time_hours?: number | null  // null means no expiration
}

export interface UpdateNotificationRequest {
  direction?: NotificationDirection
  trigger?: NotificationTrigger
  value_type?: NotificationValueType
  value?: number
  is_active?: boolean
  expire_time_hours?: number | null  // null means no expiration
}

export interface NotificationResponse {
  id: number
  user_id: number
  crypto_id: string
  crypto_symbol: string
  crypto_name: string
  direction: NotificationDirection
  trigger: NotificationTrigger
  value_type: NotificationValueType
  value: number
  current_price: number
  is_active: boolean
  created_at: string
  updated_at?: string
  triggered_at?: string
  expire_time_hours?: number | null  // null means no expiration
  crypto_image_url?: string  // URL изображения монеты из CoinGecko
}

class ApiService {
  private baseUrl: string

  constructor() {
    this.baseUrl = API_BASE_URL
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    if (!response.ok) {
      let errorMessage = `API Error: ${response.statusText}`
      try {
        const errorData = await response.json()
        errorMessage = errorData.detail || errorData.message || errorMessage
      } catch {
        // If JSON parse fails, use status text
      }
      const error: Error & { status?: number } = new Error(errorMessage)
      error.status = response.status
      throw error
    }

    return await response.json()
  }

  async getCoinChart(coinId: string, period: string = '7d'): Promise<ChartDataPoint[]> {
    try {
      const response = await this.fetch<ChartResponse>(
        `/api/v1/coins/${coinId}/chart?period=${period}`
      )
      return response.data || []
    } catch {
      return []
    }
  }

  async getCoinDetails(coinId: string): Promise<CoinDetailsResponse['data'] | null> {
    try {
      const response = await this.fetch<CoinDetailsResponse>(`/api/v1/coins/${coinId}`)
      return response.data || null
    } catch {
      return null
    }
  }

  async getCoinsList(limit: number = 100, start: number = 1): Promise<CoinListItem[]> {
    try {
      const response = await this.fetch<CoinsListResponse>(
        `/api/v1/coins/list?limit=${limit}&start=${start}`
      )
      return response.data || []
    } catch {
      return []
    }
  }

  async getCoinsListStatic(limit: number = 100, start: number = 1): Promise<CoinListItem[]> {
    try {
      const response = await this.fetch<CoinsListResponse>(
        `/api/v1/coins/list/static?limit=${limit}&start=${start}`
      )
      return response.data || []
    } catch {
      return []
    }
  }

  async getCoinsListPrices(coinIds: string[]): Promise<Record<string, { price: number; percent_change_24h: number; volume_24h: number; priceDecimals: number }>> {
    try {
      const response = await this.fetch<{ data: Record<string, { price: number; percent_change_24h: number; volume_24h: number; priceDecimals: number }> }>(
        `/api/v1/coins/list/prices`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(coinIds),
        }
      )
      return response.data || {}
    } catch {
      return {}
    }
  }

  // Notifications API
  async getNotifications(userId: number): Promise<NotificationResponse[]> {
    try {
      const response = await this.fetch<NotificationResponse[]>(
        `/api/v1/notifications/?user_id=${userId}`
      )
      return response || []
    } catch {
      return []
    }
  }

  async getNotification(notificationId: number): Promise<NotificationResponse> {
    return await this.fetch<NotificationResponse>(
      `/api/v1/notifications/${notificationId}`
    )
  }

  async createNotification(data: CreateNotificationRequest): Promise<NotificationResponse> {
    return await this.fetch<NotificationResponse>(
      '/api/v1/notifications/',
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    )
  }

  async updateNotification(
    notificationId: number,
    data: UpdateNotificationRequest
  ): Promise<NotificationResponse> {
    return await this.fetch<NotificationResponse>(
      `/api/v1/notifications/${notificationId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      }
    )
  }

  async deleteNotification(notificationId: number): Promise<void> {
    await this.fetch(`/api/v1/notifications/${notificationId}`, {
      method: 'DELETE',
    })
  }

  // Users API
  async registerUser(userData: {
    id: number
    username?: string
    first_name?: string
    last_name?: string
    language_code?: string
  }): Promise<void> {
    try {
      await this.fetch('/api/v1/users/register', {
        method: 'POST',
        body: JSON.stringify(userData),
      })
    } catch {
      // Non-critical operation, silently ignore errors
    }
  }

  // DND Settings API
  async getDndSettings(userId: number): Promise<{ dnd_start_time: string | null; dnd_end_time: string | null }> {
    try {
      return await this.fetch<{ dnd_start_time: string | null; dnd_end_time: string | null }>(
        `/api/v1/users/${userId}/dnd-settings`
      )
    } catch {
      return { dnd_start_time: null, dnd_end_time: null }
    }
  }

  async updateDndSettings(
    userId: number,
    settings: { dnd_start_time?: string | null; dnd_end_time?: string | null }
  ): Promise<{ dnd_start_time: string | null; dnd_end_time: string | null }> {
    return await this.fetch<{ dnd_start_time: string | null; dnd_end_time: string | null }>(
      `/api/v1/users/${userId}/dnd-settings`,
      {
        method: 'PUT',
        body: JSON.stringify(settings),
      }
    )
  }

  // Favorite Tokens API
  async getFavoriteTokens(userId: number): Promise<string[]> {
    try {
      const response = await this.fetch<{ favorite_tokens: string[] }>(
        `/api/v1/users/${userId}/favorite-tokens`
      )
      return response.favorite_tokens || []
    } catch {
      return []
    }
  }

  async addFavoriteToken(userId: number, tokenId: string): Promise<string[]> {
    try {
      const response = await this.fetch<{ favorite_tokens: string[] }>(
        `/api/v1/users/${userId}/favorite-tokens/${tokenId}`,
        {
          method: 'POST',
        }
      )
      return response.favorite_tokens || []
    } catch {
      return []
    }
  }

  async removeFavoriteToken(userId: number, tokenId: string): Promise<string[]> {
    try {
      const response = await this.fetch<{ favorite_tokens: string[] }>(
        `/api/v1/users/${userId}/favorite-tokens/${tokenId}`,
        {
          method: 'DELETE',
        }
      )
      return response.favorite_tokens || []
    } catch {
      return []
    }
  }

  async updateFavoriteTokens(userId: number, tokenIds: string[]): Promise<string[]> {
    try {
      const response = await this.fetch<{ favorite_tokens: string[] }>(
        `/api/v1/users/${userId}/favorite-tokens`,
        {
          method: 'PUT',
          body: JSON.stringify({ favorite_tokens: tokenIds }),
        }
      )
      return response.favorite_tokens || []
    } catch {
      return []
    }
  }
}

export const apiService = new ApiService()

