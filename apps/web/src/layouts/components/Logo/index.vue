<script lang="ts" setup>
const { collapse = true } = defineProps<{ collapse?: boolean }>()
</script>

<template>
  <router-link to="/console" class="patrol-logo" aria-label="Campus Patrol 任务工作台">
    <img src="/favicon.svg" alt="" width="32" height="32">
    <span v-if="!collapse">CAMPUS PATROL<small>受限区域 · 现场查看</small></span>
  </router-link>
</template>

<style scoped>
.patrol-logo {
  height: var(--v3-header-height);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  overflow: hidden;
  color: #e8f7f5;
}
.patrol-logo span {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
  white-space: nowrap;
}
.patrol-logo small {
  display: block;
  font-size: 9px;
  color: #8daeb6;
  font-weight: 400;
  letter-spacing: 1.5px;
  margin-top: 6px;
}
.patrol-logo img {
  flex: none;
}
</style>
