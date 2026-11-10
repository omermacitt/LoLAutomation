import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { catalog, health, settings } from '../src/test/fixtures'
import { catalogSchema, healthSchema, settingsSchema } from '../src/api/contracts'
import type { AutomationConfig, ChampionCatalog, Settings } from '../src/api/contracts'
import { roles } from '../src/features/champions/selection'

const apiPattern = /\/api\/(health|settings|champion-catalog|session|start_automation|stop_automation|automation\/config|champions\/[1-9]\d*\/portrait)$/
const portraitPng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1cAAAAASUVORK5CYII=', 'base64')

async function mockBackend(page: Page, complete = false, roster: ChampionCatalog = catalog) {
  const initial = structuredClone(settings)
  initial.custom_runes = { '266': { '1': { name: 'Keep my rune', selectedPerkIds: [1, 2] } } }
  initial.custom_skins = { TOP: { '266': 266001 } }
  if (complete) for (const role of roles) {
    initial.role_champions_ui[role.key] = [266, 86, 122]
    initial.role_bans_ui[role.key] = 84
  }
  const state = { saved: initial, version: 1, failSave: false, running: false, saves: 0,
    starts: [] as AutomationConfig[], updates: [] as AutomationConfig[], stops: 0, order: [] as string[] }
  await page.route(apiPattern, async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const method = request.method()
    if (path.endsWith('/portrait')) return route.fulfill({ contentType: 'image/png', body: portraitPng })
    if (path === '/api/session') return route.fulfill({ json: { token: 'development-session-token-12345' } })
    if (path === '/api/health') return route.fulfill({ json: { ...health, running: state.running } })
    if (path === '/api/champion-catalog') return route.fulfill({ json: roster })
    if (path === '/api/settings') {
      if (method === 'PUT') {
        state.saves++
        if (request.headers()['if-match'] !== `"${state.version}"`) return route.fulfill({ status: 412, json: {} })
        if (state.failSave) return route.fulfill({ status: 500, json: {} })
        state.saved = request.postDataJSON() as Settings
        state.version++
        state.order.push('save')
      }
      return route.fulfill({ json: state.saved, headers: { ETag: `"${state.version}"` } })
    }
    if (path === '/api/start_automation') {
      const config = request.postDataJSON() as AutomationConfig
      state.starts.push(config)
      state.running = true
      state.order.push('start')
      return route.fulfill({ json: { status: 'started', config } })
    }
    if (path === '/api/automation/config') {
      if (!state.running) return route.fulfill({ status: 409, json: {} })
      const config = request.postDataJSON() as AutomationConfig
      state.updates.push(config)
      return route.fulfill({ json: { status: 'updated', config } })
    }
    state.stops++
    state.running = false
    return route.fulfill({ json: { status: 'stopped' } })
  })
  return state
}

test('saves picks, bans and spells; restores them after reload and fits the viewport', async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const backend = await mockBackend(page)
  await page.goto('/')
  await expect(page.getByRole('button', { name: '1. tercih: Aatrox', exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Akali seç', exact: true })).toBeDisabled()
  await expect(page.getByText('Ayarlar güncel', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Hesaplar', exact: true })).toHaveCount(0)
  await expect(page.locator('input[type="password"]')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('champion-workspace.png'), fullPage: true })
  await page.getByRole('textbox', { name: 'Şampiyon ara' }).fill('Ahri')
  await page.getByRole('button', { name: 'Ahri seç', exact: true }).click()
  await page.getByRole('combobox', { name: 'Birinci büyü', exact: true }).selectOption('4')
  await page.getByRole('combobox', { name: 'İkinci büyü', exact: true }).selectOption('14')
  await expect.poll(() => backend.saved.custom_summoner_spells.TOP?.['103']?.spell2Id).toBe(14)
  expect(backend.saved.role_champions_ui.TOP[0]).toBe(103)
  expect(backend.saved.custom_runes['266']).toBeDefined()
  expect(backend.saved.custom_skins.TOP).toEqual({ '266': 266001 })
  await expect(page.getByText('Ayarlar güncel', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: '1. tercih: Ahri', exact: true })).toBeEnabled()
  await expect(page.getByRole('combobox', { name: 'Birinci büyü', exact: true })).toHaveValue('4')
  await page.getByRole('button', { name: /^Orta koridor/ }).click()
  await page.getByRole('button', { name: /^Üst koridor/ }).click()
  await page.getByRole('button', { name: '1. tercihi aşağı taşı', exact: true }).click()
  await expect.poll(() => backend.saved.role_champions_ui.TOP[1]).toBe(103)
  await expect(page.getByRole('combobox', { name: 'Birinci büyü', exact: true })).toHaveValue('4')
  await page.getByRole('button', { name: '2. tercihi yukarı taşı', exact: true }).click()
  await expect.poll(() => backend.saved.role_champions_ui.TOP[0]).toBe(103)
  await page.getByRole('button', { name: 'Yasaklama: Akali', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Akali yasakla', exact: true })).toBeEnabled()
  await page.getByRole('textbox', { name: 'Şampiyon ara' }).fill('Ahri')
  await page.getByRole('button', { name: 'Ahri yasakla', exact: true }).click()
  await expect.poll(() => backend.saved.role_bans_ui.TOP).toBe(103)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
  expect(backend.starts).toHaveLength(0)
})

test('save failure retains selections and blocks controlled exit until retry succeeds', async ({ page }) => {
  const backend = await mockBackend(page)
  backend.failSave = true
  await page.goto('/')
  await page.getByRole('button', { name: 'Ahri seç', exact: true }).click()
  await expect(page.getByText('Ayarlar kaydedilemedi', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Kaydet ve oturumu bitir' }).click()
  await expect(page.getByRole('button', { name: 'Kaydet ve oturumu bitir' })).toBeEnabled()
  expect(backend.stops).toBe(0)
  await expect(page.getByRole('button', { name: '1. tercih: Ahri', exact: true })).toBeVisible()
  await expect(page.getByText('Ayarlar kaydedildi ve otomasyon durduruldu.', { exact: false })).toHaveCount(0)
  backend.failSave = false
  await page.getByRole('button', { name: 'Kaydı tekrar dene' }).click()
  await expect(page.getByText('Ayarlar güncel', { exact: true })).toBeVisible()
  expect(backend.saved.role_champions_ui.TOP[0]).toBe(103)
  await page.getByRole('button', { name: 'Kaydet ve oturumu bitir' }).click()
  await expect(page.getByText('Ayarlar kaydedildi ve otomasyon durduruldu.', { exact: false })).toBeVisible()
  expect(backend.stops).toBe(1)
})

test('flushes before Start, live updates through update-only endpoint and does not restart after Stop', async ({ page }) => {
  const backend = await mockBackend(page, true)
  await page.goto('/')
  await page.getByRole('combobox', { name: 'Oyun modu', exact: true }).selectOption('Ranked Flex')
  await page.getByRole('button', { name: 'Otomasyonu başlat', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Çalışıyor', exact: true })).toBeVisible()
  expect(backend.order.slice(0, 2)).toEqual(['save', 'start'])
  expect(backend.starts[0].queue_id).toBe(440)
  expect(backend.starts[0].custom_runes['266']).toBeDefined()
  await page.getByRole('button', { name: 'Ahri seç', exact: true }).click()
  await expect.poll(() => backend.updates.length).toBe(1)
  expect(backend.updates[0].role_champions.TOP[0]).toBe(103)
  await page.getByRole('button', { name: 'Durdur', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Otomasyonu başlat', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Aatrox seç', exact: true }).click()
  await expect.poll(() => backend.saved.role_champions_ui.TOP[0]).toBe(266)
  expect(backend.starts).toHaveLength(1)
  expect(backend.updates).toHaveLength(1)
  expect(backend.running).toBe(false)
})

test('conflicting window changes do not overwrite local or remote settings', async ({ page }) => {
  const backend = await mockBackend(page)
  await page.goto('/')
  await expect(page.getByText('Ayarlar güncel', { exact: true })).toBeVisible()
  backend.saved = { ...structuredClone(backend.saved), role_champions_ui: { TOP: [86, 266, 122] } }
  backend.version++
  await page.getByRole('button', { name: 'Ahri seç', exact: true }).click()
  const reload = page.getByRole('button', { name: 'Yerel değişiklikleri bırak ve yeniden yükle' })
  await expect(reload).toBeVisible()
  expect(backend.saved.role_champions_ui.TOP[0]).toBe(86)
  await expect(page.getByRole('button', { name: '1. tercih: Ahri', exact: true })).toBeVisible()
  await reload.click()
  await expect(page.getByRole('button', { name: '1. tercih: Garen', exact: true })).toBeVisible()
  await expect(page.getByText('Ayarlar güncel', { exact: true })).toBeVisible()
})

test('disconnected catalog and failed settings keep selections and Start disabled', async ({ page }, testInfo) => {
  await page.route(apiPattern, (route) => route.fulfill({ status: 503, json: {} }))
  await page.goto('/')
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByText('Servis çevrimdışı', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Tekrar dene', exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: '1. tercih: Şampiyon seç', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Otomasyonu başlat', exact: true })).toBeDisabled()
  await page.screenshot({ path: testInfo.outputPath('offline-workspace.png'), fullPage: true })
})

test('failed settings alone never saves catalog defaults', async ({ page }) => {
  const writes: string[] = []
  await page.route(apiPattern, async (route) => {
    const request = route.request()
    if (request.method() !== 'GET') writes.push(request.method())
    const path = new URL(request.url()).pathname
    await route.fulfill(path.endsWith('/settings') ? { status: 500, json: {} } : { json: path.endsWith('/health') ? health : catalog })
  })
  await page.goto('/')
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Ahri seç', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Şimdi kaydet', exact: true })).toBeDisabled()
  expect(writes).toEqual([])
})

test('one champion per role is enforced while other roles and bans stay independent', async ({ page }) => {
  const backend = await mockBackend(page)
  await page.goto('/')
  const aatrox = page.getByRole('button', { name: 'Aatrox seç', exact: true })
  await expect(aatrox).toBeEnabled()
  await page.getByRole('button', { name: '2. tercih: Garen', exact: true }).click()
  await expect(aatrox).toBeDisabled()
  await expect(aatrox).toHaveAttribute('title', '1. tercihte zaten seçili')
  const ahri = page.getByRole('button', { name: 'Ahri seç', exact: true })
  await expect(ahri).toBeEnabled()
  await ahri.click()
  await expect.poll(() => backend.saved.role_champions_ui.TOP).toEqual([266, 103, 122])
  await page.getByRole('button', { name: '3. tercih: Darius', exact: true }).click()
  await expect(ahri).toBeDisabled()
  await page.getByRole('button', { name: /^Orta koridor/ }).click()
  await expect(aatrox).toBeEnabled()
  await aatrox.click()
  await expect.poll(() => backend.saved.role_champions_ui.MIDDLE).toEqual([103, null, 266])
  await page.getByRole('button', { name: /^Üst koridor/ }).click()
  await expect(aatrox).toBeDisabled()
  await page.getByRole('button', { name: '1. tercih: Aatrox', exact: true }).click()
  await expect(aatrox).toBeEnabled()
  await page.getByRole('button', { name: 'Etkin seçimi temizle', exact: true }).click()
  await page.getByRole('button', { name: '3. tercih: Darius', exact: true }).click()
  await expect(aatrox).toBeEnabled()
  await aatrox.click()
  await expect.poll(() => backend.saved.role_champions_ui.TOP).toEqual([null, 103, 266])
  await page.getByRole('button', { name: 'Yasaklama: Akali', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Aatrox yasakla', exact: true })).toBeEnabled()
})

test('proxy rejects untrusted writes, origins and unrelated endpoints', async ({ request }) => {
  expect((await request.put('/api/settings', { data: {} })).status()).toBe(403)
  expect((await request.post('/api/stop_automation')).status()).toBe(403)
  expect((await request.get('/api/session', { headers: { Origin: 'https://untrusted.example' } })).status()).toBe(403)
  expect((await request.get('/api/internal-settings')).status()).toBe(404)
  const { token } = await (await request.get('/api/session')).json()
  const headers = { 'X-RunePilot-Session': token }
  expect((await request.get('/api/accounts', { headers })).status()).toBe(404)
  expect((await request.post('/api/accounts', { headers, data: {} })).status()).toBe(404)
  expect((await request.put('/api/accounts/synthetic', { headers, data: {} })).status()).toBe(404)
  expect((await request.delete('/api/accounts/synthetic', { headers })).status()).toBe(404)
  expect((await request.post('/api/accounts/synthetic/login', { headers, data: {} })).status()).toBe(404)
  expect((await request.get('/api/login-jobs/active', { headers })).status()).toBe(404)
  expect((await request.get('/api/login-jobs/11111111-1111-4111-8111-111111111111', { headers })).status()).toBe(404)
  expect((await request.post('/api/league/launch', { headers, data: {} })).status()).toBe(404)
  expect((await request.delete('/api/settings')).status()).toBe(405)
  expect((await request.post('/api/champions/266/portrait')).status()).toBe(405)
  expect((await request.get('/api/champions/0/portrait')).status()).toBe(404)
})

test('renders three full rows per page, including after resize and paging', async ({ page }, testInfo) => {
  const large = { all_champions: [...catalog.all_champions, ...Array.from({ length: 100 }, (_, index) => ({ id: 10000 + index, name: `Test champion ${index}` }))], pickable_champions: catalog.pickable_champions }
  await mockBackend(page, false, large)
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Aatrox seç', exact: true })).toBeEnabled()
  const checkRows = async () => {
    await expect.poll(() => page.locator('.champion-grid').evaluate((grid) => {
      const columns = getComputedStyle(grid).gridTemplateColumns.split(' ').length
      const cards = [...grid.querySelectorAll('.champion-card')]
      const rows = new Map<number, number>()
      for (const card of cards) {
        const y = Math.round(card.getBoundingClientRect().top)
        rows.set(y, (rows.get(y) ?? 0) + 1)
      }
      return cards.length === columns * 3 && rows.size === 3 && [...rows.values()].every((count) => count === columns)
    })).toBe(true)
  }
  await checkRows()
  await page.getByRole('button', { name: 'Sonraki sayfa', exact: true }).click()
  await checkRows()
  if (testInfo.project.name === 'desktop') {
    await page.setViewportSize({ width: 1920, height: 1080 })
    await checkRows()
    await expect(page.locator('.champion-grid > .champion-card')).toHaveCount(33)
    await page.setViewportSize({ width: 1024, height: 768 })
    await checkRows()
  }
  await page.getByRole('textbox', { name: 'Şampiyon ara' }).fill('Ahri')
  await expect(page.locator('.champion-grid > .champion-card')).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Sonraki sayfa', exact: true })).toBeDisabled()
})

test('portraits load and failed images retry without changing selections', async ({ page }) => {
  const backend = await mockBackend(page)
  let broken = true
  await page.route(/\/api\/champions\/266\/portrait$/, (route) => broken
    ? route.fulfill({ status: 404, json: {}, headers: { 'Cache-Control': 'no-store' } })
    : route.fulfill({ contentType: 'image/png', body: portraitPng }))
  await page.goto('/')
  const aatrox = page.getByRole('button', { name: 'Aatrox seç', exact: true })
  await expect(aatrox).toBeEnabled()
  await expect(aatrox.locator('img')).toHaveCount(0)
  await expect(aatrox.locator('.champion-art__initials')).toHaveText('AA')
  const ahri = page.getByRole('button', { name: 'Ahri seç', exact: true })
  await expect(ahri.locator('.champion-art--loaded')).toHaveCount(1)
  broken = false
  await page.getByRole('button', { name: 'Listeyi yenile', exact: true }).click()
  await expect(aatrox.locator('.champion-art--loaded')).toHaveCount(1)
  expect(await aatrox.locator('img').evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true)
  expect(backend.saves).toBe(0)
})

test('live backend reads and concurrency header work without mutating the real profile', async ({ page, request }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'One live integration check is enough.')
  const response = await request.get('/api/health')
  test.skip(!response.ok(), 'Start python main.py to include the live check.')
  healthSchema.parse(await response.json())
  const config = await request.get('/api/settings')
  expect(config.ok()).toBe(true)
  expect(config.headers()['etag']).toMatch(/^"[a-f0-9]{64}"$/)
  settingsSchema.parse(await config.json())
  const champions = await request.get('/api/champion-catalog')
  expect([200, 503]).toContain(champions.status())
  if (champions.ok()) catalogSchema.parse(await champions.json())
  await page.goto('/')
  await expect(page.getByText('Servis bağlı', { exact: true })).toBeVisible()
  await expect(page.getByText('Ayarlar güncel', { exact: true })).toBeVisible()
  if (champions.ok()) {
    const firstId = (await champions.json()).all_champions[0].id
    const portrait = await request.get(`/api/champions/${firstId}/portrait`)
    expect(portrait.status()).toBe(200)
    expect(portrait.headers()['content-type']).toBe('image/png')
    expect((await portrait.body()).subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
    await expect.poll(() => page.locator('.champion-grid').evaluate((grid) => {
      const images = [...grid.querySelectorAll<HTMLImageElement>('img')]
      return images.length === grid.querySelectorAll('.champion-card').length
        && images.every((image) => image.complete && image.naturalWidth > 0)
    }), { timeout: 15_000 }).toBe(true)
  }
  await page.screenshot({ path: testInfo.outputPath('live-workspace.png'), fullPage: true })
})
