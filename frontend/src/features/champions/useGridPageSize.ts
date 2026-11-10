import { useLayoutEffect, useRef, useState } from 'react'

export const ROWS_PER_PAGE = 3

export function useGridPageSize() {
  const gridRef = useRef<HTMLDivElement>(null)
  const [columns, setColumns] = useState(8)
  useLayoutEffect(() => {
    const grid = gridRef.current
    if (!grid) return
    const measure = () => {
      const style = getComputedStyle(grid)
      const width = grid.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)
      const minimum = parseFloat(style.getPropertyValue('--champion-card-min')) || 75
      const gap = parseFloat(style.columnGap) || 0
      if (width > 0) setColumns(Math.max(1, Math.floor((width + gap + .01) / (minimum + gap))))
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(grid)
    // Media queries can change the card minimum without changing container width.
    window.addEventListener('resize', measure)
    return () => { observer.disconnect(); window.removeEventListener('resize', measure) }
  }, [])
  return { gridRef, columns, pageSize: columns * ROWS_PER_PAGE }
}
