import React, { useEffect, useState } from 'react'
import {
  Card,
  Switch,
  Input,
  InputNumber,
  Button,
  Space,
  Tag,
  Typography,
  message,
  Slider,
  Row,
  Col,
  Divider,
  Modal,
  Alert,
} from 'antd'
import { PlusOutlined, SaveOutlined, ReloadOutlined, DeleteOutlined, FolderOpenOutlined } from '@ant-design/icons'
import { emoteApi } from '@/services/api'
import { EmoteCategory, EmoteConfig, EmoteCategoryInfo } from '@/types'

const { Title, Text, Paragraph } = Typography

const createEmptyCategory = (): EmoteCategory => ({
  name: '',
  keywords: [],
  weight: 1,
  enabled: true,
  path: '',
})

const EmotePage: React.FC = () => {
  const [config, setConfig] = useState<EmoteConfig>({
    enabled: true,
    send_probability: 0.25,
    base_path: 'data/emotes',
    max_per_message: 1,
    categories: [],
    file_extensions: ['png', 'jpg', 'jpeg', 'gif', 'webp'],
  })
  const [categoryInfo, setCategoryInfo] = useState<EmoteCategoryInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [keywordInputs, setKeywordInputs] = useState<Record<number, string>>({})
  const [scanModalVisible, setScanModalVisible] = useState(false)
  const [scanPath, setScanPath] = useState('')
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState<{
    categories: EmoteCategoryInfo[]
    total_categories: number
    total_files: number
    base_path: string
  } | null>(null)

  const loadConfig = async () => {
    setLoading(true)
    try {
      const data = await emoteApi.getConfig()
      setConfig(data.config)
      setCategoryInfo(data.categories || [])
    } catch (error) {
      console.error(error)
      message.error('获取表情包配置失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadConfig()
  }, [])

  const updateCategory = (index: number, updater: (cat: EmoteCategory) => EmoteCategory) => {
    setConfig(prev => {
      const categories = [...(prev.categories || [])]
      categories[index] = updater({ ...categories[index] })
      return { ...prev, categories }
    })
  }

  const handleAddKeyword = (index: number) => {
    const value = keywordInputs[index]?.trim()
    if (!value) return
    updateCategory(index, cat => ({
      ...cat,
      keywords: Array.from(new Set([...(cat.keywords || []), value])),
    }))
    setKeywordInputs(prev => ({ ...prev, [index]: '' }))
  }

  const handleRemoveKeyword = (index: number, keyword: string) => {
    updateCategory(index, cat => ({
      ...cat,
      keywords: (cat.keywords || []).filter(k => k !== keyword),
    }))
  }

  const handleAddCategory = () => {
    setConfig(prev => ({
      ...prev,
      categories: [...(prev.categories || []), createEmptyCategory()],
    }))
  }

  const handleRemoveCategory = (index: number) => {
    setConfig(prev => ({
      ...prev,
      categories: (prev.categories || []).filter((_, i) => i !== index),
    }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const sanitizedCategories = (config.categories || [])
        .filter(cat => (cat.name || '').trim())
        .map(cat => ({
          ...cat,
          name: cat.name.trim(),
          keywords: (cat.keywords || []).map(k => k.trim()).filter(Boolean),
          path: cat.path?.trim() || undefined,
          weight: Number(cat.weight) || 0,
        }))

      const payload: EmoteConfig = {
        ...config,
        send_probability: Math.min(1, Math.max(0, Number(config.send_probability))),
        base_path: config.base_path?.trim() || 'data/emotes',
        categories: sanitizedCategories,
      }

      const data = await emoteApi.updateConfig(payload)
      setConfig(data.config)
      setCategoryInfo(data.categories || [])
      message.success('已保存表情包配置')
    } catch (error) {
      console.error(error)
      message.error('保存失败，请检查配置')
    } finally {
      setSaving(false)
    }
  }

  const handleReload = async () => {
    setLoading(true)
    try {
      const data = await emoteApi.reloadFiles()
      setCategoryInfo(data.categories || [])
      message.success('已重新扫描表情包目录')
    } catch (error) {
      console.error(error)
      message.error('重载失败')
    } finally {
      setLoading(false)
    }
  }

  const handleScanFolder = async () => {
    if (!scanPath.trim()) {
      message.warning('请输入表情包文件夹路径')
      return
    }
    setScanning(true)
    setScanResult(null)
    try {
      const data = await emoteApi.scanFolder(scanPath.trim(), config.file_extensions)
      setScanResult(data)
    } catch (error: any) {
      console.error(error)
      const detail = error?.response?.data?.detail || '扫描失败，请检查路径是否正确'
      message.error(detail)
    } finally {
      setScanning(false)
    }
  }

  const handleApplyScanResult = (mode: 'replace' | 'merge') => {
    if (!scanResult) return
    const scannedCategories: EmoteCategory[] = scanResult.categories.map(cat => ({
      name: cat.name,
      keywords: cat.keywords || [],
      weight: cat.weight ?? 1,
      enabled: cat.enabled ?? true,
      path: cat.path || '',
    }))

    if (mode === 'replace') {
      setConfig(prev => ({
        ...prev,
        base_path: scanResult.base_path,
        categories: scannedCategories,
      }))
    } else {
      // merge: 保留已有分类的关键词和权重配置，新增未有的分类
      const existingMap = new Map((config.categories || []).map(c => [c.name, c]))
      const merged: EmoteCategory[] = scannedCategories.map(scanned => {
        const existing = existingMap.get(scanned.name)
        if (existing) {
          // 保留已有配置，只更新路径
          return { ...existing, path: scanned.path }
        }
        return scanned
      })
      setConfig(prev => ({
        ...prev,
        base_path: scanResult.base_path,
        categories: merged,
      }))
    }

    setScanModalVisible(false)
    setScanResult(null)
    message.success(`已${mode === 'replace' ? '替换' : '合并'}应用扫描结果，记得点击"保存配置"生效`)
  }

  const getCategoryStat = (name: string) => categoryInfo.find(item => item.name === name)

  return (
    <Card loading={loading}>
      <Title level={4}>表情包发送</Title>
      <Paragraph>
        发送概率、语境关键词驱动的自动表情包。请将表情文件放在
        <Text code>{config.base_path || 'data/emotes'}</Text>
        下按分类创建子文件夹，前端管理关键词、开关和权重即可。
      </Paragraph>

      <Row gutter={16}>
        <Col span={12}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div>
              <Space size="middle">
                <Text strong>启用自动表情包</Text>
                <Switch
                  checked={config.enabled}
                  onChange={checked => setConfig(prev => ({ ...prev, enabled: checked }))}
                />
              </Space>
            </div>
            <div>
              <Text strong>单轮发送概率</Text>
              <Slider
                min={0}
                max={1}
                step={0.01}
                value={config.send_probability}
                onChange={(value) => setConfig(prev => ({ ...prev, send_probability: Number(value) }))}
              />
              <InputNumber
                min={0}
                max={1}
                step={0.01}
                value={config.send_probability}
                onChange={(value) => setConfig(prev => ({ ...prev, send_probability: Number(value || 0) }))}
              />
            </div>
            <div>
              <Text strong>单条最多附带</Text>
              <InputNumber
                min={1}
                value={config.max_per_message}
                onChange={(value) => setConfig(prev => ({ ...prev, max_per_message: Number(value || 1) }))}
              />
            </div>
            <div>
              <Text strong>表情包根目录</Text>
              <Input
                value={config.base_path}
                onChange={(e) => setConfig(prev => ({ ...prev, base_path: e.target.value }))}
              />
              <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                默认存放在项目根目录下的 <Text code>data/emotes/&lt;分类名&gt;</Text>
              </Text>
            </div>
            <div>
              <Space size="small">
                <Button icon={<ReloadOutlined />} onClick={handleReload}>重新扫描目录</Button>
                <Button icon={<FolderOpenOutlined />} onClick={() => { setScanPath(config.base_path || ''); setScanModalVisible(true) }}>
                  从文件夹导入
                </Button>
                <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>保存配置</Button>
              </Space>
            </div>
          </Space>
        </Col>
        <Col span={12}>
          <Card size="small" title="使用说明">
            <ul style={{ paddingLeft: 20 }}>
              <li>在根目录创建分类文件夹，例如 <Text code>happy</Text>、<Text code>sad</Text>。</li>
              <li>同名分类将读取 <Text code>{config.file_extensions?.join(', ')}</Text> 等后缀的图片/GIF。</li>
              <li>在此页面维护关键词和开关，命中关键词优先，未命中按权重随机。</li>
              <li>当前可用分类会显示文件数，方便检查是否放置成功。</li>
            </ul>
          </Card>
        </Col>
      </Row>

      <Divider />
      <Space style={{ marginBottom: 12 }}>
        <Button type="dashed" icon={<PlusOutlined />} onClick={handleAddCategory}>
          新增分类
        </Button>
      </Space>

      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {(config.categories || []).map((cat, index) => {
          const stat = getCategoryStat(cat.name)
          return (
            <Card
              key={`${cat.name || 'new'}-${index}`}
              size="small"
              title={cat.name || '未命名分类'}
              extra={
                <Space>
                  <Switch
                    checked={cat.enabled}
                    onChange={(checked) => updateCategory(index, prev => ({ ...prev, enabled: checked }))}
                  />
                  <Button
                    icon={<DeleteOutlined />}
                    danger
                    size="small"
                    onClick={() => handleRemoveCategory(index)}
                  />
                </Space>
              }
            >
              <Space direction="vertical" style={{ width: '100%' }} size="small">
                <Input
                  placeholder="分类名称（同时作为文件夹名）"
                  value={cat.name}
                  onChange={(e) => updateCategory(index, prev => ({ ...prev, name: e.target.value }))}
                />
                <Input
                  placeholder="可选：自定义子路径，默认与分类名一致"
                  value={cat.path}
                  onChange={(e) => updateCategory(index, prev => ({ ...prev, path: e.target.value }))}
                />
                <div>
                  <Text strong>关键词（命中优先发送）</Text>
                  <div style={{ marginTop: 8 }}>
                    {(cat.keywords || []).map((kw) => (
                      <Tag
                        key={kw}
                        closable
                        onClose={() => handleRemoveKeyword(index, kw)}
                        style={{ marginBottom: 4 }}
                      >
                        {kw}
                      </Tag>
                    ))}
                  </div>
                  <Space style={{ marginTop: 8 }}>
                    <Input
                      placeholder="输入关键词后回车"
                      value={keywordInputs[index] || ''}
                      onChange={(e) => setKeywordInputs(prev => ({ ...prev, [index]: e.target.value }))}
                      onPressEnter={() => handleAddKeyword(index)}
                      style={{ width: 240 }}
                    />
                    <Button onClick={() => handleAddKeyword(index)}>添加关键词</Button>
                  </Space>
                </div>
                <div>
                  <Text strong>随机权重</Text>
                  <InputNumber
                    min={0}
                    step={0.1}
                    value={cat.weight}
                    onChange={(value) => updateCategory(index, prev => ({ ...prev, weight: Number(value || 0) }))}
                  />
                  {stat && (
                    <Text type="secondary" style={{ marginLeft: 12 }}>
                      文件数：{stat.file_count}，示例：{(stat.sample_files || []).slice(0, 3).join(', ')}
                    </Text>
                  )}
                </div>
              </Space>
            </Card>
          )
        })}
      </Space>

      {/* 扫描文件夹弹窗 */}
      <Modal
        title="从文件夹导入表情包分类"
        open={scanModalVisible}
        onCancel={() => { setScanModalVisible(false); setScanResult(null) }}
        footer={null}
        width={640}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Alert
            type="info"
            message="输入表情包文件夹的路径，系统会自动扫描所有子文件夹并识别为表情包分类。支持绝对路径和相对路径（相对于项目根目录）。"
            showIcon
          />
          <Space.Compact style={{ width: '100%' }}>
            <Input
              placeholder="例如：/home/user/emotes 或 data/emotes"
              value={scanPath}
              onChange={(e) => setScanPath(e.target.value)}
              onPressEnter={handleScanFolder}
            />
            <Button type="primary" loading={scanning} onClick={handleScanFolder} icon={<FolderOpenOutlined />}>
              扫描
            </Button>
          </Space.Compact>

          {scanResult && (
            <>
              <Alert
                type="success"
                message={`扫描完成：发现 ${scanResult.total_categories} 个分类，共 ${scanResult.total_files} 个文件`}
                showIcon
              />
              <div style={{ maxHeight: 300, overflow: 'auto' }}>
                {scanResult.categories.map((cat) => (
                  <Card key={cat.name} size="small" style={{ marginBottom: 8 }}>
                    <Row justify="space-between" align="middle">
                      <Col>
                        <Text strong>{cat.name}</Text>
                        <Text type="secondary" style={{ marginLeft: 8 }}>
                          {cat.file_count} 个文件
                        </Text>
                      </Col>
                      <Col>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {(cat.sample_files || []).slice(0, 3).join(', ')}
                        </Text>
                      </Col>
                    </Row>
                  </Card>
                ))}
              </div>
              <Row gutter={12}>
                <Col>
                  <Button type="primary" onClick={() => handleApplyScanResult('replace')}>
                    替换当前配置
                  </Button>
                </Col>
                <Col>
                  <Button onClick={() => handleApplyScanResult('merge')}>
                    合并到当前配置
                  </Button>
                </Col>
              </Row>
              <Text type="secondary">
                替换：清空现有分类，使用扫描结果。合并：保留已有分类的关键词和权重，新增扫描到的分类。
              </Text>
            </>
          )}
        </Space>
      </Modal>
    </Card>
  )
}

export default EmotePage
