import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import {
  ChatDotRound,
  CircleCheck,
  CircleClose,
  Loading,
  Promotion,
  Service,
  ShoppingBag,
  WarningFilled,
} from '@element-plus/icons-vue'

import 'element-plus/dist/index.css'
import './style.css'

import App from './App.vue'

const app = createApp(App)

app.use(createPinia())
app.use(ElementPlus, { locale: zhCn })

// Register only the icons used in templates (tree-shaking friendly).
// Plus is imported locally in ChatSidebar.vue.
const icons = {
  ChatDotRound,
  CircleCheck,
  CircleClose,
  Loading,
  Promotion,
  Service,
  ShoppingBag,
  WarningFilled,
}
for (const [name, component] of Object.entries(icons)) {
  app.component(name, component)
}

app.mount('#app')
