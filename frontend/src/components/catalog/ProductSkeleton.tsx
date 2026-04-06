export function ProductSkeleton() {
  return (
    <div className="overflow-hidden rounded-[28px] border border-white/10 bg-slate-950/65">
      <div className="aspect-square animate-pulse bg-gradient-to-br from-white/10 to-transparent" />
      <div className="space-y-4 p-5">
        <div className="space-y-2">
          <div className="h-3 w-1/3 animate-pulse rounded-full bg-white/10" />
          <div className="h-5 w-3/4 animate-pulse rounded-full bg-white/10" />
          <div className="h-5 w-1/2 animate-pulse rounded-full bg-white/10" />
        </div>
        <div className="h-10 animate-pulse rounded-2xl bg-white/10" />
        <div className="h-12 animate-pulse rounded-2xl bg-white/10" />
      </div>
    </div>
  )
}
