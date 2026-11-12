import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { catalog, health, settings } from '../src/test/fixtures'
import type { Settings } from '../src/api/contracts'

type TestState = { saved: Settings; running: boolean; downloads: number; installs: number; starts: number; stops: number; order: string[]; holdDownload: boolean; failSave: boolean; failCheck: boolean; offer: boolean; resolveDownload?: () => void }
const pageErrors = new WeakMap<Page, string[]>()
test.beforeEach(({ page }) => { const errors: string[] = []; pageErrors.set(page, errors); page.on('pageerror', (error) => errors.push(error.message)) })
test.afterEach(({ page }) => { expect(pageErrors.get(page)).toEqual([]) })
async function nativeApp(page: Page, offer = true) {
  // All native commands and game reads/writes terminate in this in-page fake.
  // No actual native process, installer, user profile or League endpoint exists.
  await page.addInitScript(({ initial, roster, initialHealth, hasOffer }) => {
    const state: TestState = { saved: initial, running: true, downloads: 0, installs: 0, starts: 0, stops: 0, order: [], holdDownload: false, failSave: false, failCheck: false, offer: hasOffer }
    let revision = 1; let callbackId = 0
    const callbacks = new Map<number, (value: unknown) => void>()
    const encode = (value: unknown) => btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(value))))
    Object.assign(window, {
      isTauri: true,
      __TAURI_EVENT_PLUGIN_INTERNALS__: { unregisterListener: () => {} },
      __runepilotUpdateTest: state,
      __TAURI_INTERNALS__: {
        transformCallback: (callback: (value: unknown) => void) => { callbacks.set(++callbackId, callback); return callbackId },
        unregisterCallback: (id: number) => callbacks.delete(id),
        invoke: async (command: string, args?: { input?: { method: string; path: string; body?: string; if_match?: string } }) => {
          if (command === 'plugin:event|listen') return ++callbackId
          if (command === 'plugin:event|unlisten') return
          if (command === 'desktop_status') return { phase: 'ready', generation: 1, version: '1.0.0' }
          if (command === 'desktop_update_check') {
            if (state.failCheck) throw new Error('offline')
            return { enabled: true, channel: 'stable', update: state.offer ? { version: '1.0.1', current_version: '1.0.0', notes: 'Yeni sürüm notları.\nOyun ayarları korunur.' } : null }
          }
          if (command === 'desktop_update_download') {
            state.downloads++; state.order.push('download')
            if (state.holdDownload) await new Promise<void>((resolve) => { state.resolveDownload = resolve })
            return
          }
          if (command === 'desktop_update_install') { state.installs++; state.order.push('install'); return new Promise(() => {}) }
          if (command !== 'desktop_request') throw new Error(`Unexpected native command: ${command}`)
          const request = args!.input!
          let status = 200; let value: unknown
          const headers: Record<string, string> = { 'content-type': 'application/json' }
          if (request.path === '/health') value = { ...initialHealth, version: '1.0.0', running: state.running }
          else if (request.path === '/champion-catalog') value = roster
          else if (request.path === '/settings') {
            if (request.method === 'PUT') {
              state.order.push('save')
              if (state.failSave) { status = 500; value = { detail: 'Test save failed' } }
              else if (request.if_match !== `"${revision}"`) { status = 412; value = {} }
              else { state.saved = JSON.parse(request.body!); revision++ }
            }
            if (status === 200) value = state.saved
            headers.etag = `"${revision}"`
          } else if (request.path === '/stop_automation') { state.stops++; state.running = false; state.order.push('stop'); value = { status: 'stopped' } }
          else if (request.path === '/automation/config') value = { status: 'updated', config: JSON.parse(request.body!) }
          else if (request.path === '/start_automation') { state.starts++; throw new Error('Unexpected Start') }
          else throw new Error(`Unexpected game command: ${request.method} ${request.path}`)
          return { status, headers, body: encode(value) }
        },
      },
    })
  }, { initial: structuredClone(settings), roster: catalog, initialHealth: health, hasOffer: offer })
  await page.route('http://runepilot.localhost/**', (route) => route.fulfill({ status: 404, body: '' }))
  await page.route(/^http:\/\/127\.0\.0\.1:5173\/api\//, (route) => route.abort('blockedbyclient'))
  await page.goto('/')
  await expect(page.getByRole('combobox', { name: 'Oyun modu', exact: true })).toBeEnabled()
}
const readState = (page: Page) => page.evaluate(() => (window as unknown as { __runepilotUpdateTest: TestState }).__runepilotUpdateTest)

test('announces the complete update, fits narrow windows, and waits for consent before download', async ({ page }, info) => {
  await nativeApp(page)
  const panel = page.getByRole('region', { name: 'Uygulama güncellemesi' })
  await expect(panel.getByRole('button', { name: 'Güncelle', exact: true })).toBeVisible()
  expect((await readState(page)).downloads).toBe(0)
  expect((await readState(page)).installs).toBe(0)
  await panel.getByText('Sürüm notları', { exact: true }).click()
  await expect(panel.getByText(/Yeni sürüm notları/)).toBeVisible()
  const bounds = await panel.boundingBox(); const size = page.viewportSize()!
  expect(bounds!.x).toBeGreaterThanOrEqual(0); expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(size.width)
  await page.screenshot({ path: info.outputPath('update-offer.png'), fullPage: true })
  await panel.getByRole('button', { name: 'Daha sonra', exact: true }).click()
  await expect(panel).toHaveCount(0)
  await page.getByRole('button', { name: 'Yeni sürümü göster', exact: true }).click()
  await expect(panel).toBeVisible()
  expect((await readState(page)).starts).toBe(0)
})

test('edits during download are flushed; a failed final save prevents Stop and installation, then retry succeeds once', async ({ page }) => {
  await nativeApp(page)
  await page.evaluate(() => { (window as unknown as { __runepilotUpdateTest: TestState }).__runepilotUpdateTest.holdDownload = true })
  const panel = page.getByRole('region', { name: 'Uygulama güncellemesi' })
  await panel.getByRole('button', { name: 'Güncelle', exact: true }).click()
  await page.evaluate(() => { (window as unknown as { __runepilotUpdateTest: TestState }).__runepilotUpdateTest.failSave = true })
  await page.getByRole('combobox', { name: 'Oyun modu', exact: true }).selectOption('Ranked Flex')
  await page.evaluate(() => { (window as unknown as { __runepilotUpdateTest: TestState }).__runepilotUpdateTest.resolveDownload?.() })
  await expect(panel.getByRole('alert')).toContainText('Güncelleme başlamadı')
  const failed = await readState(page)
  expect(failed.installs).toBe(0); expect(failed.stops).toBe(0)
  await expect(page.getByRole('combobox', { name: 'Oyun modu', exact: true })).toHaveValue('Ranked Flex')
  await page.evaluate(() => { (window as unknown as { __runepilotUpdateTest: TestState }).__runepilotUpdateTest.failSave = false })
  await panel.getByRole('button', { name: 'Güncelle', exact: true }).click()
  await expect.poll(async () => (await readState(page)).installs).toBe(1)
  const finished = await readState(page)
  expect(finished.saved.queue_name).toBe('Ranked Flex'); expect(finished.starts).toBe(0)
  expect(finished.downloads).toBe(1); expect(finished.stops).toBe(1)
  expect(finished.order.slice(-2)).toEqual(['stop', 'install'])
})

test('a failed recheck never claims that the installed version is current', async ({ page }) => {
  await nativeApp(page, false)
  await page.getByRole('button', { name: 'Güncellemeleri kontrol et', exact: true }).click()
  const panel = page.getByRole('region', { name: 'Uygulama güncellemesi' })
  await expect(panel.getByRole('status')).toHaveText('En güncel sürümü kullanıyorsun.')
  await page.evaluate(() => { (window as unknown as { __runepilotUpdateTest: TestState }).__runepilotUpdateTest.failCheck = true })
  await panel.getByRole('button', { name: 'Güncellemeleri kontrol et', exact: true }).click()
  await expect(panel.getByRole('status')).toHaveText('Güncelleme tamamlanamadı.')
  await expect(panel.getByRole('alert')).toContainText('kontrol edilemedi')
  expect((await readState(page)).installs).toBe(0)
})
