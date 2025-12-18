import cn from 'classnames'
import React, { ChangeEvent } from 'react'

import styles from './ListInput.module.scss'

export interface ListInputProps {
  textColor?: 'primary' | 'secondary' | 'tertiary'
  value?: string | number
  onChange?: (value: string) => void
  onBlur?: () => void
  onFocus?: () => void
  type?: 'text' | 'number' | 'password' | 'email' | 'tel' | 'url' | 'search'
  placeholder?: string
  disabled?: boolean
  className?: string
  autoComplete?: 'on' | 'off'
  maxLength?: number
  minLength?: number
  pattern?: string
  required?: boolean
  readOnly?: boolean
  name?: string
  id?: string
  inputMode?:
    | 'none'
    | 'text'
    | 'decimal'
    | 'numeric'
    | 'tel'
    | 'search'
    | 'email'
    | 'url'
  after?: React.ReactNode
  inputRef?: React.RefObject<HTMLInputElement>
}

export const ListInput: React.FC<ListInputProps> = ({
  value,
  onChange,
  type = 'text',
  placeholder,
  disabled = false,
  className,
  autoComplete = 'off',
  maxLength,
  minLength,
  pattern,
  required = false,
  readOnly = false,
  name,
  id,
  textColor = 'primary',
  inputMode,
  after,
  onBlur,
  onFocus,
  inputRef,
}) => {
  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (onChange) {
      onChange(e.target.value)
    }
  }

  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    if (onFocus) {
      onFocus()
    }
    
    // On mobile devices, scroll the input field into the visible area
    // with a small delay, to give the keyboard time to open
    setTimeout(() => {
      e.target.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'center',
        inline: 'nearest'
      })
    }, 300)
  }

  return (
    <div className={styles.listInputContainer}>
      <input
        ref={inputRef}
        className={cn(
          styles.listInput,
          textColor && styles[`listInput-${textColor}`],
          className
        )}
        type={type}
        value={value}
        onChange={handleChange}
        onBlur={onBlur}
        onFocus={handleFocus}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete={autoComplete}
        maxLength={maxLength}
        minLength={minLength}
        pattern={pattern}
        required={required}
        readOnly={readOnly}
        name={name}
        id={id}
        inputMode={inputMode}
      />
      <div>{after}</div>
    </div>
  )
}

