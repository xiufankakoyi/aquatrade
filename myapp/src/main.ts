import { createApp } from 'vue';
import { createPinia } from 'pinia';
import router from './router';

// 设计系统样式（必须先引入，提供CSS变量）
import './styles/design-system.css';

import './style.css';
import App from './App.vue';
import './index.css';
import '@fortawesome/fontawesome-free/css/all.css';
import VueVirtualScroller from 'vue-virtual-scroller';
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import Antd from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);
app.use(VueVirtualScroller);
app.use(Antd);
app.mount('#app');