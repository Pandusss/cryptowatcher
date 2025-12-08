import {
  Block,
  Button,
  Group,
  GroupItem,
  PageLayout,
  SourceIcon,
  Text,
} from '@components'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useTelegramBackButton } from '@hooks'
import cn from 'classnames'

import { ROUTES_NAME } from '../../constants/routes'

import styles from './SourceSettingsPage.module.scss'

type SourceOption = {
  id: string
  name: string
  available: boolean
}

const SOURCE_OPTIONS: SourceOption[] = [
  { id: 'coingecko', name: 'CoinGecko', available: true },
  { id: 'binance', name: 'Binance', available: false },
  { id: 'cmc', name: 'CoinMarketCap', available: false },
  { id: 'coinbase', name: 'Coinbase', available: false },
]

export const SourceSettingsPage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  useTelegramBackButton()

  // Получаем текущий выбранный источник из location state или используем CoinGecko по умолчанию
  const [selectedSource, setSelectedSource] = useState<string>(
    location.state?.source || 'coingecko'
  )

  const handleSelectSource = (sourceId: string) => {
    const source = SOURCE_OPTIONS.find((opt) => opt.id === sourceId)
    if (source && source.available) {
      setSelectedSource(sourceId)
    }
  }

  const handleSave = () => {
    const sourceName = SOURCE_OPTIONS.find((opt) => opt.id === selectedSource)?.name || 'CoinGecko'
    
    navigate(ROUTES_NAME.MAIN, {
      state: {
        source: selectedSource,
        sourceDisplay: sourceName,
      },
    })
  }

  return (
    <PageLayout>
      <Block margin="top" marginValue={16} align="center">
        <Text type="title1" align="center">
          Source
        </Text>
      </Block>

      <Block margin="top" marginValue={32}>
        <Group>
          {SOURCE_OPTIONS.map((source) => {
            const isSelected = source.id === selectedSource
            const isAvailable = source.available

            return (
              <GroupItem
                key={source.id}
                before={<SourceIcon sourceId={source.id} size={24} />}
                text={
                  !isAvailable ? (
                    <span style={{ textDecoration: 'line-through' }}>
                      {source.name}
                    </span>
                  ) : (
                    source.name
                  )
                }
                after={
                  !isAvailable ? (
                    <Text type="text" color="secondary">
                      Soon
                    </Text>
                  ) : isSelected ? (
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 16 16"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                      style={{ 
                        flexShrink: 0,
                        color: 'var(--color-accent-primary)'
                      }}
                    >
                      <path
                        d="M13.3333 4L6 11.3333L2.66667 8"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  ) : null
                }
                disabled={!isAvailable}
                onClick={() => handleSelectSource(source.id)}
              />
            )
          })}
        </Group>
      </Block>

      <Block margin="top" marginValue={32} fixed="bottom">
        <Button type="primary" onClick={handleSave}>
          Save
        </Button>
      </Block>
    </PageLayout>
  )
}

