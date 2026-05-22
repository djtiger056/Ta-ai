import React, { useEffect, useRef, useState } from 'react'
import { Alert, Button, Card, Input, message, Spin } from 'antd'
import { RobotOutlined, SendOutlined, UserOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

import { proactiveApi } from '@/services/api'
import { useAuth } from '../contexts/AuthContext'

const { TextArea } = Input
const PROACTIVE_POLL_INTERVAL = 10000

interface ChatEmote {
  category: string
  file_name: string
  data_url: string
  mime_type?: string
  matched_keywords?: string[]
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  emote?: ChatEmote
  imageDataUrl?: string
  videoUrl?: string
  source?: 'dialogue' | 'proactive'
}

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const seenProactiveIdsRef = useRef<Set<string>>(new Set())
  
  // 获取当前登录用户
  const { user } = useAuth()
  const userId = user ? String(user.id) : 'web_user'
  const sessionId = userId

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    let active = true

    const pollMessages = async () => {
      if (!active || streaming) {
        return
      }
      try {
        const payloads = await proactiveApi.pollMessages({
          channel: 'web',
          user_id: userId,
          session_id: sessionId,
          limit: 20,
        })

        const nextMessages: ChatMessage[] = (payloads || [])
          .filter((item: any) => {
            const id = String(item?.id || '')
            if (!id || seenProactiveIdsRef.current.has(id)) {
              return false
            }
            seenProactiveIdsRef.current.add(id)
            return true
          })
          .map((item: any) => ({
            id: String(item.id),
            role: 'assistant',
            content: String(item.content || ''),
            timestamp: item.created_at ? new Date(item.created_at) : new Date(),
            source: 'proactive',
            imageDataUrl: item.image_base64 ? `data:image/png;base64,${item.image_base64}` : undefined,
          }))

        if (active && nextMessages.length > 0) {
          setMessages(prev => [...prev, ...nextMessages])
        }
      } catch (error) {
        console.error('poll proactive messages failed:', error)
      }
    }

    pollMessages()
    const timer = window.setInterval(pollMessages, PROACTIVE_POLL_INTERVAL)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [streaming, userId, sessionId])

  const handleSend = async () => {
    if (!input.trim()) return

    const clickAt = performance.now()
    const clientTimeline: Array<{ stage: string; elapsed_ms: number }> = []
    const serverTimeline: Array<{ stage: string; server_elapsed_ms: number; client_recv_ms: number }> = []
    const markClient = (stage: string) => {
      clientTimeline.push({
        stage,
        elapsed_ms: Number((performance.now() - clickAt).toFixed(2)),
      })
    }
    markClient('click_send')

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
      source: 'dialogue',
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setStreaming(true)

    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: input,
          user_id: userId,
          session_id: sessionId,
        }),
      })
      markClient('response_headers_received')

      if (!response.ok) {
        throw new Error('发送消息失败')
      }

      const botMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        source: 'dialogue',
      }

      setMessages(prev => [...prev, botMessage])

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (reader) {
        let firstBodyChunkMarked = false
        let firstContentMarked = false
        let sseBuffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          if (!firstBodyChunkMarked) {
            markClient('first_body_chunk_received')
            firstBodyChunkMarked = true
          }

          sseBuffer += decoder.decode(value, { stream: true })
          const rawEvents = sseBuffer.split('\n\n')
          sseBuffer = rawEvents.pop() || ''

          for (const rawEvent of rawEvents) {
            const dataLines = rawEvent
              .split('\n')
              .filter(line => line.startsWith('data:'))
              .map(line => line.slice(5).trimStart())

            if (!dataLines.length) continue

            const data = dataLines.join('\n')
            if (data === '[DONE]') continue

            try {
              const parsed = JSON.parse(data)

              if (parsed.meta && parsed.meta.stage) {
                serverTimeline.push({
                  stage: parsed.meta.stage,
                  server_elapsed_ms: Number(parsed.meta.elapsed_ms || 0),
                  client_recv_ms: Number((performance.now() - clickAt).toFixed(2)),
                })
              }

              if (parsed.content) {
                if (!firstContentMarked) {
                  markClient('first_content_rendered')
                  firstContentMarked = true
                }
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === botMessage.id
                      ? { ...msg, content: msg.content + parsed.content }
                      : msg
                  )
                )
              }

              if (parsed.image) {
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === botMessage.id
                      ? { ...msg, imageDataUrl: `data:image/png;base64,${parsed.image}` }
                      : msg
                  )
                )
              }

              if (parsed.video) {
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === botMessage.id
                      ? { ...msg, videoUrl: parsed.video }
                      : msg
                  )
                )
              }

              if (parsed.audio) {
                const mime = parsed.audio_mime || 'audio/mpeg'
                const audio = new Audio(`data:${mime};base64,${parsed.audio}`)
                audio.play().catch(e => console.error('Audio play error:', e))
              }

              if (parsed.emote) {
                const emoteData: any = parsed.emote
                const dataUrl = emoteData.data_url || (emoteData.base64_data ? `data:${emoteData.mime_type || 'image/png'};base64,${emoteData.base64_data}` : '')
                if (dataUrl) {
                  const normalizedEmote: ChatEmote = {
                    category: emoteData.category,
                    file_name: emoteData.file_name,
                    data_url: dataUrl,
                    mime_type: emoteData.mime_type,
                    matched_keywords: emoteData.matched_keywords,
                  }
                  setMessages(prev =>
                    prev.map(msg =>
                      msg.id === botMessage.id
                        ? { ...msg, emote: normalizedEmote }
                        : msg
                    )
                  )
                }
              }
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }
    } catch (error) {
      message.error('发送消息失败，请检查配置')
      console.error('Chat error:', error)
    } finally {
      markClient('request_finished')
      console.groupCollapsed('[Latency] chat stream timeline')
      console.table(clientTimeline)
      if (serverTimeline.length) {
        console.table(serverTimeline)
      }
      console.groupEnd()
      setLoading(false)
      setStreaming(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <Card title="聊天测试" style={{ height: 'calc(100vh - 200px)' }}>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message={`当前用户: ${user?.nickname || user?.username || "未登录"} (ID: ${userId})`}
        description="聊天时将使用你的个人配置。如需修改配置，请前往「我的设置」页面。"
      />
      <div className="chat-messages" style={{ height: 'calc(100% - 120px)', overflowY: 'auto', padding: '16px' }}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`message-item ${msg.role === 'user' ? 'message-user' : 'message-bot'}`}
            style={{ marginBottom: '16px' }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
              {msg.role === 'user' ? (
                <UserOutlined style={{ fontSize: '16px', marginTop: '4px' }} />
              ) : (
                <RobotOutlined style={{ fontSize: '16px', marginTop: '4px' }} />
              )}
              <div className="message-content" style={{
                background: msg.role === 'user' ? '#1890ff' : '#f0f0f0',
                color: msg.role === 'user' ? 'white' : '#333',
                padding: '8px 12px',
                borderRadius: '8px',
                maxWidth: '70%',
                wordWrap: 'break-word',
              }}>
                {msg.role === 'assistant' ? (
                  <>
                    {msg.source === 'proactive' && (
                      <div style={{ fontSize: '12px', color: '#999', marginBottom: '6px' }}>
                        主动消息
                      </div>
                    )}
                    <ReactMarkdown
                      components={{
                        code({ inline, className, children, ...props }: any) {
                          const match = /language-(\w+)/.exec(className || '')
                          return !inline && match ? (
                            <SyntaxHighlighter
                              style={oneDark}
                              language={match[1]}
                              PreTag="div"
                              {...props}
                            >
                              {String(children).replace(/\n$/, '')}
                            </SyntaxHighlighter>
                          ) : (
                            <code className={className} {...props}>
                              {children}
                            </code>
                          )
                        },
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                    {msg.imageDataUrl && (
                      <div style={{ marginTop: '8px' }}>
                        <img
                          src={msg.imageDataUrl}
                          alt="assistant generated"
                          style={{ maxWidth: '220px', borderRadius: '8px', display: 'block' }}
                        />
                      </div>
                    )}
                    {msg.videoUrl && (
                      <div style={{ marginTop: '8px' }}>
                        <video
                          src={msg.videoUrl}
                          controls
                          style={{ maxWidth: '320px', width: '100%', borderRadius: '8px', display: 'block' }}
                        />
                      </div>
                    )}
                    {msg.emote && msg.emote.data_url && (
                      <div style={{ marginTop: '8px' }}>
                        <img
                          src={msg.emote.data_url}
                          alt={`${msg.emote.category}/${msg.emote.file_name}`}
                          style={{ maxWidth: '220px', borderRadius: '8px', display: 'block' }}
                        />
                        <div style={{ fontSize: '12px', color: '#888', marginTop: '4px' }}>
                          表情包：{msg.emote.category}/{msg.emote.file_name}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="message-item message-bot">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <RobotOutlined />
              <Spin size="small" />
              <span>正在思考...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input" style={{
        position: 'sticky',
        bottom: 0,
        background: 'white',
        padding: '16px',
        borderTop: '1px solid #f0f0f0',
      }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入消息..."
            autoSize={{ minRows: 2, maxRows: 4 }}
            disabled={loading}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            style={{ alignSelf: 'flex-end' }}
          >
            发送
          </Button>
        </div>
      </div>
    </Card>
  )
}

export default ChatPage
