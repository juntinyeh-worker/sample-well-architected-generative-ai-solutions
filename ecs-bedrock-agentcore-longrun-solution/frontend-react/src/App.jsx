import React, { useState, useRef, useEffect } from 'react'
import AppLayout from '@cloudscape-design/components/app-layout'
import Container from '@cloudscape-design/components/container'
import Header from '@cloudscape-design/components/header'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Button from '@cloudscape-design/components/button'
import Textarea from '@cloudscape-design/components/textarea'
import Box from '@cloudscape-design/components/box'
import StatusIndicator from '@cloudscape-design/components/status-indicator'

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const chatRef = useRef(null)

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [])

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight
  }, [messages])

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = window.APP_CONFIG?.api?.wsEndpoint || `${proto}//${location.host}/ws`
    const ws = new WebSocket(wsUrl)
    ws.onopen = () => setConnected(true)
    ws.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      setMessages(prev => [...prev, { role: 'ai', type: msg.type, text: msg.message || '', data: msg.data }])
    }
    wsRef.current = ws
  }

  function send() {
    if (!input.trim() || !wsRef.current || wsRef.current.readyState !== 1) return
    setMessages(prev => [...prev, { role: 'user', text: input }])
    wsRef.current.send(JSON.stringify({ text: input }))
    setInput('')
  }

  return (
    <AppLayout
      navigationHide
      toolsHide
      content={
        <SpaceBetween size="l">
          <Header variant="h1" description="Async task dispatch via Bedrock AgentCore Runtime">
            AgentCore Long-Running Orchestrator
          </Header>
          <Container header={<Header variant="h2" actions={
            <StatusIndicator type={connected ? 'success' : 'error'}>{connected ? 'Connected' : 'Disconnected'}</StatusIndicator>
          }>Chat</Header>}>
            <SpaceBetween size="s">
              <div ref={chatRef} style={{ height: '400px', overflowY: 'auto', padding: '8px' }}>
                <SpaceBetween size="xs">
                  {messages.map((m, i) => (
                    <ChatMessage key={i} message={m} />
                  ))}
                </SpaceBetween>
              </div>
              <SpaceBetween direction="horizontal" size="xs">
                <div style={{ flex: 1 }}>
                  <Textarea
                    value={input}
                    onChange={({ detail }) => setInput(detail.value)}
                    onKeyDown={(e) => { if (e.detail.key === 'Enter' && !e.detail.shiftKey) { e.preventDefault(); send() } }}
                    placeholder="Ask about your AWS environment..."
                    rows={2}
                  />
                </div>
                <Button variant="primary" onClick={send}>Send</Button>
              </SpaceBetween>
            </SpaceBetween>
          </Container>
        </SpaceBetween>
      }
    />
  )
}

function ChatMessage({ message }) {
  const isUser = message.role === 'user'
  const bgColor = isUser ? '#0073bb' : message.type === 'task_error' ? '#1a0000' : '#232f3e'
  const borderLeft = message.type === 'task_complete' ? '3px solid #1d8102' : message.type === 'task_error' ? '3px solid #d13212' : 'none'

  return (
    <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      <div style={{ maxWidth: '75%', padding: '10px 14px', borderRadius: '8px', background: bgColor, color: '#fff', borderLeft, whiteSpace: 'pre-wrap', fontSize: '14px' }}>
        {message.text}
        {message.data && <pre style={{ marginTop: '8px', padding: '8px', background: '#0f1b2d', borderRadius: '4px', fontSize: '12px', overflow: 'auto' }}>{JSON.stringify(message.data, null, 2)}</pre>}
      </div>
    </div>
  )
}
