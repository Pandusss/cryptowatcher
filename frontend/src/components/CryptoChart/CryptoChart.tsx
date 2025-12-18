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

  // Calculate values for the chart
  const chartCalculations = useMemo(() => {
    // Convert triggerLines to triggerLevels for calculateChartValues
    const triggerLevels = triggerLines ? {
      upper: triggerLines.upper?.value,
      lower: triggerLines.lower?.value,
    } : undefined
    return calculateChartValues(data, period, priceDecimals, triggerLevels)
  }, [data, period, priceDecimals, triggerLines])

  // Determine the color of the chart
  const chartColor = customColor || chartCalculations.chartColor

  // Custom rendering of ticks to shift extreme marks
  const renderCustomTick = (props: any) => {
    const { x, y, payload, index } = props
    const ticks = chartCalculations.xAxisTicks
    const isFirst = index === 0
    const isLast = ticks && index === ticks.length - 1
    
    // Shift: first mark to the right by 8px, last mark to the left by 8px
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

  // Formatting for the Y axis
  const yAxisTickFormatter = yAxisFormatter 
    ? yAxisFormatter 
    : (value: number) => formatPriceForYAxis(value, priceDecimals)

  // Formatting for the price tooltip
  const priceTooltipFormatter = tooltipFormatter?.price 
    ? tooltipFormatter.price 
    : (value: number) => formatPriceForTooltip(value, priceDecimals)

  // Formatting for the volume tooltip
  const volumeTooltipFormatter = tooltipFormatter?.volume 
    ? tooltipFormatter.volume 
    : formatVolume

  // Formatting for the date tooltip
  const dateTooltipFormatter = tooltipFormatter?.date 
    ? tooltipFormatter.date 
    : (dateStr: string) => formatDateForTooltip(dateStr, period)

  if (isLoading) {
    return (
      <div className={styles.chartContainer} style={{ height }}>
        <div className={styles.loading}>Loading chart...</div>
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
        <div className={styles.empty}>No data to display</div>
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
          
          {/* X axis */}
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
          
          {/* Y axis for price */}
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
          
          {/* Y axis for volume (hidden) */}
          {showVolume && (
            <YAxis 
              yAxisId="volume"
              orientation="left"
              hide
              domain={chartCalculations.volumeDomain}
            />
          )}
          
          {/* Tooltip */}
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
          
          {/* Price chart */}
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
          
          {/* Volumes */}
          {showVolume && (
            <Bar
              yAxisId="volume"
              dataKey="volume"
              fill="var(--color-foreground-tertiary)"
              opacity={0.3}
              radius={[2, 2, 0, 0]}
            />
          )}
          
          {/* Current price line */}
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
          
          {/* Trigger lines */}
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