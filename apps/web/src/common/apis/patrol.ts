import { request } from "@/http/axios"

export interface Capabilities {
  simulation_configured: boolean
  simulation_camera_photo: boolean
  simulation_video: boolean
  motion_enabled: boolean
  huawei_configured: boolean
  task_timeout_seconds: number
  single_task: boolean
  queue_enabled: boolean
  automatic_retry: boolean
  simulation_routes?: SimulationRoute[]
  execution_backend?: "local" | "remote"
  local_suspended?: boolean
  remote?: { online: boolean, ready: boolean, configured: boolean, device_id: string, last_seen_utc: string | null } | null
}
export interface SimulationRoute { id: string, description: string, scene: string, waypoints: { x: number, y: number, radius: number }[] }
export interface Point { id: string, description: string, goal_forward: number, goal_left: number }
export interface PointCatalog { reference: "initial_pose", example_configuration: boolean, points: Point[] }
export type TaskState = "PREPARING" | "NAVIGATING" | "PARKED" | "CAPTURING" | "STOPPING" | "SUCCEEDED" | "FAILED" | "CANCELLED" | "TIMED_OUT" | "REJECTED"
export interface TaskError { code?: string, message?: string, [key: string]: unknown }
export interface Task {
  task_id: string
  point_id: string
  point: { goal_forward: number, goal_left: number, [key: string]: unknown }
  point_reference: "initial_pose"
  mode: "simulation" | "motion"
  question: string
  state: TaskState
  created_at_utc: string
  updated_at_utc: string
  timeout_seconds: number
  error: TaskError | null
  stop_acknowledged: boolean | null
  cleanup_forced: boolean
  requires_operator_review: boolean
  worker_alive: boolean
  cancel_requested: boolean
  photo_available: boolean
  video_available: boolean
  photo_url: string | null
  video_url: string | null
  photo: { source: string, captured_at_utc: string, capture_time_basis: string, width: number, height: number, image_sha256: string } | null
  simulation_progress: { step?: number, position_xy?: number[], target_distance?: number, goal_reached?: boolean, collision?: boolean, fallen?: boolean, waypoint_index?: number, waypoints_total?: number, waypoints_reached?: number } | null
  simulation_summary: Record<string, unknown> | null
  simulation_route?: SimulationRoute | null
  execution_backend?: "local" | "remote"
  executor_online?: boolean | null
  remote_pending?: boolean
  remote_phase?: "WAITING" | "RUNNING" | "UPLOADING" | "DELIVERED" | null
  analysis_state: "NOT_REQUESTED" | "NO_CAMERA_PHOTO" | "NOT_CONFIGURED" | "RUNNING" | "SUCCEEDED" | "FAILED"
  analysis_error: TaskError | null
  answer: { answer: string, question: string, model: string, provider: string, request_id: string, answered_at_utc: string, image_sha256: string, task_id: string } | null
}
export interface TaskEvent { state: string, at_utc: string, error?: TaskError | null }
export interface TaskPage { data: Task[], count: number }

const terminal = new Set<TaskState>(["SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT", "REJECTED"])
export function isTaskRunning(task: Task | null | undefined): boolean {
  return !!task && (!terminal.has(task.state) || task.worker_alive || task.remote_pending || task.analysis_state === "RUNNING")
}
const states: Record<string, string> = { PREPARING: "准备中", NAVIGATING: "导航处理中", PARKED: "停车请求已应答", CAPTURING: "采集照片", STOPPING: "正在停止", SUCCEEDED: "任务完成", FAILED: "任务失败", CANCELLED: "已取消", TIMED_OUT: "任务超时", REJECTED: "任务被拒绝" }
const analyses: Record<string, string> = { NOT_REQUESTED: "未请求图片分析", NO_CAMERA_PHOTO: "本任务无相机照片", NOT_CONFIGURED: "视觉模型未配置", RUNNING: "正在分析图片", SUCCEEDED: "分析完成", FAILED: "分析失败" }
export function stateLabel(state: string): string {
  return states[state] || state
}
export function analysisLabel(state: string): string {
  return analyses[state] || state
}
export function formatTime(value: string | null | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("zh-CN", { hour12: false })
}
function taskPath(id: string) {
  return `/tasks/${encodeURIComponent(id)}`
}
export const api = {
  getCapabilities: () => request<Capabilities>({ url: "/capabilities" }),
  getPoints: () => request<PointCatalog>({ url: "/points" }),
  createTask: (data: { point_id?: string, simulation_route_id?: string, mode: "simulation" | "motion", question: string }) => request<Task>({ url: "/tasks", method: "post", data }),
  listTasks: (offset = 0, limit = 20) => request<TaskPage>({ url: "/tasks", params: { offset, limit } }),
  getTask: (id: string) => request<Task>({ url: taskPath(id) }),
  cancelTask: (id: string) => request<{ task_id: string, state: string, cancel_requested: boolean }>({ url: `${taskPath(id)}/cancel`, method: "post" }),
  getEvents: (id: string, after = 0) => request<{ data: TaskEvent[], next_offset: number }>({ url: `${taskPath(id)}/events`, params: { after } }),
  getResult: (id: string) => request<Record<string, unknown>>({ url: `${taskPath(id)}/result` }),
  analyzeTask: (id: string, question: string) => request<Task>({ url: `${taskPath(id)}/analysis`, method: "post", data: { question } }),
  fetchArtifact: (url: string, signal?: AbortSignal) => {
    // Never send a bearer token to a server-provided external URL or unrelated endpoint.
    if (!/^\/api\/v1\/tasks\/[\w-]+\/(photo|video)$/.test(url)) return Promise.reject(new Error("影像地址无效。"))
    return request<Blob>({ url, baseURL: "", responseType: "blob", signal, timeout: 30000 })
  }
}
