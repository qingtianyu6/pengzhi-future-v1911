import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#168464',
          colorInfo: '#168464',
          colorSuccess: '#2e8b57',
          colorWarning: '#d99a1d',
          colorError: '#d84a3a',
          borderRadius: 10,
          borderRadiusLG: 14,
          boxShadowSecondary: '0 10px 30px rgba(28, 65, 53, .09)',
          colorText: '#19322a',
          colorBgLayout: '#f4f7f5',
          fontFamily: "'Noto Sans CJK SC','HarmonyOS Sans SC','PingFang SC','Microsoft YaHei UI','Microsoft YaHei',sans-serif",
        },
        components: { Table: { cellPaddingBlock: 12 }, Card: { headerFontSize: 15 } },
      }}
    >
      <App />
    </ConfigProvider>
  </StrictMode>,
)
