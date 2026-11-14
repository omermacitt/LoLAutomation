import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import type { AutomationConfig, Settings } from '../src/api/contracts'
import { catalog, deferred, health, settings } from '../src/test/fixtures'
import { runePage } from '../src/test/runeFixtures'

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1cAAAAASUVORK5CYII=', 'base64')
const chromaNames = ['Deniz Mavisi', 'Yakut', 'Zümrüt', 'Tanzanit', 'Test rengi 5', 'Test rengi 6']
const rengarChromas = chromaNames.map((name, index) => ({ id: 107004 + index,
  name: `Kelle Avcısı Rengar (${name})`, parent_skin_id: 107001,
}))
const options = (id: number) => ({ champion_id: id, skins: [
  { id: id * 1000, name: `Default ${id}` },
  ...(id === 266 ? [{ id: 266001, name: 'Justicar Aatrox' }, { id: 266002, name: 'Mecha Aatrox' }]
    : id === 103 ? [{ id: 103001, name: 'Dynasty Ahri' }]
      : id === 107 ? [{ id: 107001, name: 'Kelle Avcısı Rengar' }, ...rengarChromas] : []),
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
    if (path === '/api/champion-catalog') return route.fulfill({ json: { ...catalog,
      all_champions: [...catalog.all_champions, { id: 107, name: 'Rengar' }],
    } })
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
  await expect(skinCard(page, 'Justicar Aatrox')).toBeEnabled()
  return state
}

const skinCard = (page: Page, name: string) => page.getByRole('button', { name: `${name} ayrıntılarını aç`, exact: true })
async function chooseSkin(page: Page, name: string) {
  await skinCard(page, name).click()
  await page.getByRole('button', { name: /^(Bu kostümü kullan|Orijinal kostümü kullan)$/ }).click()
  await page.getByRole('button', { name: 'Kostüm listesine dön', exact: true }).click()
}

test('owned gallery saves by role and champion, restores selections, and updates only a running engine', async ({ page }, info) => {
  const state = await mockGallery(page, true)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await expect(skinCard(page, 'Justicar Aatrox')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.skin-card')).toHaveCount(3)
  await chooseSkin(page, 'Mecha Aatrox')
  await expect.poll(() => (state.saved.custom_skins.TOP as Record<string, number>)['266']).toBe(266002)
  await expect.poll(() => state.updates.length).toBe(1)
  expect((state.updates[0].custom_skins.TOP as Record<string, number>)['266']).toBe(266002)
  expect(state.starts).toBe(0)
  await page.getByRole('combobox', { name: 'Kostüm rolü' }).selectOption('MIDDLE')
  await expect(skinCard(page, 'Mecha Aatrox')).toHaveAttribute('aria-pressed', 'true')
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
  await expect(skinCard(page, 'Mecha Aatrox')).toHaveAttribute('aria-pressed', 'true')
  expect(errors).toEqual([])
})

test('Rengar colors stay inside costume details and restore the selected color by role', async ({ page }, info) => {
  const state = await mockGallery(page, true)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.getByRole('combobox', { name: 'Kostüm şampiyonu' }).selectOption('107')
  const parent = skinCard(page, 'Kelle Avcısı Rengar')
  await expect(page.locator('.skin-card')).toHaveCount(2)
  await expect(page.getByRole('button', { name: /renk paketini seç$/ })).toHaveCount(0)
  await parent.click()
  await expect(page.getByRole('heading', { name: 'Kelle Avcısı Rengar', exact: true, level: 2 })).toBeFocused()
  expect(state.writes).toBe(0)
  expect(state.updates).toHaveLength(0)
  await page.getByRole('button', { name: 'Kostüm listesine dön', exact: true }).click()
  await expect(parent).toBeFocused()
  expect(state.writes).toBe(0)
  await page.getByRole('textbox', { name: 'Kostüm ara' }).fill('Yakut')
  await expect(page.locator('.skin-card')).toHaveCount(1)
  await parent.click()
  await expect(page.locator('.chroma-card')).toHaveCount(6)
  for (const chroma of rengarChromas) {
    await expect(page.getByRole('button', { name: `${chroma.name} renk paketini seç`, exact: true })).toBeEnabled()
  }
  await expect(page.getByText(/^Skin 107/)).toHaveCount(0)
  const ruby = page.getByRole('button', { name: 'Kelle Avcısı Rengar (Yakut) renk paketini seç', exact: true })
  await ruby.click()
  await expect.poll(() => (state.saved.custom_skins.TOP as Record<string, number>)['107']).toBe(107005)
  await expect.poll(() => state.updates.length).toBe(1)
  expect((state.updates[0].custom_skins.TOP as Record<string, number>)['107']).toBe(107005)
  const image = page.locator('.skin-hero .skin-artwork > img')
  await expect(image).toHaveAttribute('src', '/api/champions/107/skins/107005/artwork')
  await expect(image).toHaveCSS('object-fit', 'contain')
  await page.getByRole('button', { name: 'Kostüm listesine dön', exact: true }).click()
  await expect(parent).toHaveAttribute('aria-pressed', 'true')
  await expect(parent).toContainText('Seçili: Kelle Avcısı Rengar (Yakut)')
  await expect(parent).toHaveAccessibleDescription('Seçili: Kelle Avcısı Rengar (Yakut)')
  await page.getByRole('combobox', { name: 'Kostüm rolü' }).selectOption('MIDDLE')
  await parent.click()
  await expect(ruby).toHaveAttribute('aria-pressed', 'false')
  await page.getByRole('button', { name: 'Kelle Avcısı Rengar (Deniz Mavisi) renk paketini seç', exact: true }).click()
  await expect.poll(() => (state.saved.custom_skins.MIDDLE as Record<string, number>)['107']).toBe(107004)
  expect((state.saved.custom_skins.TOP as Record<string, number>)['107']).toBe(107005)
  expect(state.saved.custom_runes).toEqual({ '266': { '1': runePage } })
  expect(state.starts).toBe(0)
  await page.reload()
  await page.getByRole('button', { name: 'Kostümler', exact: true }).click()
  await page.getByRole('combobox', { name: 'Kostüm şampiyonu' }).selectOption('107')
  await expect(page.locator('.skin-card')).toHaveCount(2)
  await expect(parent).toHaveAttribute('aria-pressed', 'true')
  await page.screenshot({ path: info.outputPath('rengar-grouped-gallery.png'), fullPage: true })
  await parent.click()
  await expect(ruby).toHaveAttribute('aria-pressed', 'true')
  // Full-page capture includes fixed elements at the current scroll offset.
  // Confirm the skip link is outside the live viewport, then capture from the top.
  expect(await page.locator('.skip-link').evaluate((node) => node.getBoundingClientRect().bottom)).toBeLessThanOrEqual(0)
  await page.evaluate(() => window.scrollTo(0, 0))
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0)
  await page.screenshot({ path: info.outputPath('rengar-skin-details.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Orijinal kostümü kullan', exact: true }).click()
  await expect.poll(() => (state.saved.custom_skins.TOP as Record<string, number>)['107']).toBe(107001)
  await expect(ruby).toHaveAttribute('aria-pressed', 'false')
  await page.getByRole('combobox', { name: 'Kostüm rolü' }).selectOption('MIDDLE')
  await expect(page.getByRole('region', { name: 'Kostüm ayrıntısı', exact: true })).toHaveCount(0)
  await parent.click()
  await expect(page.getByRole('button', { name: 'Kelle Avcısı Rengar (Deniz Mavisi) renk paketini seç', exact: true })).toHaveAttribute('aria-pressed', 'true')
  expect(errors).toEqual([])
})

test('browsing costumes without owned colors never changes settings and supports keyboard return', async ({ page }) => {
  const state = await mockGallery(page)
  const card = skinCard(page, 'Mecha Aatrox')
  await card.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'Mecha Aatrox', exact: true, level: 2 })).toBeFocused()
  await expect(page.getByText('Önizleme · seçim yapılmadı', { exact: true })).toBeVisible()
  await expect(page.getByText('Bu kostüm için sahip olduğun bir renk paketi bulunmuyor.', { exact: true })).toBeVisible()
  expect(state.writes).toBe(0)
  expect(state.starts).toBe(0)
  await page.getByRole('button', { name: 'Kostüm listesine dön', exact: true }).click()
  await expect(card).toBeFocused()
  expect((state.saved.custom_skins.TOP as Record<string, number>)['266']).toBe(266001)
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
  await chooseSkin(page, 'Justicar Aatrox')
  await expect.poll(() => (state.saved.custom_skins.TOP as Record<string, number>)['266']).toBe(266001)
  state.failArtwork = false
  await page.getByRole('button', { name: 'Kostümleri yenile', exact: true }).click()
  await expect(page.locator('.skin-hero .skin-artwork > img')).toBeVisible()
  await expect(skinCard(page, 'Justicar Aatrox')).toHaveAttribute('aria-pressed', 'true')
})

test('late champion responses, loading errors and an empty collection do not overwrite another champion', async ({ page }) => {
  const state = await mockGallery(page)
  state.held = deferred<void>()
  await page.getByRole('button', { name: 'Kostümleri yenile', exact: true }).click()
  await expect.poll(() => state.heldRequests).toBe(1)
  await page.getByRole('combobox', { name: 'Kostüm şampiyonu' }).selectOption('103')
  await expect(skinCard(page, 'Dynasty Ahri')).toBeEnabled()
  state.held.resolve()
  state.held = undefined
  await chooseSkin(page, 'Dynasty Ahri')
  await expect(page.getByRole('heading', { name: 'Ahri kostümleri 2', exact: true })).toBeVisible()
  state.failSkins = true
  await page.getByRole('button', { name: 'Kostümleri yenile', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Kostümleri tekrar yükle', exact: true })).toBeVisible()
  expect(state.writes).toBe(0)
  state.failSkins = false
  await page.getByRole('button', { name: 'Kostümleri tekrar yükle', exact: true }).click()
  await expect(skinCard(page, 'Dynasty Ahri')).toBeEnabled()
  await page.getByRole('combobox', { name: 'Kostüm şampiyonu' }).selectOption('1')
  await expect(page.locator('.skin-card')).toHaveCount(1)
  await expect(page.getByText('Bu şampiyon için sahip olduğun ek bir kostüm görünmüyor.', { exact: false })).toBeVisible()
  expect(state.writes).toBe(0)
})

test('failed autosave retains the newest skin until retry succeeds', async ({ page }) => {
  const state = await mockGallery(page)
  state.failSave = true
  await chooseSkin(page, 'Mecha Aatrox')
  await expect(page.getByText('Ayarlar kaydedilemedi', { exact: true })).toBeVisible()
  await expect(skinCard(page, 'Mecha Aatrox')).toHaveAttribute('aria-pressed', 'true')
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
  await expect(skinCard(page, 'Varsayılan Teemo')).toBeEnabled()
  const img = page.locator('.skin-hero .skin-artwork > img')
  await expect(img).toBeVisible()
  await expect.poll(() => img.evaluate((node: HTMLImageElement) => node.complete && node.naturalWidth > 0)).toBe(true)
  await page.screenshot({ path: info.outputPath('live-skin-gallery.png'), fullPage: true })
  const after = await page.request.get('/api/settings')
  expect(await after.json()).toEqual(body)
  expect(after.headers().etag).toBe(before.headers().etag)
})
