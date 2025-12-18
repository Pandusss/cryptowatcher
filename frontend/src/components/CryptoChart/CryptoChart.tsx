import React, { useMemo } from 'react'
import {
  Area,
  Bar,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { 
  convertServerDateToLocal, 
  getCurrentLocalTime 
} from '../../common/utils/chartTimeUtils'

import { ChartDataPoint } from '../../services/api'
import { ChartPeriod, CryptoChartProps } from '../../types/chart.types'
import {
  calculateChartValues,
  formatDateForAxis,
  formatDateForTooltip,
  formatPriceForTooltip,
  formatPriceForYAxis,
  formatVolume,
  getChartColor,
} from '../../common/utils/chartUtils'
import { getPriceDecimals } from '../../common/utils/price'

import styles from './CryptoChart.module.scss'

const CryptoChart: React.FC<CryptoChartProps> = ({
  data,
  period,
  currentPrice,
  options = {},
  onPeriodChange,
  isLoading = false,
  error = null,
  priceDecimals = 2,
}) => {
  const {
    showVolume = true,
    color: customColor,
    showPriceAnimation = false,
    height = 280,
    margin = { top: 10, right: 5, left: 5, bottom: 5 },
    showCurrentPriceLine = false,
    showTriggerLines = false,
    triggerLines,
    yAxisFormatter,
    tooltipFormatter,
  } = options

  // Рассчитываем значения для графика
  const chartCalculations = useMemo(() => {
    // Преобразуем triggerLines в triggerLevels для calculateChartValues
    const triggerLevels = triggerLines ? {
      upper: triggerLines.upper?.value,
      lower: triggerLines.lower?.value,
    } : undefined
    return calculateChartValues(data, period, priceDecimals, triggerLevels)
  }, [data, period, priceDecimals, triggerLines])

  // Определяем цвет графика
  const chartColor = customColor || chartCalculations.chartColor

  // Кастомный рендеринг тиков для смещения крайних меток
  const renderCustomTick = (props: any) => {
    const { x, y, payload, index } = props
    const ticks = chartCalculations.xAxisTicks
    const isFirst = index === 0
    const isLast = ticks && index === ticks.length - 1
    
    // Смещение: первая метка вправо на 8px, последняя влево на 8px
    const offsetX = isFirst ? 8 : isLast ? -8 : 0
    
    return (
      <text
        x={x + offsetX}
        y={y}
        fill="var(--color-foreground-tertiary)"
        fontSize={10}
        textAnchor="middle"
      >
        {formatDateForAxis(payload.value, period)}
      </text>
    )
  }

  // Форматирование для оси Y
  const yAxisTickFormatter = yAxisFormatter 
    ? yAxisFormatter 
    : (value: number) => formatPriceForYAxis(value, priceDecimals)

  // Форматирование для тултипа цены
  const priceTooltipFormatter = tooltipFormatter?.price 
    ? tooltipFormatter.price 
    : (value: number) => formatPriceForTooltip(value, priceDecimals)

  // Форматирование для тултипа объема
  const volumeTooltipFormatter = tooltipFormatter?.volume 
    ? tooltipFormatter.volume 
    : formatVolume

  // Форматирование для тултипа даты
  const dateTooltipFormatter = tooltipFormatter?.date 
    ? tooltipFormatter.date 
    : (dateStr: string) => formatDateForTooltip(dateStr, period)

  if (isLoading) {
    return (
      <div className={styles.chartContainer} style={{ height }}>
        <div className={styles.loading}>Загрузка графика...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.chartContainer} style={{ height }}>
        <div className={styles.error}>{error}</div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className={styles.chartContainer} style={{ height }}>
        <div className={styles.empty}>Нет данных для отображения</div>
      </div>
    )
  }

  return (
    <div className={styles.chartContainer}>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={data}
          margin={margin}
        >
          <defs>
            <linearGradient id="colorGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={chartColor} stopOpacity={0.3} />
              <stop offset="100%" stopColor={chartColor} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          
          {/* Ось X */}
          <XAxis 
            dataKey="date" 
            axisLine={{ stroke: 'var(--color-border-separator)' }}
            tickLine={{ stroke: 'transparent' }}
            height={40}
            ticks={chartCalculations.xAxisTicks}
            interval={0}
            angle={0}
            tick={renderCustomTick}
            minTickGap={period === '1d' ? 12 : period === '30d' || period === '1y' ? 8 : 6}
          />
          
          {/* Ось Y для цены */}
          <YAxis 
            yAxisId="price"
            orientation="right"
            domain={chartCalculations.yAxisDomain}
            tick={{ fill: 'var(--color-foreground-tertiary)', fontSize: 10 }}
            axisLine={{ stroke: 'transparent' }}
            tickLine={{ stroke: 'transparent' }}
            width={45}
            ticks={chartCalculations.yAxisTicks}
            allowDecimals={true}
            tickFormatter={yAxisTickFormatter}
          />
          
          {/* Ось Y для объема (скрыта) */}
          {showVolume && (
            <YAxis 
              yAxisId="volume"
              orientation="left"
              hide
              domain={chartCalculations.volumeDomain}
            />
          )}
          
          {/* Тултип */}
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-background-modal)',
              borderColor: 'var(--color-border-separator)',
              borderRadius: '8px',
              padding: '8px 12px',
            }}
            labelStyle={{ 
              color: 'var(--color-foreground-primary)',
              fontSize: '12px',
              marginBottom: '4px',
            }}
            itemStyle={{ 
              color: 'var(--color-foreground-primary)',
              fontSize: '12px',
            }}
            formatter={(value: number, name: string) => {
              if (name === 'price') {
                return [priceTooltipFormatter(value), 'Price']
              }
              if (name === 'volume') {
                return [volumeTooltipFormatter(value), 'Vol 24h']
              }
              return [value, name]
            }}
            labelFormatter={(label) => dateTooltipFormatter(label as string)}
            cursor={{ stroke: chartColor, strokeWidth: 1, strokeDasharray: '3 3' }}
          />
          
          {/* График цены */}
          <Area
            yAxisId="price"
            type="monotone"
            dataKey="price"
            stroke={chartColor}
            strokeWidth={2}
            fill="url(#colorGradient)"
            dot={false}
            activeDot={{ 
              r: 4, 
              fill: chartColor, 
              strokeWidth: 2, 
              stroke: 'var(--color-background-primary)' 
            }}
            connectNulls={false}
          />
          
          {/* Объемы */}
          {showVolume && (
            <Bar
              yAxisId="volume"
              dataKey="volume"
              fill="var(--color-foreground-tertiary)"
              opacity={0.3}
              radius={[2, 2, 0, 0]}
            />
          )}
          
          {/* Линия текущей цены */}
          {showCurrentPriceLine && currentPrice != null && (
            <ReferenceLine
              yAxisId="price"
              y={currentPrice}
              stroke="var(--color-foreground-secondary)"
              strokeWidth={1}
              strokeDasharray="3 3"
              label={{
                value: `$${currentPrice.toFixed(priceDecimals)}`,
                position: 'right',
                fill: 'var(--color-foreground-secondary)',
                fontSize: 11,
              }}
            />
          )}
          
          {/* Линии триггеров */}
          {showTriggerLines && triggerLines?.upper !== undefined && (
            <ReferenceLine
              yAxisId="price"
              y={triggerLines.upper.value}
              stroke={triggerLines.upper.color || 'var(--color-state-success)'}
              strokeWidth={2}
              strokeDasharray="5 5"
              label={{
                value: triggerLines.upper.label,
                position: 'left',
                fill: triggerLines.upper.color || 'var(--color-state-success)',
                fontSize: 11,
                fontWeight: 'bold',
              }}
            />
          )}
          
          {showTriggerLines && triggerLines?.lower !== undefined && (
            <ReferenceLine
              yAxisId="price"
              y={triggerLines.lower.value}
              stroke={triggerLines.lower.color || 'var(--color-state-destructive)'}
              strokeWidth={2}
              strokeDasharray="5 5"
              label={{
                value: triggerLines.lower.label,
                position: 'left',
                fill: triggerLines.lower.color || 'var(--color-state-destructive)',
                fontSize: 11,
                fontWeight: 'bold',
              }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

export default CryptoChart