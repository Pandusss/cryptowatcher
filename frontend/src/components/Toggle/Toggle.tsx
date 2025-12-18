import { useState } from 'react'
import cn from 'classnames'

import styles from './Toggle.module.scss'

interface ToggleProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  className?: string
}

export const Toggle = ({ checked, onChange, disabled = false, className }: ToggleProps) => {
  const [isAnimating, setIsAnimating] = useState(false)

  const handleClick = () => {
    if (disabled) return
    
    setIsAnimating(true)
    onChange(!checked)
    
    setTimeout(() => {
      setIsAnimating(false)
    }, 300)
  }

  return (
    <div
      className={cn(
        styles.toggle,
        checked && styles.checked,
        disabled && styles.disabled,
        isAnimating && styles.animating,
        className
      )}
      onClick={handleClick}
      role="switch"
      aria-checked={checked}
      aria-disabled={disabled}
    >
      <div className={styles.track}>
        <div className={styles.thumb} />
      </div>
    </div>
  )
}

