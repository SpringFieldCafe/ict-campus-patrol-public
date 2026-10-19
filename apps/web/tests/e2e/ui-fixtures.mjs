import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

async function main() {
  // Explicit browser-only route fixtures. No real robot, cloud model, credentials,
  // or backend API is used. Test artifacts are written only into repo/.local.
  const repositoryRoot = fileURLToPath(new URL("../../../../", import.meta.url))
  const artifactsDirectory = path.join(repositoryRoot, ".local")
  const browserToolsDirectory = path.join(artifactsDirectory, "browser-tools")
  // Install locally with: npm install --prefix .local/browser-tools playwright@1.64.1
  // Then run: PLAYWRIGHT_BROWSERS_PATH=.local/browser-tools/browsers node .local/browser-tools/node_modules/playwright/cli.js install chromium
  process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(browserToolsDirectory, "browsers")
  const { chromium } = await import(pathToFileURL(path.join(browserToolsDirectory, "node_modules/playwright/index.mjs")).href)
  fs.mkdirSync(artifactsDirectory, { recursive: true })
  const origin = new URL(process.env.WEB_QA_ORIGIN || "http://127.0.0.1:8000").origin
  const report = {
    kind: "UI_ROUTE_FIXTURES_ONLY",
    disclaimer: "浏览器接口替身验证；不属于实机、真实相机或华为云模型验证。未读取真实凭据，所有API请求均被拦截。",
    origin,
    checks: [],
    pageErrors: [],
    unexpectedApiCalls: [],
    forbiddenExternalRequests: []
  }
  const sha = "a".repeat(64)
  const now = "2026-10-16T06:00:00Z"
  const testPhoto = `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="480" viewBox="0 0 800 480"><rect width="800" height="480" fill="#173842"/><rect x="65" y="65" width="670" height="350" rx="8" fill="#234d52" stroke="#72b3a4" stroke-width="2"/><text x="400" y="220" text-anchor="middle" fill="#cce7d9" font-family="sans-serif" font-size="30">UI TEST FIXTURE</text><text x="400" y="270" text-anchor="middle" fill="#9cbeb6" font-family="sans-serif" font-size="18">SYNTHETIC IMAGE · NOT A ROBOT PHOTO</text></svg>`
  const capabilities = { simulation_configured: true, simulation_camera_photo: false, simulation_video: true, motion_enabled: true, huawei_configured: true, task_timeout_seconds: 90, single_task: true, queue_enabled: false, automatic_retry: false }
  const points = { reference: "initial_pose", example_configuration: true, points: [{ id: "fixture-a", description: "UI TEST FIXTURE ONLY", goal_forward: 1, goal_left: 0 }] }
  const fixtureUser = { id: "fixture-user", email: "fixture@example.invalid", full_name: "UI 测试替身", is_active: true, is_superuser: true }

  function task(overrides = {}) {
    return { task_id: "task-fixture-photo", point_id: "fixture-a", point: points.points[0], point_reference: "initial_pose", mode: "motion", question: "UI 测试问题", state: "SUCCEEDED", created_at_utc: now, updated_at_utc: now, timeout_seconds: 90, error: null, stop_acknowledged: null, cleanup_forced: false, requires_operator_review: false, worker_alive: false, cancel_requested: false, photo_available: true, video_available: false, photo_url: "/api/v1/tasks/task-fixture-photo/photo", video_url: null, photo: { source: "UI_TEST_FIXTURE_ONLY", captured_at_utc: now, capture_time_basis: "fixture", width: 800, height: 480, image_sha256: sha }, simulation_progress: null, simulation_summary: null, analysis_state: "NOT_REQUESTED", analysis_error: null, answer: null, ...overrides }
  }
  function answer(overrides = {}) {
    return { answer: "UI_TEST_FIXTURE_ANSWER：测试图像中的观察区可见。", question: "UI 测试问题", model: "fixture-model-no-cloud-call", provider: "fixture", request_id: "fixture-request", answered_at_utc: now, image_sha256: sha, task_id: "task-fixture-photo", ...overrides }
  }
  async function json(route, value, status = 200) {
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(value) })
  }

  let browser
  async function scenario(name, initial, extra, verify) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } })
    await context.addInitScript(() => sessionStorage.setItem("campus-patrol-token-key", "ui-fixture-token-not-a-real-jwt"))
    const state = { current: initial, events: initial ? [{ state: initial.state, at_utc: now }] : [], createCalls: 0, analysisCalls: 0, cancelCalls: 0, listCalls: 0, taskReads: [], eventReads: [], failTaskReads: false, ...extra }
    const page = await context.newPage()
    page.on("pageerror", error => report.pageErrors.push({ scenario: name, message: error.message }))
    await context.route("**/*", async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      if (url.origin !== origin) {
        report.forbiddenExternalRequests.push({ scenario: name, origin: url.origin })
        return route.abort("blockedbyclient")
      }
      if (!url.pathname.startsWith("/api/v1/")) return route.continue()
      if (request.method() === "GET" && url.pathname === "/api/v1/users/me") return json(route, fixtureUser)
      if (request.method() === "GET" && url.pathname === "/api/v1/capabilities") return json(route, state.capabilities || capabilities)
      if (request.method() === "GET" && url.pathname === "/api/v1/points") return json(route, points)
      if (request.method() === "GET" && url.pathname === "/api/v1/tasks") {
        state.listCalls += 1
        return json(route, { data: state.current ? [state.current] : [], count: state.current ? 1 : 0 })
      }
      if (request.method() === "GET" && /\/tasks\/[^/]+\/photo$/.test(url.pathname)) {
        return route.fulfill({ status: 200, contentType: "image/svg+xml", body: testPhoto })
      }
      if (request.method() === "GET" && /\/tasks\/[^/]+\/events$/.test(url.pathname)) {
        state.eventReads.push(performance.now())
        const after = Number(url.searchParams.get("after") || "0")
        return json(route, { data: state.events.slice(after), next_offset: state.events.length })
      }
      if (request.method() === "GET" && /\/tasks\/[^/]+$/.test(url.pathname)) {
        state.taskReads.push({ at: performance.now(), failed: state.failTaskReads })
        if (state.failTaskReads) return route.abort("connectionrefused")
        if (state.analysisRequested) state.current = task({ analysis_state: "SUCCEEDED", answer: state.expectedAnswer })
        return json(route, state.current)
      }
      if (request.method() === "POST" && /\/tasks\/[^/]+\/analysis$/.test(url.pathname)) {
        state.analysisCalls += 1
        state.analysisBody = request.postDataJSON()
        state.analysisRequested = true
        state.current = task({ analysis_state: "RUNNING", worker_alive: true })
        return json(route, state.current, 202)
      }
      if (request.method() === "POST" && /\/tasks\/[^/]+\/cancel$/.test(url.pathname)) {
        state.cancelCalls += 1
        state.current = { ...state.current, cancel_requested: true }
        return json(route, { task_id: state.current.task_id, state: state.current.state, cancel_requested: true })
      }
      if (request.method() === "POST" && url.pathname === "/api/v1/tasks" && state.unknownSubmission) {
        state.createCalls += 1
        state.current = task({ task_id: state.createCalls === 1 ? "task-fixture-unknown" : "task-fixture-second", mode: "simulation", state: "NAVIGATING", worker_alive: true, photo_available: false, photo_url: null, photo: null, analysis_state: "NO_CAMERA_PHOTO" })
        state.events = [{ state: state.current.state, at_utc: now }]
        if (state.createCalls === 1) return route.abort("connectionreset")
        return json(route, state.current, 202)
      }
      report.unexpectedApiCalls.push({ scenario: name, method: request.method(), path: url.pathname })
      return json(route, { detail: "Unexpected UI fixture request" }, 500)
    })
    try {
      await page.goto(`${origin}/console${initial ? `?task=${initial.task_id}` : ""}`)
      await page.getByRole("heading", { name: "现场观察工作台" }).waitFor()
      await page.getByText("任务服务已连接", { exact: true }).waitFor()
      await page.evaluate(() => {
        const badge = document.createElement("div")
        badge.textContent = "UI TEST FIXTURE · 合成接口替身，非实机 / 云模型结果"
        badge.id = "fixture-test-disclaimer"
        Object.assign(badge.style, { position: "fixed", bottom: "0", left: "0", right: "0", zIndex: "100000", textAlign: "center", background: "#633e81", color: "#ffffff", padding: "8px", fontSize: "12px", pointerEvents: "none" })
        document.body.append(badge)
      })
      await verify(page, state)
      report.checks.push({ name, result: "passed", fixtureOnly: true })
    } finally {
      await context.close()
    }
  }

  try {
    browser = await chromium.launch({ headless: true })

    const remoteCapabilities = { ...capabilities, motion_enabled: false, huawei_configured: false, execution_backend: "remote", remote: { online: false, ready: false, configured: true }, simulation_routes: [{ id: "fixture-route", description: "UI TEST FIXTURE ROUTE", scene: "flat_obstacle", seed: 0, waypoints: [{ x: 1, y: 0, radius: 0.4 }] }] }
    await scenario("offline remote executor blocks submission while history remains accessible", null, { capabilities: remoteCapabilities }, async (page, state) => {
      await page.getByText("执行端离线", { exact: true }).waitFor()
      assert(await page.getByRole("button", { name: "发起任务", exact: true }).isDisabled())
      assert.equal(state.createCalls, 0)
      assert(state.listCalls > 0)
    })
    await scenario("local workbench explains suspension during remote demo", null, { capabilities: { ...capabilities, local_suspended: true, simulation_configured: false, motion_enabled: false } }, async (page) => {
      await page.getByText("远程演示已开启，本地暂停接新任务；请使用统一的服务端工作台。", { exact: true }).waitFor()
      assert(await page.getByRole("button", { name: "发起任务", exact: true }).isDisabled())
    })
    await scenario("remote recording delivery and lost heartbeat keep task admission blocked", task({ mode: "simulation", state: "NAVIGATING", worker_alive: false, photo_available: false, photo_url: null, photo: null, analysis_state: "NO_CAMERA_PHOTO", remote_pending: true, remote_phase: "UPLOADING", executor_online: true }), { capabilities: { ...remoteCapabilities, remote: { ...remoteCapabilities.remote, online: true } } }, async (page, state) => {
      await page.getByText("仿真执行已结束，正在回传结果和录像。", { exact: true }).waitFor()
      assert(await page.getByRole("button", { name: "发起任务", exact: true }).isDisabled())
      state.current = { ...state.current, executor_online: false }
      await page.getByText("执行端连接中断，当前任务结果待确认；恢复连接后核对同一任务，不会自动重跑。", { exact: true }).waitFor()
      assert(await page.getByRole("button", { name: "发起任务", exact: true }).isDisabled())
      assert.equal(state.createCalls, 0)
    })

    await scenario("motion photo decode and photo-question API success", task(), { expectedAnswer: answer() }, async (page, state) => {
      await page.waitForFunction(() => {
        const image = document.querySelector(".observation-photo img")
        return image?.complete && image.naturalWidth === 800
      })
      await page.getByRole("textbox", { name: "照片分析问题", exact: true }).fill("UI 测试问题")
      await page.getByRole("button", { name: "分析照片", exact: true }).click()
      await page.locator(".answer-text").waitFor()
      assert.equal(state.analysisCalls, 1)
      assert.deepEqual(state.analysisBody, { question: "UI 测试问题" })
      assert.equal((await page.locator(".answer-text").textContent()).trim(), state.expectedAnswer.answer)
      assert(await page.getByText("回答已关联当前照片", { exact: true }).isVisible())
      assert.equal(state.createCalls, 0)
      await page.screenshot({ path: path.join(artifactsDirectory, "frontend-fixture-photo-answer.png"), fullPage: true })
    })

    for (const [name, expectedAnswer] of [
      ["answer task_id mismatch is hidden", answer({ task_id: "task-fixture-other" })],
      ["answer photo SHA256 mismatch is hidden", answer({ image_sha256: "b".repeat(64) })]
    ]) {
      await scenario(name, task({ analysis_state: "SUCCEEDED", answer: expectedAnswer }), {}, async (page) => {
        await page.getByText("回答与当前照片的关联校验未通过，暂不展示回答。", { exact: true }).waitFor()
        assert.equal(await page.locator(".answer-text").count(), 0)
        assert(!(await page.locator("body").textContent()).includes("UI_TEST_FIXTURE_ANSWER"))
      })
    }

    const htmlAnswer = "<img src=x onerror=\"window.__fixtureHtmlExecuted=1\"><script>window.__fixtureHtmlExecuted=2</script>UI_TEST_FIXTURE_HTML"
    await scenario("HTML answer remains literal text without HTML or script execution", task({ analysis_state: "SUCCEEDED", answer: answer({ answer: htmlAnswer }) }), {}, async (page) => {
      await page.locator(".answer-text").waitFor()
      assert.equal((await page.locator(".answer-text").textContent()).trim(), htmlAnswer)
      assert.equal(await page.locator(".answer-text img, .answer-text script").count(), 0)
      assert.equal(await page.evaluate(() => window.__fixtureHtmlExecuted), undefined)
    })

    await scenario("cancel request waits for executor confirmation before showing cancelled", task({ task_id: "task-fixture-cancel", mode: "simulation", state: "NAVIGATING", worker_alive: true, photo_available: false, photo_url: null, photo: null, analysis_state: "NO_CAMERA_PHOTO" }), {}, async (page, state) => {
      await page.getByRole("button", { name: "请求取消", exact: true }).click()
      await page.getByText("取消已请求，等待确认", { exact: true }).waitFor()
      assert.equal(state.cancelCalls, 1)
      await page.waitForTimeout(1400)
      assert.equal((await page.locator(".execution-header .el-tag").textContent()).trim(), "导航处理中")
      assert(!(await page.locator("body").textContent()).includes("已取消"))
      assert(!(await page.locator("body").textContent()).includes("机器狗已停"))
      assert(await page.getByText("正在等待取消确认", { exact: true }).isVisible())
      await page.screenshot({ path: path.join(artifactsDirectory, "frontend-fixture-cancel-awaiting.png"), fullPage: true })
      state.current = { ...state.current, state: "CANCELLED", worker_alive: false, updated_at_utc: "2026-10-16T06:00:05Z", error: { code: "CANCELLED", message: "Fixture executor confirmed cancellation" } }
      state.events.push({ state: "CANCELLED", at_utc: state.current.updated_at_utc })
      await page.waitForFunction(() => document.querySelector(".execution-header .el-tag")?.textContent.trim() === "已取消")
      assert.equal(await page.locator(".cancel-pending").count(), 0)
    })

    await scenario("unknown submission blocks retries until refresh and task reconciliation", null, { unknownSubmission: true }, async (page, state) => {
      const submit = page.getByRole("button", { name: "发起任务", exact: true })
      await submit.click()
      await page.getByText("上次提交尚未确认，请刷新连接并核对最近任务，避免重复发起。", { exact: true }).waitFor()
      assert(await submit.isDisabled())
      await page.waitForTimeout(1600)
      assert.equal(state.createCalls, 1, "must not automatically resend an unknown submission")
      await page.getByRole("button", { name: "刷新连接", exact: true }).click()
      await page.locator(".recent-task").first().waitFor()
      assert(await submit.isDisabled(), "reconciled task is still running")
      assert.equal(state.createCalls, 1)
      await page.locator(".recent-task").first().click()
      await page.getByText("导航处理中", { exact: true }).first().waitFor()
      state.current = { ...state.current, state: "SUCCEEDED", worker_alive: false }
      state.events.push({ state: "SUCCEEDED", at_utc: "2026-10-16T06:00:10Z" })
      await page.waitForFunction(() => document.querySelector(".execution-header .el-tag")?.textContent.trim() === "任务完成")
      await page.getByRole("button", { name: "刷新连接", exact: true }).click()
      await page.waitForFunction(() => {
        const button = [...document.querySelectorAll("button")].find(item => item.textContent.trim() === "发起任务")
        return button && !button.disabled
      })
      assert.equal(state.createCalls, 1)
      await submit.click()
      await page.waitForFunction(() => document.querySelector(".task-id")?.textContent.includes("fixture-seco"))
      assert.equal(state.createCalls, 2, "only an explicit new click after reconciliation can create another task")
    })

    await scenario("GET polling backs off after failures and manual recovery is immediate", task({ task_id: "task-fixture-backoff", mode: "simulation", photo_available: false, photo_url: null, photo: null, analysis_state: "NO_CAMERA_PHOTO" }), {}, async (page, state) => {
      async function until(condition, timeout = 15000) {
        const deadline = performance.now() + timeout
        while (!condition()) {
          if (performance.now() >= deadline) throw new Error("Fixture polling timing condition timed out")
          await page.waitForTimeout(50)
        }
      }
      await page.locator(".execution-header .el-tag").waitFor()
      state.failTaskReads = true
      await until(() => state.taskReads.some(read => read.failed))
      const eventsAtFailure = state.eventReads.length
      await until(() => state.taskReads.filter(read => read.failed).length >= 3)
      const failures = state.taskReads.filter(read => read.failed)
      const firstRetryMs = failures[1].at - failures[0].at
      const secondRetryMs = failures[2].at - failures[1].at
      assert(firstRetryMs >= 1750 && firstRetryMs < 3250, `First GET failure retry should wait ~2s, observed ${firstRetryMs}ms`)
      assert(secondRetryMs >= 3600 && secondRetryMs < 5600, `Second GET failure retry should wait ~4s, observed ${secondRetryMs}ms`)
      assert.equal(state.eventReads.length, eventsAtFailure, "failed task reads do not fetch events")
      const retry = page.getByRole("button", { name: "重试查询", exact: true })
      await retry.waitFor()
      state.failTaskReads = false
      const manuallyClickedAt = performance.now()
      await retry.click()
      await until(() => state.taskReads.some(read => !read.failed && read.at > manuallyClickedAt))
      const recovered = state.taskReads.find(read => !read.failed && read.at > manuallyClickedAt)
      const manualRetryMs = recovered.at - manuallyClickedAt
      assert(manualRetryMs < 1500, `Manual read retry should bypass backoff, observed ${manualRetryMs}ms`)
      await until(() => state.taskReads.filter(read => !read.failed && read.at >= recovered.at).length >= 2)
      const recoveryReads = state.taskReads.filter(read => !read.failed && read.at >= recovered.at)
      const recoveredIntervalMs = recoveryReads[1].at - recoveryReads[0].at
      assert(recoveredIntervalMs >= 850 && recoveredIntervalMs < 1900, `Successful reads should return to ~1s cadence, observed ${recoveredIntervalMs}ms`)
      assert.equal(state.createCalls + state.analysisCalls + state.cancelCalls, 0, "read retry never resends POST actions")
      assert.equal(await page.locator(".connection-error").count(), 0)
      report.pollBackoffTimingsMs = { firstRetry: Math.round(firstRetryMs), secondRetry: Math.round(secondRetryMs), manualRecovery: Math.round(manualRetryMs), afterRecovery: Math.round(recoveredIntervalMs) }
    })

    assert.deepEqual(report.pageErrors, [])
    assert.deepEqual(report.unexpectedApiCalls, [])
    assert.deepEqual(report.forbiddenExternalRequests, [])
    report.result = "passed"
  } catch (error) {
    report.result = "failed"
    report.error = error.message
    process.exitCode = 1
  } finally {
    await browser?.close()
    fs.writeFileSync(path.join(artifactsDirectory, "frontend-ui-fixture-report.json"), JSON.stringify(report, null, 2))
    console.log(JSON.stringify(report, null, 2))
  }
}

void main().catch((error) => {
  console.error("UI fixture tests could not start. Install local browser tools as documented.", error.message)
  process.exitCode = 1
})
