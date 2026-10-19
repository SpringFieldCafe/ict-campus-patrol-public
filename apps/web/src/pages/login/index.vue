<script lang="ts" setup>
import { useUserStore } from "@/pinia/stores/user"
import { loginApi } from "./apis"

const router = useRouter()
const route = useRoute()
const user = useUserStore()
const email = ref("operator@example.com")
const password = ref("")
const loading = ref(false)
const error = ref("")
async function submit() {
  if (loading.value) return
  error.value = ""
  if (!email.value.trim() || !password.value) {
    error.value = "请输入邮箱和密码。"
    return
  }
  loading.value = true
  try {
    const result = await loginApi({ username: email.value.trim(), password: password.value })
    user.setToken(result.access_token)
    // Let the router guard fetch user information and initialize the sidebar routes.
    password.value = ""
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/console"
    await router.replace(redirect.startsWith("/") && !redirect.startsWith("//") ? redirect : "/console")
  } catch (e) {
    user.resetToken()
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-story">
      <div class="login-brand">
        <img src="/favicon.svg" alt="" width="38" height="38"><span>CAMPUS PATROL<small>受限区域 · 现场查看</small></span>
      </div>
      <div class="story-copy">
        <div class="story-kicker">
          SEE WHAT'S BEYOND REACH
        </div><h1>让机器狗<br>替你到现场看看。</h1><p>从一个观察点开始，跟随任务进度，<br>让现场影像成为回答的依据。</p>
      </div>
      <div class="field-map" aria-hidden="true">
        <div class="map-line" /><span class="map-start">起点</span><span class="map-point">A<small>观察点</small></span><div class="map-ring" />
      </div>
      <div class="story-steps">
        <span>01 选择观察点</span><i /><span>02 前往查看</span><i /><span>03 回看结果</span>
      </div>
    </section>
    <section class="login-panel">
      <div class="login-box">
        <span class="login-eyebrow">任务工作台</span><h2>登录，查看现场</h2><p class="login-intro">
          使用已配置的操作员账户继续。
        </p>
        <form @submit.prevent="submit">
          <label for="login-email">邮箱</label><el-input id="login-email" v-model="email" name="username" type="email" autocomplete="username" placeholder="请输入邮箱" size="large" :disabled="loading" />
          <label for="login-password">密码</label><el-input id="login-password" v-model="password" name="password" type="password" autocomplete="current-password" placeholder="请输入密码" show-password size="large" :disabled="loading" />
          <p v-if="error" class="login-error" role="alert">
            {{ error }}
          </p>
          <el-button type="primary" native-type="submit" size="large" :loading="loading" class="login-submit">
            进入工作台 <span aria-hidden="true">↗</span>
          </el-button>
        </form><p class="login-note">
          每一次任务，都有迹可循。
        </p>
      </div><footer>Campus Patrol · 现场查看</footer>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  background: #fff;
}
.login-story {
  background: #102f3d;
  color: #f5fffd;
  padding: 48px 9%;
  position: relative;
  overflow: hidden;
  min-height: 720px;
}
.login-brand {
  display: flex;
  gap: 14px;
  align-items: center;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 2px;
}
.login-brand small {
  display: block;
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 2px;
  color: #a6c4c9;
  margin-top: 8px;
}
.story-copy {
  position: relative;
  z-index: 1;
  margin-top: 90px;
}
.story-kicker {
  font-size: 10px;
  letter-spacing: 2.5px;
  color: #65d8c7;
}
.story-copy h1 {
  font-size: clamp(36px, 3.7vw, 58px);
  line-height: 1.4;
  font-weight: 600;
  letter-spacing: 2px;
  margin: 22px 0;
}
.story-copy p {
  line-height: 1.9;
  color: #adc7cd;
  font-size: 14px;
}
.field-map {
  position: absolute;
  width: 400px;
  height: 260px;
  bottom: 90px;
  right: -10px;
  background-image:
    linear-gradient(#b7e3d80a 1px, transparent 1px), linear-gradient(90deg, #b7e3d80a 1px, transparent 1px);
  background-size: 32px 32px;
  transform: rotate(-15deg);
}
.map-line {
  position: absolute;
  left: 30px;
  top: 140px;
  width: 220px;
  height: 70px;
  border-left: 2px dashed #65d8c766;
  border-top: 2px dashed #65d8c766;
  border-radius: 20px 0 0 0;
}
.map-start {
  position: absolute;
  left: 17px;
  top: 210px;
  font-size: 10px;
  color: #adc7cd;
}
.map-point {
  position: absolute;
  left: 230px;
  top: 115px;
  background: #65d8c7;
  color: #102f3d;
  display: grid;
  place-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  font-size: 20px;
  font-weight: 600;
}
.map-point small {
  position: absolute;
  top: 58px;
  width: 70px;
  font-size: 11px;
  color: #adc7cd;
  text-align: center;
  left: -11px;
}
.map-ring {
  position: absolute;
  left: 201px;
  top: 86px;
  width: 106px;
  height: 106px;
  border: 1px solid #65d8c733;
  border-radius: 50%;
}
.story-steps {
  position: absolute;
  bottom: 42px;
  left: 9%;
  right: 9%;
  display: flex;
  align-items: center;
  gap: 12px;
  color: #adc7cd;
  font-size: 11px;
}
.story-steps i {
  height: 1px;
  flex: 1;
  background: #adc7cd33;
}
.login-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 44px;
  position: relative;
}
.login-box {
  max-width: 360px;
  width: 100%;
}
.login-eyebrow {
  font-size: 12px;
  color: #168b80;
  letter-spacing: 2px;
}
.login-box h2 {
  font-size: 30px;
  font-weight: 600;
  color: #173442;
  margin: 18px 0 10px;
}
.login-intro {
  font-size: 13px;
  color: #7b8c95;
  margin-bottom: 38px;
}
.login-box label {
  display: block;
  font-size: 13px;
  margin: 24px 0 10px;
  color: #334f5b;
}
.login-submit {
  width: 100%;
  margin-top: 30px;
  display: flex;
  justify-content: space-between;
  height: 46px !important;
}
.login-submit span {
  margin-left: 15px;
}
.login-note {
  text-align: center;
  color: #99a6ad;
  font-size: 12px;
  margin-top: 26px;
}
.login-error {
  font-size: 12px;
  color: #ba3d3d;
  line-height: 1.6;
}
.login-panel footer {
  position: absolute;
  bottom: 28px;
  color: #9aa8ae;
  font-size: 11px;
  letter-spacing: 1px;
}
@media (max-width: 850px) {
  .login-page {
    grid-template-columns: 1fr;
  }
  .login-story {
    min-height: 270px;
    padding: 28px;
  }
  .login-brand {
    font-size: 12px;
  }
  .story-copy {
    margin-top: 28px;
  }
  .story-kicker,
  .story-copy p,
  .story-steps,
  .field-map {
    display: none;
  }
  .story-copy h1 {
    font-size: 30px;
    margin-bottom: 0;
  }
  .login-panel {
    padding: 40px 28px 70px;
    min-height: 510px;
  }
}
</style>
