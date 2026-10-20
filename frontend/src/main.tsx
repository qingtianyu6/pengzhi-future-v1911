import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import { platformTheme } from './theme'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={platformTheme}
    >
      <App />
    </ConfigProvider>
  </StrictMode>,
)

import './layouts/workbench-polish.css'

import './layouts/workbench-redesign.css'

import './layouts/platform-visual.css'
import './typography.css'
