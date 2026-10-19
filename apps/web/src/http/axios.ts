import type { AxiosRequestConfig } from "axios"
import { getToken } from "@@/utils/local-storage"
import axios from "axios"
import { useUserStore } from "@/pinia/stores/user"

export class ApiError extends Error {
  constructor(message: string, public status?: number, public code?: string) {
    super(message)
    this.name = "ApiError"
  }
}

const messages: Record<string, string> = {
  BUSY: "已有任务在运行，请等待它结束后再发起。",
  MOTION_DISABLED: "实机运动尚未启用。",
  SIMULATION_NOT_CONFIGURED: "仿真环境尚未配置。",
  POINTS_NOT_CONFIGURED: "观察点尚未配置。",
  UNKNOWN_POINT: "找不到这个观察点，请刷新后重试。",
  PHOTO_NOT_READY: "这项任务暂时没有可用照片。",
  VIDEO_NOT_READY: "这项任务暂时没有可用录像。",
  HUAWEI_NOT_CONFIGURED: "华为视觉模型尚未配置。",
  TASK_NOT_FOUND: "找不到这项任务。",
  MODEL_TIMEOUT: "图片分析超时，请稍后检查任务结果。"
}

const instance = axios.create({
  baseURL: import.meta.env.VITE_BASE_URL || "/api/v1",
  timeout: 10000,
  withCredentials: false
})

instance.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

instance.interceptors.response.use(response => response.data, async (error) => {
  if (axios.isCancel(error)) return Promise.reject(error)
  const status = error.response?.status as number | undefined
  let payload = error.response?.data
  if (payload instanceof Blob) {
    try {
      payload = JSON.parse(await payload.text())
    } catch {
      payload = undefined
    }
  }
  const detail = payload?.detail
  const code = typeof detail === "object" && !Array.isArray(detail) ? detail?.code : undefined
  const expired = status === 401 || (status === 403 && typeof detail === "string" && /credentials/i.test(detail))
  if (expired && getToken()) useUserStore().logout()
  const message = expired
    ? "登录已失效，请重新登录。"
    : code && messages[code]
      ? messages[code]
      : status === 400 && typeof detail === "string"
        ? "登录失败，请检查邮箱和密码。"
        : status === 422
          ? "提交内容不符合要求，请检查后重试。"
          : typeof detail?.message === "string"
            ? detail.message
            : status === 403
              ? "当前账户没有访问权限。"
              : status === 404
                ? "请求的内容不存在。"
                : status && status >= 500
                  ? "后端暂时不可用，请稍后重试。"
                  : error.code === "ECONNABORTED"
                    ? "请求超时，请检查后端连接。"
                    : !status ? "连接后端失败，请检查服务是否启动。" : "请求失败，请稍后重试。"
  return Promise.reject(new ApiError(message, status, code))
})

/** FastAPI returns the payload directly, without the template's mock code/data envelope. */
export function request<T>(config: AxiosRequestConfig): Promise<T> {
  // The response interceptor returns data, while Axios 1.20 keeps a
  // conditional response type unresolved for generic T.
  return instance.request<T, T>(config) as Promise<T>
}
