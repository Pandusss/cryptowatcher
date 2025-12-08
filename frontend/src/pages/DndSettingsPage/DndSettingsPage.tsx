import {
  Block,
  Button,
  Group,
  GroupItem,
  PageLayout,
  Text,
} from '@components'
import { useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { ROUTES_NAME } from '../../constants/routes'
import { useTelegramBackButton } from '@hooks'

import styles from './DndSettingsPage.module.scss'

export const DndSettingsPage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  
  // Получаем начальные значения из location state или используем дефолтные
  const initialStartTime = location.state?.startTime || '12:00'
  const initialEndTime = location.state?.endTime || '07:00'
  
  const [startTime, setStartTime] = useState(initialStartTime)
  const [endTime, setEndTime] = useState(initialEndTime)
  
  const startTimeInputRef = useRef<HTMLInputElement>(null)
  const endTimeInputRef = useRef<HTMLInputElement>(null)

  // Управление кнопкой "Назад" в Telegram Mini App
  useTelegramBackButton()

  // Форматирование времени для отображения (12:00 -> 12 PM, 07:00 -> 7 AM)
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

  // Форматирование для отображения диапазона
  const formatTimeRange = () => {
    return `${formatTimeForDisplay(startTime)} - ${formatTimeForDisplay(endTime)}`
  }

  const handleSave = () => {
    // TODO: Сохранить настройки через API
    // Пока просто возвращаемся назад с данными
    navigate(ROUTES_NAME.MAIN, {
      state: {
        dndSettings: {
          startTime,
          endTime,
          display: formatTimeRange(),
        },
      },
    })
  }

  return (
    <PageLayout>
      <Block margin="top" marginValue={16} align="center">
        <Text type="title1" align="center">
          Don't Disturb
        </Text>
      </Block>

      <Block margin="top" marginValue={32}>
        <Group>
          <GroupItem
            text="Start Time"
            after={
              <div className={styles.timeInputWrapper}>
                <input
                  ref={startTimeInputRef}
                  type="time"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className={styles.timeInput}
                />
                <span className={styles.timeDisplay}>
                  <Text type="text" color="accent">
                    {formatTimeForDisplay(startTime)}
                  </Text>
                </span>
              </div>
            }
            onClick={() => startTimeInputRef.current?.showPicker()}
          />
          <GroupItem
            text="End Time"
            after={
              <div className={styles.timeInputWrapper}>
                <input
                  ref={endTimeInputRef}
                  type="time"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  className={styles.timeInput}
                />
                <span className={styles.timeDisplay}>
                  <Text type="text" color="accent">
                    {formatTimeForDisplay(endTime)}
                  </Text>
                </span>
              </div>
            }
            onClick={() => endTimeInputRef.current?.showPicker()}
          />
        </Group>
      </Block>

      <Block margin="top" marginValue={16}>
        <Text type="text" color="secondary" align="center">
          Notifications will be muted during this time
        </Text>
      </Block>

      <Block margin="top" marginValue={32} fixed="bottom">
        <Button type="primary" onClick={handleSave}>
          Save
        </Button>
      </Block>
    </PageLayout>
  )
}

