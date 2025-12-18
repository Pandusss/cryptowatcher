/**
 * Utilities for working with Telegram WebApp
 */

/**
 * Get user_id from Telegram WebApp
 * @returns user_id or null if not available
 */
export const getTelegramUserId = (): number | null => {
  try {
    const webApp = window.Telegram?.WebApp
    if (!webApp) {
      return null
    }

    return webApp.initDataUnsafe?.user?.id || null
  } catch {
    return null
  }
}

/**
 * Get user data from Telegram WebApp
 */
export const getTelegramUser = () => {
  try {
    const webApp = window.Telegram?.WebApp
    return webApp?.initDataUnsafe?.user || null
  } catch {
    return null
  }
}
