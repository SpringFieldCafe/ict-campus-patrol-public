<script lang="ts" setup>
import type { Capabilities, PointCatalog, Task, TaskEvent } from "@/common/apis/patrol"
import { ArrowRight, Camera, ChatDotRound, Check, Clock, Connection, Download, Location, Picture, Refresh, VideoCamera, VideoPlay, Warning } from "@element-plus/icons-vue"
import { ElMessage } from "element-plus"
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { analysisLabel, api, formatTime, isTaskRunning, stateLabel } from "@/common/apis/patrol"

defineOptions({ name: "ObservationConsole" })

const route = useRoute()
const router = useRouter()
const capabilities = ref<Capabilities | null>(null)
const catalog = ref<PointCatalog | null>(null)
const recentTasks = ref<Task[]>([])
const task = ref<Task | null>(null)
const events = ref<TaskEvent[]>([])
const pointId = ref("")
const simulationRouteId = ref("")
const mode = ref<"simulation" | "motion">("simulation")
const question = ref("")
const analysisQuestion = ref("")
const bootLoading = ref(false)
const submitBusy = ref(false)
const cancelBusy = ref(false)
const analysisBusy = ref(false)
const taskLoading = ref(false)
const statusLoading = ref(false)
const submissionUncertain = ref(false)
const bootError = ref("")
const taskError = ref("")
const actionError = ref("")
const mediaUrl = ref("")
const mediaError = ref("")
const mediaLoading = ref(false)
const lastUpdated = ref("")
let alive = true
let initialized = false
let viewVersion = 0
let eventsOffset = 0
let pollTimer: ReturnType<typeof setTimeout> | undefined
let pollCount = 0
let pollFailures = 0
let mediaVersion = 0
let mediaController: AbortController | undefined

const selectedPoint = computed(() => catalog.value?.points.find(point => point.id === pointId.value))
const selectedSimulationRoute = computed(() => mode.value === "simulation" ? capabilities.value?.simulation_routes?.find(item => item.id === simulationRouteId.value) : undefined)
const taskRunning = computed(() => Boolean(task.value && isTaskRunning(task.value)))
const activeTask = computed(() => recentTasks.value.find(value => isTaskRunning(value) || value.requires_operator_review))
const operationsBusy = computed(() => submitBusy.value || cancelBusy.value || analysisBusy.value)
const modeReady = computed(() => mode.value === "simulation" ? capabilities.value?.simulation_configured && (!capabilities.value.remote || capabilities.value.remote.ready) : capabilities.value?.motion_enabled)
const canSubmit = computed(() => Boolean((selectedSimulationRoute.value || ((!simulationRouteId.value || mode.value === "motion") && selectedPoint.value)) && modeReady.value && !operationsBusy.value && !submissionUncertain.value && !taskRunning.value && !activeTask.value))
const terminalStates = new Set(["SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT", "REJECTED"])
const canCancel = computed(() => Boolean(task.value && !terminalStates.has(task.value.state) && !task.value.cancel_requested))
const canAnalyze = computed(() => Boolean(task.value?.mode === "motion" && task.value.photo_available && task.value.state === "SUCCEEDED" && capabilities.value?.huawei_configured && !taskRunning.value && !activeTask.value && !operationsBusy.value && analysisQuestion.value.trim()))
const mediaEndpoint = computed(() => task.value?.mode === "simulation" ? task.value.video_url : task.value?.photo_url)
const isSimulation = computed(() => task.value?.mode === "simulation")
const taskShortId = computed(() => task.value?.task_id.replace(/^task-/, "").slice(0, 12) ?? "")
const stages = computed(() => task.value?.mode === "motion"
  ? [{ key: "PREPARING", title: "准备任务" }, { key: "NAVIGATING", title: "导航处理" }, { key: "PARKED", title: "停车请求应答" }, { key: "CAPTURING", title: "采集照片" }, { key: "SUCCEEDED", title: "任务完成" }]
  : [{ key: "PREPARING", title: "准备任务" }, { key: "NAVIGATING", title: "仿真导航" }, { key: "SUCCEEDED", title: "结果归档" }])
const stageIndex = computed(() => {
  if (!task.value) return -1
  const direct = stages.value.findIndex(stage => stage.key === task.value?.state)
  if (direct >= 0) return direct
  for (const event of [...events.value].reverse()) {
    const index = stages.value.findIndex(stage => stage.key === event.state)
    if (index >= 0) return index
  }
  return 0
})
const progressDistance = computed(() => {
  const value = task.value?.simulation_progress?.target_distance
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(2)} m` : "—"
})
const hasFailed = computed(() => Boolean(task.value && ["FAILED", "TIMED_OUT", "REJECTED"].includes(task.value.state)))
const connectionInterrupted = computed(() => Boolean(bootError.value || taskError.value || !capabilities.value))
const answerMatchesPhoto = computed(() => Boolean(task.value?.answer && task.value.photo?.image_sha256 && task.value.answer.task_id === task.value.task_id && task.value.answer.image_sha256 === task.value.photo.image_sha256))
const submitHelp = computed(() => {
  if (submissionUncertain.value) return "上次提交尚未确认，请刷新连接并核对最近任务，避免重复发起。"
  if (activeTask.value?.requires_operator_review) return "有任务需要人工检查，处理后才能发起新任务。"
  if (activeTask.value || taskRunning.value) return "当前任务仍在执行，请等待完成后再发起。"
  if (!capabilities.value) return "正在等待后端连接。"
  if (capabilities.value.local_suspended) return "远程演示已开启，请统一使用服务端工作台。"
  if (capabilities.value.remote && !capabilities.value.remote.online) return "执行端未在线，暂不能发起任务；仍可查看已有结果。"
  if (capabilities.value.remote && !capabilities.value.remote.ready) return "执行端正在处理任务、回传结果或等待准备。"
  if (!modeReady.value) return mode.value === "motion" ? "实机执行尚未开启。" : "仿真环境尚未配置。"
  return capabilities.value.remote ? `本地执行上限 ${capabilities.value.task_timeout_seconds} 秒 · 完成后回传录像` : `单任务执行 · 最长 ${capabilities.value.task_timeout_seconds} 秒 · 不自动重试`
})
const simulationStatus = computed(() => {
  const value = capabilities.value
  if (!value) return "等待连接"
  if (value.local_suspended) return "远程演示已占用"
  if (value.remote) return !value.remote.online ? "执行端离线" : !value.remote.configured ? "执行端待准备" : value.remote.ready ? "执行端已就绪" : "执行／回传中"
  return value.simulation_configured ? "环境已配置" : "等待配置"
})

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "请求未完成，请检查连接后重试。"
}

function stateTone(state: string) {
  if (state === "SUCCEEDED") return "success"
  if (["FAILED", "TIMED_OUT", "REJECTED"].includes(state)) return "danger"
  if (["CANCELLED", "STOPPING"].includes(state)) return "warning"
  return "primary"
}

function coordinate(value: number | undefined) {
  return typeof value === "number" ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}` : "—"
}

function stopPolling() {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = undefined
}

function isCurrent(version: number) {
  return alive && version === viewVersion
}

function rememberTask(value: Task) {
  const values = recentTasks.value.filter(item => item.task_id !== value.task_id)
  values.push(value)
  recentTasks.value = values.sort((a, b) => b.created_at_utc.localeCompare(a.created_at_utc)).slice(0, 5)
}

async function refreshEvents(id: string, version: number) {
  const response = await api.getEvents(id, eventsOffset)
  if (!isCurrent(version)) return
  events.value.push(...response.data)
  eventsOffset = response.next_offset
}

function schedulePoll(version: number) {
  stopPolling()
  if (!isCurrent(version) || !task.value) return
  const delay = Math.min(10000, 1000 * 2 ** Math.min(pollFailures, 4))
  pollTimer = setTimeout(() => void pollTask(version), delay)
}

async function pollTask(version: number) {
  if (!isCurrent(version) || !task.value) return
  statusLoading.value = true
  const id = task.value.task_id
  try {
    const value = await api.getTask(id)
    if (!isCurrent(version)) return
    task.value = value
    rememberTask(value)
    lastUpdated.value = new Date().toISOString()
    await refreshEvents(id, version)
    if (!isCurrent(version)) return
    pollCount += 1
    if (pollCount % 5 === 0) {
      const [recent, capability] = await Promise.allSettled([api.listTasks(0, 5), api.getCapabilities()])
      if (!isCurrent(version)) return
      if (recent.status === "fulfilled") recentTasks.value = recent.value.data
      if (capability.status === "fulfilled") capabilities.value = capability.value
    }
    taskError.value = ""
    pollFailures = 0
  } catch (error) {
    if (isCurrent(version)) {
      pollFailures += 1
      taskError.value = errorMessage(error)
    }
  } finally {
    if (isCurrent(version)) {
      statusLoading.value = false
      schedulePoll(version)
    }
  }
}

async function selectTask(id: string, initialTask?: Task) {
  const version = ++viewVersion
  stopPolling()
  taskLoading.value = true
  statusLoading.value = false
  taskError.value = ""
  actionError.value = ""
  task.value = initialTask ?? null
  if (initialTask) analysisQuestion.value = initialTask.question
  events.value = []
  eventsOffset = 0
  pollCount = 0
  pollFailures = 0
  try {
    const value = await api.getTask(id)
    if (!isCurrent(version)) return
    task.value = value
    analysisQuestion.value = value.answer?.question || value.question || ""
    rememberTask(value)
    lastUpdated.value = new Date().toISOString()
    await refreshEvents(id, version)
  } catch (error) {
    if (isCurrent(version)) taskError.value = errorMessage(error)
  } finally {
    if (isCurrent(version)) {
      taskLoading.value = false
      schedulePoll(version)
    }
  }
}

async function loadWorkspace() {
  if (bootLoading.value) return
  bootLoading.value = true
  bootError.value = ""
  const responses = await Promise.allSettled([api.getCapabilities(), api.getPoints(), api.listTasks(0, 5)])
  if (!alive) return
  const failures: string[] = []
  const [capabilityResponse, pointResponse, historyResponse] = responses
  if (capabilityResponse.status === "fulfilled") {
    capabilities.value = capabilityResponse.value
    if (!initialized) simulationRouteId.value = capabilities.value.simulation_routes?.[0]?.id ?? ""
  } else {
    failures.push(errorMessage(capabilityResponse.reason))
  }
  if (pointResponse.status === "fulfilled") {
    catalog.value = pointResponse.value
    if (!catalog.value.points.some(point => point.id === pointId.value)) pointId.value = catalog.value.points[0]?.id ?? ""
  } else {
    failures.push(errorMessage(pointResponse.reason))
  }
  if (historyResponse.status === "fulfilled") {
    recentTasks.value = historyResponse.value.data
    submissionUncertain.value = false
  } else {
    failures.push(errorMessage(historyResponse.reason))
  }
  bootError.value = [...new Set(failures)].join("；")
  bootLoading.value = false
  if (!initialized) {
    initialized = true
    const selected = typeof route.query.task === "string" ? route.query.task : recentTasks.value[0]?.task_id
    if (selected) await selectTask(selected)
  }
}

async function retryStatus() {
  if (taskLoading.value || statusLoading.value) return
  if (task.value) {
    stopPolling()
    await pollTask(++viewVersion)
  } else if (typeof route.query.task === "string") {
    await selectTask(route.query.task)
  } else {
    await loadWorkspace()
    if (recentTasks.value[0]) await selectTask(recentTasks.value[0].task_id)
  }
}

async function openTask(id: string) {
  if (id === task.value?.task_id) return
  await router.replace({ path: "/console", query: { task: id } })
}

async function submitTask() {
  if (!canSubmit.value) return
  submitBusy.value = true
  actionError.value = ""
  try {
    const target = selectedSimulationRoute.value ? { simulation_route_id: selectedSimulationRoute.value.id } : { point_id: pointId.value }
    const created = await api.createTask({ ...target, mode: mode.value, question: mode.value === "motion" ? question.value.trim() : "" })
    if (!alive) return
    rememberTask(created)
    await selectTask(created.task_id, created)
    await router.replace({ path: "/console", query: { task: created.task_id } })
    ElMessage.success("任务已提交，可以在右侧查看执行进度。")
  } catch (error) {
    if (alive) {
      submissionUncertain.value = true
      actionError.value = `${errorMessage(error)} 请刷新连接并核对最近任务，确认本次提交结果。`
    }
  } finally {
    submitBusy.value = false
  }
}

async function cancelTask() {
  if (!canCancel.value || operationsBusy.value || !task.value) return
  const id = task.value.task_id
  const version = ++viewVersion
  stopPolling()
  statusLoading.value = false
  cancelBusy.value = true
  actionError.value = ""
  try {
    const response = await api.cancelTask(id)
    if (!isCurrent(version) || task.value?.task_id !== id) return
    if (response.cancel_requested) {
      task.value.cancel_requested = true
      ElMessage.info("取消请求已提交，正在等待执行端确认。")
    } else {
      ElMessage.info("任务已经结束，请查看最新状态。")
    }
  } catch (error) {
    if (isCurrent(version) && task.value?.task_id === id) actionError.value = errorMessage(error)
  } finally {
    cancelBusy.value = false
    if (isCurrent(version)) schedulePoll(version)
  }
}

async function analyzePhoto() {
  if (!canAnalyze.value || !task.value) return
  const id = task.value.task_id
  const version = ++viewVersion
  stopPolling()
  statusLoading.value = false
  analysisBusy.value = true
  actionError.value = ""
  try {
    const value = await api.analyzeTask(id, analysisQuestion.value.trim())
    if (!isCurrent(version) || task.value?.task_id !== id) return
    task.value = value
    rememberTask(value)
    ElMessage.success("图片问题已提交。")
  } catch (error) {
    if (isCurrent(version) && task.value?.task_id === id) actionError.value = errorMessage(error)
  } finally {
    analysisBusy.value = false
    if (isCurrent(version)) schedulePoll(version)
  }
}

function releaseMedia() {
  mediaVersion += 1
  mediaController?.abort()
  mediaController = undefined
  if (mediaUrl.value) URL.revokeObjectURL(mediaUrl.value)
  mediaUrl.value = ""
  mediaError.value = ""
  mediaLoading.value = false
}

async function loadMedia() {
  releaseMedia()
  const endpoint = mediaEndpoint.value
  if (!endpoint) return
  const version = mediaVersion
  mediaController = new AbortController()
  mediaLoading.value = true
  try {
    const blob = await api.fetchArtifact(endpoint, mediaController.signal)
    if (!alive || version !== mediaVersion) return
    mediaUrl.value = URL.createObjectURL(blob)
  } catch (error) {
    if (alive && version === mediaVersion) mediaError.value = errorMessage(error)
  } finally {
    if (alive && version === mediaVersion) mediaLoading.value = false
  }
}

function handleMediaError(event: Event) {
  const element = event.target
  if ((element instanceof HTMLVideoElement || element instanceof HTMLImageElement) && element.src !== mediaUrl.value) return
  mediaError.value = isSimulation.value
    ? "浏览器无法播放这份录像。可以重新读取，或下载原始录像查看。"
    : "浏览器无法显示这张照片。可以重新读取，或下载原图查看。"
}

watch(mediaEndpoint, () => void loadMedia())
watch(() => route.query.task, (id) => {
  if (initialized && typeof id === "string" && id !== task.value?.task_id) void selectTask(id)
})
onMounted(() => void loadWorkspace())
onBeforeUnmount(() => {
  alive = false
  viewVersion += 1
  stopPolling()
  releaseMedia()
})
</script>

<template>
  <div class="observation-console">
    <header class="page-heading">
      <div>
        <div class="eyebrow">
          <span class="eyebrow-line" /> FIELD OBSERVATION
        </div>
        <h1>现场观察工作台</h1>
        <p>下达一个任务，让机器狗替你到现场看一看。</p>
      </div>
      <div class="heading-actions">
        <span class="connection-label" :class="{ offline: connectionInterrupted }"><span class="status-dot" />{{ bootLoading ? "正在连接服务" : !capabilities ? "任务服务未连接" : connectionInterrupted ? "服务更新中断" : "任务服务已连接" }}</span>
        <el-button :icon="Refresh" :loading="bootLoading" @click="loadWorkspace">
          刷新连接
        </el-button>
      </div>
    </header>

    <el-alert v-if="bootError" :title="bootError" type="error" show-icon :closable="false" class="page-alert" />
    <el-alert v-if="capabilities?.local_suspended" title="远程演示已开启，本地暂停接新任务；请使用统一的服务端工作台。" type="info" show-icon :closable="false" class="page-alert" />
    <el-alert v-if="capabilities?.remote && !capabilities.remote.online" title="执行端离线：可以查看已有记录，暂不能发起新任务。" type="info" show-icon :closable="false" class="page-alert" />

    <div class="capability-strip">
      <div class="capability-item">
        <span class="capability-icon"><el-icon><VideoCamera /></el-icon></span>
        <div><span>{{ capabilities?.remote ? '远程 MuJoCo 仿真' : 'MuJoCo 仿真' }}</span><strong>{{ simulationStatus }}</strong></div>
        <span class="mini-dot" :class="{ ready: capabilities?.simulation_configured }" />
      </div>
      <div class="capability-item">
        <span class="capability-icon"><el-icon><Connection /></el-icon></span>
        <div><span>机器狗实机</span><strong>{{ capabilities?.motion_enabled ? "执行已开启" : "执行未开启" }}</strong></div>
        <span class="small-status">{{ capabilities?.motion_enabled ? "已开启" : "待接入" }}</span>
      </div>
      <div class="capability-item">
        <span class="capability-icon"><el-icon><ChatDotRound /></el-icon></span>
        <div><span>华为云图片问答</span><strong>{{ capabilities?.huawei_configured ? "模型已配置" : "等待模型开通" }}</strong></div>
        <span class="small-status" :class="{ configured: capabilities?.huawei_configured }">{{ capabilities?.huawei_configured ? "已配置" : "待配置" }}</span>
      </div>
    </div>

    <main class="workspace-grid">
      <aside class="task-sidebar">
        <section class="surface task-form">
          <div class="section-heading">
            <h2>发起观察任务</h2><span class="section-number">01</span>
          </div>
          <p class="section-description">
            选择预设观察点与执行方式。
          </p>

          <el-form label-position="top" @submit.prevent="submitTask">
            <el-form-item label="执行方式">
              <div class="mode-picker" role="group" aria-label="执行方式">
                <button type="button" class="mode-option" :class="{ selected: mode === 'simulation' }" :aria-pressed="mode === 'simulation'" :disabled="operationsBusy" @click="mode = 'simulation'">
                  <el-icon><VideoCamera /></el-icon><span>仿真执行</span><el-icon v-if="mode === 'simulation'" class="mode-check">
                    <Check />
                  </el-icon>
                </button>
                <button type="button" class="mode-option" :class="{ selected: mode === 'motion' }" :aria-pressed="mode === 'motion'" :disabled="!capabilities?.motion_enabled || operationsBusy" @click="mode = 'motion'">
                  <el-icon><Connection /></el-icon><span>实机执行</span><span v-if="!capabilities?.motion_enabled" class="mode-pending">未开启</span>
                </button>
              </div>
            </el-form-item>

            <el-form-item v-if="mode === 'simulation' && capabilities?.simulation_routes?.length" label="仿真路线">
              <el-select v-model="simulationRouteId" :disabled="operationsBusy" class="full-width" size="large" aria-label="仿真路线">
                <el-option v-if="capabilities?.execution_backend !== 'remote'" label="单个观察点" value="" />
                <el-option v-for="item in capabilities.simulation_routes" :key="item.id" :label="`${item.id} · ${item.waypoints.length} 个 checkpoint`" :value="item.id" />
              </el-select>
            </el-form-item>

            <div v-if="selectedSimulationRoute" class="point-card">
              <div class="point-card-title">
                <strong>{{ selectedSimulationRoute.id }}</strong><span>顺序导航</span>
              </div>
              <p>{{ selectedSimulationRoute.description }}</p>
              <p v-for="(checkpoint, index) in selectedSimulationRoute.waypoints" :key="index">
                CP{{ index + 1 }}：前向 {{ coordinate(checkpoint.x) }} m，左向 {{ coordinate(checkpoint.y) }} m；到点半径 {{ checkpoint.radius }} m
              </p>
              <small>到达当前 checkpoint 后自动切换下一点，最后一点完成后结束。</small>
            </div>

            <el-form-item v-if="!selectedSimulationRoute" label="目标观察点">
              <el-select v-model="pointId" placeholder="选择观察点" :disabled="!catalog?.points.length || operationsBusy" class="full-width" size="large" aria-label="目标观察点">
                <el-option v-for="point in catalog?.points ?? []" :key="point.id" :label="point.id" :value="point.id">
                  <span>{{ point.id }}</span><span class="point-option-description">{{ point.description }}</span>
                </el-option>
              </el-select>
            </el-form-item>

            <div v-if="selectedPoint && !selectedSimulationRoute" class="point-card">
              <div class="point-card-title">
                <span class="location-icon"><el-icon><Location /></el-icon></span><strong>{{ selectedPoint.id }}</strong><span>预设观察点</span>
              </div>
              <p v-if="selectedPoint.description">
                {{ selectedPoint.description }}
              </p>
              <div class="point-coordinates">
                <span>前向 <b>{{ coordinate(selectedPoint.goal_forward) }} m</b></span><span>左向 <b>{{ coordinate(selectedPoint.goal_left) }} m</b></span>
              </div>
              <small>相对每次任务启动时的位置与朝向。</small>
              <small v-if="catalog?.example_configuration" class="example-note">当前为示例点位，请在实际场地确认后使用。</small>
            </div>
            <div v-else-if="!selectedSimulationRoute && !bootLoading" class="form-note">
              尚无可用观察点，请先配置点位。
            </div>

            <el-form-item label="想了解的现场情况" class="question-form-item">
              <el-input v-model="question" type="textarea" :rows="3" :maxlength="2000" :disabled="mode === 'simulation' || operationsBusy" :placeholder="mode === 'simulation' ? '仿真仅展示导航状态与录像' : '例如：观察点附近有什么？通道是否畅通？'" resize="none" aria-label="现场问题" />
              <span class="field-help">{{ mode === 'simulation' ? "图片问答需等待真实相机照片。" : "选填。问题只用于照片分析，不改变导航目标。" }}</span>
            </el-form-item>

            <el-button type="primary" size="large" class="submit-button" :disabled="!canSubmit" :loading="submitBusy" native-type="submit">
              <el-icon v-if="!submitBusy">
                <VideoPlay />
              </el-icon><span>发起任务</span><el-icon v-if="!submitBusy" class="submit-arrow">
                <ArrowRight />
              </el-icon>
            </el-button>
            <p class="submit-help">
              {{ submitHelp }}
            </p>
          </el-form>
        </section>

        <section class="surface recent-section">
          <div class="section-heading">
            <h2>最近任务</h2><router-link to="/history" class="text-link">
              全部记录 <el-icon><ArrowRight /></el-icon>
            </router-link>
          </div>
          <div v-if="!recentTasks.length" class="small-empty">
            <el-icon><Clock /></el-icon><span>提交后，任务会保存在这里</span>
          </div>
          <button v-for="item in recentTasks.slice(0, 4)" :key="item.task_id" type="button" class="recent-task" :class="{ selected: item.task_id === task?.task_id }" @click="openTask(item.task_id)">
            <span class="recent-point"><el-icon><Location /></el-icon></span><span class="recent-copy"><strong>{{ item.point_id }} <small>{{ item.mode === 'simulation' ? '仿真' : '实机' }}</small></strong><span>{{ formatTime(item.created_at_utc) }}</span></span><span class="state-text" :class="stateTone(item.state)">{{ stateLabel(item.state) }}</span>
          </button>
        </section>
      </aside>

      <div class="observation-main">
        <el-alert v-if="actionError" :title="actionError" type="error" show-icon :closable="false" />
        <div v-if="taskError" class="connection-error" role="alert">
          <el-icon><Warning /></el-icon><span>状态更新暂时中断：{{ taskError }}<small v-if="task">当前保留上次取得的任务信息。</small></span><el-button size="small" :icon="Refresh" :loading="statusLoading" @click="retryStatus">
            重试查询
          </el-button>
        </div>

        <section class="surface observation-panel" v-loading="taskLoading" element-loading-text="正在读取任务">
          <div class="observation-header">
            <div class="section-heading">
              <h2>{{ task ? isSimulation ? '仿真现场录像' : '现场相机照片' : '现场观察' }}</h2><span v-if="task" class="media-mode">{{ isSimulation ? 'SIMULATION' : 'CAMERA' }}</span>
            </div>
            <a v-if="mediaUrl" :href="mediaUrl" :download="`${task?.task_id}.${isSimulation ? 'mp4' : 'jpg'}`" class="text-link"><el-icon><Download /></el-icon>下载{{ isSimulation ? '录像' : '照片' }}</a>
          </div>

          <div class="media-stage" :class="{ 'has-media': mediaUrl }" v-loading="mediaLoading" element-loading-text="正在读取任务媒体">
            <video v-if="mediaUrl && isSimulation && !mediaError" :key="mediaUrl" :src="mediaUrl" controls preload="metadata" playsinline class="observation-video" aria-label="MuJoCo 仿真场景录像" @error="handleMediaError" />
            <el-image v-else-if="mediaUrl && !mediaError" :src="mediaUrl" :preview-src-list="[mediaUrl]" fit="contain" class="observation-photo" preview-teleported hide-on-click-modal @error="handleMediaError">
              <template #error>
                <span class="image-error">照片无法显示，请重新读取。</span>
              </template>
            </el-image>
            <div v-else class="media-placeholder">
              <div class="viewfinder">
                <span /><span /><span /><span /><el-icon><component :is="task ? isSimulation ? VideoCamera : Camera : Picture" /></el-icon>
              </div>
              <template v-if="mediaError">
                <h3>媒体暂时无法读取</h3><p>{{ mediaError }}</p><el-button :icon="Refresh" plain @click="loadMedia">
                  重新读取
                </el-button>
              </template>
              <template v-else-if="!task">
                <h3>等待第一份现场记录</h3><p>在左侧选择观察点并发起任务。<br>执行完成后，在这里查看{{ mode === 'simulation' ? '仿真录像' : '现场照片' }}。</p>
              </template>
              <template v-else-if="taskRunning">
                <h3>{{ task.cancel_requested ? '正在等待取消确认' : stateLabel(task.state) }}</h3><p>{{ isSimulation ? '仿真运行中，录像将在执行结束后显示。' : '机器狗到点停车后，将采集并回传一张现场照片。' }}</p>
              </template>
              <template v-else>
                <h3>{{ isSimulation ? '本次任务没有可用录像' : '本次任务没有可用相机照片' }}</h3><p>{{ hasFailed ? '请查看下方任务记录，确认原因后再手动发起任务。' : '任务状态已保留，可在执行记录中查看详情。' }}</p>
              </template>
            </div>
            <div class="media-corner-label">
              <span class="status-dot" />{{ task ? isSimulation ? 'MuJoCo 场景视角 · 非相机照片' : '任务关联的相机原图' : 'OBSERVATION FEED' }}
            </div>
          </div>

          <div class="media-caption">
            <div><el-icon><Location /></el-icon><strong>{{ task?.point_id ?? '未选择任务' }}</strong><span v-if="task" class="caption-divider" /><span v-if="task" class="task-id">{{ taskShortId }}</span></div><span v-if="task?.photo">{{ task.photo.width }} × {{ task.photo.height }} · {{ formatTime(task.photo.captured_at_utc) }}</span><span v-else>{{ task ? formatTime(task.created_at_utc) : '现场证据将与任务编号一同保存' }}</span>
          </div>
        </section>

        <section v-if="task" class="surface execution-panel">
          <el-alert v-if="task.remote_pending && task.executor_online === false" title="执行端连接中断，当前任务结果待确认；恢复连接后核对同一任务，不会自动重跑。" type="warning" show-icon :closable="false" class="task-detail-alert" />
          <el-alert v-else-if="task.remote_phase === 'UPLOADING'" title="仿真执行已结束，正在回传结果和录像。" type="info" show-icon :closable="false" class="task-detail-alert" />
          <div class="execution-header">
            <div class="section-heading">
              <h2>任务执行</h2><el-tag :type="stateTone(task.state)" effect="light" round>
                {{ stateLabel(task.state) }}
              </el-tag>
            </div><el-button v-if="canCancel" size="small" :loading="cancelBusy" :disabled="operationsBusy" @click="cancelTask">
              请求取消
            </el-button><span v-else-if="task.cancel_requested && taskRunning" class="cancel-pending">取消已请求，等待确认</span><span v-else class="last-update"><el-icon><Clock /></el-icon>{{ lastUpdated ? `更新于 ${formatTime(lastUpdated)}` : '' }}</span>
          </div>
          <div class="stage-track" :class="{ 'five-stages': stages.length === 5 }">
            <div v-for="(stage, index) in stages" :key="stage.key" class="stage-item" :class="{ done: index < stageIndex || task.state === 'SUCCEEDED', current: index === stageIndex && task.state !== 'SUCCEEDED', failed: index === stageIndex && hasFailed }">
              <span class="stage-marker"><el-icon v-if="index < stageIndex || task.state === 'SUCCEEDED'"><Check /></el-icon><span v-else>{{ String(index + 1).padStart(2, '0') }}</span></span><span>{{ stage.title }}</span>
            </div>
          </div>
          <div v-if="task.mode === 'simulation' && task.simulation_progress" class="progress-facts">
            <span v-if="task.simulation_progress.waypoints_total">Checkpoint <strong>{{ task.simulation_progress.waypoints_reached ?? 0 }} / {{ task.simulation_progress.waypoints_total }}</strong></span>
            <span>距目标 <strong>{{ progressDistance }}</strong></span><span v-if="typeof task.simulation_progress.step === 'number'">仿真步数 <strong>{{ task.simulation_progress.step }}</strong></span><span v-if="task.simulation_summary?.goal_reached === true" class="goal-reached"><el-icon><Check /></el-icon>已到达目标</span>
          </div>
          <el-alert v-if="task.error" :title="`${task.error.code ?? 'TASK_ERROR'} · ${task.error.message ?? stateLabel(task.state)}`" :type="task.state === 'CANCELLED' ? 'info' : 'error'" :closable="false" show-icon class="task-detail-alert" />
          <el-alert v-if="task.requires_operator_review" title="此任务需要人工检查执行端，确认处置完成后再发起新任务。" type="warning" :closable="false" show-icon class="task-detail-alert" />
          <div class="execution-events">
            <span class="record-label">执行记录</span><div v-if="!events.length" class="event-empty">
              暂未取得阶段记录
            </div><div v-for="(event, index) in events" :key="`${event.at_utc}-${index}`" class="event-row">
              <span class="event-dot" :class="{ latest: index === events.length - 1 }" /><time>{{ formatTime(event.at_utc) }}</time><span>{{ stateLabel(event.state) }}</span><small v-if="event.error">{{ event.error.code }}</small>
            </div>
          </div>
        </section>

        <section class="surface analysis-panel">
          <div class="section-heading">
            <h2><el-icon><ChatDotRound /></el-icon>照片与回答</h2><el-tag size="small" :type="task?.analysis_state === 'SUCCEEDED' ? 'success' : 'info'" effect="plain">
              {{ task ? analysisLabel(task.analysis_state) : '等待相机照片' }}
            </el-tag>
          </div>
          <div v-if="task?.answer && answerMatchesPhoto" class="answer-content">
            <div class="answer-question">
              <span>现场问题</span><p>{{ task.answer.question }}</p>
            </div><div class="answer-text">
              {{ task.answer.answer }}
            </div><div class="answer-meta">
              <span>华为云 · {{ task.answer.model }}</span><span>{{ formatTime(task.answer.answered_at_utc) }}</span><span class="evidence-check"><el-icon><Check /></el-icon>回答已关联当前照片</span>
            </div>
          </div>
          <el-alert v-else-if="task?.answer" title="回答与当前照片的关联校验未通过，暂不展示回答。" type="warning" :closable="false" show-icon class="task-detail-alert" />
          <div v-else class="analysis-empty">
            <span class="analysis-empty-icon"><el-icon><Camera /></el-icon></span><div><h3>{{ task?.analysis_state === 'RUNNING' ? '正在分析现场照片' : task?.mode === 'simulation' ? '仿真展示状态与录像' : '取得相机照片后，即可询问现场' }}</h3><p>{{ task?.analysis_state === 'RUNNING' ? '任务照片已提交，正在等待模型回答。' : task?.mode === 'simulation' ? '当前仿真没有机器狗相机照片，暂不进行图片问答。' : capabilities?.huawei_configured ? '照片采集完成后，可基于原图提交问题。' : '华为云视觉模型尚未配置，照片采集与保存可独立进行。' }}</p></div>
          </div>
          <el-alert v-if="task?.analysis_error" :title="`${task.analysis_error.code ?? 'ANALYSIS_ERROR'} · ${task.analysis_error.message ?? '照片分析未完成'}`" type="error" show-icon :closable="false" class="task-detail-alert" />
          <div v-if="task?.mode === 'motion' && task.photo_available" class="analysis-input">
            <el-input v-model="analysisQuestion" placeholder="基于这张照片，你想了解什么？" :maxlength="2000" :disabled="operationsBusy || taskRunning || !capabilities?.huawei_configured" aria-label="照片分析问题" @keyup.enter="analyzePhoto" /><el-button type="primary" :loading="analysisBusy" :disabled="!canAnalyze" @click="analyzePhoto">
              {{ task.answer ? '再次提问' : '分析照片' }}<el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </section>
      </div>
    </main>
    <div class="workspace-footer">
      <span>Campus Patrol · 受限区域现场查看</span><router-link to="/project">
        了解项目与当前能力 <el-icon><ArrowRight /></el-icon>
      </router-link>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.observation-console {
  --work-ink: #172c3c;
  --work-muted: #7a8a99;
  --work-green: #14846d;
  --work-border: #e5ebee;
  padding: 29px 32px 20px;
  color: var(--work-ink);
  background: #f3f6f8;
  font-size: 13px;
  :deep(.el-button--primary) {
    --el-color-primary: #14846d;
    --el-color-primary-light-3: #429c89;
    --el-color-primary-light-5: #77b9ac;
    --el-color-primary-light-7: #b1d9d0;
    --el-color-primary-light-9: #eff8f5;
    --el-color-primary-dark-2: #106b58;
  }
  :deep(.el-input__wrapper),
  :deep(.el-select__wrapper),
  :deep(.el-textarea__inner) {
    box-shadow: 0 0 0 1px #dce4e9 inset;
  }
  :deep(.el-form-item__label) {
    color: #4c5e6d;
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 9px;
  }
  :deep(.el-tag--primary) {
    --el-tag-bg-color: #edf4fa;
    --el-tag-text-color: #397397;
    --el-tag-border-color: #dceaf3;
  }
}
.page-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  margin-bottom: 24px;
  h1 {
    margin: 8px 0;
    font-size: 27px;
    line-height: 1.35;
    letter-spacing: 0.2px;
    font-weight: 650;
  }
  p {
    margin: 0;
    color: #81909c;
    line-height: 1.6;
  }
}
.eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #558073;
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 2px;
}
.eyebrow-line {
  width: 20px;
  height: 2px;
  background: var(--work-green);
}
.heading-actions {
  display: flex;
  align-items: center;
  gap: 22px;
}
.connection-label {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: #5c7f73;
  &.offline {
    color: #9b8b64;
    .status-dot {
      background: #bd9f63;
    }
  }
}
.status-dot {
  display: inline-block;
  flex: 0 0 auto;
  height: 6px;
  width: 6px;
  border-radius: 50%;
  background: #2ba480;
}
.page-alert {
  margin-bottom: 16px;
}
.capability-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  background: white;
  border: 1px solid var(--work-border);
  border-radius: 10px;
  margin-bottom: 22px;
  box-shadow: 0 2px 7px #18394c03;
}
.capability-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 17px 22px;
  position: relative;
  & + &::before {
    content: "";
    position: absolute;
    left: 0;
    top: 18px;
    bottom: 18px;
    width: 1px;
    background: #edf0f3;
  }
  > div {
    display: flex;
    flex-direction: column;
    gap: 5px;
    > span {
      color: #8b98a3;
      font-size: 11px;
    }
    strong {
      font-size: 13px;
      font-weight: 550;
    }
  }
}
.capability-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  background: #f1f6f5;
  border-radius: 9px;
  color: #568775;
  font-size: 18px;
}
.mini-dot {
  width: 7px;
  height: 7px;
  margin-left: auto;
  background: #bec8ce;
  border-radius: 50%;
  &.ready {
    background: #25a37d;
    box-shadow: 0 0 0 4px #eef8f3;
  }
}
.small-status {
  margin-left: auto;
  padding: 4px 8px;
  border-radius: 4px;
  background: #f3f5f7;
  color: #8b97a2;
  font-size: 10px;
  &.configured {
    color: #23816a;
    background: #eff8f4;
  }
}
.workspace-grid {
  display: grid;
  grid-template-columns: 304px minmax(0, 1fr);
  gap: 22px;
  align-items: start;
}
.task-sidebar,
.observation-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}
.surface {
  background: #fff;
  border: 1px solid var(--work-border);
  border-radius: 10px;
  box-shadow: 0 2px 6px #213b4c03;
  overflow: hidden;
}
.section-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  h2 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 650;
    margin: 0;
    line-height: 1.4;
  }
}
.section-number {
  margin-left: auto;
  font-family: monospace;
  color: #c0ccd2;
  font-size: 15px;
  font-weight: 600;
}
.section-description {
  font-size: 12px;
  color: #8c99a4;
  margin: 9px 0 25px;
}
.task-form {
  padding: 23px 22px 17px;
}
.mode-picker {
  display: flex;
  width: 100%;
  border: 1px solid #e3e8ec;
  border-radius: 6px;
  padding: 3px;
  gap: 3px;
  background: #f7f9fa;
}
.mode-option {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  height: 37px;
  flex: 1;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  font-size: 12px;
  color: #748591;
  cursor: pointer;
  white-space: nowrap;
  &.selected {
    color: #197b66;
    background: #fff;
    border-color: #dce8e3;
    box-shadow: 0 1px 3px #173b2810;
  }
  &:disabled {
    color: #b0b8c0;
    cursor: not-allowed;
  }
  .mode-check {
    font-size: 11px;
  }
}
.mode-pending {
  font-size: 9px;
}
.full-width {
  width: 100%;
}
.point-option-description {
  float: right;
  padding-left: 20px;
  color: #99a3aa;
  font-size: 12px;
}
.point-card {
  border: 1px solid #e4ede8;
  border-radius: 6px;
  background: #f7faf8;
  padding: 13px 12px 11px;
  margin: -3px 0 22px;
  > p {
    font-size: 12px;
    color: #72867b;
    line-height: 1.6;
    margin: 10px 0;
  }
  small {
    font-size: 10px;
    color: #8ea096;
    display: block;
    line-height: 1.7;
  }
  .example-note {
    color: #a28c61;
    margin-top: 6px;
  }
}
.point-card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  strong {
    font-size: 12px;
    color: #376e59;
  }
  > span:last-child {
    font-size: 10px;
    color: #9aaa9f;
    margin-left: auto;
  }
}
.location-icon {
  color: #398266;
  display: flex;
  font-size: 14px;
}
.point-coordinates {
  display: flex;
  gap: 16px;
  margin: 11px 0 7px;
  font-size: 10px;
  color: #94a39b;
  b {
    font-family: monospace;
    margin-left: 5px;
    color: #5a7566;
    font-size: 11px;
    font-weight: 500;
  }
}
.form-note {
  margin: -4px 0 20px;
  color: #9b8965;
  font-size: 12px;
}
.field-help {
  display: block;
  font-size: 10px;
  color: #9ca7b1;
  line-height: 1.8;
  margin-top: 7px;
}
.question-form-item {
  margin-bottom: 24px;
}
.submit-button {
  width: 100%;
  height: 42px;
  border-radius: 6px;
  font-size: 13px;
  letter-spacing: 0.5px;
  :deep(> span) {
    width: 100%;
    display: flex;
    gap: 9px;
    align-items: center;
  }
  .submit-arrow {
    margin-left: auto;
  }
}
.submit-help {
  color: #9ca7b0;
  font-size: 10px;
  line-height: 1.8;
  margin: 11px 0 0;
  text-align: center;
}
.recent-section {
  padding: 20px 18px 7px;
  .section-heading {
    justify-content: space-between;
    padding: 0 4px 14px;
  }
  .text-link {
    font-size: 10px;
  }
}
.text-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: #719287;
  text-decoration: none;
  &:hover {
    color: #117c61;
  }
}
.recent-task {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 5px;
  border: 0;
  border-top: 1px solid #f0f3f5;
  background: transparent;
  text-align: left;
  cursor: pointer;
  border-radius: 4px;
  &.selected {
    background: #f4f8f6;
  }
  &:hover {
    background: #f3f7f8;
  }
}
.recent-point {
  height: 29px;
  width: 29px;
  display: grid;
  place-items: center;
  color: #82978d;
  background: #f0f5f2;
  border-radius: 7px;
}
.recent-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-width: 0;
  strong {
    font-size: 12px;
    font-weight: 550;
    small {
      font-size: 9px;
      margin-left: 4px;
      color: #98a59e;
      font-weight: 400;
    }
  }
  > span {
    font-size: 9px;
    color: #a0aab2;
  }
}
.state-text {
  font-size: 10px;
  &.success {
    color: #329373;
  }
  &.primary {
    color: #4f88b0;
  }
  &.danger {
    color: #cf6868;
  }
  &.warning {
    color: #b69155;
  }
}
.small-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px 0 29px;
  color: #a3afb7;
  font-size: 11px;
  .el-icon {
    font-size: 21px;
  }
}
.observation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 21px;
  min-height: 56px;
}
.media-mode {
  font-family: monospace;
  font-size: 9px;
  color: #889da6;
  background: #f2f6f7;
  border: 1px solid #eaf0f1;
  padding: 3px 6px;
  border-radius: 3px;
  letter-spacing: 0.8px;
}
.media-stage {
  background: #132932;
  min-height: 315px;
  height: clamp(315px, 29vw, 475px);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background-image: radial-gradient(#8ea9b610 1px, transparent 1px);
  background-size: 24px 24px;
  &.has-media {
    background: #0f1b21;
  }
  :deep(.el-loading-mask) {
    background: #11262de8;
  }
  :deep(.el-loading-text) {
    color: #a7c5be;
  }
  :deep(.el-loading-spinner .path) {
    stroke: #73b5a5;
  }
}
.media-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  color: #728b95;
  padding: 28px 35px 49px;
  h3 {
    font-size: 15px;
    font-weight: 500;
    margin: 24px 0 8px;
    color: #c4d3d9;
    letter-spacing: 0.4px;
  }
  p {
    font-size: 11px;
    line-height: 1.95;
    color: #7c959f;
    margin: 0;
    max-width: 430px;
    overflow-wrap: anywhere;
  }
  .el-button {
    margin-top: 14px;
    --el-button-text-color: #a6c9bf;
    --el-button-bg-color: transparent;
    --el-button-border-color: #46625d;
  }
}
.viewfinder {
  height: 74px;
  width: 100px;
  display: grid;
  place-items: center;
  position: relative;
  > .el-icon {
    font-size: 27px;
    color: #7a9b9d;
  }
  > span {
    position: absolute;
    height: 13px;
    width: 13px;
    border-color: #496c6c;
    border-style: solid;
  }
  > span:nth-child(1) {
    left: 0;
    top: 0;
    border-width: 1px 0 0 1px;
    border-top-left-radius: 3px;
  }
  > span:nth-child(2) {
    right: 0;
    top: 0;
    border-width: 1px 1px 0 0;
    border-top-right-radius: 3px;
  }
  > span:nth-child(3) {
    left: 0;
    bottom: 0;
    border-width: 0 0 1px 1px;
    border-bottom-left-radius: 3px;
  }
  > span:nth-child(4) {
    right: 0;
    bottom: 0;
    border-width: 0 1px 1px 0;
    border-bottom-right-radius: 3px;
  }
}
.media-corner-label {
  position: absolute;
  bottom: 14px;
  left: 18px;
  color: #91abae;
  font-size: 9px;
  display: flex;
  align-items: center;
  gap: 7px;
  letter-spacing: 0.5px;
  padding: 5px 8px;
  border-radius: 3px;
  background: #132932bf;
  pointer-events: none;
  .status-dot {
    height: 4px;
    width: 4px;
    background: #7ba99c;
  }
  .has-media & {
    bottom: auto;
    top: 13px;
  }
}
.observation-video,
.observation-photo {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.observation-photo {
  :deep(.el-image__inner) {
    width: 100%;
    height: 100%;
  }
}
.image-error {
  color: #afc0c6;
  font-size: 12px;
}
.media-caption {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 14px 20px;
  font-size: 10px;
  color: #9aa8b0;
  > div {
    display: flex;
    align-items: center;
    gap: 7px;
    .el-icon {
      color: #78988b;
      font-size: 14px;
    }
    strong {
      font-size: 11px;
      font-weight: 600;
      color: #5c736a;
    }
  }
}
.caption-divider {
  width: 1px;
  height: 11px;
  background: #e4e9eb;
  margin: 0 3px;
}
.task-id {
  font-family: monospace;
  color: #899aa4;
  font-size: 10px;
}
.execution-panel {
  padding: 20px 23px;
}
.execution-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  .el-tag {
    font-size: 10px;
    height: 21px;
    padding: 0 9px;
  }
}
.last-update {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #9facb4;
  font-size: 10px;
}
.cancel-pending {
  font-size: 10px;
  color: #b18b53;
}
.stage-track {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin: 27px 0 24px;
  &.five-stages {
    grid-template-columns: repeat(5, 1fr);
  }
}
.stage-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  font-size: 11px;
  color: #a6b2b9;
  position: relative;
  & + &::before {
    content: "";
    position: absolute;
    height: 1px;
    left: calc(-50% + 21px);
    right: calc(50% + 21px);
    top: 14px;
    background: #e5ecee;
  }
  &.done {
    color: #608b78;
    .stage-marker {
      color: #2b926e;
      background: #eaf6ee;
      border-color: #dcefe4;
    }
  }
  &.current {
    color: #3d7760;
    .stage-marker {
      color: white;
      background: #378c71;
      border-color: #378c71;
      box-shadow: 0 0 0 4px #eef7f2;
    }
  }
  &.failed {
    color: #c16f69;
    .stage-marker {
      background: #cf7b72;
      border-color: #cf7b72;
      box-shadow: 0 0 0 4px #fff2ef;
    }
  }
}
.stage-marker {
  height: 29px;
  width: 29px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #f7f9fa;
  border: 1px solid #e5ecee;
  font-size: 10px;
  font-family: monospace;
  .el-icon {
    font-size: 14px;
  }
}
.progress-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  background: #f6f9fa;
  border-radius: 5px;
  padding: 11px 14px;
  margin-bottom: 17px;
  font-size: 10px;
  color: #90a0aa;
  strong {
    font-family: monospace;
    color: #597488;
    font-size: 11px;
    font-weight: 500;
    margin-left: 7px;
  }
  .goal-reached {
    display: flex;
    gap: 5px;
    align-items: center;
    color: #4c9077;
    margin-left: auto;
  }
}
.execution-events {
  padding-top: 15px;
  border-top: 1px solid #eef2f4;
}
.record-label {
  display: block;
  font-size: 10px;
  color: #91a0aa;
  margin-bottom: 13px;
}
.event-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-height: 27px;
  font-size: 11px;
  > time {
    font-family: monospace;
    color: #9caab4;
    font-size: 10px;
    min-width: 143px;
  }
  > span:not(.event-dot) {
    color: #738894;
  }
  > small {
    font-size: 9px;
    color: #b1857b;
    overflow-wrap: anywhere;
  }
}
.event-dot {
  height: 5px;
  width: 5px;
  background: #d1dce1;
  border-radius: 50%;
  position: relative;
  top: -1px;
  &.latest {
    background: #72a28c;
  }
}
.event-empty {
  color: #acb6bd;
  font-size: 11px;
}
.task-detail-alert {
  margin: 12px 0;
  overflow-wrap: anywhere;
  :deep(.el-alert__title) {
    font-size: 11px;
    line-height: 1.8;
  }
}
.analysis-panel {
  padding: 20px 23px;
  > .section-heading {
    justify-content: space-between;
    h2 > .el-icon {
      color: #719888;
      font-size: 16px;
    }
    .el-tag {
      font-size: 10px;
    }
  }
}
.analysis-empty {
  display: flex;
  gap: 14px;
  align-items: center;
  margin: 23px 0 7px;
  h3 {
    font-size: 12px;
    color: #799088;
    font-weight: 500;
    margin: 0 0 7px;
  }
  p {
    color: #a1aeb6;
    font-size: 11px;
    line-height: 1.8;
    margin: 0;
  }
}
.analysis-empty-icon {
  height: 42px;
  width: 42px;
  flex: 0 0 42px;
  display: grid;
  place-items: center;
  background: #f3f7f5;
  border-radius: 10px;
  color: #abc0b4;
  font-size: 21px;
}
.answer-content {
  margin-top: 22px;
}
.answer-question {
  padding: 12px 15px;
  background: #f5f8f9;
  border-radius: 5px;
  > span {
    color: #94a3af;
    font-size: 10px;
  }
  p {
    color: #526d7b;
    font-size: 12px;
    line-height: 1.7;
    margin: 7px 0 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
}
.answer-text {
  margin: 18px 0;
  color: #415d6b;
  line-height: 1.95;
  font-size: 13px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.answer-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 9px;
  color: #a1afb7;
  padding-top: 12px;
  border-top: 1px solid #f0f3f5;
}
.evidence-check {
  margin-left: auto;
  display: flex;
  gap: 4px;
  align-items: center;
  color: #75a08c;
}
.analysis-input {
  display: flex;
  gap: 9px;
  margin-top: 20px;
  .el-button .el-icon {
    margin-left: 5px;
  }
}
.connection-error {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff8eb;
  border: 1px solid #f0e4cb;
  border-radius: 7px;
  padding: 12px 15px;
  color: #a1844c;
  font-size: 11px;
  > .el-icon {
    font-size: 17px;
    flex-shrink: 0;
  }
  > span {
    flex: 1;
    line-height: 1.7;
    overflow-wrap: anywhere;
  }
  small {
    display: block;
    font-size: 10px;
    color: #b6a175;
  }
}
.workspace-footer {
  margin-top: 23px;
  display: flex;
  justify-content: space-between;
  color: #a4b0b8;
  font-size: 10px;
  a {
    display: flex;
    gap: 4px;
    align-items: center;
    color: #94a79f;
    text-decoration: none;
  }
}
@media (min-width: 1600px) {
  .observation-console {
    padding-left: 42px;
    padding-right: 42px;
  }
  .workspace-grid {
    grid-template-columns: 325px minmax(0, 1fr);
    gap: 26px;
  }
}
@media (max-width: 1180px) {
  .observation-console {
    padding: 24px 22px 18px;
  }
  .workspace-grid {
    grid-template-columns: 278px minmax(0, 1fr);
    gap: 17px;
  }
  .task-form {
    padding: 20px 17px 16px;
  }
  .heading-actions {
    gap: 12px;
  }
  .connection-label {
    font-size: 10px;
  }
  .capability-item {
    padding: 15px;
    gap: 9px;
  }
  .capability-icon {
    width: 30px;
    height: 30px;
    font-size: 15px;
  }
  .small-status {
    font-size: 9px;
    padding: 3px 5px;
  }
  .last-update {
    max-width: 165px;
    text-align: right;
    line-height: 1.6;
  }
}
@media (max-width: 960px) {
  .page-heading {
    align-items: flex-start;
  }
  .heading-actions {
    flex-direction: column;
    align-items: flex-end;
    gap: 9px;
  }
  .capability-item {
    padding: 14px 12px;
    .capability-icon {
      display: none;
    }
    > div strong {
      font-size: 11px;
    }
  }
  .workspace-grid {
    grid-template-columns: 255px minmax(0, 1fr);
    gap: 15px;
  }
  .task-form {
    padding: 19px 14px 15px;
  }
  .section-heading h2 {
    font-size: 13px;
  }
  .mode-option {
    font-size: 11px;
    gap: 4px;
  }
  .mode-pending {
    display: none;
  }
  .observation-header,
  .media-caption {
    padding-left: 15px;
    padding-right: 15px;
  }
  .media-mode {
    font-size: 8px;
  }
  .media-caption {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }
  .execution-panel,
  .analysis-panel {
    padding: 18px 16px;
  }
  .last-update {
    display: none;
  }
  .event-row {
    gap: 7px;
    > time {
      min-width: 125px;
      font-size: 9px;
    }
  }
  .five-stages .stage-item {
    font-size: 9px;
  }
  .recent-copy > span {
    font-size: 8px;
  }
  .state-text {
    font-size: 9px;
  }
  .task-id {
    font-size: 9px;
  }
}
@media (max-width: 760px) {
  .observation-console {
    padding: 20px 15px 16px;
  }
  .page-heading {
    gap: 12px;
    h1 {
      font-size: 23px;
    }
    p {
      font-size: 11px;
    }
  }
  .connection-label {
    display: none;
  }
  .heading-actions > .el-button {
    font-size: 10px;
    padding: 8px;
  }
  .capability-strip {
    gap: 0;
  }
  .capability-item {
    gap: 5px;
    flex-wrap: wrap;
    padding: 12px 10px;
    > div {
      gap: 5px;
      > span {
        font-size: 9px;
      }
      > strong {
        font-size: 10px;
      }
    }
    .small-status {
      display: none;
    }
    .mini-dot {
      width: 5px;
      height: 5px;
    }
  }
  .workspace-grid {
    grid-template-columns: 1fr;
    gap: 19px;
  }
  .task-sidebar {
    display: contents;
  }
  .task-form {
    padding: 21px;
  }
  .recent-section {
    order: 3;
  }
  .observation-main {
    gap: 18px;
  }
  .media-stage {
    min-height: 275px;
    height: 60vw;
    max-height: 430px;
  }
  .section-heading h2 {
    font-size: 14px;
  }
  .mode-option {
    font-size: 12px;
  }
  .mode-pending {
    display: initial;
  }
  .media-caption {
    flex-direction: row;
    flex-wrap: wrap;
  }
  .workspace-footer {
    gap: 15px;
    font-size: 9px;
    line-height: 1.7;
  }
  .event-row > time {
    min-width: 135px;
    font-size: 10px;
  }
  .analysis-input {
    flex-direction: column;
  }
}
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
