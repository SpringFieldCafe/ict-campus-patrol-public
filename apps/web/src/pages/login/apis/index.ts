import type { LoginRequestData, LoginResponseData } from "./type"
import { request } from "@/http/axios"

export function loginApi(data: LoginRequestData) {
  return request<LoginResponseData>({
    url: "/login/access-token",
    method: "post",
    data: new URLSearchParams({ username: data.username, password: data.password }),
    headers: { "Content-Type": "application/x-www-form-urlencoded" }
  })
}
