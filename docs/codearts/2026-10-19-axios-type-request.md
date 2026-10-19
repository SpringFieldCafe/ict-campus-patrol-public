请让这次贡献进一步落实到一个实际源码兼容修复。请只返回一个 json 代码块，结构 {"old":"完整旧函数含注释", "new":"完整新函数含必要简短英文注释", "rationale":"中文解释"}。不要给多个方案、不改其他代码、不假称你已运行。

事实：你前一轮主笔依赖修复配置已应用，pnpm10.34.0独立fresh/frozen安装完成，22项测试通过；pnpm audit从63降到1，只剩braces无补丁。Axios1.18.1更新1.20.0后vue-tsc失败：
src/http/axios.ts(77,3): TS2322: Type Promise<AxiosResponseResult<T,T,any,any>> is not assignable to Promise<T>; T could be instantiated with unrelated type.

以下是已实际安装的axios1.20.0类型：
declare const axiosResponseDefault: unique symbol;
type AxiosResponseDefault = typeof axiosResponseDefault;
type AxiosResponseResult<T,R,D,P> = R extends AxiosResponseDefault ? AxiosResponse<T,D,{},P> : R;
request<T=any,R=AxiosResponseDefault,D=any,P=any>(config: AxiosRequestConfig<D,P>): Promise<AxiosResponseResult<T,R,D,P>>;

项目响应成功拦截器确实返回 response.data，不返回AxiosResponse包装；已有真实Axios实例+替身HTTP传输的测试，覆盖OAuth form、Bearer、直接JSON、Blob媒体、403退出/权限区别、拒绝媒体穿越、不重试POST。升级后这些22项均通过，运行时行为不用改变。本轮只需要维持原公开 request<T>(config): Promise<T> 契约，处理Axios新条件类型对任意T不收敛的类型边界。允许在这个已知“拦截器返回payload”的局部边界使用有依据的单处类型断言；禁止ts-ignore、any扩散、禁用vue-tsc或变更整个http层。不要为绕错降级回有漏洞Axios。需要把类型断言原因写成简短英文注释，让后来维护者知道来自拦截器与Axios1.20的条件类型；JSON输出需可解析。

当前完整文件：
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
  return instance.request<T, T>(config)
}

