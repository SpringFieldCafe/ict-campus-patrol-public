<script lang="ts" setup>
import type { Task } from "@/common/apis/patrol"
import { ArrowRight, Camera, Clock, Document, Refresh, VideoCamera } from "@element-plus/icons-vue"
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { analysisLabel, api, formatTime, isTaskRunning, stateLabel } from "@/common/apis/patrol"

defineOptions({ name: "ObservationHistory" })

const router = useRouter()
const tasks = ref<Task[]>([])
const count = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const error = ref("")
const updatedAt = ref("")
let alive = true
let requestVersion = 0
const range = computed(() => tasks.value.length ? `${(page.value - 1) * pageSize + 1}–${(page.value - 1) * pageSize + tasks.value.length}` : "0")

function stateTone(state: string) {
  if (state === "SUCCEEDED") return "success"
  if (["FAILED", "TIMED_OUT", "REJECTED"].includes(state)) return "danger"
  if (["CANCELLED", "STOPPING"].includes(state)) return "warning"
  return "primary"
}

async function loadTasks() {
  const version = ++requestVersion
  loading.value = true
  error.value = ""
  try {
    const result = await api.listTasks((page.value - 1) * pageSize, pageSize)
    if (!alive || version !== requestVersion) return
    tasks.value = result.data
    count.value = result.count
    updatedAt.value = new Date().toISOString()
  } catch (failure) {
    if (alive && version === requestVersion) error.value = failure instanceof Error ? failure.message : "任务记录暂时无法读取，请重试。"
  } finally {
    if (alive && version === requestVersion) loading.value = false
  }
}

function openTask(task: Task) {
  void router.push({ path: "/console", query: { task: task.task_id } })
}

onMounted(() => void loadTasks())
onBeforeUnmount(() => {
  alive = false
  requestVersion += 1
})
</script>

<template>
  <div class="history-page">
    <header class="page-heading">
      <div>
        <div class="eyebrow">
          <span /> TASK ARCHIVE
        </div><h1>任务记录</h1><p>每次出发都有记录，每份现场证据都能追溯。</p>
      </div><el-button type="primary" :icon="ArrowRight" @click="router.push('/console')">
        前往工作台
      </el-button>
    </header>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="history-alert" />

    <section class="history-surface">
      <div class="table-heading">
        <div><span class="table-icon"><el-icon><Document /></el-icon></span><h2>全部观察任务</h2><span class="count-chip">{{ count }} 条</span></div><div>
          <span v-if="updatedAt" class="updated-time">更新于 {{ formatTime(updatedAt) }}</span><el-button :icon="Refresh" :loading="loading" @click="loadTasks">
            刷新记录
          </el-button>
        </div>
      </div>
      <div class="history-table-wrapper">
        <el-table v-loading="loading" :data="tasks" row-key="task_id" class="history-table" empty-text="尚未发起观察任务" :row-class-name="({ row }: { row: Task }) => isTaskRunning(row as Task) ? 'running-row' : ''">
          <el-table-column label="任务 / 观察点" min-width="220">
            <template #default="{ row }">
              <button type="button" class="task-link" @click="openTask(row as Task)">
                <strong>{{ row.point_id }}</strong><span>{{ row.task_id }}</span>
              </button>
            </template>
          </el-table-column>
          <el-table-column label="执行方式" width="120">
            <template #default="{ row }">
              <span class="mode-label" :class="{ simulation: row.mode === 'simulation' }"><el-icon><VideoCamera v-if="row.mode === 'simulation'" /><Camera v-else /></el-icon>{{ row.mode === 'simulation' ? '仿真' : '实机' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="任务状态" width="120">
            <template #default="{ row }">
              <el-tag :type="stateTone(row.state)" effect="light" round>
                {{ stateLabel(row.state) }}
              </el-tag><span v-if="row.requires_operator_review" class="review-note">需要人工检查</span><span v-else-if="row.cancel_requested && isTaskRunning(row as Task)" class="review-note">等待取消确认</span>
            </template>
          </el-table-column>
          <el-table-column label="现场记录" min-width="155">
            <template #default="{ row }">
              <div class="artifact-list">
                <span v-if="row.photo_available"><el-icon><Camera /></el-icon>相机照片</span><span v-if="row.video_available"><el-icon><VideoCamera /></el-icon>仿真录像</span><span v-if="!row.photo_available && !row.video_available" class="no-artifact">{{ isTaskRunning(row as Task) ? '等待采集完成' : '无可用媒体' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="照片问答" min-width="140">
            <template #default="{ row }">
              <span class="analysis-state" :class="{ answered: Boolean(row.answer) }">{{ analysisLabel(row.analysis_state) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="175">
            <template #default="{ row }">
              <span class="created-time">{{ formatTime(row.created_at_utc) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="" width="95" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" class="detail-button" @click="openTask(row as Task)">
                查看详情<el-icon><ArrowRight /></el-icon>
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <div class="empty-history">
              <span><el-icon><Clock /></el-icon></span><h3>{{ error ? '任务记录暂时无法读取' : '这里将保存每一次现场观察' }}</h3><p>{{ error ? '请检查服务连接，然后刷新记录。' : '选择一个观察点，完成你的第一个任务。' }}</p><el-button v-if="!error" type="primary" plain @click="router.push('/console')">
                发起观察任务<el-icon><ArrowRight /></el-icon>
              </el-button>
            </div>
          </template>
        </el-table>
      </div>
      <div class="table-footer">
        <span>显示 {{ range }} 条，共 {{ count }} 条任务</span><el-pagination v-model:current-page="page" :page-size="pageSize" :total="count" layout="prev, pager, next" :disabled="loading" background hide-on-single-page @current-change="loadTasks" />
      </div>
    </section>
    <div class="archive-note">
      <el-icon><Document /></el-icon><p>历史任务只读取已保存的状态、媒体与回答。查看详情不会重新执行任务。</p>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.history-page {
  padding: 31px 32px;
  background: #f3f6f8;
  color: #172c3c;
  --el-color-primary: #14846d;
  --el-color-primary-light-9: #eff8f5;
  --el-color-primary-light-3: #429c89;
  --el-color-primary-dark-2: #106b58;
}
.page-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 27px;
  h1 {
    margin: 9px 0;
    font-size: 27px;
    font-weight: 650;
  }
  p {
    margin: 0;
    color: #8595a1;
    font-size: 13px;
    line-height: 1.7;
  }
  > .el-button {
    font-size: 12px;
    border-radius: 6px;
  }
}
.eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #658b7d;
  font-size: 10px;
  letter-spacing: 2px;
  font-weight: 600;
  > span {
    width: 20px;
    height: 2px;
    background: #228b70;
  }
}
.history-alert {
  margin-bottom: 18px;
}
.history-surface {
  border: 1px solid #e5ebee;
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 2px 7px #18394c03;
}
.table-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 21px 23px;
  border-bottom: 1px solid #edf1f3;
  > div {
    display: flex;
    align-items: center;
    gap: 11px;
  }
  h2 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }
  .el-button {
    font-size: 11px;
  }
}
.table-icon {
  display: grid;
  place-items: center;
  height: 29px;
  width: 29px;
  background: #f0f6f3;
  color: #6b9684;
  border-radius: 7px;
  font-size: 16px;
}
.count-chip {
  padding: 4px 8px;
  border-radius: 4px;
  background: #f1f5f6;
  color: #8d9ea8;
  font-size: 10px;
}
.updated-time {
  color: #a2afb7;
  font-size: 10px;
}
.history-table-wrapper {
  padding: 0 22px;
}
.history-table {
  --el-table-header-bg-color: #fff;
  --el-table-border-color: #edf1f3;
  --el-table-row-hover-bg-color: #f7faf8;
  --el-table-text-color: #6f8593;
  :deep(th.el-table__cell) {
    color: #94a2ac;
    font-size: 11px;
    font-weight: 500;
    height: 49px;
  }
  :deep(td.el-table__cell) {
    height: 83px;
    font-size: 12px;
  }
  :deep(.el-tag) {
    font-size: 10px;
    height: 22px;
    padding: 0 9px;
  }
  :deep(.el-tag--primary) {
    --el-tag-bg-color: #eef5fb;
    --el-tag-text-color: #5084ab;
    --el-tag-border-color: #e2edf7;
  }
}
.task-link {
  display: flex;
  flex-direction: column;
  gap: 7px;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 0;
  cursor: pointer;
  max-width: 100%;
  strong {
    color: #385c65;
    font-size: 12px;
    font-weight: 600;
  }
  span {
    color: #a2afb8;
    font-size: 9px;
    font-family: monospace;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  &:hover strong {
    color: #138369;
  }
}
.mode-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #7e929d;
  font-size: 11px;
  &.simulation {
    color: #778eaa;
  }
  .el-icon {
    font-size: 14px;
  }
}
.artifact-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  > span {
    display: flex;
    align-items: center;
    gap: 5px;
    color: #648c7c;
    font-size: 11px;
  }
  .no-artifact {
    font-size: 10px;
    color: #acb6be;
  }
}
.analysis-state {
  font-size: 11px;
  color: #a1adb6;
  &.answered {
    color: #66947d;
  }
}
.created-time {
  font-size: 10px;
  color: #91a0aa;
}
.review-note {
  display: block;
  color: #bd9b66;
  font-size: 9px;
  margin-top: 4px;
  line-height: 1.4;
}
.detail-button {
  font-size: 11px;
  .el-icon {
    margin-left: 3px;
  }
}
.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 27px;
  gap: 15px;
  > span {
    color: #a0adb7;
    font-size: 10px;
  }
  :deep(.el-pagination.is-background .el-pager li.is-active) {
    background: #21866e;
  }
  :deep(.el-pager li),
  :deep(.btn-prev),
  :deep(.btn-next) {
    font-size: 11px;
    min-width: 28px;
    height: 28px;
  }
}
.empty-history {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 350px;
  padding: 45px 25px;
  > span {
    width: 58px;
    height: 58px;
    display: grid;
    place-items: center;
    background: #f1f7f4;
    color: #98baab;
    border-radius: 15px;
    font-size: 27px;
  }
  h3 {
    font-size: 14px;
    color: #718f83;
    font-weight: 500;
    margin: 23px 0 5px;
    line-height: 1.6;
  }
  p {
    color: #a0afb6;
    font-size: 12px;
    margin: 0 0 22px;
    line-height: 1.8;
  }
  .el-button {
    font-size: 12px;
    .el-icon {
      margin-left: 8px;
    }
  }
}
.archive-note {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #a1afb8;
  font-size: 10px;
  padding: 16px 4px;
  .el-icon {
    font-size: 13px;
  }
  p {
    margin: 0;
    line-height: 1.8;
  }
}
@media (min-width: 1600px) {
  .history-page {
    padding: 36px 42px;
  }
}
@media (max-width: 1050px) {
  .updated-time {
    display: none;
  }
  .history-page {
    padding: 25px 22px;
  }
  .history-table-wrapper {
    padding: 0 12px;
  }
}
@media (max-width: 760px) {
  .history-page {
    padding: 21px 15px;
  }
  .page-heading {
    gap: 12px;
    align-items: flex-start;
    h1 {
      font-size: 23px;
    }
    p {
      font-size: 11px;
      max-width: 220px;
    }
    > .el-button {
      font-size: 10px;
      padding: 8px 10px;
      margin-top: 26px;
    }
  }
  .table-heading {
    padding: 17px 14px;
    gap: 8px;
    h2 {
      font-size: 12px;
    }
    > div {
      gap: 7px;
    }
    .el-button {
      font-size: 10px;
      padding: 8px;
    }
  }
  .count-chip {
    font-size: 9px;
  }
  .table-icon {
    display: none;
  }
  .table-footer {
    padding: 18px 16px;
    flex-wrap: wrap;
  }
}
</style>
