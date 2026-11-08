import { createRouter, createWebHistory } from 'vue-router'
import { tokenStore } from './api/client.js'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/LoginView.vue') },
  { path: '/', name: 'home', component: () => import('./views/ShellView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const authed = !!tokenStore.get()
  if (to.name !== 'login' && !authed) return { name: 'login' }
  if (to.name === 'login' && authed) return { name: 'home' }
  return true
})
