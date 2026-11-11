import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import type { RunePage, Settings } from '../src/api/contracts'
import { catalog, deferred, health, settings } from '../src/test/fixtures'
import { runeCatalog, runePage } from '../src/test/runeFixtures'

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1cAAAAASUVORK5CYII=', 'base64')
async function mockRunes(page: Page, editorCatalog = runeCatalog) {
  const initial = structuredClone(settings)
  initial.custom_runes = { '103': { '2': { ...runePage, name: 'Other champion' } } }
  initial.rune_selection = { '103': 2 }
  initial.custom_skins = { TOP: { '266': 266001 } }
  const state = { saved: initial, version: 1, writes: 0, validations: [] as RunePage[], failSave: false, failCatalog: false, failIcons: false,
    recommendation: 'valid' as 'valid' | 'missing' | 'outdated', stops: 0 }
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path.endsWith('/portrait') || path.includes('/runes/icons/')) return route.fulfill({ status: state.failIcons ? 404 : 200, contentType: 'image/png', body: png })
    if (path === '/api/health') return route.fulfill({ json: health })
    if (path === '/api/session') return route.fulfill({ json: { token: 'development-session-token-12345' } })
    if (path === '/api/champion-catalog') return route.fulfill({ json: catalog })
    if (path === '/api/runes/editor-catalog') return route.fulfill({ status: state.failCatalog ? 503 : 200, json: editorCatalog })
    if (path.endsWith('/runes/recommended')) {
      const id = Number(path.split('/')[3])
      return route.fulfill({ json: { champion_id: id, source: 'bundled', page: state.recommendation === 'valid' ? { ...runePage, name: 'Recommended' } : null,
        unavailableReason: state.recommendation === 'valid' ? null : state.recommendation } })
    }
    if (path === '/api/runes/validate') {
      state.validations.push(request.postDataJSON() as RunePage)
      return route.fulfill({ json: request.postDataJSON() })
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
    if (path === '/api/stop_automation') { state.stops++; return route.fulfill({ json: { status: 'stopped' } }) }
    throw new Error(`Unexpected API call: ${request.method()} ${path}`)
  })
  await page.goto('/')
  await expect(page.getByRole('button', { name: '1. tercih: Aatrox', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Rünler', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Rün Preset 1', exact: true })).toBeEnabled()
  return state
}

test('compact rune editor uses a 3 by 3 shard grid and keeps actions visible', async ({ page }, info) => {
  if (info.project.name !== 'mobile-width') await page.setViewportSize(info.project.name === 'compact' ? { width: 1024, height: 768 } : { width: 1440, height: 900 })
  const fullCatalog = structuredClone(runeCatalog)
  for (const id of [8200, 8300, 8400]) fullCatalog.styles.push({ ...structuredClone(runeCatalog.styles[0]), id, name: `Style ${id}` })
  await mockRunes(page, fullCatalog)
  await page.getByRole('button', { name: 'Rün Preset 1', exact: true }).click()
  const shards = page.getByRole('region', { name: 'Nitelik parçaları', exact: true })
  const rows = shards.getByRole('group')
  await expect(rows).toHaveCount(3)
  for (let index = 0; index < 3; index++) await expect(rows.nth(index).getByRole('button')).toHaveCount(3)
  const geometry = await rows.evaluateAll((nodes) => nodes.map((row) => [...row.querySelectorAll('button')].map((button) => {
    const box = button.getBoundingClientRect(); return { x: box.x, y: box.y, width: box.width, height: box.height }
  })))
  for (let index = 0; index < 3; index++) {
    expect(new Set(geometry[index].map((box) => Math.round(box.y))).size).toBe(1)
    expect(geometry[index].map((box) => Math.round(box.x))).toEqual(geometry[0].map((box) => Math.round(box.x)))
    if (index > 0) expect(geometry[index][0].y).toBeGreaterThan(geometry[index - 1][0].y)
  }
  await expect(page.getByLabel('Rün özeti', { exact: true })).toHaveCount(0)
  await expect(page.locator('.rune-draft-note')).toHaveCount(0)
  await expect(page.getByText('Kaydedilmemiş rün düzenlemesi', { exact: true })).toHaveCount(0)
  if (info.project.name !== 'mobile-width') {
    await expect(page.getByRole('button', { name: 'Preseti kaydet', exact: true })).toBeInViewport({ ratio: 1 })
    await expect(page.getByRole('button', { name: 'Kaydet ve oturumu bitir', exact: true })).toBeInViewport({ ratio: 1 })
    expect(await page.evaluate(() => scrollY)).toBe(0)
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  const choice = page.getByRole('button', { name: 'Nitelik 2: Rune 5001', exact: true })
  await choice.focus()
  await page.keyboard.press('Enter')
  await expect(choice).toHaveAttribute('aria-pressed', 'true')
  await expect(choice.locator('.rune-choice__tooltip')).toBeVisible()
  await page.screenshot({ path: info.outputPath('compact-rune-editor.png'), fullPage: true })
})

test('read-only rune descriptions support keyboard access and drafts keep an accurate status', async ({ page }) => {
  const state = await mockRunes(page)
  const choice = page.getByRole('button', { name: 'Ana 1: Rune 8002', exact: true })
  await choice.focus()
  await page.keyboard.press('Tab')
  await page.keyboard.press('Shift+Tab')
  await expect(choice).toBeFocused()
  await expect(choice.locator('.rune-choice__tooltip')).toBeVisible()
  await page.keyboard.press('Enter')
  await expect(choice).toHaveAttribute('aria-pressed', 'false')
  expect(state.writes).toBe(0)
  await page.getByRole('button', { name: 'Rün Preset 1', exact: true }).click()
  await page.getByRole('textbox', { name: 'Rün preset adı' }).fill('Local draft')
  await expect(page.getByText('Kaydedilmemiş rün düzenlemesi', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Şampiyonlar', exact: true }).click()
  await expect(page.getByText('Rün düzenleniyor', { exact: true })).toBeVisible()
  await expect(page.getByText('Ayarlar güncel', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Kaydet ve oturumu bitir' }).click()
  expect(state.stops).toBe(0)
  await expect(page.getByText('Kaydedilmemiş rün düzenlemeleri var.', { exact: false })).toBeVisible()
})

test('saving remains visible when a translator wraps the button label during the request', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const state = await mockRunes(page)
  const pending = deferred<void>()
  let validating = false
  await page.route('**/api/runes/validate', async (route) => {
    validating = true
    await pending.promise
    await route.fulfill({ json: route.request().postDataJSON() })
  })
  await page.getByRole('button', { name: 'Rün Preset 1', exact: true }).click()
  await page.getByRole('textbox', { name: 'Rün preset adı' }).fill('Translated save')
  const save = page.getByRole('button', { name: 'Preseti kaydet', exact: true })
  await save.click()
  await expect.poll(() => validating).toBe(true)
  await expect(save).toBeDisabled()
  const wrapped = await save.evaluate((button) => {
    const walker = document.createTreeWalker(button, NodeFilter.SHOW_TEXT)
    const labels: Node[] = []
    while (walker.nextNode()) {
      const node = walker.currentNode
      if (node.textContent?.trim() && node.parentElement?.namespaceURI === 'http://www.w3.org/1999/xhtml') labels.push(node)
    }
    for (const node of labels) {
      const translated = document.createElement('font')
      translated.textContent = node.textContent
      node.parentNode!.replaceChild(translated, node)
    }
    return labels.length
  })
  expect(wrapped).toBeGreaterThan(0)
  pending.resolve()
  await expect.poll(() => state.saved.rune_selection['266']).toBe(1)
  await expect(page.getByRole('region', { name: 'Rün çalışma alanı', exact: true })).toBeVisible()
  await expect(save).toBeEnabled()
  expect(errors).toEqual([])
})

test('saving live-shaped rune data keeps the editor mounted and reports no browser errors', async ({ page }) => {
  test.skip(process.env.RUNEPILOT_LIVE_READS !== '1', 'Opt in with RUNEPILOT_LIVE_READS=1 and a running League client.')
  test.skip(test.info().project.name !== 'desktop', 'One live-data reproduction is sufficient.')
  const settingsResponse = await page.request.get('/api/settings')
  let config = await settingsResponse.json() as Settings
  const liveCatalog = await (await page.request.get('/api/runes/editor-catalog')).json()
  const champions = await (await page.request.get('/api/champion-catalog')).json()
  let version = 1
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.stack ?? error.message))
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path === '/api/settings') {
      if (request.method() === 'PUT') { config = request.postDataJSON() as Settings; version++ }
      return route.fulfill({ json: config, headers: { ETag: `"${version}"` } })
    }
    if (path === '/api/health') return route.fulfill({ json: health })
    if (path === '/api/champion-catalog') return route.fulfill({ json: champions })
    if (path === '/api/runes/editor-catalog') return route.fulfill({ json: liveCatalog })
    if (path === '/api/session') return route.fulfill({ json: { token: 'development-session-token-12345' } })
    if (path === '/api/runes/validate') {
      const validated = await page.request.post('http://127.0.0.1:8000/runes/validate', { data: request.postDataJSON() })
      return route.fulfill({ response: validated })
    }
    if (request.method() !== 'GET') throw new Error(`Unexpected write: ${path}`)
    return route.continue()
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Rünler', exact: true }).click()
  await page.getByRole('combobox', { name: 'Rün şampiyonu' }).selectOption('106')
  for (const slot of [1, 2, 3]) {
    await page.getByRole('button', { name: `Rün Preset ${slot}`, exact: true }).click()
    await page.getByRole('textbox', { name: 'Rün preset adı' }).fill(`Save check ${slot}`)
    await page.getByRole('button', { name: 'Preseti kaydet', exact: true }).click()
    await expect(page.getByText('Ayarlar güncel', { exact: true })).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Rün preset adı' })).toHaveValue(`Save check ${slot}`)
  }
  expect(errors).toEqual([])
  await expect(page.getByRole('region', { name: 'Rün çalışma alanı', exact: true })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath('after-live-shaped-save.png'), fullPage: true })
})

test('edits all nine choices, preserves drafts across navigation, saves independent shared presets', async ({ page }, info) => {
  const state = await mockRunes(page)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.getByRole('button', { name: 'Rün Preset 1', exact: true }).click()
  await page.getByRole('textbox', { name: 'Rün preset adı' }).fill('Ranked')
  await page.getByRole('button', { name: 'Ana 1: Rune 8002', exact: true }).click()
  await page.getByRole('button', { name: 'İkincil 1: Rune 8112', exact: true }).click()
  await page.getByRole('button', { name: 'Nitelik 2: Rune 5001', exact: true }).click()
  await page.getByRole('button', { name: 'Kaydet ve oturumu bitir' }).click()
  expect(state.stops).toBe(0)
  await expect(page.getByText('Kaydedilmemiş rün düzenlemeleri var.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Rün Preset 2', exact: true }).click()
  await page.getByRole('textbox', { name: 'Rün preset adı' }).fill('Second')
  await page.getByRole('combobox', { name: 'Rün şampiyonu' }).selectOption('103')
  await expect(page.getByRole('textbox', { name: 'Rün preset adı' })).toHaveValue('Other champion')
  await page.getByRole('combobox', { name: 'Rün şampiyonu' }).selectOption('266')
  await page.getByRole('button', { name: 'Rün Preset 1', exact: true }).click()
  await page.getByRole('button', { name: 'Şampiyonlar', exact: true }).click()
  await page.getByRole('button', { name: 'Rünler', exact: true }).click()
  await page.getByRole('button', { name: 'Rün Preset 1', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Rün preset adı' })).toHaveValue('Ranked')
  await expect(page.getByRole('button', { name: 'Ana 1: Rune 8002', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.screenshot({ path: info.outputPath('rune-editor.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Preseti kaydet', exact: true }).click()
  await expect.poll(() => state.saved.rune_selection['266']).toBe(1)
  expect(state.validations.at(-1)?.selectedPerkIds).toEqual([8002, 8011, 8021, 8031, 8112, 8121, 5008, 5001, 5001])
  await page.getByRole('button', { name: 'Rün Preset 2', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Rün preset adı' })).toHaveValue('Second')
  await page.getByRole('button', { name: 'Preseti kaydet', exact: true }).click()
  await expect.poll(() => state.saved.rune_selection['266']).toBe(2)
  expect((state.saved.custom_runes['266'] as Record<string, RunePage>)['1'].name).toBe('Ranked')
  expect(state.saved.custom_runes['103']).toEqual({ '2': { ...runePage, name: 'Other champion' } })
  expect(state.saved.custom_skins).toEqual({ TOP: { '266': 266001 } })
  expect(state.saved.role_champions_ui).toEqual(settings.role_champions_ui)
  await page.getByRole('button', { name: 'Preseti sil', exact: true }).click()
  await expect.poll(() => state.saved.rune_selection['266']).toBeUndefined()
  expect((state.saved.custom_runes['266'] as Record<string, RunePage>)['2']).toBeUndefined()
  await page.reload()
  await page.getByRole('button', { name: 'Rünler', exact: true }).click()
  await page.getByRole('button', { name: 'Rün Preset 1', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Rün preset adı' })).toHaveValue('Ranked')
  expect(errors).toEqual([])
})

test('failed saves retain the local rune form and retry acknowledges the same draft', async ({ page }) => {
  const state = await mockRunes(page)
  state.failSave = true
  await page.getByRole('button', { name: 'Rün Preset 3', exact: true }).click()
  await page.getByRole('textbox', { name: 'Rün preset adı' }).fill('Retry me')
  await page.getByRole('button', { name: 'Preseti kaydet', exact: true }).click()
  await expect(page.getByText('Ayarlar kaydedilemedi', { exact: true })).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Rün preset adı' })).toHaveValue('Retry me')
  expect(state.saved.rune_selection['266']).toBeUndefined()
  state.failSave = false
  await page.getByRole('button', { name: 'Kaydı tekrar dene', exact: true }).click()
  await expect(page.getByText('Ayarlar güncel', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Düzenlemeyi geri al', exact: true })).toBeDisabled()
  expect(state.saved.rune_selection['266']).toBe(3)
})

test('recommendation is read only until copied, and icon failures do not reset choices', async ({ page }) => {
  const state = await mockRunes(page)
  await expect(page.getByRole('button', { name: 'Ana 1: Rune 8002', exact: true })).toBeDisabled()
  expect(state.writes).toBe(0)
  await page.getByRole('combobox', { name: 'Önerinin kopyalanacağı preset' }).selectOption('3')
  await page.getByRole('button', { name: 'Düzenlemek için kopyala', exact: true }).click()
  await page.getByRole('textbox', { name: 'Rün preset adı' }).fill('My copy')
  await page.getByRole('button', { name: 'Ana yol: Domination', exact: true }).click()
  await expect(page.getByRole('button', { name: 'İkincil yol: Precision', exact: true })).toHaveAttribute('aria-pressed', 'true')
  state.failIcons = true
  await page.getByRole('button', { name: 'Rünleri yenile', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Rün preset adı' })).toHaveValue('My copy')
  await expect(page.getByRole('button', { name: 'Ana yol: Domination', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Preseti kaydet', exact: true }).click()
  await expect.poll(() => state.saved.rune_selection['266']).toBe(3)
  await page.getByRole('button', { name: 'Önerilen rünler', exact: true }).click()
  await page.getByRole('button', { name: 'Önerileni kullan', exact: true }).click()
  await expect.poll(() => state.saved.rune_selection['266']).toBeUndefined()
  expect((state.saved.custom_runes['266'] as Record<string, RunePage>)['3'].primaryStyleId).toBe(8100)
})

test('discard after a failed save removes the pending preset without undoing other settings', async ({ page }) => {
  const state = await mockRunes(page)
  state.failSave = true
  await page.getByRole('button', { name: 'Rün Preset 1', exact: true }).click()
  await page.getByRole('textbox', { name: 'Rün preset adı' }).fill('Discard me')
  await page.getByRole('button', { name: 'Preseti kaydet', exact: true }).click()
  await expect(page.getByText('Ayarlar kaydedilemedi', { exact: true })).toBeVisible()
  state.failSave = false
  await page.getByRole('button', { name: 'Düzenlemeyi geri al', exact: true }).click()
  await expect(page.getByText('Ayarlar güncel', { exact: true })).toBeVisible()
  expect(state.saved.custom_runes['266']).toBeUndefined()
  expect(state.saved.rune_selection['266']).toBeUndefined()
  expect(state.saved.custom_runes['103']).toEqual({ '2': { ...runePage, name: 'Other champion' } })
  expect(state.saved.custom_skins).toEqual({ TOP: { '266': 266001 } })
  await page.getByRole('button', { name: 'Kaydet ve oturumu bitir' }).click()
  await expect.poll(() => state.stops).toBe(1)
  expect(state.saved.custom_runes['266']).toBeUndefined()
})

test('catalog errors and outdated recommendations never save defaults', async ({ page }) => {
  const state = await mockRunes(page)
  state.failCatalog = true
  state.recommendation = 'outdated'
  await page.getByRole('button', { name: 'Rünleri yenile', exact: true }).click()
  await expect(page.getByText('League istemcisine ulaşılamadı.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Rün Preset 1', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Preseti kaydet', exact: true })).toBeDisabled()
  expect(state.writes).toBe(0)
  state.failCatalog = false
  await page.getByRole('button', { name: 'Rünleri yenile', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Preseti kaydet', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Önerilen rünler', exact: true }).click()
  await expect(page.getByText('Bu öneri güncel katalogla uyuşmuyor', { exact: true })).toBeVisible()
  expect(state.writes).toBe(0)
})

test('an unreadable legacy preset is preserved until explicitly replaced', async ({ page }) => {
  const state = await mockRunes(page)
  state.saved.custom_runes['266'] = { '1': { name: 'Legacy', selectedPerkIds: [1, 2] } }
  state.saved.rune_selection['266'] = 1
  await page.reload()
  await page.getByRole('button', { name: 'Rünler', exact: true }).click()
  await expect(page.getByText('Kayıtlı preset bu biçimde okunamıyor', { exact: true })).toBeVisible()
  expect(state.writes).toBe(0)
  await page.getByRole('button', { name: 'Yeni sayfa hazırla', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Rün preset adı' })).toHaveValue('Custom Aatrox')
  await expect(page.getByRole('button', { name: 'Düzenlemeyi geri al', exact: true })).toBeEnabled()
  expect(state.writes).toBe(0)
  await page.getByRole('button', { name: 'Preseti kaydet', exact: true }).click()
  await expect(page.getByText('Ayarlar güncel', { exact: true })).toBeVisible()
  expect((state.saved.custom_runes['266'] as Record<string, RunePage>)['1'].selectedPerkIds).toHaveLength(9)
})

test('live rune metadata and artwork render without changing the profile', async ({ page }, info) => {
  test.skip(process.env.RUNEPILOT_LIVE_READS !== '1', 'Opt in with RUNEPILOT_LIVE_READS=1 and a running League client.')
  test.skip(info.project.name !== 'desktop', 'One read-only live check is sufficient.')
  const before = await page.request.get('/api/settings')
  const beforeBody = await before.json()
  await page.goto('/')
  await page.getByRole('button', { name: 'Rünler', exact: true }).click()
  await page.getByRole('button', { name: 'Rün Preset 1', exact: true }).click()
  const tree = page.getByRole('region', { name: 'Ana rün ağacı', exact: true })
  await expect(tree).toBeVisible()
  await expect(page.getByRole('button', { name: /^Ana yol: / })).toHaveCount(5)
  await tree.scrollIntoViewIfNeeded()
  await expect.poll(() => tree.locator('img').evaluateAll((nodes) => nodes.filter((node) => {
    const rect = node.getBoundingClientRect()
    return rect.top < innerHeight && rect.bottom > 0
  }).every((node) => (node as HTMLImageElement).complete && (node as HTMLImageElement).naturalWidth > 0))).toBe(true)
  await page.screenshot({ path: info.outputPath('live-rune-editor.png'), fullPage: true })
  const after = await page.request.get('/api/settings')
  expect(await after.json()).toEqual(beforeBody)
  expect(after.headers().etag).toBe(before.headers().etag)
})
