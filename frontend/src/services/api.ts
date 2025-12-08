// В разработке используем относительные пути (Vite proxy)
// В продакшене будет один домен, поэтому тоже относительные пути
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
  }
}

export interface CoinListItem {
  id: string  // Changed to string to match backend
  name: string
  symbol: string
  slug: string
  imageUrl?: string
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

// Backend использует snake_case, поэтому создаем интерфейсы для API
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
  expire_time_hours?: number | null  // null означает бессрочное уведомление
}

export interface UpdateNotificationRequest {
  direction?: NotificationDirection
  trigger?: NotificationTrigger
  value_type?: NotificationValueType
  value?: number
  is_active?: boolean
  expire_time_hours?: number | null  // null означает бессрочное уведомление
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
  expire_time_hours?: number | null  // null означает бессрочное уведомление
  crypto_image_url?: string  // URL изображения монеты из CoinGecko
}

class ApiService {
  private baseUrl: string

  constructor() {
    this.baseUrl = API_BASE_URL
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    console.log('API Request:', { url, method: options?.method || 'GET', body: options?.body })
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    console.log('API Response:', { status: response.status, statusText: response.statusText, ok: response.ok })

    if (!response.ok) {
      let errorMessage = `API Error: ${response.statusText}`
      try {
        const errorData = await response.json()
        console.error('API Error data:', errorData)
        errorMessage = errorData.detail || errorData.message || errorMessage
      } catch (e) {
        // Если не удалось распарсить JSON, используем статус текст
        const text = await response.text()
        console.error('API Error text:', text)
      }
      const error: any = new Error(errorMessage)
      error.status = response.status
      throw error
    }

    const data = await response.json()
    console.log('API Response data:', data)
    return data
  }

  async getCoinChart(coinId: string, period: string = '7d'): Promise<ChartDataPoint[]> {
    try {
      const response = await this.fetch<ChartResponse>(
        `/api/v1/coins/${coinId}/chart?period=${period}`
      )
      return response.data || []
    } catch (error) {
      console.error('Failed to fetch chart data:', error)
      return []
    }
  }

  async getCoinDetails(coinId: string): Promise<CoinDetailsResponse['data'] | null> {
    try {
      const response = await this.fetch<CoinDetailsResponse>(`/api/v1/coins/${coinId}`)
      return response.data || null
    } catch (error) {
      console.error('Failed to fetch coin details:', error)
      return null
    }
  }

  async getCoinsList(limit: number = 100, start: number = 1): Promise<CoinListItem[]> {
    try {
      const response = await this.fetch<CoinsListResponse>(
        `/api/v1/coins/list?limit=${limit}&start=${start}`
      )
      return response.data || []
    } catch (error) {
      console.error('Failed to fetch coins list:', error)
      return []
    }
  }

  // Notifications API
  async getNotifications(userId: number): Promise<NotificationResponse[]> {
    try {
      const response = await this.fetch<NotificationResponse[]>(
        `/api/v1/notifications/?user_id=${userId}`
      )
      return response || []
    } catch (error) {
      console.error('Failed to fetch notifications:', error)
      return []
    }
  }

  async getNotification(notificationId: number): Promise<NotificationResponse> {
    try {
      const response = await this.fetch<NotificationResponse>(
        `/api/v1/notifications/${notificationId}`
      )
      return response
    } catch (error) {
      console.error('Failed to fetch notification:', error)
      throw error
    }
  }

  async createNotification(data: CreateNotificationRequest): Promise<NotificationResponse> {
    try {
      const response = await this.fetch<NotificationResponse>(
        '/api/v1/notifications/',
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      )
      return response
    } catch (error) {
      console.error('Failed to create notification:', error)
      throw error
    }
  }

  async updateNotification(
    notificationId: number,
    data: UpdateNotificationRequest
  ): Promise<NotificationResponse> {
    try {
      const response = await this.fetch<NotificationResponse>(
        `/api/v1/notifications/${notificationId}`,
        {
          method: 'PUT',
          body: JSON.stringify(data),
        }
      )
      return response
    } catch (error) {
      console.error('Failed to update notification:', error)
      throw error
    }
  }

  async deleteNotification(notificationId: number): Promise<void> {
    try {
      await this.fetch(`/api/v1/notifications/${notificationId}`, {
        method: 'DELETE',
      })
    } catch (error) {
      console.error('Failed to delete notification:', error)
      throw error
    }
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
    } catch (error) {
      console.error('Failed to register user:', error)
      // Не бросаем ошибку, так как это не критично
    }
  }

  // DND Settings API
  async getDndSettings(userId: number): Promise<{ dnd_start_time: string | null; dnd_end_time: string | null }> {
    try {
      const response = await this.fetch<{ dnd_start_time: string | null; dnd_end_time: string | null }>(
        `/api/v1/users/${userId}/dnd-settings`
      )
      return response
    } catch (error) {
      console.error('Failed to fetch DND settings:', error)
      return { dnd_start_time: null, dnd_end_time: null }
    }
  }

  async updateDndSettings(
    userId: number,
    settings: { dnd_start_time?: string | null; dnd_end_time?: string | null }
  ): Promise<{ dnd_start_time: string | null; dnd_end_time: string | null }> {
    try {
      const response = await this.fetch<{ dnd_start_time: string | null; dnd_end_time: string | null }>(
        `/api/v1/users/${userId}/dnd-settings`,
        {
          method: 'PUT',
          body: JSON.stringify(settings),
        }
      )
      return response
    } catch (error) {
      console.error('Failed to update DND settings:', error)
      throw error
    }
  }
}

export const apiService = new ApiService()

