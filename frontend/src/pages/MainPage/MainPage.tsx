import {
  Block,
  Button,
  CryptoIcon,
  Group,
  GroupItem,
  PageLayout,
  SourceIcon,
  Text,
} from '@components'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Lottie from 'lottie-react'

import { ROUTES_NAME } from '../../constants/routes'
import { apiService, type NotificationResponse } from '@services'
import { getTelegramUserId } from '@utils'

import styles from './MainPage.module.scss'

export const MainPage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  
  // Состояние для настроек DND
  const [dndDisplay, setDndDisplay] = useState('Always')
  const [dndStartTime, setDndStartTime] = useState<string | null>(null)
  const [dndEndTime, setDndEndTime] = useState<string | null>(null)
  // Состояние для источника данных
  const [sourceDisplay, setSourceDisplay] = useState('CoinGecko')
  const [notifications, setNotifications] = useState<NotificationResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [logoAnimation, setLogoAnimation] = useState<any>(null)
  
  useEffect(() => {
    // Загружаем Lottie анимацию
    fetch('/icons/logo.json')
      .then((res) => res.json())
      .then((data) => setLogoAnimation(data))
      .catch((err) => console.error('Failed to load logo animation:', err))
  }, [])

  useEffect(() => {
    // Получаем настройки DND из location state (при возврате со страницы настроек)
    if (location.state?.dndSettings?.display) {
      setDndDisplay(location.state.dndSettings.display)
      setDndStartTime(location.state.dndSettings.startTime || null)
      setDndEndTime(location.state.dndSettings.endTime || null)
    }
    // Получаем настройки Source из location state
    if (location.state?.sourceDisplay) {
      setSourceDisplay(location.state.sourceDisplay)
    }
  }, [location.state])

  useEffect(() => {
    // Загружаем DND настройки с сервера при первой загрузке
    const loadDndSettings = async () => {
      const userId = getTelegramUserId()
      if (!userId) {
        return
      }

      try {
        const settings = await apiService.getDndSettings(userId)
        if (settings.dnd_start_time && settings.dnd_end_time) {
          // Сохраняем время в формате HH:MM
          setDndStartTime(settings.dnd_start_time)
          setDndEndTime(settings.dnd_end_time)
          
          // Форматируем время для отображения
          const formatTimeForDisplay = (time: string) => {
            const [hours, minutes] = time.split(':')
            const hour = parseInt(hours, 10)
            const minute = parseInt(minutes, 10)
            
            if (hour === 0 && minute === 0) {
              return '12 AM'
            }
            
            const period = hour >= 12 ? 'PM' : 'AM'
            const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour
            
            if (minute === 0) {
              return `${displayHour} ${period}`
            }
            
            return `${displayHour}:${minute.toString().padStart(2, '0')} ${period}`
          }
          
          const display = `${formatTimeForDisplay(settings.dnd_start_time)} - ${formatTimeForDisplay(settings.dnd_end_time)}`
          setDndDisplay(display)
        } else {
          // Если оба времени null, значит DND отключен
          setDndDisplay('Always')
          setDndStartTime(null as any)
          setDndEndTime(null as any)
        }
      } catch (error) {
        console.error('Failed to load DND settings:', error)
      }
    }

    // Загружаем только если нет данных в location.state (первая загрузка)
    if (!location.state?.dndSettings?.display) {
      loadDndSettings()
    }
  }, []) // Запускаем только один раз при монтировании

  useEffect(() => {
    // Загружаем список уведомлений
    const loadNotifications = async () => {
      const userId = getTelegramUserId()
      if (!userId) {
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        const data = await apiService.getNotifications(userId)
        setNotifications(data)
      } catch (error) {
        console.error('Failed to load notifications:', error)
      } finally {
        setLoading(false)
      }
    }

    loadNotifications()
  }, [location.pathname, location.key]) // Обновляем при изменении пути или ключа (возврат на главную)

  // Преобразуем sourceDisplay в sourceId для иконки
  const getSourceId = (display: string): string => {
    const mapping: Record<string, string> = {
      'CoinGecko': 'coingecko',
      'Binance': 'binance',
      'CoinMarketCap': 'cmc',
      'Coinbase': 'coinbase',
    }
    return mapping[display] || 'coingecko'
  }

  // Форматируем описание уведомления для отображения
  const formatNotificationDescription = (notification: NotificationResponse) => {
    const directionMap: Record<string, string> = {
      'rise': 'Rise',
      'fall': 'Fall',
      'both': 'Both',
    }
    const directionText = directionMap[notification.direction] || notification.direction

    const triggerMap: Record<string, string> = {
      'stop-loss': 'Stop-loss',
      'take-profit': 'Take-profit',
    }
    const triggerText = triggerMap[notification.trigger] || notification.trigger

    const valueText = notification.value_type === 'percent' 
      ? `${notification.value}%`
      : `$${notification.value.toFixed(2)}`

    return `${directionText} - ${triggerText} - ${valueText}`
  }

  return (
    <PageLayout>
      <Block margin="top" marginValue={6} align="center">
        <div
          style={{
            width: '80px',
            height: '80px',
            marginBottom: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {logoAnimation ? (
            <Lottie
              animationData={logoAnimation}
              loop={true}
              autoplay={true}
              style={{
                width: '80px',
                height: '80px',
              }}
            />
          ) : (
            <img 
              src="/icons/logo.webp" 
              alt="Crypto Watcher" 
              style={{ 
                width: '80px', 
                height: '80px', 
                objectFit: 'contain'
              }} 
            />
          )}
        </div>
        <Text type="title1" align="center" weight="bold">
          Crypto Watcher
        </Text>
      </Block>

      <Block margin="top" marginValue={2}>
        <Text type="text" color="secondary" align="center">
          Create any notification in a seconds
        </Text>
      </Block>

      {/* Source - отдельный островок */}
      <Block margin="top" marginValue={12}>
        <Group>
          <GroupItem
            text="Source"
            after={
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <SourceIcon
                  sourceId={location.state?.source || getSourceId(sourceDisplay)}
                  size={20}
                />
                <Text type="text" color="secondary">
                  {sourceDisplay}
                </Text>
              </div>
            }
            chevron
            chevronType="single"
            onClick={() => {
              navigate(ROUTES_NAME.SOURCE_SETTINGS, {
                state: {
                  source: location.state?.source || 'coingecko',
                },
              })
            }}
          />
        </Group>
      </Block>

      {/* Don't Disturb - отдельный островок */}
      <Block margin="top" marginValue={12}>
        <Group>
          <GroupItem
            text="Don't Disturb"
            after={
              <Text type="text" color="secondary">
                {dndDisplay}
              </Text>
            }
            chevron
            onClick={() => {
              navigate(ROUTES_NAME.DND_SETTINGS, {
                state: {
                  startTime: dndStartTime || null,
                  endTime: dndEndTime || null,
                },
              })
            }}
          />
        </Group>
      </Block>

      <Block margin="top" marginValue={16}>
        <div className={styles.notificationsContainer}>
          <Group header="NOTIFICATIONS">
            {loading ? (
              <GroupItem
                text="Loading..."
                disabled
              />
            ) : notifications.length === 0 ? (
              <GroupItem
                text="Here will appear your notifications"
                description="Create your first notification"
                disabled
              />
            ) : (
              notifications.map((notification) => (
                <GroupItem
                  key={notification.id}
                  text={notification.crypto_name}
                  description={formatNotificationDescription(notification)}
                  before={
                    <CryptoIcon
                      symbol={notification.crypto_symbol}
                      name={notification.crypto_name}
                      size={32}
                      imageUrl={notification.crypto_image_url}
                    />
                  }
                  chevron
                  onClick={() => {
                    navigate(`${ROUTES_NAME.EDIT_NOTIFICATION.replace(':id', String(notification.id))}`)
                  }}
                />
              ))
            )}
          </Group>
        </div>
      </Block>

      <Block margin="top" marginValue={32} fixed="bottom">
        <Button
          type="primary"
          onClick={() => navigate(ROUTES_NAME.CREATE_NOTIFICATION)}
        >
          Create Notification
        </Button>
      </Block>
    </PageLayout>
  )
}

