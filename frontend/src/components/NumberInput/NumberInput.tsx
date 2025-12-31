import { useState, useRef, useEffect } from 'react'
import cn from 'classnames'

import styles from './NumberInput.module.scss'

interface NumberInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  inputRef?: React.RefObject<HTMLInputElement>
  onFocus?: () => void
  min?: number
  max?: number
  step?: number
}

export const NumberInput = ({
  value,
  onChange,
  placeholder,
  disabled = false,
  className,
  inputRef,
  onFocus,
  min,
  max,
  step = 1,
}: NumberInputProps) => {
  const [isFocused, setIsFocused] = useState(false)
  const internalRef = useRef<HTMLInputElement>(null)
  const inputElementRef = inputRef || internalRef

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let newValue = e.target.value
    // Replace comma with dot for internal storage (parseFloat works with dots)
    // But allow both comma and dot for user input
    if (newValue === '' || /^-?\d*[,.]?\d*$/.test(newValue)) {
      // Convert comma to dot for internal storage
      const normalizedValue = newValue.replace(',', '.')
      onChange(normalizedValue)
    }
  }

  const handleIncrement = () => {
    // Value is stored with dot, so parseFloat works directly
    const currentValue = parseFloat(value) || 0
    const newValue = currentValue + step
    const finalValue = max !== undefined ? Math.min(newValue, max) : newValue
    onChange(finalValue.toString())
  }

  const handleDecrement = () => {
    // Value is stored with dot, so parseFloat works directly
    const currentValue = parseFloat(value) || 0
    const newValue = currentValue - step
    const finalValue = min !== undefined ? Math.max(newValue, min) : newValue
    onChange(finalValue.toString())
  }

  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    setIsFocused(true)
    if (onFocus) {
      onFocus()
    }
    
    // On mobile devices, scroll the input field into the visible area
    setTimeout(() => {
      e.target.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'center',
        inline: 'nearest'
      })
    }, 300)
  }

  const handleBlur = () => {
    setIsFocused(false)
  }

  // Display value with comma instead of dot for Russian locale
  const displayValue = value.replace('.', ',')

  return (
    <div className={cn(styles.numberInputContainer, className)}>
      <input
        ref={inputElementRef}
        type="text"
        inputMode="decimal"
        value={displayValue}
        onChange={handleChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        className={styles.numberInput}
      />
      {!disabled && (
        <div className={styles.controls}>
          <button
            type="button"
            className={styles.controlButton}
            onClick={handleIncrement}
            disabled={max !== undefined && parseFloat(value || '0') >= max}
            aria-label="Increase value"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M6 2L6 10M2 6L10 6"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
          <button
            type="button"
            className={styles.controlButton}
            onClick={handleDecrement}
            disabled={min !== undefined && parseFloat(value || '0') <= min}
            aria-label="Decrease value"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M2 6L10 6"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      )}
    </div>
  )
}

