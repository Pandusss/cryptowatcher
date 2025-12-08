import { createContext, useContext, useEffect, useState } from 'react'

interface ThemeContextType {
  darkTheme: boolean
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export const ThemeProvider = ({ children }: { children: React.ReactNode }) => {
  const webApp = window.Telegram?.WebApp
  const [darkTheme, setDarkTheme] = useState(
    webApp?.colorScheme === 'dark' || false
  )

  useEffect(() => {
    if (webApp) {
      const colorScheme = webApp.colorScheme
      setDarkTheme(colorScheme === 'dark')
    }
  }, [webApp])

  const toggleTheme = () => {
    setDarkTheme((prev) => !prev)
  }

  return (
    <ThemeContext.Provider value={{ darkTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

