/**
 * Utility functions for managing favorite tokens
 * Now uses API instead of localStorage for user-specific favorites
 */

import { apiService } from '@services'
import { getTelegramUserId } from './telegram'

/**
 * Get list of favorite token IDs from API
 */
export const getFavoriteTokens = async (): Promise<string[]> => {
  const userId = getTelegramUserId()
  if (!userId) {
    return []
  }
  
  try {
    return await apiService.getFavoriteTokens(userId)
  } catch {
    return []
  }
}

/**
 * Check if a token is in favorites (synchronous check against provided list)
 */
export const isFavoriteToken = (tokenId: string, favorites: string[]): boolean => {
  return favorites.includes(tokenId)
}

/**
 * Add token to favorites via API
 */
export const addFavoriteToken = async (tokenId: string): Promise<string[]> => {
  const userId = getTelegramUserId()
  if (!userId) {
    return []
  }
  
  try {
    return await apiService.addFavoriteToken(userId, tokenId)
  } catch {
    return []
  }
}

/**
 * Remove token from favorites via API
 */
export const removeFavoriteToken = async (tokenId: string): Promise<string[]> => {
  const userId = getTelegramUserId()
  if (!userId) {
    return []
  }
  
  try {
    return await apiService.removeFavoriteToken(userId, tokenId)
  } catch {
    return []
  }
}

/**
 * Toggle favorite status of a token via API
 * Returns the updated list of favorites
 */
export const toggleFavoriteToken = async (tokenId: string, currentFavorites: string[]): Promise<string[]> => {
  const isFavorite = currentFavorites.includes(tokenId)
  if (isFavorite) {
    return await removeFavoriteToken(tokenId)
  } else {
    return await addFavoriteToken(tokenId)
  }
}

