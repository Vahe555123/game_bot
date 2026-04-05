import { describe, expect, it } from 'vitest'
import { formatDualCurrencyInline, getDualCurrencyPriceDisplay } from './format'

describe('getDualCurrencyPriceDisplay', () => {
  it('shows local currency with rubles as secondary text', () => {
    const display = getDualCurrencyPriceDisplay(331, 'TRY', 1948)

    expect(display.primary).not.toContain('RUB')
    expect(display.secondary).toContain('₽')
  })

  it('falls back to rubles only when local currency is unavailable', () => {
    const display = getDualCurrencyPriceDisplay(null, 'TRY', 1948)

    expect(display.primary).toContain('₽')
    expect(display.secondary).toBeNull()
  })
})

describe('formatDualCurrencyInline', () => {
  it('joins local and ruble prices into one readable string', () => {
    expect(formatDualCurrencyInline(1299, 'INR', 7641)).toContain('/')
  })
})
