import { Text } from '@components'
import cn from 'classnames'
import { useEffect, useRef, useState } from 'react'

import styles from './GroupItem.module.scss'

interface GroupProps {
  text?: React.ReactNode
  description?: React.ReactNode
  before?: React.ReactNode
  after?: React.ReactNode
  onClick?: () => void
  disabled?: boolean
  chevron?: boolean
  chevronType?: 'single' | 'double' // 'single' for navigation, 'double' for dropdown
  className?: string
}

const GROUP_ITEM_GAP = 10
const ITEM_LEFT_GAP = 16

const renderText = (text: string | React.ReactNode) => {
  if (typeof text === 'string') {
    return <Text type="text">{text}</Text>
  }
  return text
}

const renderDescription = (description: string | React.ReactNode) => {
  if (typeof description === 'string') {
    return <Text type="caption">{description}</Text>
  }
  return description
}

export const GroupItem = ({
  text,
  description,
  before,
  after,
  disabled,
  onClick,
  chevron,
  chevronType = 'single',
  className,
}: GroupProps) => {
  const beforeRef = useRef<HTMLDivElement>(null)

  const [leftGapBottomBorder, setLeftGapBottomBorder] = useState(0)

  const handleClick = () => {
    if (onClick && !disabled) {
      onClick()
    }
  }

  useEffect(() => {
    if (beforeRef.current) {
      const beforeWidth = beforeRef.current.getBoundingClientRect().width
      setLeftGapBottomBorder(beforeWidth + ITEM_LEFT_GAP + GROUP_ITEM_GAP)
      return
    }

    setLeftGapBottomBorder(ITEM_LEFT_GAP)
  }, [before])

  return (
    <div
      className={cn(
        styles.container,
        onClick && styles.clickable,
        disabled && styles.disabled,
        className
      )}
      onClick={handleClick}
      data-group-item
    >
      {before && (
        <div ref={beforeRef} className={styles.before}>
          {before}
        </div>
      )}
      <div className={styles.main}>
        <div className={styles.content}>
          {text && renderText(text)}
          {description && renderDescription(description)}
        </div>
        {after && <div className={styles.after}>{after}</div>}
        {chevron && (
          <div className={cn(styles.chevron, chevronType === 'double' && styles.chevronDouble)}>
            {chevronType === 'double' ? (
              <svg
                width="16"
                height="16"
                viewBox="0 0 12 12"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M2.5 4.5L6 1L9.5 4.5"
                  stroke="currentColor"
                  strokeWidth="1"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M2.5 7.5L6 11L9.5 7.5"
                  stroke="currentColor"
                  strokeWidth="1"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            ) : (
              <svg
                width="7"
                height="12"
                viewBox="0 0 7 12"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M1 1L6 6L1 11"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>
        )}
      </div>
      <div
        data-group-item-border-bottom
        className={styles.bottomBorder}
        style={{ left: leftGapBottomBorder }}
      />
    </div>
  )
}

