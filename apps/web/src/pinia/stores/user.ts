import { getCurrentUserApi } from "@@/apis/users"
import { setToken as _setToken, getToken, removeToken } from "@@/utils/local-storage"
import { pinia } from "@/pinia"
import { resetRouter, router } from "@/router"
import { useSettingsStore } from "./settings"
import { useTagsViewStore } from "./tags-view"

export const useUserStore = defineStore("user", () => {
  const token = ref<string>(getToken() || "")

  const roles = ref<string[]>([])

  const permissions = ref<string[]>([])

  const username = ref<string>("")

  const isGotUserInfo = ref<boolean>(false)

  const tagsViewStore = useTagsViewStore()

  const settingsStore = useSettingsStore()

  // 设置 Token
  const setToken = (value: string) => {
    _setToken(value)
    token.value = value
  }

  // 获取用户详情
  const getInfo = async () => {
    const data = await getCurrentUserApi()
    username.value = data.full_name || data.email
    roles.value = data.is_superuser ? ["admin"] : ["operator"]
    permissions.value = []
    // 防止路由守卫逻辑进入无限循环
    isGotUserInfo.value = true
  }

  // Retained for unused upstream demo components; switching identities requires real login.
  const changeUser = (_value: string) => logout()

  // 登出
  const logout = () => {
    resetToken()
    resetRouter()
    resetTagsView()
    // 重定向到登录页
    router.replace("/login")
  }

  // 重置 Token
  const resetToken = () => {
    removeToken()
    token.value = ""
    username.value = ""
    roles.value = []
    permissions.value = []
    isGotUserInfo.value = false
  }

  // 重置 Visited Views 和 Cached Views
  const resetTagsView = () => {
    if (!settingsStore.cacheTagsView) {
      tagsViewStore.delAllVisitedViews()
      tagsViewStore.delAllCachedViews()
    }
  }

  return { token, roles, permissions, username, isGotUserInfo, setToken, getInfo, changeUser, logout, resetToken }
})

/**
 * @description 在 SPA 应用中可用于在 pinia 实例被激活前使用 store
 * @description 在 SSR 应用中可用于在 setup 外使用 store
 */
export function useUserStoreOutside() {
  return useUserStore(pinia)
}
