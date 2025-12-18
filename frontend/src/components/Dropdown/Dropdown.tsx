import cn from 'classnames'
import { useEffect, useRef } from 'react'

import { Text } from '../Text'
import styles from './Dropdown.module.scss'

type DropdownOption = {
  label: string
  value: string
}

type DropdownProps = {
  options: DropdownOption[]
  active: boolean
  selectedValue?: string
  onSelect: (value: string) => void
  onClose: () => void
  className?: string
  triggerRef?: React.RefObject<HTMLElement>
}

export const Dropdown = ({
  options,
  active,
  selectedValue,
  onSelect,
  onClose,
  className,
  triggerRef,
}: DropdownProps) => {
  const dropdownRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!active || !triggerRef?.current || !dropdownRef.current) {
      return
    }

    // Reset maxHeight before positioning
    const dropdownElement = dropdownRef.current
    dropdownElement.style.maxHeight = ''

    // Use requestAnimationFrame to ensure dropdown has rendered
    requestAnimationFrame(() => {
      if (!triggerRef?.current || !dropdownRef.current) {
        return
      }

      const triggerRect = triggerRef.current.getBoundingClientRect()
      const viewportHeight = window.innerHeight
      const viewportWidth = window.innerWidth
      const spacing = 8

      // Get real sizes of dropdown after rendering
      const dropdownRect = dropdownElement.getBoundingClientRect()
      const dropdownHeight = dropdownRect.height || 300
      const dropdownWidth = dropdownRect.width || 200

      // Calculate available space
      const spaceBelow = viewportHeight - triggerRect.bottom - spacing
      const spaceAbove = triggerRect.top - spacing

      // Calculate position from below (default)
      let top = triggerRect.bottom + spacing
      let right = viewportWidth - triggerRect.right

      // If it doesn't fit below, but fits above - open above
      if (spaceBelow < dropdownHeight && spaceAbove > spaceBelow) {
        top = triggerRect.top - dropdownHeight - spacing
        if (top < spacing) {
          top = spacing
          dropdownElement.style.maxHeight = `${spaceAbove - spacing * 2}px`
        }
      } else if (spaceBelow < dropdownHeight) {
        // If there is little space below, limit the height
        dropdownElement.style.maxHeight = `${spaceBelow - spacing}px`
      }

      // Check horizontal boundaries
      if (right < spacing) {
        right = spacing
      }
      if (right + dropdownWidth > viewportWidth - spacing) {
        right = viewportWidth - dropdownWidth - spacing
        if (right < spacing) {
          right = spacing
        }
      }

      dropdownElement.style.position = 'fixed'
      dropdownElement.style.top = `${top}px`
      dropdownElement.style.right = `${right}px`
    })

    const handleClickOutside = (event: PointerEvent) => {
      const target = event.target as Node

      if (
        dropdownRef.current?.contains(target) ||
        triggerRef?.current?.contains(target)
      ) {
        return
      }

      onClose()
    }

    document.addEventListener('pointerdown', handleClickOutside, true)

    return () => {
      document.removeEventListener('pointerdown', handleClickOutside, true)
    }
  }, [active, onClose, triggerRef])

  const handleSelect = (value: string) => {
    onSelect(value)
    onClose()
  }

  return (
    <div
      ref={dropdownRef}
      className={cn(
        styles.dropdown,
        active && styles.dropdownActive,
        className
      )}
    >
      <ul className={styles.list}>
        {options.map(({ label, value }) => {
          const isSelected = value === selectedValue

          return (
            <li
              key={value}
              className={cn(styles.item, isSelected && styles.itemActive)}
              onClick={() => handleSelect(value)}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className={cn(
                  styles.checkIcon,
                  isSelected && styles.checkIconActive
                )}
              >
                <path
                  d="M13.3333 4L6 11.3333L2.66667 8"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>

              <Text type="text" color="primary">
                {label}
              </Text>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

