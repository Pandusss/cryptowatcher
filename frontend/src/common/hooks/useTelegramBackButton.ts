import { useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { ROUTES_NAME } from '../../constants/routes'

/**
 * Определяет целевую страницу для кнопки "Назад" на основе текущего пути
 * Использует фиксированную иерархию страниц:
 * 
 * MainPage (нет кнопки)
 *   ├─> CreateNotificationPage -> MainPage
 *   │     └─> ChooseCoinPage -> CreateNotificationPage
 *   │           └─> CoinDetailsPage -> ChooseCoinPage
 *   ├─> EditNotificationPage -> MainPage
 *   └─> DndSettingsPage -> MainPage
 */
const getBackRoute = (currentPath: string): string | null => {
  // Главная страница - нет кнопки назад
  if (currentPath === ROUTES_NAME.MAIN) {
    return null
  }

  // Create Notification (новое уведомление) - назад на главную
  if (currentPath === ROUTES_NAME.CREATE_NOTIFICATION) {
    return ROUTES_NAME.MAIN
  }

  // Edit Notification (редактирование) - назад на главную
  // Путь будет /edit-notification/:id, но это обрабатывается через CREATE_NOTIFICATION с id
  if (currentPath.startsWith('/edit-notification/')) {
    return ROUTES_NAME.MAIN
  }

  // Choose Coin - назад на главную
  // (так как при возврате на CreateNotificationPage без криптовалюты будет цикл редиректов)
  if (currentPath === ROUTES_NAME.CHOOSE_COIN) {
    return ROUTES_NAME.MAIN
  }

  // Coin Details - назад на Choose Coin
  // (так как CoinDetailsPage открывается только из ChooseCoinPage)
  if (currentPath.startsWith('/coin-details/')) {
    return ROUTES_NAME.CHOOSE_COIN
  }

  // DND Settings - назад на главную
  if (currentPath === ROUTES_NAME.DND_SETTINGS) {
    return ROUTES_NAME.MAIN
  }

  // По умолчанию - на главную
  return ROUTES_NAME.MAIN
}

/**
 * Хук для управления кнопкой "Назад" в Telegram Mini App
 * Использует фиксированную иерархию страниц вместо истории браузера
 */
export const useTelegramBackButton = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const webApp = window.Telegram?.WebApp

  useEffect(() => {
    if (!webApp) return

    const backButton = webApp.BackButton
    const backRoute = getBackRoute(location.pathname)

    // Если нет целевой страницы (главная), скрываем кнопку
    if (!backRoute) {
      backButton.hide()
      return
    }

    // Показываем кнопку на всех остальных страницах
    backButton.show()

    // Обработчик нажатия на кнопку "Назад"
    const handleBackClick = () => {
      // Переходим на целевую страницу согласно иерархии
      // Помечаем, что это возврат по кнопке "Назад", чтобы избежать циклов редиректов
      navigate(backRoute, { state: { fromBackButton: true } })
    }

    // Подписываемся на событие клика
    backButton.onClick(handleBackClick)

    // Очистка при размонтировании или изменении страницы
    return () => {
      backButton.offClick(handleBackClick)
      // Скрываем кнопку при размонтировании компонента
      backButton.hide()
    }
  }, [location.pathname, navigate, webApp])
}

