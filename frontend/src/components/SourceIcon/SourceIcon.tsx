import { useState } from 'react'

import styles from './SourceIcon.module.scss'

interface SourceIconProps {
  sourceId: string
  size?: number
  className?: string
}

/**
 * Component for displaying the source icon
 * Supports local files from the assets/icons/sources/ folder
 * File format: {sourceId}.png, {sourceId}.svg, {sourceId}.jpg
 */
export const SourceIcon = ({
  sourceId,
  size = 24,
  className,
}: SourceIconProps) => {
  const [currentUrlIndex, setCurrentUrlIndex] = useState(0)
  const [hasError, setHasError] = useState(false)

  // Path to local icons
  // Vite automatically serves files from the public folder
  const iconPaths = [
    `/icons/sources/${sourceId}.png`,
    `/icons/sources/${sourceId}.svg`,
  ]

  const currentPath = iconPaths[currentUrlIndex] || null

  const handleError = () => {
    if (currentUrlIndex < iconPaths.length - 1) {
      setCurrentUrlIndex(currentUrlIndex + 1)
    } else {
      setHasError(true)
    }
  }

  if (hasError || !currentPath) {
    return (
      <div
        className={className}
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          backgroundColor: 'var(--color-fill-secondary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: size * 0.4,
          fontWeight: 'bold',
          color: 'var(--color-foreground-primary)',
          flexShrink: 0,
        }}
      >
        {sourceId.charAt(0).toUpperCase()}
      </div>
    )
  }

  return (
    <img
      src={currentPath}
      alt={sourceId}
      width={size}
      height={size}
      className={className}
      style={{
        borderRadius: '50%',
        objectFit: 'cover',
        flexShrink: 0,
      }}
      onError={handleError}
    />
  )
}

