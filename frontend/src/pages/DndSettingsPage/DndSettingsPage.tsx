import {
  Block,
  Button,
  Group,
  GroupItem,
  PageLayout,
  Text,
  TimePicker,
  Toggle,
} from '@components'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { ROUTES_NAME } from '../../constants/routes'
import { useTelegramBackButton } from '@hooks'
import { apiService } from '@services'
import { getTelegramUserId } from '@utils'

import styles from './DndSettingsPage.module.scss'

export const DndSettingsPage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  
  // Get initial values from location state or use defaults
  const initialStartTime = location.state?.startTime || null
  const initialEndTime = location.state?.endTime || null
  
  // Determine if DND is enabled (if both times are not null)
  const [isDndEnabled, setIsDndEnabled] = useState(initialStartTime !== null && initialEndTime !== null)
  const [startTime, setStartTime] = useState(initialStartTime || '12:00')
  const [endTime, setEndTime] = useState(initialEndTime || '07:00')
  const [isSaving, setIsSaving] = useState(false)

  // Manage Telegram Mini App back button
  useTelegramBackButton()

  // Format time for display (12:00 -> 12 PM, 07:00 -> 7 AM)
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

  // Formatting for display of the range
  const formatTimeRange = () => {
    return `${formatTimeForDisplay(startTime)} - ${formatTimeForDisplay(endTime)}`
  }

  const handleSave = async () => {
    
    const userId = getTelegramUserId()
    if (!userId) {
      console.error('User ID not found')
      return
    }

    // If DND is disabled, send null
    const dndStartTime = isDndEnabled ? startTime : null
    const dndEndTime = isDndEnabled ? endTime : null

    setIsSaving(true)
    try {
      // Save settings through API
      const result = await apiService.updateDndSettings(userId, {
        dnd_start_time: dndStartTime,
        dnd_end_time: dndEndTime,
      })


      // Return back with data
      navigate(ROUTES_NAME.MAIN, {
        state: {
          dndSettings: {
            startTime: dndStartTime,
            endTime: dndEndTime,
            display: isDndEnabled ? formatTimeRange() : 'Always',
          },
        },
      })
    } catch (error: any) {
      console.error('Failed to save DND settings:', error)
      console.error('Error details:', {
        message: error?.message,
        status: error?.status,
        response: error?.response,
        stack: error?.stack,
      })
      // Show error to user
      alert(`Failed to save settings: ${error?.message || 'Unknown error'}`)
      setIsSaving(false)
    }
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
            text="Enable Don't Disturb"
            after={
              <Toggle
                checked={isDndEnabled}
                onChange={setIsDndEnabled}
              />
            }
          />
          {isDndEnabled && (
            <>
              <GroupItem
                text="Start Time"
                after={
                  <div className={styles.timePickerWrapper}>
                    <TimePicker value={startTime} onChange={setStartTime} />
                  </div>
                }
              />
              <GroupItem
                text="End Time"
                after={
                  <div className={styles.timePickerWrapper}>
                    <TimePicker value={endTime} onChange={setEndTime} />
                  </div>
                }
              />
            </>
          )}
        </Group>
      </Block>

      <Block margin="top" marginValue={16}>
        <Text type="text" color="secondary" align="center">
          {isDndEnabled 
            ? 'Notifications will be muted during this time'
            : 'Notifications will always be sent'}
        </Text>
      </Block>

      <Block margin="top" marginValue={32} fixed="bottom">
        <Button 
          type="primary" 
          onClick={handleSave} 
          disabled={isSaving}
        >
          {isSaving ? 'Saving...' : 'Save'}
        </Button>
      </Block>
    </PageLayout>
  )
}

