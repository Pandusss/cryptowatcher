import {
  Block,
  Button,
  CryptoIcon,
  Group,
  GroupItem,
  PageLayout,
  Text,
} from '@components'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Lottie from 'lottie-react'

import { ROUTES_NAME } from '../../constants/routes'
import { apiService, type NotificationResponse } from '@services'
import { getTelegramUserId, getPriceDecimals } from '@utils'

import styles from './MainPage.module.scss'

export const MainPage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  
  // State for DND settings
  const [dndDisplay, setDndDisplay] = useState('Always')
  const [dndStartTime, setDndStartTime] = useState<string | null>(null)
  const [dndEndTime, setDndEndTime] = useState<string | null>(null)
  const [notifications, setNotifications] = useState<NotificationResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [logoAnimation, setLogoAnimation] = useState<any>(null)
  
  useEffect(() => {
    // Load Lottie animation
    fetch('/icons/logo.json')
      .then((res) => res.json())
      .then((data) => setLogoAnimation(data))
      .catch((err) => console.error('Failed to load logo animation:', err))
  }, [])

  useEffect(() => {
    // Get DND settings from location state (when returning from settings page)
    if (location.state?.dndSettings?.display) {
      setDndDisplay(location.state.dndSettings.display)
      setDndStartTime(location.state.dndSettings.startTime || null)
      setDndEndTime(location.state.dndSettings.endTime || null)
    }
  }, [location.state])

  useEffect(() => {
    // Load DND settings from server on first load
    const loadDndSettings = async () => {
      const userId = getTelegramUserId()
      if (!userId) {
        return
      }

      try {
        const settings = await apiService.getDndSettings(userId)
        if (settings.dnd_start_time && settings.dnd_end_time) {
          // Save time in format HH:MM
          setDndStartTime(settings.dnd_start_time)
          setDndEndTime(settings.dnd_end_time)
          
          // Format time for display
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
          // If both times are null, then DND is disabled
          setDndDisplay('Always')
          setDndStartTime(null as any)
          setDndEndTime(null as any)
        }
      } catch (error) {
        console.error('Failed to load DND settings:', error)
      }
    }

    // Load only if there is no data in location.state (first load)
    if (!location.state?.dndSettings?.display) {
      loadDndSettings()
    }
  }, []) // Run only once when mounting

  useEffect(() => {
    const userId = getTelegramUserId()
    if (!userId) {
      setLoading(false)
      return
    }

    // Load list of notifications
    const loadNotifications = async (showLoading = true) => {
      try {
        if (showLoading) {
          setLoading(true)
        }
        const data = await apiService.getNotifications(userId)
        setNotifications(data)
      } catch (error) {
        console.error('Failed to load notifications:', error)
      } finally {
        if (showLoading) {
          setLoading(false)
        }
      }
    }

    // Load immediately when mounting or changing path (with loading indicator)
    loadNotifications(true)

    // Update list every 30 seconds in background (without loading indicator)
    const intervalId = setInterval(() => {
      loadNotifications(false)
    }, 30000) // 30 seconds

    // Clear interval when unmounting
    return () => {
      clearInterval(intervalId)
    }
  }, [location.pathname, location.key]) // Update when path or key changes (return to main page)

  // Format notification description for display
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
      : notification.value_type === 'price'
      ? `$${notification.value.toFixed(getPriceDecimals(notification.value))}`
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
          {logoAnimation && (
            <Lottie
              animationData={logoAnimation}
              loop={true}
              autoplay={true}
              style={{
                width: '80px',
                height: '80px',
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

      {/* Don't Disturb - separate island */}
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

