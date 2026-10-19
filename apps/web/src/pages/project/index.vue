<script lang="ts" setup>
import type { Capabilities } from "@/common/apis/patrol"
import { ArrowRight, Camera, ChatDotRound, Check, Connection, Document, Location, Monitor, Refresh, VideoCamera } from "@element-plus/icons-vue"
import { onBeforeUnmount, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { api } from "@/common/apis/patrol"

defineOptions({ name: "ObservationProject" })

const router = useRouter()
const capabilities = ref<Capabilities | null>(null)
const loading = ref(false)
const error = ref("")
let alive = true

async function loadCapabilities() {
  if (loading.value) return
  loading.value = true
  error.value = ""
  try {
    const value = await api.getCapabilities()
    if (alive) capabilities.value = value
  } catch (failure) {
    if (alive) error.value = failure instanceof Error ? failure.message : "暂时无法读取服务状态。"
  } finally {
    if (alive) loading.value = false
  }
}

onMounted(() => void loadCapabilities())
onBeforeUnmount(() => {
  alive = false
})
</script>

<template>
  <div class="project-page">
    <section class="project-hero">
      <div class="hero-copy">
        <span class="hero-eyebrow"><span /> CAMPUS PATROL</span><h1>代人到现场，<br>让观察有依据。</h1><p>面向人员不便或无法进入的受限区域，<br>让机器狗自主前往预设观察点，回传现场照片与任务记录。</p><el-button type="primary" size="large" @click="router.push('/console')">
          打开观察工作台<el-icon><ArrowRight /></el-icon>
        </el-button><span class="project-caption">华为 ICT 大赛中国创新赛 · 赛题 1 项目</span>
      </div>
      <div class="hero-diagram" aria-label="任务流程：选择观察点，机器狗前往，回传现场记录">
        <div class="diagram-orbit orbit-one" /><div class="diagram-orbit orbit-two" /><div class="diagram-center">
          <el-icon><Location /></el-icon><strong>观察点 A</strong><span>自主到点 · 现场查看</span>
        </div><div class="diagram-node node-task">
          <el-icon><Monitor /></el-icon><span>下达任务</span>
        </div><div class="diagram-node node-photo">
          <el-icon><Camera /></el-icon><span>回传证据</span>
        </div><span class="diagram-cross cross-one">+</span><span class="diagram-cross cross-two">+</span><span class="diagram-code">POINT → OBSERVE → REPORT</span>
      </div>
    </section>

    <section class="process-section">
      <div class="section-intro">
        <span class="eyebrow">THE WORKFLOW</span><h2>一次任务，一份现场记录</h2><p>复用现有导航与相机能力，形成从出发到查看的完整交互。</p>
      </div><div class="process-grid">
        <article><span class="process-number">01</span><span class="process-icon"><el-icon><Location /></el-icon></span><h3>指定观察位置</h3><p>在工作台选择预设观察点。点位以每次启动位置与朝向为参考。</p></article><article><span class="process-number">02</span><span class="process-icon"><el-icon><Connection /></el-icon></span><h3>自主前往并记录</h3><p>跟踪导航阶段、任务结果与失败原因。实机到点停车后采集一张相机照片。</p></article><article><span class="process-number">03</span><span class="process-icon"><el-icon><ChatDotRound /></el-icon></span><h3>查看证据与回答</h3><p>照片与任务关联保存；华为云模型配置完成后，可对真实照片提问。</p></article>
      </div>
    </section>

    <section class="status-section">
      <div class="status-heading">
        <div><span class="eyebrow">CURRENT CAPABILITIES</span><h2>当前能力与验证边界</h2><p>配置状态与真实验证分开记录，展示已完成的实际进展。</p></div><el-button :icon="Refresh" :loading="loading" @click="loadCapabilities">
          刷新状态
        </el-button>
      </div><el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="status-error" /><div class="capabilities-grid">
        <article class="status-card">
          <span class="status-icon"><el-icon><Monitor /></el-icon></span><div><h3>本地任务工作台</h3><p>任务提交、阶段查询、取消请求、历史和媒体查看，连接本地 FastAPI 接口。</p></div><span class="capability-badge" :class="{ ready: capabilities }">{{ capabilities ? '服务已连接' : '等待读取' }}</span>
        </article><article class="status-card">
          <span class="status-icon"><el-icon><VideoCamera /></el-icon></span><div><h3>MuJoCo 物理仿真</h3><p>复用已有导航仿真，展示真实状态与场景录像；仿真不生成相机照片或图片问答。</p></div><span class="capability-badge" :class="{ ready: capabilities?.simulation_configured }">{{ capabilities ? capabilities.simulation_configured ? '环境已配置' : '等待配置' : '等待读取' }}</span>
        </article><article class="status-card">
          <span class="status-icon"><el-icon><Camera /></el-icon></span><div><h3>机器狗与真实相机</h3><p>已准备到点拍照接口。当前未完成本项目实机验证，运动执行默认关闭。</p></div><span class="capability-badge">{{ capabilities?.motion_enabled ? '已开启 · 待实测' : '待实机验证' }}</span>
        </article><article class="status-card">
          <span class="status-icon"><el-icon><ChatDotRound /></el-icon></span><div><h3>华为云视觉问答</h3><p>已准备配置与调用入口。模型开通、凭据和真实相机照片就绪后，再验证实际回答。</p></div><span class="capability-badge">{{ capabilities?.huawei_configured ? '已配置 · 待验证' : '待模型配置' }}</span>
        </article>
      </div>
    </section>

    <section class="competition-panel">
      <div class="competition-copy">
        <span class="eyebrow">COMPETITION READINESS</span><h2>围绕真实应用，逐步补齐参赛证据</h2><p>本地可视化页面是展示入口。华为云部署、云产品使用和 CodeArts 开发证据需要实际完成与归档。</p><a href="https://e.huawei.com/cn/talent/#/ict/innovation-details?zoneCode=027425&compId=85132021&type=C002&zoneId=98269700" target="_blank" rel="noopener noreferrer">查看赛事官方要求<el-icon><ArrowRight /></el-icon></a>
      </div><div class="readiness-list">
        <div><span class="readiness-mark ready"><el-icon><Check /></el-icon></span><span>可视化任务页面与后端接口</span><small>本地实现</small></div><div><span class="readiness-mark"><el-icon><Document /></el-icon></span><span>CodeArts 真实使用与证据</span><small>已有分析记录，持续补齐</small></div><div><span class="readiness-mark"><el-icon><Connection /></el-icon></span><span>华为云产品与应用部署</span><small>尚未完成</small></div><div><span class="readiness-mark"><el-icon><Camera /></el-icon></span><span>实机演示、评测与公开复现</span><small>待后续验证与整理</small></div>
      </div>
    </section>

    <footer class="project-footer">
      <span>基于开源资产构建，保留来源与许可。</span><div><a href="/template-LICENSE.txt" target="_blank" rel="noopener noreferrer">前端模板许可</a><a href="https://github.com/un-pany/v3-admin-vite" target="_blank" rel="noopener noreferrer">V3 Admin Vite<el-icon><ArrowRight /></el-icon></a><a href="https://github.com/fastapi/full-stack-fastapi-template" target="_blank" rel="noopener noreferrer">FastAPI 官方模板<el-icon><ArrowRight /></el-icon></a></div>
    </footer>
  </div>
</template>

<style lang="scss" scoped>
.project-page {
  padding: 28px 32px 22px;
  color: #203949;
  background: #f3f6f8;
  --el-color-primary: #19866e;
  --el-color-primary-light-3: #429c89;
  --el-color-primary-dark-2: #106b58;
}
.project-hero {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  min-height: 355px;
  background: #142f38;
  border: 1px solid #183a42;
  border-radius: 12px;
  overflow: hidden;
  position: relative;
}
.hero-copy {
  padding: 37px 42px;
  position: relative;
  z-index: 1;
  h1 {
    font-size: 34px;
    letter-spacing: 1px;
    line-height: 1.5;
    font-weight: 550;
    margin: 19px 0 15px;
    color: #e6eeec;
  }
  > p {
    color: #89a4aa;
    font-size: 12px;
    line-height: 2;
    margin-bottom: 23px;
  }
  > .el-button {
    font-size: 12px;
    border-radius: 5px;
    .el-icon {
      margin-left: 17px;
    }
  }
}
.hero-eyebrow {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 9px;
  color: #86b5a4;
  letter-spacing: 2px;
  > span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #6cbb94;
    box-shadow: 0 0 0 4px #34534870;
  }
}
.project-caption {
  display: block;
  margin-top: 18px;
  color: #587e82;
  font-size: 9px;
  letter-spacing: 0.5px;
}
.hero-diagram {
  position: relative;
  display: grid;
  place-items: center;
  min-width: 0;
  background: radial-gradient(ellipse, #2f5b5435, transparent 70%);
  &::before {
    content: "";
    position: absolute;
    inset: 0;
    background-image: radial-gradient(#a1c0bc14 1px, transparent 1px);
    background-size: 19px 19px;
    mask-image: linear-gradient(to right, transparent, #000 40%);
  }
}
.diagram-orbit {
  position: absolute;
  width: 270px;
  height: 270px;
  border: 1px solid #47756940;
  border-radius: 50%;
}
.orbit-two {
  width: 340px;
  height: 340px;
  border-style: dashed;
  opacity: 0.6;
}
.diagram-center {
  position: relative;
  width: 139px;
  height: 139px;
  border-radius: 50%;
  background: #264b45;
  border: 1px solid #477568;
  box-shadow:
    0 0 0 12px #2e514536,
    0 0 0 13px #40625125;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  > .el-icon {
    color: #a9d3b8;
    font-size: 33px;
    margin-bottom: 10px;
  }
  > strong {
    color: #b9d6c8;
    font-size: 14px;
    font-weight: 500;
  }
  > span {
    font-size: 8px;
    color: #759d8d;
    margin-top: 7px;
  }
}
.diagram-node {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 15px;
  border: 1px solid #4e797152;
  background: #1c3b40;
  color: #9ebfb3;
  border-radius: 7px;
  position: absolute;
  font-size: 10px;
  box-shadow: 0 6px 15px #071d2419;
  .el-icon {
    font-size: 17px;
  }
}
.node-task {
  left: 13%;
  top: 22%;
}
.node-photo {
  right: 10%;
  bottom: 23%;
}
.diagram-cross {
  position: absolute;
  color: #557e77;
  font-family: monospace;
  font-size: 17px;
}
.cross-one {
  right: 18%;
  top: 18%;
}
.cross-two {
  left: 16%;
  bottom: 23%;
}
.diagram-code {
  position: absolute;
  bottom: 32px;
  font-size: 8px;
  color: #5e8882;
  letter-spacing: 1.8px;
  font-family: monospace;
}
.process-section {
  margin: 32px 0 28px;
}
.section-intro {
  margin-bottom: 21px;
  h2 {
    font-size: 19px;
    font-weight: 600;
    margin: 10px 0 8px;
  }
  p {
    margin: 0;
    font-size: 12px;
    color: #93a2ad;
    line-height: 1.8;
  }
}
.eyebrow {
  color: #81998e;
  font-size: 9px;
  letter-spacing: 1.6px;
  font-weight: 550;
}
.process-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 19px;
  > article {
    position: relative;
    padding: 24px;
    background: #fff;
    border-radius: 9px;
    border: 1px solid #e4ebed;
    h3 {
      margin: 16px 0 9px;
      font-size: 14px;
      font-weight: 600;
    }
    p {
      margin: 0;
      max-width: 310px;
      color: #8e9faa;
      font-size: 11px;
      line-height: 1.9;
    }
  }
}
.process-number {
  position: absolute;
  top: 27px;
  right: 23px;
  font-family: monospace;
  color: #d1dce0;
  font-size: 18px;
}
.process-icon {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  background: #f0f6f2;
  color: #689781;
  font-size: 20px;
  border-radius: 9px;
}
.status-section {
  padding: 26px;
  border: 1px solid #e4ebed;
  background: #fff;
  border-radius: 10px;
}
.status-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  h2 {
    margin: 10px 0 8px;
    font-size: 18px;
    font-weight: 600;
  }
  p {
    color: #95a4ae;
    font-size: 11px;
    margin: 0;
    line-height: 1.8;
  }
  .el-button {
    font-size: 11px;
  }
}
.status-error {
  margin-top: 20px;
}
.capabilities-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  column-gap: 27px;
  margin-top: 20px;
}
.status-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 21px 0;
  border-top: 1px solid #edf1f2;
  > div {
    flex: 1;
  }
  h3 {
    margin: 1px 0 8px;
    font-weight: 550;
    font-size: 12px;
    color: #577468;
  }
  p {
    color: #9aa8b1;
    font-size: 10px;
    line-height: 1.85;
    margin: 0;
    max-width: 330px;
  }
}
.status-icon {
  display: grid;
  place-items: center;
  background: #f4f7f6;
  color: #8ca79a;
  width: 31px;
  height: 31px;
  border-radius: 7px;
  font-size: 16px;
  flex-shrink: 0;
}
.capability-badge {
  color: #a99776;
  background: #fcf8f0;
  border: 1px solid #f4ecdf;
  font-size: 8px;
  white-space: nowrap;
  border-radius: 4px;
  padding: 4px 6px;
  margin-top: 1px;
  &.ready {
    background: #f0f8f2;
    border-color: #e3f0e8;
    color: #73a38a;
  }
}
.competition-panel {
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 35px;
  padding: 29px;
  margin-top: 26px;
  background: #edf3f0;
  border: 1px solid #e0e9e3;
  border-radius: 10px;
}
.competition-copy {
  h2 {
    font-size: 16px;
    font-weight: 550;
    line-height: 1.7;
    margin: 12px 0 10px;
    color: #486957;
  }
  p {
    color: #8a9f92;
    font-size: 11px;
    line-height: 1.9;
    margin: 0 0 17px;
    max-width: 400px;
  }
  a {
    color: #608a73;
    font-size: 10px;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
}
.readiness-list {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
  > div {
    display: flex;
    align-items: center;
    gap: 9px;
    > span:not(.readiness-mark) {
      color: #718c7a;
      font-size: 11px;
    }
    > small {
      font-size: 9px;
      color: #9baa9e;
      margin-left: auto;
      white-space: nowrap;
    }
  }
}
.readiness-mark {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid #d3e0d8;
  color: #a0b5a6;
  font-size: 10px;
  flex-shrink: 0;
  &.ready {
    background: #d6eadd;
    color: #5e9371;
    border-color: #d1e5d7;
  }
}
.project-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  margin-top: 22px;
  color: #a6b2ba;
  font-size: 9px;
  > div {
    display: flex;
    gap: 19px;
  }
  a {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: #90a499;
    text-decoration: none;
    &:hover {
      color: #14836b;
    }
  }
}
@media (min-width: 1600px) {
  .project-page {
    padding-left: 42px;
    padding-right: 42px;
  }
  .hero-copy {
    padding: 44px 50px;
  }
}
@media (max-width: 1150px) {
  .project-page {
    padding: 25px 23px;
  }
  .hero-copy {
    padding: 32px;
    h1 {
      font-size: 29px;
    }
    > p {
      font-size: 11px;
    }
  }
  .diagram-orbit {
    width: 230px;
    height: 230px;
  }
  .orbit-two {
    width: 295px;
    height: 295px;
  }
  .node-task {
    left: 2%;
  }
  .node-photo {
    right: 2%;
  }
  .process-grid {
    gap: 14px;
    > article {
      padding: 20px;
    }
  }
  .status-card {
    position: relative;
    padding-bottom: 34px;
    .capability-badge {
      position: absolute;
      bottom: 12px;
      left: 43px;
    }
  }
  .competition-panel {
    gap: 25px;
    padding: 24px;
  }
  .readiness-list > div {
    flex-wrap: wrap;
    > small {
      padding-left: 29px;
      width: 100%;
      margin-top: -5px;
    }
  }
}
@media (max-width: 900px) {
  .project-hero {
    grid-template-columns: 1.25fr 1fr;
  }
  .hero-copy {
    padding: 29px;
  }
  .diagram-center {
    width: 112px;
    height: 112px;
    > .el-icon {
      font-size: 27px;
    }
    > strong {
      font-size: 12px;
    }
    > span {
      font-size: 7px;
    }
  }
  .diagram-orbit {
    width: 190px;
    height: 190px;
  }
  .orbit-two {
    width: 250px;
    height: 250px;
  }
  .diagram-node {
    padding: 9px;
    font-size: 9px;
    .el-icon {
      font-size: 14px;
    }
  }
  .node-task {
    left: 0;
    top: 22%;
  }
  .node-photo {
    right: 0;
    bottom: 24%;
  }
  .diagram-code {
    font-size: 6px;
  }
  .hero-copy > p br {
    display: none;
  }
  .capabilities-grid {
    gap: 0 20px;
  }
  .status-card {
    gap: 9px;
  }
}
@media (max-width: 760px) {
  .project-page {
    padding: 18px 15px;
  }
  .project-hero {
    grid-template-columns: 1fr;
  }
  .hero-copy {
    padding: 30px 27px;
    h1 {
      font-size: 30px;
      margin-top: 18px;
    }
  }
  .hero-diagram {
    display: none;
  }
  .process-section {
    margin-top: 27px;
  }
  .section-intro h2 {
    font-size: 17px;
  }
  .process-grid {
    grid-template-columns: 1fr;
    gap: 12px;
    > article {
      padding: 20px;
      h3 {
        margin: 0 0 8px 54px;
      }
      p {
        margin-left: 54px;
        max-width: initial;
      }
    }
  }
  .process-icon {
    float: left;
    margin-top: 2px;
  }
  .process-number {
    top: 20px;
    right: 18px;
    font-size: 15px;
  }
  .status-section {
    padding: 21px;
  }
  .status-heading {
    align-items: flex-start;
    h2 {
      font-size: 16px;
    }
    p {
      font-size: 10px;
    }
    .el-button {
      font-size: 10px;
      padding: 8px;
      margin-top: 27px;
    }
  }
  .capabilities-grid {
    grid-template-columns: 1fr;
  }
  .status-card {
    padding-bottom: 36px;
    p {
      max-width: none;
    }
  }
  .competition-panel {
    grid-template-columns: 1fr;
    gap: 20px;
    padding: 23px;
  }
  .readiness-list {
    gap: 17px;
    > div > small {
      margin-left: auto;
      width: auto;
      margin-top: 0;
      padding-left: 0;
    }
  }
  .project-footer {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
    line-height: 1.7;
  }
}
@media (max-width: 420px) {
  .readiness-list > div {
    > span:not(.readiness-mark) {
      font-size: 10px;
    }
    > small {
      font-size: 8px;
    }
  }
}
</style>
