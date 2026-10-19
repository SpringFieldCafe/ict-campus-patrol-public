请作为华为 CodeArts 实际参与公开仓前端依赖修复。输出三个明确代码围栏块：
1) json：完整新的 apps/web/package.json，保持其他所有字段不变，axios改1.20.0、vue改3.5.42、vitest改4.1.11、删除vxe-table；新增pnpm.overrides，采用下列已核对注册表可用版本（如发现具体兼容问题可说明，但不可自造版本）。
2) json：{"delete_files":[...],"review_issues":[...]}，列出应移除的四个未使用Vxe文件，并给真实审查意见。
3) markdown：约600中文字的 docs/DEPENDENCY_REPAIR.md 初稿，写明你主笔包配置、删除清单和审查；实际删除/lock解析/安装/测试/PR由Codex执行，当前尚未验证通过，后续以真实记录补齐。不要输出额外代码围栏；不要声称你直接编辑或运行过工具。

用户授权：下一轮单独开分支修复公开仓前端依赖，与华为智能体合作，最少改动；原私有仓与导航/仿真环境不升级，零现金预算。公开仓SpringFieldCafe/ict-campus-patrol-public，新工作树fix/frontend-dependency-alerts-20261019基于b032b03。GitHub Pages只上传docs，不安装前端依赖，不涉及华为云服务创建。CodeArts本次工具deny只审查与主笔，Codex将应用你真实生成的配置并留原稿/回执。

核实事实：GitHub61告警=41不同GHSA（2critical来自tinypool）；本轮pnpm audit独立基线63条（2critical43high17moderate1low），NPM/GitHub计数不可混用。tinypool实际来自eslint-plugin-format>oxfmt，不是Vitest直接依赖，必须明确override才能从2.1.0更新到2.1.2。axios/所有Vue配套/Vitest已核对官方registry修复版本存在。其余补丁按原主版本分支精确覆盖，不pnpm update --latest全量升级。

Vxe：GitHub官方GHSA-89fp-f5mx-748x仍Patched=None，first_patched_version=null；上游PR2791仍open，不能把版本升出受影响范围当作已证明修复。项目锁vxe-table4.6.25，但业务router只有console/history/project，dynamic=false；plugins/index.ts、main.ts、styles/index.scss均不加载Vxe。需移除四个未使用文件：apps/web/src/plugins/vxe-table.ts；apps/web/src/pages/demo/vxe-table/index.vue；apps/web/src/common/assets/styles/vxe-table.scss；apps/web/src/common/assets/styles/vxe-table.css；同步从package和锁移除vxe以及孤立dom-zindex/xe-utils。不要删common/apis/tables，ElementPlus示例仍使用。types目录无Vxe引用。UPSTREAM“Vxe资产保留”要更新。该处理属于移除未使用的脆弱组件，不是修复Vxe上游。

另外发现braces@3.0.3 GHSA-vfj7-8cjw-p6xm当前无修复版本，路径unplugin-svg-component>fast-glob>micromatch>braces，是受控本地SVG构建工具；不为了告警归零伪造版本、不静默audit ignore、不自制无证据安全补丁，也不在本轮更换整套图标插件。预计仍需保留一项明确未解决告警并说明真实可达性尚未评估，不能称全部漏洞修复。不得把静态网站不加载它写成依赖已安全。

KaTeX旧0.16.47来自@antfu/eslint-config>@eslint/markdown>micromark-extension-math，官方修复0.18.2跨0.x小版本，必须在记录中单列兼容性风险；Codex将核对Markdown数学解析/渲染API并做构建验证。此处不是运行时业务依赖，不替换项目功能。

验证计划：新工作树创建独立node_modules（绝不沿用/修改原仓node_modules软链接）；锁解析由pnpm10.34.0，Node24.22.0；frozen-lockfile安装、前端22测试、TypeScript/Vitebuild、audit前后对照、页面最小浏览器检查，核对原仓441文件和依赖元数据哈希。暂不跑机器人/仿真/真实视觉模型。先完成可复核分支/PR，GitHub默认分支告警关闭必须等实际合入与扫描结果，不以分支audit冒充已经清零。

建议overrides JSON（请逐项审查）：
{
  "tinypool@<2.1.2": "2.1.2",
  "source-map-js@<1.2.2": "1.2.2",
  "postcss-selector-parser@<7.1.6": "7.1.6",
  "js-yaml@>=4.0.0 <4.3.2": "4.3.2",
  "svgo@>=2.0.0 <2.8.4": "2.8.4",
  "svgo@>=3.0.0 <3.3.5": "3.3.5",
  "@xmldom/xmldom@>=0.7.0 <0.8.15": "0.8.15",
  "baseline-browser-mapping@>=2.0.0 <2.11.0": "2.11.0",
  "browserslist@>=4.0.0 <4.28.7": "4.28.7",
  "nanoid@>=3.0.0 <3.3.18": "3.3.18",
  "postcss@>=8.0.0 <8.5.23": "8.5.23",
  "glob@>=10.2.0 <10.5.0": "10.5.0",
  "katex@>=0.11.0 <0.18.2": "0.18.2",
  "brace-expansion@>=1.0.0 <1.1.21": "1.1.21",
  "brace-expansion@>=2.0.0 <2.1.7": "2.1.7",
  "brace-expansion@>=4.0.0 <5.0.12": "5.0.12"
}

原package.json：
{
  "name": "campus-patrol-web",
  "type": "module",
  "version": "5.2.0",
  "description": "受限区域现场查看任务工作台，基于 V3 Admin Vite 改造",
  "author": "pany <939630029@qq.com> (https://github.com/pany-ang)",
  "repository": "https://github.com/un-pany/v3-admin-vite",
  "scripts": {
    "dev": "vite",
    "build:staging": "vue-tsc && vite build --mode staging",
    "build": "vue-tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint --fix",
    "test": "vitest",
    "typecheck": "vue-tsc --noEmit",
    "test:run": "vitest run"
  },
  "dependencies": {
    "@element-plus/icons-vue": "2.3.2",
    "axios": "1.18.1",
    "dayjs": "1.11.21",
    "element-plus": "2.14.2",
    "lodash-es": "4.18.1",
    "mitt": "3.0.1",
    "normalize.css": "8.0.1",
    "nprogress": "0.2.0",
    "path-browserify": "1.0.1",
    "path-to-regexp": "8.4.2",
    "pinia": "3.0.4",
    "screenfull": "6.0.2",
    "vue": "3.5.39",
    "vue-router": "5.1.0",
    "vxe-table": "4.6.25"
  },
  "devDependencies": {
    "@antfu/eslint-config": "9.1.0",
    "@types/lodash-es": "4.17.12",
    "@types/node": "26.1.1",
    "@types/nprogress": "0.2.3",
    "@types/path-browserify": "1.0.3",
    "@vitejs/plugin-vue": "6.0.7",
    "@vue/test-utils": "2.4.11",
    "eslint": "10.6.0",
    "eslint-plugin-format": "2.0.1",
    "happy-dom": "20.10.6",
    "husky": "9.1.7",
    "lint-staged": "17.0.8",
    "sass-embedded": "1.78.0",
    "typescript": "5.9.3",
    "unocss": "66.7.5",
    "unplugin-auto-import": "21.0.0",
    "unplugin-svg-component": "0.12.6",
    "unplugin-vue-components": "32.1.0",
    "vite": "7.3.6",
    "vite-svg-loader": "5.1.1",
    "vitest": "4.1.10",
    "vue-tsc": "3.3.7"
  },
  "lint-staged": {
    "*": "eslint --fix"
  },
  "private": true,
  "packageManager": "pnpm@10.34.0",
  "engines": {
    "node": ">=22.12.0"
  }
}
