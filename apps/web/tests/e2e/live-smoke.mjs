import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

async function main() {
  // Live local browser test. The opt-in task action only uses simulation, never motion.
  const repoRoot = fileURLToPath(new URL("../../../../", import.meta.url))
  process.chdir(repoRoot)
  process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(repoRoot, ".local/browser-tools/browsers")
  const { chromium } = await import(pathToFileURL(path.join(repoRoot, ".local/browser-tools/node_modules/playwright/index.mjs")).href)
  const origin = process.env.WEB_QA_ORIGIN || "http://127.0.0.1:8000"
  const credentials = Object.fromEntries(fs.readFileSync(process.env.WEB_QA_ENV_FILE || "cloud/backend/.env", "utf8").split("\n").filter(l => l && !l.startsWith("#") && l.includes("=")).map((l) => {
    const i = l.indexOf("=")
    return [l.slice(0, i).trim(), l.slice(i + 1).trim().replace(/^['"]|['"]$/g, "")]
  }))
  const judge = process.env.WEB_QA_ACCOUNT === "judge"
  const username = judge ? credentials.REMOTE_DEMO_USER : credentials.FIRST_SUPERUSER
  const password = judge ? credentials.REMOTE_DEMO_PASSWORD : credentials.FIRST_SUPERUSER_PASSWORD
  const secrets = [credentials.FIRST_SUPERUSER_PASSWORD, credentials.REMOTE_DEMO_PASSWORD, credentials.REMOTE_EXECUTOR_KEY].filter(Boolean)
  const clean = s => secrets.reduce((a, b) => a.split(b).join("[REDACTED]"), String(s))
  const report = { origin, checks: [], pageErrors: [], task: null }
  let browser
  try {
    browser = await chromium.launch({ headless: true })
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
    page.on("pageerror", e => report.pageErrors.push(clean(e.message)))
    await page.goto(`${origin}/console`)
    await page.waitForSelector("#login-email")
    assert(page.url().includes("/login"))
    await page.locator("#login-email").fill(username)
    await page.locator("#login-password").fill("intentionally-invalid-test-value")
    await page.getByRole("button", { name: "进入工作台" }).click()
    await page.locator(".login-error").waitFor()
    report.checks.push("unauthenticated redirect and failed login")
    await page.locator("#login-password").fill(password)
    await page.getByRole("button", { name: "进入工作台" }).click()
    await page.getByRole("heading", { name: "现场观察工作台" }).waitFor()
    await page.getByText("任务服务已连接", { exact: true }).waitFor()
    await page.getByRole("button", { name: "发起任务", exact: true }).waitFor()
    assert(await page.getByRole("button", { name: /实机执行/ }).isDisabled())
    report.checks.push("real OAuth login; actual capabilities; motion disabled")
    if (process.env.WEB_QA_RUN_SIM === "1") {
      if (process.env.WEB_QA_ROUTE) {
        const routeInput = page.getByRole("combobox", { name: "仿真路线", exact: true })
        await page.locator(".el-select").filter({ has: routeInput }).locator(".el-select__wrapper").click()
        await page.getByRole("option", { name: new RegExp(`^${process.env.WEB_QA_ROUTE} ·`) }).click()
      }
      const create = page.waitForResponse(r => r.url() === `${origin}/api/v1/tasks` && r.request().method() === "POST")
      await page.getByRole("button", { name: "发起任务", exact: true }).click()
      const accepted = await create
      assert.equal(accepted.status(), 202)
      const created = await accepted.json()
      report.task = { task_id: created.task_id, point_id: created.point_id, mode: created.mode }
      assert.equal(created.mode, "simulation")
      if (process.env.WEB_QA_ROUTE) assert.equal(created.simulation_route.id, process.env.WEB_QA_ROUTE)
      assert(await page.getByRole("button", { name: "发起任务", exact: true }).isDisabled())
      const done = await page.waitForResponse(async (r) => {
        if (r.url() !== `${origin}/api/v1/tasks/${created.task_id}` || r.request().method() !== "GET" || r.status() !== 200) return false
        const v = await r.json()
        return ["SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED", "REJECTED"].includes(v.state) && !v.worker_alive
      }, { timeout: 120000 })
      const finished = await done.json()
      Object.assign(report.task, { state: finished.state, video_available: finished.video_available, analysis_state: finished.analysis_state, simulation_summary: finished.simulation_summary })
      assert.equal(finished.state, "SUCCEEDED")
      assert.equal(finished.photo_available, false)
      assert.equal(finished.analysis_state, "NO_CAMERA_PHOTO")
      report.checks.push("browser submitted real MuJoCo task; reached goal; no simulated photo/answer")
    }
    await page.waitForFunction(() => document.querySelector("video")?.readyState >= 1, {}, { timeout: 45000 })
    const video = await page.locator("video").evaluate(v => ({ width: v.videoWidth, height: v.videoHeight, duration: v.duration, source: v.src.startsWith("blob:") }))
    assert(video.source)
    assert(video.width > 0)
    report.video = video
    await page.locator("video").evaluate(async (v) => {
      v.muted = true
      await v.play()
      v.pause()
      v.currentTime = Math.min(0.9, v.duration / 2)
      await new Promise(r => v.addEventListener("seeked", r, { once: true }))
    })
    await page.screenshot({ animations: "disabled", path: ".local/frontend-console-desktop.png", fullPage: true })
    report.checks.push("authenticated Blob video decodes in Chromium")
    const taskQuery = new URL(page.url()).search
    await page.reload()
    await page.getByRole("heading", { name: "现场观察工作台" }).waitFor()
    await page.waitForFunction(() => document.querySelector("video")?.readyState >= 1, {}, { timeout: 30000 })
    assert.equal(new URL(page.url()).search, taskQuery)
    assert.equal(await page.evaluate(() => localStorage.getItem("campus-patrol-token-key")), null)
    assert(await page.evaluate(() => !!sessionStorage.getItem("campus-patrol-token-key")))
    report.checks.push("refresh restores task and session; no JWT in localStorage")
    await page.route("**/api/v1/tasks/*", r => r.abort("connectionrefused"))
    await page.waitForFunction(() => document.body.textContent.includes("状态更新暂时中断"), {}, { timeout: 15000 })
    assert(await page.locator("video").isVisible())
    await page.unroute("**/api/v1/tasks/*")
    await page.getByRole("button", { name: "重试查询" }).click()
    await page.waitForFunction(() => !document.body.textContent.includes("状态更新暂时中断"), {}, { timeout: 15000 })
    report.checks.push("poll connection error retains evidence; manual retry recovers")
    await page.goto(`${origin}/history`)
    await page.getByRole("heading", { name: "任务记录", exact: true }).waitFor()
    await page.locator(".task-link").first().waitFor()
    await page.waitForTimeout(650)
    await page.screenshot({ animations: "disabled", path: ".local/frontend-history.png", fullPage: true })
    let orphanPolls = 0
    const watch = (r) => {
      if (/\/api\/v1\/tasks\/[^/]+(?:\/events)?(?:\?|$)/.test(r.url()) && r.method() === "GET")orphanPolls++
    }
    await page.waitForTimeout(1200)
    page.on("request", watch)
    await page.waitForTimeout(1500)
    page.off("request", watch)
    assert.equal(orphanPolls, 0)
    await page.getByRole("button", { name: "查看详情" }).first().click()
    await page.getByRole("heading", { name: "现场观察工作台" }).waitFor()
    report.checks.push("history direct refresh/detail; task polling stops on leaving console")
    await page.goto(`${origin}/project`)
    await page.getByRole("heading", { name: "当前能力与验证边界" }).waitFor()
    await page.screenshot({ animations: "disabled", path: ".local/frontend-project.png", fullPage: true })
    assert((await page.locator("body").textContent()).includes("尚未完成"))
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`${origin}/console`)
    await page.getByRole("heading", { name: "现场观察工作台" }).waitFor()
    await page.waitForTimeout(800)
    report.mobile = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }))
    assert(report.mobile.scroll <= report.mobile.width + 1)
    await page.screenshot({ animations: "disabled", path: ".local/frontend-console-mobile.png", fullPage: true })
    report.checks.push("project truthfully lists cloud gaps; mobile has no page overflow")
    await page.route("**/api/v1/tasks/*", r => r.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "Could not validate credentials" }) }))
    await page.waitForSelector("#login-email", { timeout: 15000 })
    assert.equal(await page.evaluate(() => sessionStorage.getItem("campus-patrol-token-key")), null)
    report.checks.push("FastAPI credential expiry logs out and clears token/media view")
    assert.deepEqual(report.pageErrors, [])
    report.result = "passed"
    fs.writeFileSync(".local/frontend-browser-report.json", JSON.stringify(report, null, 2))
    console.log(JSON.stringify(report, null, 2))
  } catch (e) {
    report.result = "failed"
    report.error = clean(e.message)
    fs.writeFileSync(".local/frontend-browser-report.json", JSON.stringify(report, null, 2))
    console.log(JSON.stringify(report, null, 2))
    process.exitCode = 1
  } finally {
    await browser?.close()
  }
}

void main().catch(() => {
  console.error("浏览器验证未能启动，请检查本地工具与后端配置。")
  process.exitCode = 1
})
