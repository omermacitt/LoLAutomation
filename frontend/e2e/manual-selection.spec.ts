import { expect, test } from '@playwright/test'
import type { Settings, SelectionNotice } from '../src/api/contracts'
import { catalog, health, settings } from '../src/test/fixtures'
import { runeCatalog, runePage } from '../src/test/runeFixtures'

test('manual selection warning stays visible across pages, survives blocked audio, clears on lock and Stop', async ({ page }, info) => {
  await page.addInitScript(() => { Object.defineProperty(window, 'AudioContext', { value: undefined, configurable: true }) })
  const state = { running: true, notice: { id: 1, code: 'no_preference', role: 'JUNGLE', champion_id: null } as SelectionNotice | null,
    stops: 0, writes: 0, starts: 0 }
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/health') return route.fulfill({ json: { ...health, running: state.running, selection: state.notice } })
    if (path === '/api/champion-catalog') return route.fulfill({ json: catalog })
    if (path === '/api/session') return route.fulfill({ json: { token: 'development-session-token-12345' } })
    if (path === '/api/settings') {
      if (route.request().method() !== 'GET') { state.writes++; throw new Error('Notification must not save settings') }
      return route.fulfill({ json: settings as Settings, headers: { ETag: '"1"' } })
    }
    if (path.endsWith('/portrait') || path.includes('/runes/icons/')) return route.fulfill({ status: 404, body: '' })
    if (path === '/api/runes/editor-catalog') return route.fulfill({ json: runeCatalog })
    if (path.endsWith('/runes/recommended')) return route.fulfill({ json: { champion_id: Number(path.split('/')[3]), source: 'bundled', page: runePage, unavailableReason: null } })
    if (path.endsWith('/skins')) {
      const id = Number(path.split('/')[3])
      return route.fulfill({ json: { champion_id: id, skins: [{ id: id * 1000, name: 'Default' }] } })
    }
    if (path.endsWith('/artwork')) return route.fulfill({ status: 404, body: '' })
    if (path === '/api/stop_automation') { state.stops++; state.running = false; state.notice = null; return route.fulfill({ json: { status: 'stopped' } }) }
    if (path === '/api/start_automation') state.starts++
    throw new Error(`Unexpected request: ${path}`)
  })
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  const alert = page.getByRole('region', { name: 'Manuel seçim bildirimi', exact: true })
  await expect(alert).toBeInViewport()
  await expect(alert).toContainText('Orman için şampiyon tercihi yok')
  await expect(alert).toContainText('Ses çalınamadı.')
  await alert.getByRole('button', { name: 'Sesi kapat' }).click()
  await expect(alert.getByRole('button', { name: 'Sesi aç' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Rünler', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Rün çalışma alanı', exact: true })).toBeVisible()
  await page.getByRole('region', { name: 'Rün çalışma alanı', exact: true }).scrollIntoViewIfNeeded()
  await expect(alert).toBeInViewport()
  await page.getByRole('button', { name: 'Kostümler', exact: true }).click()
  await page.getByRole('region', { name: 'Kostüm galerisi', exact: true }).scrollIntoViewIfNeeded()
  await expect(alert).toBeInViewport()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('manual-selection-alert.png'), fullPage: true })
  state.notice = null  // League reports a confirmed manual pick.
  await expect(alert).toHaveCount(0)
  state.notice = { id: 2, code: 'all_unavailable', role: 'MIDDLE', champion_id: null }
  await expect(alert).toContainText('Orta koridor için uygun şampiyon kalmadı')
  await alert.getByRole('button', { name: 'Otomasyonu durdur', exact: true }).click()
  await expect(alert).toHaveCount(0)
  expect(state.stops).toBe(1)
  expect(state.writes).toBe(0)
  expect(state.starts).toBe(0)
  expect(errors).toEqual([])
})

test('Mid and ADC preparation can start and autofill Jungle hands control to the user', async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(window, 'AudioContext', { value: undefined, configurable: true }) })
  const config = { ...structuredClone(settings), primary_role_name: 'Mid', secondary_role_name: 'ADC',
    role_champions_ui: { MIDDLE: [103], BOTTOM: [22] }, role_bans_ui: { MIDDLE: 84, BOTTOM: 84 } }
  let running = false
  let starts = 0
  let notice: SelectionNotice | null = null
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/settings') return route.fulfill({ json: config, headers: { ETag: '"1"' } })
    if (path === '/api/champion-catalog') return route.fulfill({ json: catalog })
    if (path === '/api/session') return route.fulfill({ json: { token: 'development-session-token-12345' } })
    if (path === '/api/health') return route.fulfill({ json: { ...health, running, selection: notice } })
    if (path.endsWith('/portrait')) return route.fulfill({ status: 404, body: '' })
    if (path === '/api/start_automation') {
      starts++
      const payload = route.request().postDataJSON()
      expect(payload.role_champions).toEqual({ MIDDLE: [103], BOTTOM: [22] })
      expect(payload.primary_role).toBe('MIDDLE')
      expect(payload.secondary_role).toBe('BOTTOM')
      running = true
      notice = { id: 1, code: 'no_preference', role: 'JUNGLE', champion_id: null }
      return route.fulfill({ json: { status: 'started', config: payload } })
    }
    throw new Error(`Unexpected request: ${path}`)
  })
  await page.goto('/')
  await expect(page.getByText('Autofill hazırlığı eksik:', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Otomasyonu başlat', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Otomasyonu başlat', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Manuel seçim bildirimi' })).toContainText('Orman için şampiyon tercihi yok')
  expect(starts).toBe(1)
  notice = null
  await expect(page.getByRole('region', { name: 'Manuel seçim bildirimi' })).toHaveCount(0)
})
