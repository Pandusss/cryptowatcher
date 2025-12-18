import { useEffect, useRef, useState } from 'react'
import cn from 'classnames'

import { Dropdown } from '../Dropdown'
import { Text } from '../Text'
import styles from './TimePicker.module.scss'

type TimePickerProps = {
  value: string // Format: "HH:MM"
  onChange: (value: string) => void
  triggerRef?: React.RefObject<HTMLElement>
}

export const TimePicker = ({ value, onChange }: TimePickerProps) => {
  const [selectedHour, setSelectedHour] = useState('12')
  const [selectedMinute, setSelectedMinute] = useState('00')
  const [activePicker, setActivePicker] = useState<'hour' | 'minute' | null>(null)

  const triggerRef = useRef<HTMLDivElement>(null)

  // Generate options for hours (0-23) with formatting for display
  const hourOptions = Array.from({ length: 24 }, (_, i) => {
    const hour24 = i
    const hour12 = hour24 === 0 ? 12 : hour24 > 12 ? hour24 - 12 : hour24
    const period = hour24 >= 12 ? 'PM' : 'AM'
    const hourStr = hour24.toString().padStart(2, '0')
    
    return {
      label: `${hour12} ${period}`,
      value: hourStr,
    }
  })

  // Generate options for minutes (0, 15, 30, 45)
  const minuteOptions = [
    { label: '00', value: '00' },
    { label: '15', value: '15' },
    { label: '30', value: '30' },
    { label: '45', value: '45' },
  ]

  // Parse value when mounting and changing
  useEffect(() => {
    if (value) {
      const [hour, minute] = value.split(':')
      setSelectedHour(hour || '12')
      setSelectedMinute(minute || '00')
    }
  }, [value])

  // Format time for display (12:00 -> 12 PM)
  const formatTimeForDisplay = (hour: string, minute: string) => {
    const hourNum = parseInt(hour, 10)
    const minuteNum = parseInt(minute, 10)

    if (hourNum === 0 && minuteNum === 0) {
      return '12 AM'
    }

    const period = hourNum >= 12 ? 'PM' : 'AM'
    const displayHour = hourNum === 0 ? 12 : hourNum > 12 ? hourNum - 12 : hourNum

    if (minuteNum === 0) {
      return `${displayHour} ${period}`
    }

    return `${displayHour}:${minute.toString().padStart(2, '0')} ${period}`
  }

  const handleHourSelect = (hour: string) => {
    setSelectedHour(hour)
    onChange(`${hour}:${selectedMinute}`)
    // After selecting the hour, switch to selecting minutes
    // Use setTimeout to ensure the dropdown closes and opens again
    setTimeout(() => {
      setActivePicker('minute')
    }, 50)
  }

  const handleMinuteSelect = (minute: string) => {
    setSelectedMinute(minute)
    onChange(`${selectedHour}:${minute}`)
    setActivePicker(null)
  }

  // Determine the current options and handler depending on activePicker
  const currentOptions = activePicker === 'hour' ? hourOptions : minuteOptions
  const currentSelectedValue = activePicker === 'hour' ? selectedHour : selectedMinute
  const handleSelect = activePicker === 'hour' ? handleHourSelect : handleMinuteSelect

  return (
    <div className={styles.timePicker}>
      <div
        ref={triggerRef}
        className={cn(styles.timeDisplay, styles.clickable)}
        onClick={() => setActivePicker(activePicker === 'hour' ? null : 'hour')}
      >
        <Text type="text" color="accent">
          {formatTimeForDisplay(selectedHour, selectedMinute)}
        </Text>
      </div>

      <Dropdown
        options={currentOptions}
        active={activePicker !== null}
        selectedValue={currentSelectedValue}
        onSelect={handleSelect}
        onClose={() => {
          // Close only if not switching to selecting minutes
          if (activePicker !== 'hour') {
            setActivePicker(null)
          }
        }}
        triggerRef={triggerRef}
      />
    </div>
  )
}

