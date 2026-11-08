import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router.js'
import { onUnauthorized, tokenStore } from './api/client.js'
import { TABS_KEY } from './stores/tabs.js'
import { clearSession } from './stores/session.js'
import './styles.css'

onUnauthorized(() => {
  tokenStore.clear()
  sessionStorage.removeItem(TABS_KEY)
  clearSession()
  router.replace('/login')
})

createApp(App).use(router).mount('#app')
