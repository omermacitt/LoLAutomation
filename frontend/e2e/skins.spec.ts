import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import type { AutomationConfig, Settings } from '../src/api/contracts'
import { catalog, deferred, health, settings } from '../src/test/fixtures'
import { runePage } from '../src/test/runeFixtures'

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1cAAAAASUVORK5CYII=', 'base64')
const options = (id: number) => ({ champion_id: id, skins: [
  { id: id * 1000, name: `Default ${id}` },
  ...(id === 266 ? [{ id: 266001, name: 'Justicar Aatrox' }, { id: 266002, name: 'Mecha Aatrox' }]
    : id === 103 ? [{ id: 103001, name: 'Dynasty Ahri' }] : []),
] })

async function mockGallery(page: Page, running = false) {
  const initial = structuredClone(settings)
  initial.custom_skins = { TOP: { '266': 266001, '103': 103001 }, MIDDLE: { '266': 266002 } }
  initial.custom_runes = { '266': { '1': runePage } }
  initial.rune_selection = { '266': 1 }
  const state = { saved: initial, version: 1, writes: 0, starts: 0, failSave: false, failSkins: false, failArtwork: false,
    updates: [] as AutomationConfig[], held: undefined as ReturnType<typeof deferred<void>> | undefined, heldRequests: 0 }
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path.endsWith('/portrait') || path.endsWith('/artwork')) {
      if (state.failArtwork && path.endsWith('/artwork')) return route.fulfill({ status: 404, body: '' })
      return route.fulfill({ contentType: 'image/png', body: png })
    }
    if (path === '/api/health') return route.fulfill({ json: { ...health, running } })
    if (path === '/api/champion-catalog') return route.fulfill({ json: catalog })
    if (path === '/api/session') return route.fulfill({ json: { token: 'development-session-token-12345' } })
    if (path.endsWith('/skins')) {
      const id = Number(path.split('/')[3])
      if (id === 266 && state.held) { const pending = state.held; state.heldRequests++; await pending.promise }
      return route.fulfill({ status: state.failSkins ? 503 : 200, json: options(id) })
    }
    if (path === '/api/settings') {
      if (request.method() === 'PUT') {
        state.writes++
        if (request.headers()['if-match'] !== `"${state.version}"`) return route.fulfill({ status: 412, json: {} })
        if (state.failSave) return route.fulfill({ status: 500, json: {} })
        state.saved = request.postDataJSON() as Settings
        state.version++
      }
      return route.fulfill({ json: state.saved, headers: { ETag: `"${state.version}"` } })
    }
    if (path === '/api/automation/config') {
      const config = request.postDataJSON() as AutomationConfig
      state.updates.push(config)
      return route.fulfill({ json: { status: 'updated', config } })
    }
    if (path === '/api/start_automation') { state.starts++; throw new Error('Gallery must never start automation') }
    throw new Error(`Unexpected API call: ${request.method()} ${path}`)
  })
  await page.goto('/')
  await expect(page.getByRole('button', { name: '1. tercih: Aatrox', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Kostümler', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Justicar Aatrox kostümünü seç', exact: true })).toBeEnabled()
  return state
}

test('owned gallery saves by role and champion, restores selections, and updates only a running engine', async ({ page }, info) => {
  const state = await mockGallery(page, true)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await expect(page.getByRole('button', { name: 'Justicar Aatrox kostümünü seç', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.skin-card')).toHaveCount(3)
  await page.getByRole('button', { name: 'Mecha Aatrox kostümünü seç', exact: true }).click()
  await expect.poll(() => (state.saved.custom_skins.TOP as Record<string, number>)['266']).toBe(266002)
  await expect.poll(() => state.updates.length).toBe(1)
  expect((state.updates[0].custom_skins.TOP as Record<string, number>)['266']).toBe(266002)
  expect(state.starts).toBe(0)
  await page.getByRole('combobox', { name: 'Kostüm rolü' }).selectOption('MIDDLE')
  await expect(page.getByRole('button', { name: 'Mecha Aatrox kostümünü seç', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Varsayılana dön', exact: true }).click()
  await expect.poll(() => (state.saved.custom_skins.MIDDLE as Record<string, number> | undefined)?.['266']).toBeUndefined()
  expect((state.saved.custom_skins.TOP as Record<string, number>)['266']).toBe(266002)
  expect((state.saved.custom_skins.TOP as Record<string, number>)['103']).toBe(103001)
  expect(state.saved.custom_runes['266']).toEqual({ '1': runePage })
  expect(state.saved.rune_selection['266']).toBe(1)
  expect(state.saved.role_champions_ui).toEqual(settings.role_champions_ui)
  await page.getByRole('combobox', { name: 'Kostüm rolü' }).selectOption('TOP')
  await page.getByRole('textbox', { name: 'Kostüm ara' }).fill('Mecha')
  await expect(page.locator('.skin-card')).toHaveCount(1)
  await page.getByRole('button', { name: 'Kostüm aramasını temizle' }).click()
  await page.screenshot({ path: info.outputPath('skin-gallery.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.reload()
  await page.getByRole('button', { name: 'Kostümler', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Mecha Aatrox kostümünü seç', exact: true })).toHaveAttribute('aria-pressed', 'true')
  expect(errors).toEqual([])
})

test('image failures preserve selectable cards and saved unavailable skins are never reset automatically', async ({ page }) => {
  const state = await mockGallery(page)
  state.saved.custom_skins.TOP = { '266': 266999, '103': 103001 }
  state.failArtwork = true
  await page.reload()
  await page.getByRole('button', { name: 'Kostümler', exact: true }).click()
  await expect(page.getByText('Kayıtlı kostüm bu listede bulunmuyor', { exact: false })).toBeVisible()
  await page.locator('.skin-card').first().scrollIntoViewIfNeeded()
  await expect(page.getByText('Görsel yüklenemedi', { exact: true }).first()).toBeVisible()
  expect(state.writes).toBe(0)
  expect((state.saved.custom_skins.TOP as Record<string, number>)['266']).toBe(266999)
  await page.getByRole('button', { name: 'Justicar Aatrox kostümünü seç', exact: true }).click()
  await expect.poll(() => (state.saved.custom_skins.TOP as Record<string, number>)['266']).toBe(266001)
  state.failArtwork = false
  await page.getByRole('button', { name: 'Kostümleri yenile', exact: true }).click()
  await expect(page.locator('.skin-hero .skin-artwork > img')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Justicar Aatrox kostümünü seç', exact: true })).toHaveAttribute('aria-pressed', 'true')
})

test('late champion responses, loading errors and an empty collection do not overwrite another champion', async ({ page }) => {
  const state = await mockGallery(page)
  state.held = deferred<void>()
  await page.getByRole('button', { name: 'Kostümleri yenile', exact: true }).click()
  await expect.poll(() => state.heldRequests).toBe(1)
  await page.getByRole('combobox', { name: 'Kostüm şampiyonu' }).selectOption('103')
  await expect(page.getByRole('button', { name: 'Dynasty Ahri kostümünü seç', exact: true })).toBeEnabled()
  state.held.resolve()
  state.held = undefined
  await page.getByRole('button', { name: 'Dynasty Ahri kostümünü seç', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Ahri kostümleri 2', exact: true })).toBeVisible()
  state.failSkins = true
  await page.getByRole('button', { name: 'Kostümleri yenile', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Kostümleri tekrar yükle', exact: true })).toBeVisible()
  expect(state.writes).toBe(0)
  state.failSkins = false
  await page.getByRole('button', { name: 'Kostümleri tekrar yükle', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Dynasty Ahri kostümünü seç', exact: true })).toBeEnabled()
  await page.getByRole('combobox', { name: 'Kostüm şampiyonu' }).selectOption('1')
  await expect(page.locator('.skin-card')).toHaveCount(1)
  await expect(page.getByText('Bu şampiyon için sahip olduğun ek bir kostüm görünmüyor.', { exact: false })).toBeVisible()
  expect(state.writes).toBe(0)
})

test('failed autosave retains the newest skin until retry succeeds', async ({ page }) => {
  const state = await mockGallery(page)
  state.failSave = true
  await page.getByRole('button', { name: 'Mecha Aatrox kostümünü seç', exact: true }).click()
  await expect(page.getByText('Ayarlar kaydedilemedi', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Mecha Aatrox kostümünü seç', exact: true })).toHaveAttribute('aria-pressed', 'true')
  expect((state.saved.custom_skins.TOP as Record<string, number>)['266']).toBe(266001)
  state.failSave = false
  await page.getByRole('button', { name: 'Kaydı tekrar dene', exact: true }).click()
  await expect(page.getByText('Ayarlar güncel', { exact: true })).toBeVisible()
  expect((state.saved.custom_skins.TOP as Record<string, number>)['266']).toBe(266002)
  expect(state.starts).toBe(0)
})

test('live League gallery and JPEG artwork render without changing the profile', async ({ page }, info) => {
  test.skip(process.env.RUNEPILOT_LIVE_READS !== '1', 'Opt in with RUNEPILOT_LIVE_READS=1 and a running League client.')
  test.skip(info.project.name !== 'desktop', 'One read-only live check is sufficient.')
  const before = await page.request.get('/api/settings')
  const body = await before.json()
  await page.goto('/')
  await page.getByRole('button', { name: 'Kostümler', exact: true }).click()
  await page.getByRole('combobox', { name: 'Kostüm şampiyonu' }).selectOption('17')
  await expect(page.getByRole('button', { name: 'Varsayılan Teemo kostümünü seç', exact: true })).toBeEnabled()
  const img = page.locator('.skin-hero .skin-artwork > img')
  await expect(img).toBeVisible()
  await expect.poll(() => img.evaluate((node: HTMLImageElement) => node.complete && node.naturalWidth > 0)).toBe(true)
  await page.screenshot({ path: info.outputPath('live-skin-gallery.png'), fullPage: true })
  const after = await page.request.get('/api/settings')
  expect(await after.json()).toEqual(body)
  expect(after.headers().etag).toBe(before.headers().etag)
})
