"use strict";
const scenes = {
  staggered_walls: { title: "错位短墙 / STAGGERED WALLS", note: "12 次成功，3 次碰撞。保留原模型与 0.18 m/s 横向限速。" },
  flat_obstacle: { title: "侧箱对照 / SIDE-BOX BASELINE", note: "15 次成功。结果仅覆盖本次简单侧箱场景与小幅起点扰动。" }
};
const variants = { center: "中", left: "左", right: "右" };
let data;
let current = "staggered_walls";
function showCase(item, button) {
  document.querySelectorAll(".case").forEach(node => node.setAttribute("aria-pressed", String(node === button)));
  const detail = document.getElementById("case-detail");
  detail.replaceChildren();
  const title = document.createElement("b");
  title.textContent = item.id;
  const summary = document.createElement("div");
  summary.textContent = `${item.state === "SUCCEEDED" ? "成功" : "碰撞"} · 按序到达 ${item.reached}/3 点 · 模拟时间 ${item.simulated_seconds.toFixed(3)} s。${item.state === "SUCCEEDED" ? "无碰撞、无跌倒。" : "保留该失败结果，未计为成功。"}`;
  detail.append(title, summary);
}
function render(scene) {
  current = scene;
  const summary = data.by_scene[scene];
  document.getElementById("scene-label").textContent = scenes[scene].title;
  document.getElementById("success-rate").textContent = String(Math.round(summary.success_rate * 100));
  document.getElementById("success-count").textContent = String(summary.states.SUCCEEDED);
  document.getElementById("collision-count").textContent = String(summary.states.COLLISION);
  document.getElementById("mean-time").textContent = summary.successful_simulated_seconds_mean.toFixed(2);
  document.getElementById("scene-description").textContent = scenes[scene].note;
  document.querySelectorAll(".scenario").forEach(button => {
    const active = button.dataset.scene === scene;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const grid = document.getElementById("case-grid");
  grid.replaceChildren();
  const items = data.cases.filter(item => item.scene === scene);
  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "case" + (item.state === "SUCCEEDED" ? "" : " failed");
    button.textContent = `${item.state === "SUCCEEDED" ? "✓" : "×"} ${variants[item.variant]} · ${String(item.seed).padStart(2, "0")}`;
    button.setAttribute("aria-label", `${item.id}，${item.state === "SUCCEEDED" ? "成功" : "碰撞"}`);
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => showCase(item, button));
    grid.append(button);
  }
  if (items.length) showCase(items[0], grid.firstElementChild);
}
document.querySelectorAll(".scenario").forEach(button => {
  button.disabled = true;
  button.addEventListener("click", () => { if (data) render(button.dataset.scene); });
});
fetch("data/evaluation.json")
  .then(response => { if (!response.ok) throw new Error("公开数据读取失败"); return response.json(); })
  .then(value => { data = value; render(current); document.querySelectorAll(".scenario").forEach(button => button.disabled = false); })
  .catch(() => { document.getElementById("case-detail").textContent = "历史数据暂时未能载入。上方汇总仍可查看，也可以下载 JSON 或进入 GitHub 核对原始记录。"; });
