export type RegionInfo = {
  code?: string
  symbol?: string
  name?: string
}

export type RawRegionalPrice = {
  region?: string | null
  flag?: string | null
  name?: string | null
  currency_code?: string | null
  price_local?: number | null
  old_price_local?: number | null
  ps_plus_price_local?: number | null
  price_rub?: number | null
  old_price_rub?: number | null
  ps_plus_price_rub?: number | null
  has_discount?: boolean
  discount_percent?: number | null
  ps_plus_discount_percent?: number | null
  localization_code?: string | null
  localization_name?: string | null
}

export type RawCatalogProduct = {
  id: string
  name?: string | null
  main_name?: string | null
  category?: string | null
  region?: string | null
  type?: string | null
  image?: string | null
  platforms?: string | null
  publisher?: string | null
  rating?: number | null
  edition?: string | null
  description?: string | null
  price?: number | null
  old_price?: number | null
  current_price?: number | null
  price_with_currency?: string | null
  has_discount?: boolean
  discount?: number | null
  discount_percent?: number | null
  discount_end?: string | null
  has_ps_plus?: boolean
  has_ea_access?: boolean
  has_ps_plus_extra_deluxe?: boolean
  region_info?: RegionInfo | null
  rub_price?: number | null
  rub_price_old?: number | null
  min_price_rub?: number | null
  favorites_count?: number | null
  regional_prices?: RawRegionalPrice[] | null
  tags?: string[] | null
  compound?: string[] | null
  info?: string[] | null
  players_min?: number | null
  players_max?: number | null
  players_online?: boolean | null
  localization?: string | null
  localization_name?: string | null
  ps_plus_collection?: string | null
}

export type ProductRegionPrice = {
  region: string
  label: string
  name: string
  currencyCode: string | null
  flag: string | null
  priceLocal: number | null
  oldPriceLocal: number | null
  psPlusPriceLocal: number | null
  priceRub: number | null
  oldPriceRub: number | null
  psPlusPriceRub: number | null
  hasDiscount: boolean
  discountPercent: number | null
  psPlusDiscountPercent: number | null
  localizationName: string | null
}

export type CatalogProduct = {
  id: string
  name: string | null
  mainName: string
  category: string | null
  region: string | null
  routeRegion: string | null
  type: string | null
  image: string | null
  platforms: string | null
  publisher: string | null
  rating: number | null
  edition: string | null
  description: string | null
  localization: string | null
  localizationName: string | null
  hasDiscount: boolean
  discount: number | null
  discountPercent: number | null
  discountEnd: string | null
  hasPsPlus: boolean
  hasEaAccess: boolean
  hasPsPlusExtraDeluxe: boolean
  psPlusCollection: string | null
  regionInfo: RegionInfo | null
  favoritesCount: number
  priceRub: number | null
  oldPriceRub: number | null
  displayPrice: string
  displayOldPrice: string | null
  regionalPrices: ProductRegionPrice[]
  tags: string[]
  compound: string[]
  info: string[]
  playersMin?: number | null
  playersMax?: number | null
  playersOnline?: boolean
}

export type RawCatalogListResponse = {
  products: RawCatalogProduct[]
  total: number
  page: number
  limit: number
  has_next: boolean
}

export type CatalogListResponse = {
  products: CatalogProduct[]
  total: number
  page: number
  limit: number
  hasNext: boolean
}

export type CatalogQuery = {
  page?: number
  limit?: number
  sort?: string
  search?: string
  category?: string
  region?: string
  platform?: string
  players?: string
  min_price?: number
  max_price?: number
  has_discount?: boolean
  has_ps_plus?: boolean
  has_ea_access?: boolean
}

export type CatalogFilterState = {
  page: number
  limit: number
  sort: string
  search: string
  category: string
  region: string
  platform: string
  players: string
  minPrice: string
  maxPrice: string
  hasDiscount: boolean
  hasPsPlus: boolean
  hasEaAccess: boolean
}
