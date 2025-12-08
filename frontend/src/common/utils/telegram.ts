/**
 * Утилиты для работы с Telegram WebApp
 */

/**
 * Получить user_id из Telegram WebApp
 * @returns user_id или null, если не доступен
 */
export const getTelegramUserId = (): number | null => {
  try {
    const webApp = window.Telegram?.WebApp
    if (!webApp) {
      console.warn('[Telegram] WebApp не доступен')
      return null
    }

    const userId = webApp.initDataUnsafe?.user?.id
    if (!userId) {
      console.warn('[Telegram] user_id не найден в initDataUnsafe')
      return null
    }

    return userId
  } catch (error) {
    console.error('[Telegram] Ошибка при получении user_id:', error)
    return null
  }
}

/**
 * Получить данные пользователя из Telegram WebApp
 */
export const getTelegramUser = () => {
  try {
    const webApp = window.Telegram?.WebApp
    return webApp?.initDataUnsafe?.user || null
  } catch (error) {
    console.error('[Telegram] Ошибка при получении данных пользователя:', error)
    return null
  }
}

