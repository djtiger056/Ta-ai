import React, { useState, useEffect } from 'react'
import { 
  Card, 
  Form, 
  Input, 
  InputNumber, 
  Button, 
  message, 
  Table, 
  Space,
  Modal,
  Popconfirm,
  Tag,
  Tooltip,
  Select
} from 'antd'
import { 
  EditOutlined, 
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined
} from '@ant-design/icons'
import { memoryApi } from '@/services/api'

const { TextArea } = Input

interface MemoryItem {
  id: string
  content: string
  importance?: number
  metadata?: any
  created_at?: string
  updated_at?: string
}

const MemoryManagePage: React.FC = () => {
  const [form] = Form.useForm()
  const [memories, setMemories] = useState<MemoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [editingMemory, setEditingMemory] = useState<MemoryItem | null>(null)
  const [userId, setUserId] = useState<string>('')
  const [userIds, setUserIds] = useState<string[]>([])
  const [userInfoMap, setUserInfoMap] = useState<Record<string, string>>({})

  useEffect(() => {
    const loadUserIds = async () => {
      try {
        const data = await memoryApi.getMemoryUsers()
        const ids = data.user_ids || []
        setUserIds(ids)
        if (data.user_info && Array.isArray(data.user_info)) {
          const map: Record<string, string> = {}
          for (const info of data.user_info) {
            map[info.user_id] = info.display_name || info.user_id
          }
          setUserInfoMap(map)
        }
        if (ids.length > 0) {
          setUserId((prev) => prev || ids[0])
        }
      } catch (error) {
        console.error('加载用户列表失败:', error)
      }
    }
    loadUserIds()
  }, [])

  const loadMemories = async () => {
    if (!userId) {
      message.warning('请选择用户')
      return
    }
    try {
      setLoading(true)
      const data = await memoryApi.getLongTermMemories(userId, 100)
      setMemories(data.memories || [])
    } catch (error) {
      console.error('加载记忆失败:', error)
      message.error('加载记忆失败')
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = (record: MemoryItem) => {
    setEditingMemory(record)
    form.setFieldsValue({
      content: record.content,
      importance: record.importance || 0.5
    })
    setEditModalVisible(true)
  }

  const handleSaveEdit = async () => {
    try {
      const values = await form.validateFields()
      await memoryApi.updateLongTermMemory(
        editingMemory!.id,
        values.content,
        values.importance
      )
      message.success('记忆更新成功')
      setEditModalVisible(false)
      setEditingMemory(null)
      form.resetFields()
      await loadMemories()
    } catch (error) {
      console.error('更新记忆失败:', error)
      message.error('更新记忆失败')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await memoryApi.deleteLongTermMemory(id)
      message.success('记忆删除成功')
      await loadMemories()
    } catch (error) {
      console.error('删除记忆失败:', error)
      message.error('删除记忆失败')
    }
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      render: (text: string) => (
        <Tooltip title={text}>
          <span>{text}</span>
        </Tooltip>
      ),
    },
    {
      title: '重要性',
      dataIndex: 'importance',
      key: 'importance',
      width: 100,
      render: (importance: number) => (
        <Tag color={importance > 0.7 ? 'green' : importance > 0.4 ? 'orange' : 'red'}>
          {importance?.toFixed(2) || '0.50'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => {
        if (!time) return '-'
        const date = new Date(time)
        return date.toLocaleString('zh-CN')
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: MemoryItem) => (
        <Space>
          <Button 
            type="link" 
            icon={<EditOutlined />} 
            size="small"
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这条记忆吗？"
            onConfirm={() => handleDelete(record.id.toString())}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger icon={<DeleteOutlined />} size="small">
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: '24px' }}>
      <Card title="记忆管理">
        <Space style={{ marginBottom: 16 }}>
          <Select
            placeholder="选择用户"
            value={userId}
            onChange={setUserId}
            style={{ width: 420 }}
            options={userIds.map(id => ({ label: userInfoMap[id] || id, value: id }))}
            showSearch
            filterOption={(input, option) =>
              (option?.label as string || '').toLowerCase().includes(input.toLowerCase())
            }
          />
          <Button type="primary" icon={<ReloadOutlined />} onClick={loadMemories} loading={loading}>
            加载记忆
          </Button>
        </Space>

        <Table
          columns={columns}
          dataSource={memories}
          rowKey="id"
          pagination={{ pageSize: 20 }}
          loading={loading}
        />
      </Card>

      <Modal
        title="编辑记忆"
        open={editModalVisible}
        onOk={handleSaveEdit}
        onCancel={() => {
          setEditModalVisible(false)
          setEditingMemory(null)
          form.resetFields()
        }}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="记忆内容"
            name="content"
            rules={[{ required: true, message: '请输入记忆内容' }]}
          >
            <TextArea rows={6} />
          </Form.Item>
          <Form.Item
            label="重要性 (0-1)"
            name="importance"
            rules={[{ required: true, message: '请输入重要性' }]}
          >
            <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default MemoryManagePage
