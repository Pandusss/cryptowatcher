import { ThemeProvider } from '@context'
import '@styles/index.scss'
import { useEffect } from 'react'

import { useTheme } from '@context'
import { apiService } from '@services'
import { getTelegramUserId, getTelegramUser } from '@utils'

import Routes from './Routes'

const webApp = window.Telegram?.WebApp

function App() {
  const { darkTheme } = useTheme()

  useEffect(() => {
    webApp?.ready()
    webApp?.expand()
    webApp?.disableVerticalSwipes()
    
    // Register user on first Mini App open
    const registerUser = async () => {
      const userId = getTelegramUserId()
      const userData = getTelegramUser()
      
      if (userId && userData) {
        await apiService.registerUser({
          id: userId,
          username: userData.username,
          first_name: userData.first_name,
          last_name: userData.last_name,
          language_code: userData.language_code,
        })
      }
    }
    
    registerUser()
  }, [])

  useEffect(() => {
    document.documentElement.setAttribute(
      'data-theme',
      darkTheme ? 'dark' : 'light'
    )

    if (darkTheme) {
      window.document.documentElement.style.backgroundColor = '#1c1c1e'
      webApp?.setBackgroundColor('#1c1c1e')
      webApp?.setHeaderColor('#1c1c1e')
      webApp?.setBottomBarColor('#1c1c1e')
    } else {
      window.document.documentElement.style.backgroundColor = '#EFEFF4'
      webApp?.setBackgroundColor('#EFEFF4')
      webApp?.setHeaderColor('#EFEFF4')
      webApp?.setBottomBarColor('#EFEFF4')
    }
  }, [darkTheme])

  return <Routes />
}

function AppWithProviders() {
  return (
    <ThemeProvider>
      <App />
    </ThemeProvider>
  )
}

export default AppWithProviders

