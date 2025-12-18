/**
 * Utilities for working with cryptocurrency prices
 */

/**
 * Determines the number of decimal places based on the price
 * @param price - Price of the cryptocurrency
 * @param cachedDecimals - Optional cached value from the API
 * @returns The number of decimal places (from 2 to 10)
 */
export const getPriceDecimals = (price: number, cachedDecimals?: number): number => {
  // If there is a cached value from the API, use it
  if (cachedDecimals !== undefined) {
    return cachedDecimals
  }
  
  // Otherwise, calculate locally based on the price
  if (price >= 1) return 2
  if (price >= 0.1) return 3
  if (price >= 0.01) return 4
  if (price >= 0.001) return 5
  if (price >= 0.0001) return 6
  if (price >= 0.00001) return 7
  if (price >= 0.000001) return 8
  if (price >= 0.0000001) return 9
  return 10
}

