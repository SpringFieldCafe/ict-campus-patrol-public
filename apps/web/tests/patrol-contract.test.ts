import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from "axios"
import axios, { AxiosError } from "axios"
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

const { logout } = vi.hoisted(() => ({ logout: vi.fn() }))
vi.mock("@/pinia/stores/user", () => ({ useUserStore: () => ({ logout }) }))
vi.mock("@@/utils/local-storage", () => ({ getToken: () => "test-session-token" }))

let reply: unknown
let status = 200
let captured: InternalAxiosRequestConfig | undefined
const transport = vi.fn<AxiosAdapter>(async (config) => {
  captured = config
  const response: AxiosResponse = { data: reply, status, statusText: "", headers: {}, config }
  if (status >= 400) throw new AxiosError("HTTP failure", undefined, config, undefined, response)
  return response
})
let api: (typeof import("@/common/apis/patrol"))["api"]
let loginApi: (typeof import("@/pages/login/apis"))["loginApi"]
let isTaskRunning: (typeof import("@/common/apis/patrol"))["isTaskRunning"]
beforeAll(async () => {
  // Keep Axios serialization and interceptors real; replace only HTTP transport.
  axios.defaults.adapter = transport
  ;({ api, isTaskRunning } = await import("@/common/apis/patrol"))
  ;({ loginApi } = await import("@/pages/login/apis"))
})
beforeEach(() => {
  reply = {}
  status = 200
  captured = undefined
  transport.mockClear()
  logout.mockClear()
})

describe("fastAPI integration contract", () => {
  it("accepts native OAuth tokens and preserves special characters in form credentials", async () => {
    reply = { access_token: "opaque-test-token", token_type: "bearer" }
    const value = await loginApi({ username: "demo+user@example.com", password: "test +&=字" })
    expect(value).toEqual(reply)
    const form = new URLSearchParams(captured?.data)
    expect(form.get("username")).toBe("demo+user@example.com")
    expect(form.get("password")).toBe("test +&=字")
    expect(captured?.headers["Content-Type"]).toContain("application/x-www-form-urlencoded")
  })
  it("reads raw FastAPI task pages with bearer authentication", async () => {
    reply = { data: [], count: 0 }
    expect(await api.listTasks(20, 20)).toEqual(reply)
    expect(captured?.headers.Authorization).toBe("Bearer test-session-token")
    expect(captured?.params).toEqual({ offset: 20, limit: 20 })
  })
  it("does not retry a rejected single-task submission", async () => {
    status = 409
    reply = { detail: { code: "BUSY", message: "busy" } }
    await expect(api.createTask({ point_id: "demo-a", mode: "simulation", question: "" })).rejects.toMatchObject({ status: 409, code: "BUSY" })
    expect(transport).toHaveBeenCalledTimes(1)
  })
  it("expires sessions for FastAPI's invalid-credentials 403", async () => {
    status = 403
    reply = { detail: "Could not validate credentials" }
    await expect(api.getCapabilities()).rejects.toMatchObject({ status: 403 })
    expect(logout).toHaveBeenCalledOnce()
  })
  it("keeps the session for an ordinary permission denial", async () => {
    status = 403
    reply = { detail: "Not enough privileges" }
    await expect(api.getPoints()).rejects.toMatchObject({ status: 403 })
    expect(logout).not.toHaveBeenCalled()
  })
  it("fetches same-origin task media without duplicating the API prefix", async () => {
    reply = new Blob(["test"], { type: "video/mp4" })
    expect(await api.fetchArtifact("/api/v1/tasks/task-test/video")).toBe(reply)
    expect(captured?.baseURL).toBe("")
    expect(captured?.url).toBe("/api/v1/tasks/task-test/video")
    expect(captured?.responseType).toBe("blob")
  })
  it("rejects external, traversal and unrelated media URLs before sending credentials", async () => {
    for (const url of ["https://other.example/video", "//other.example/video", "/api/v1/tasks/../video", "/api/v1/users/me", "/api/v1/tasks/task-test/video?token=secret"]) {
      await expect(api.fetchArtifact(url)).rejects.toThrow("影像地址无效")
    }
    expect(transport).not.toHaveBeenCalled()
  })
  it("holds task admission until the delivery worker and photo analysis finish", () => {
    const completed = { state: "SUCCEEDED", worker_alive: false, analysis_state: "NO_CAMERA_PHOTO" } as import("@/common/apis/patrol").Task
    expect(isTaskRunning(completed)).toBe(false)
    expect(isTaskRunning({ ...completed, worker_alive: true })).toBe(true)
    expect(isTaskRunning({ ...completed, analysis_state: "RUNNING" })).toBe(true)
    expect(isTaskRunning({ ...completed, remote_pending: true, remote_phase: "UPLOADING" })).toBe(true)
    expect(isTaskRunning({ ...completed, state: "STOPPING" })).toBe(true)
  })
})
