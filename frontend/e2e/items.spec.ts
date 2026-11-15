import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { catalog, deferred, health, settings } from '../src/test/fixtures'
import type { ItemCatalog, ItemSetCollection } from '../src/api/itemSets'

const uid = 'runepilot-11111111-1111-4111-8111-111111111111'
const zero = { ad: 0, ap: 0, hp: 0, armor: 0, mr: 0, attack_speed: 0, haste: 0 }
const gameData: ItemCatalog = { version: '16.22.1', champions: [{ id: 107, name: 'Rengar' }, { id: 266, name: 'Aatrox' }], items: [
  { id: 1036, name: 'Uzun Kılıç', price: 350, stats: { ...zero, ad: 10 }, tags: ['Damage'], description: '10 AD' },
  { id: 1052, name: 'Kuvvet Kitabı', price: 400, stats: { ...zero, ap: 20 }, tags: ['SpellDamage'], description: '20 AP' },
  { id: 1028, name: 'Yakut Kristal', price: 400, stats: { ...zero, hp: 150 }, tags: ['Health'], description: '150 Can' },
] }
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1cAAAAASUVORK5CYII=', 'base64')

async function setup(page: Page) {
  const collection: ItemSetCollection = { sets: [{ uid, title: 'Rengar Orman', champion_id: 107, map_id: 11, blocks: [{ name: 'Başlangıç', items: [] }, { name: 'Ana eşyalar', items: [] }] }] }
  const state = { collection, version: 1, writes: 0, exports: 0, stops: 0, firstCatalogFails: false, delayedCatalog: undefined as ReturnType<typeof deferred<void>> | undefined, delayedExport: undefined as ReturnType<typeof deferred<void>> | undefined, loseSaveReply: false, conflict: false }
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request(); const path = new URL(request.url()).pathname
    if (path.endsWith('/icon') || path.endsWith('/portrait')) return route.fulfill({ contentType: 'image/png', body: png })
    if (path === '/api/health') return route.fulfill({ json: health })
    if (path === '/api/session') return route.fulfill({ json: { token: 'mock-session-token-more-than-twenty' } })
    if (path === '/api/champion-catalog') return route.fulfill({ json: catalog })
    if (path === '/api/settings') return route.fulfill({ json: settings, headers: { ETag: '"settings-1"' } })
    if (path === '/api/item-builder/catalog') {
      if (state.delayedCatalog) await state.delayedCatalog.promise
      return route.fulfill({ status: state.firstCatalogFails ? 503 : 200, json: gameData })
    }
    if (path.startsWith('/api/item-builder/champions/')) return route.fulfill({ json: { champion_id: Number(path.split('/').at(-1)), version: '16.22.1', base: { ...zero, ad: 68, hp: 590, armor: 34, mr: 32, attack_speed: .667 }, growth: { ...zero, ad: 3, hp: 104, armor: 4.2, mr: 2.05, attack_speed: 3 }, attack_speed_ratio: .667 } })
    if (path === '/api/item-sets') {
      if (request.method() === 'PUT') {
        if (state.conflict || request.headers()['if-match'] !== `"items-${state.version}"`) return route.fulfill({ status: 412, json: {} })
        state.writes++; state.collection = request.postDataJSON() as ItemSetCollection; state.version++
        if (state.loseSaveReply) { state.loseSaveReply = false; return route.abort() }
      }
      return route.fulfill({ json: state.collection, headers: { ETag: `"items-${state.version}"` } })
    }
    if (path === '/api/item-sets/client-state') return route.fulfill({ json: { revision: '"client-context-11111111111111111111"', set_count: 2 } })
    if (path.endsWith('/export')) {
      state.exports++
      if (state.delayedExport) await state.delayedExport.promise
      return route.fulfill({ json: { revision: '"client-context-22222222222222222222"', set_count: 3 } })
    }
    if (path === '/api/stop_automation') { state.stops++; return route.fulfill({ json: { status: 'stopped' } }) }
    throw new Error(`Unexpected request ${request.method()} ${path}`)
  })
  await page.goto('/')
  await expect(page.getByRole('button', { name: '1. tercih: Aatrox', exact: true })).toBeEnabled()
  return state
}
async function open(page: Page) {
  await page.getByRole('button', { name: 'Eşya Setleri', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Uzun Kılıç ekle', exact: true })).toBeEnabled()
  await expect(page.getByLabel('Seviye ve eşya istatistikleri').getByText('68', { exact: true })).toBeVisible()
}

test('retired items in inactive blocks are identified and block save and export', async ({ page }) => {
  const state = await setup(page)
  state.collection.sets[0].blocks[1].items = [{ id: 2051, count: 1 }]
  await open(page)
  await expect(page.getByRole('alert')).toContainText('Ana eşyalar (2051)')
  await expect(page.getByRole('button', { name: 'LoL’e aktar', exact: true })).toBeDisabled()
  await page.getByLabel('Eşya seti adı').fill('Düzeltilecek set')
  await expect(page.getByRole('button', { name: 'Seti kaydet', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: 'Ana eşyalar bölümünü düzenle' }).click()
  await page.getByRole('button', { name: '1. eşyayı kaldır' }).click()
  await expect(page.getByRole('button', { name: 'Seti kaydet', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Seti kaydet', exact: true }).click()
  await expect.poll(() => state.writes).toBe(1)
  expect(state.exports).toBe(0)
})

test('item builder calculates only active block, preserves slots and local save never exports', async ({ page }, info) => {
  const state = await setup(page); await open(page)
  await page.getByRole('button', { name: 'Uzun Kılıç ekle' }).click()
  await expect(page.getByLabel('Seviye ve eşya istatistikleri').getByText('78', { exact: true })).toBeVisible()
  await page.getByRole('slider', { name: 'Şampiyon seviyesi' }).focus()
  await page.getByRole('slider', { name: 'Şampiyon seviyesi' }).press('End')
  await expect(page.getByLabel('Seviye ve eşya istatistikleri').getByText('129', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '1. eşyayı sağa taşı' }).click()
  await page.getByRole('button', { name: 'Seti kaydet', exact: true }).click()
  await expect.poll(() => state.writes).toBe(1)
  expect(state.collection.sets[0].blocks[0].slots).toEqual([null, 1036, null, null, null, null])
  expect(state.exports).toBe(0)
  await page.getByRole('button', { name: 'Ana eşyalar bölümünü düzenle' }).click()
  await expect(page.getByLabel('Seviye ve eşya istatistikleri').getByText('119', { exact: true })).toBeVisible()
  await expect(page.getByText('Pasifler, biriken yükler, rünler ve koşullu güçlendirmeler', { exact: false })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('item-builder.png'), fullPage: true })
})

test('six slot limit and navigation retain draft until saved or discarded', async ({ page }) => {
  const state = await setup(page); await open(page)
  for (let i = 0; i < 7; i++) await page.getByRole('button', { name: 'Uzun Kılıç ekle' }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Altı eşya yuvası dolu' })).toBeVisible()
  await page.getByRole('button', { name: 'Şampiyonlar', exact: true }).click()
  await page.getByRole('button', { name: 'Kaydet ve oturumu bitir', exact: true }).click()
  await expect(page.getByText('Kaydedilmemiş eşya seti var.', { exact: false })).toBeVisible()
  expect(state.stops).toBe(0)
  await page.getByRole('button', { name: 'Eşya Setleri', exact: true }).click()
  await expect(page.getByLabel('Aktif bölüm dizilimi').getByText('6/6', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Düzenlemeyi geri al', exact: true }).click()
  await expect(page.getByLabel('Aktif bölüm dizilimi').getByText('0/6', { exact: true })).toBeVisible()
})

test('late refresh disables changes and an initial catalog error can be retried', async ({ page }) => {
  const state = await setup(page); state.firstCatalogFails = true
  await page.getByRole('button', { name: 'Eşya Setleri', exact: true }).click()
  await expect(page.getByText('Oyun verileri alınamadı.', { exact: false })).toBeVisible()
  state.firstCatalogFails = false
  await page.getByRole('button', { name: 'Listeyi yenile', exact: true }).click()
  await expect(page.getByLabel('Eşya seti adı')).toHaveValue('Rengar Orman')
  const waiting = deferred<void>(); state.delayedCatalog = waiting
  await page.getByRole('button', { name: 'Listeyi yenile', exact: true }).click()
  await expect(page.getByLabel('1. bölüm adı')).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Uzun Kılıç ekle' })).toBeDisabled()
  waiting.resolve()
  await expect(page.getByLabel('1. bölüm adı')).toBeEnabled()
})

test('lost save reply reconciles without a second write and conflicts preserve draft', async ({ page }) => {
  const state = await setup(page); await open(page)
  await page.getByLabel('Eşya seti adı').fill('Yerel taslak')
  state.loseSaveReply = true
  await page.getByRole('button', { name: 'Seti kaydet', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('İşlem sonucu doğrulanamadı')
  await page.getByRole('button', { name: 'Seti kaydet', exact: true }).click()
  await expect(page.getByText('Eşya setleri RunePilot’a kaydedildi.', { exact: true })).toBeVisible()
  expect(state.writes).toBe(1)
  await page.getByLabel('Eşya seti adı').fill('İkinci taslak')
  state.conflict = true; state.version++
  await page.getByRole('button', { name: 'Seti kaydet', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Taslağın korundu')
  await page.getByRole('button', { name: 'Kayıt durumunu kontrol et (taslak korunur)', exact: true }).click()
  await expect(page.getByLabel('Eşya seti adı')).toHaveValue('İkinci taslak')
  state.conflict = false
  await page.getByRole('button', { name: 'Seti kaydet', exact: true }).click()
  await expect.poll(() => state.collection.sets[0].title).toBe('İkinci taslak')
})

test('explicit League export blocks controlled exit until confirmed', async ({ page }) => {
  const state = await setup(page); await open(page)
  const pending = deferred<void>(); state.delayedExport = pending
  await page.getByRole('button', { name: 'LoL’e aktar', exact: true }).click()
  await expect.poll(() => state.exports).toBe(1)
  await page.getByRole('button', { name: 'Kaydet ve oturumu bitir', exact: true }).click()
  expect(state.stops).toBe(0)
  pending.resolve()
  await expect(page.getByText('Eşya seti LoL istemcisine aktarıldı.', { exact: false })).toBeVisible()
})

test('new sets, filters, copy and confirmed local delete preserve the original', async ({ page }) => {
  const state = await setup(page); state.collection = { sets: [] }
  await page.getByRole('button', { name: 'Eşya Setleri', exact: true }).click()
  await expect(page.getByText('İlk eşya setini oluştur', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Yeni set', exact: true }).click()
  await page.getByLabel('Eşya seti adı').fill('AP dizilimi')
  await page.getByRole('button', { name: 'AP', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Uzun Kılıç ekle' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Kuvvet Kitabı ekle' }).click()
  await page.getByRole('button', { name: 'Seti kaydet', exact: true }).click()
  await expect.poll(() => state.collection.sets.length).toBe(1)
  await page.getByRole('button', { name: 'Kopyala', exact: true }).click()
  await page.getByLabel('Eşya seti adı').fill('Kopya dizilim')
  await page.getByRole('button', { name: 'Seti kaydet', exact: true }).click()
  await expect.poll(() => state.collection.sets.length).toBe(2)
  await page.getByRole('button', { name: 'Seti sil', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Silmeyi onayla', exact: true })).toBeVisible()
  expect(state.collection.sets.length).toBe(2)
  await page.getByRole('button', { name: 'Silmeyi onayla', exact: true }).click()
  await expect.poll(() => state.collection.sets.length).toBe(1)
  expect(state.collection.sets[0].title).toBe('AP dizilimi')
  expect(state.exports).toBe(0)
})
