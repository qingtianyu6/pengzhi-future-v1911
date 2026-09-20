import { useState } from 'react'
import { Button, Drawer, Tooltip } from 'antd'
import AIAssistantPage from '../pages/AI/AIAssistantPage'
import { AgriculturalAgentMascot } from './AgriculturalAgentMascot'

export function FloatingAIAssistant() {
  const [open, setOpen] = useState(false)

  return <>
    <Tooltip title="棚小智" placement="left">
      <Button
        className="ai-floating-button agent-character-button"
        shape="circle"
        onClick={() => setOpen(true)}
        aria-label="打开棚小智"
      >
        <AgriculturalAgentMascot compact />
        <span className="agent-online-dot" />
      </Button>
    </Tooltip>
    <Drawer
      className="ai-global-drawer"
      title={null}
      placement="right"
      width="min(1160px, 98vw)"
      open={open}
      onClose={() => setOpen(false)}
      destroyOnHidden
    >
      <AIAssistantPage />
    </Drawer>
  </>
}
