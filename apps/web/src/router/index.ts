import type { RouteRecordRaw } from "vue-router"
import { createRouter } from "vue-router"
import { DASHBOARD_PATH, REDIRECT_PATH, routerConfig } from "@/router/config"
import { registerNavigationGuard } from "@/router/guard"

const Layouts = () => import("@/layouts/index.vue")
export const constantRoutes: RouteRecordRaw[] = [
  { path: "/login", component: () => import("@/pages/login/index.vue"), meta: { hidden: true } },
  {
    path: REDIRECT_PATH,
    component: Layouts,
    meta: { hidden: true },
    children: [{ path: ":path(.*)", component: () => import("@/pages/redirect/index.vue") }]
  },
  { path: "/", redirect: DASHBOARD_PATH, meta: { hidden: true } },
  {
    path: "/console",
    component: Layouts,
    children: [{ path: "", name: "Console", component: () => import("@/pages/console/index.vue"), meta: { title: "任务工作台", elIcon: "Monitor" } }]
  },
  {
    path: "/history",
    component: Layouts,
    children: [{ path: "", name: "History", component: () => import("@/pages/history/index.vue"), meta: { title: "任务记录", elIcon: "Clock" } }]
  },
  {
    path: "/project",
    component: Layouts,
    children: [{ path: "", name: "Project", component: () => import("@/pages/project/index.vue"), meta: { title: "项目说明", elIcon: "Document" } }]
  },
  { path: "/:pathMatch(.*)*", redirect: DASHBOARD_PATH, meta: { hidden: true } }
]
export const dynamicRoutes: RouteRecordRaw[] = []
export const router = createRouter({ history: routerConfig.history, routes: constantRoutes })
// All application routes are static; authentication is enforced by the guard and FastAPI.
export function resetRouter() {}
registerNavigationGuard(router)
