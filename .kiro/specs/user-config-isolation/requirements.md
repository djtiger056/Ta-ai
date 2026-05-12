# 需求文档：用户配置隔离系统

## 简介

本功能为聊天机器人系统实现完整的用户配置隔离方案。当前系统部署到服务器后，所有用户共享同一份 `config.yaml` 配置文件，任何用户的修改都会影响其他用户。本功能将实现：用户登录认证系统、每用户独立配置文件、管理员全局兜底配置、以及用户数据目录结构，确保多用户环境下各用户配置互不干扰。

## 术语表

- **System（系统）**: 整个聊天机器人后端服务，包括 FastAPI 后端和前端界面
- **Auth_Module（认证模块）**: 负责用户注册、登录、令牌管理的子系统
- **Config_Service（配置服务）**: 负责配置文件的读取、写入、合并的子系统
- **User_Data_Store（用户数据存储）**: 项目根目录下用于保存每个用户独立数据的文件夹结构
- **Global_Config（全局配置）**: 管理员设置的系统级默认配置，作为所有用户的兜底配置
- **User_Config（用户配置）**: 单个用户的自定义配置覆盖项，仅包含用户修改过的字段
- **Merged_Config（合并配置）**: 将用户配置覆盖到全局配置之上后得到的最终生效配置
- **Admin_Panel（管理员面板）**: 管理员专用的前端界面，用于管理全局配置和用户
- **Fallback（兜底）**: 当用户未设置某项配置时，自动使用全局默认值的机制

## 需求

### 需求 1：用户注册与登录

**用户故事：** 作为一个前端用户，我想要注册和登录自己的账号，以便系统能识别我的身份并加载我的专属配置。

#### 验收标准

1. WHEN 用户提交有效的用户名和密码进行注册, THE Auth_Module SHALL 创建用户账号并返回用户信息
2. WHEN 用户提交已存在的用户名进行注册, THE Auth_Module SHALL 返回"用户名已存在"错误提示
3. WHEN 用户提交正确的用户名和密码进行登录, THE Auth_Module SHALL 返回有效的访问令牌（access_token）
4. WHEN 用户提交错误的用户名或密码进行登录, THE Auth_Module SHALL 返回"用户名或密码错误"错误提示
5. WHILE 用户持有有效的访问令牌, THE System SHALL 允许用户访问受保护的 API 接口
6. IF 用户的访问令牌过期或无效, THEN THE System SHALL 返回 401 未授权状态码并拒绝请求

### 需求 2：用户配置隔离存储

**用户故事：** 作为一个已登录用户，我想要拥有独立的配置文件，以便我的配置修改不会影响其他用户。

#### 验收标准

1. WHEN 新用户首次登录, THE Config_Service SHALL 为该用户创建独立的配置记录，初始值为空（继承全局配置）
2. WHEN 用户修改某项配置, THE Config_Service SHALL 仅将修改的字段保存到该用户的配置记录中
3. THE Config_Service SHALL 将每个用户的配置数据独立存储，确保用户 A 的配置修改不影响用户 B 的配置
4. WHEN 用户请求获取配置, THE Config_Service SHALL 返回该用户已自定义的配置项
5. WHEN 用户重置某项配置, THE Config_Service SHALL 删除该用户对应的自定义配置项，使其回退到全局默认值

### 需求 3：配置合并与兜底机制

**用户故事：** 作为一个用户，我想要在没有自定义配置的情况下也能正常使用所有功能，系统应自动使用管理员设置的默认配置。

#### 验收标准

1. WHEN 用户与机器人聊天, THE Config_Service SHALL 将用户配置与全局配置进行深度合并，生成最终生效的 Merged_Config
2. WHILE 用户未自定义某项配置, THE Config_Service SHALL 使用 Global_Config 中对应字段的值作为该项的生效值
3. WHILE 用户已自定义某项配置, THE Config_Service SHALL 使用 User_Config 中对应字段的值覆盖 Global_Config 的值
4. WHEN 合并配置时遇到嵌套字典结构, THE Config_Service SHALL 递归地进行字段级合并，而非整体替换
5. WHEN 用户配置中某字段值为空（None、空字符串、空字典、空列表）, THE Config_Service SHALL 跳过该字段，继续使用全局配置的值

### 需求 4：管理员全局配置管理

**用户故事：** 作为管理员，我想要设置全局默认配置，以便所有未自定义配置的用户都能正常使用系统的各项功能。

#### 验收标准

1. WHEN 管理员通过管理面板修改全局配置, THE System SHALL 将修改保存到全局配置文件（config.yaml）中
2. THE Admin_Panel SHALL 提供 LLM、TTS、图像生成、视觉识别、ASR、表情包、主动聊天等所有模块的全局配置编辑界面
3. WHEN 管理员修改全局配置后, THE Config_Service SHALL 使新的全局配置对所有未自定义该项的用户立即生效
4. WHILE 管理员未通过认证, THE System SHALL 拒绝所有管理员 API 请求并返回 401 状态码
5. WHEN 管理员请求查看某用户的配置, THE Admin_Panel SHALL 同时展示该用户的自定义覆盖项和合并后的最终生效配置

### 需求 5：用户数据目录结构

**用户故事：** 作为系统管理员，我想要在项目根目录下有一个统一的用户数据文件夹，以便集中管理每个用户的配置文件、图片资源和日志。

#### 验收标准

1. THE User_Data_Store SHALL 在项目根目录下创建 `user_data/` 文件夹作为所有用户数据的根目录
2. WHEN 新用户首次产生数据, THE User_Data_Store SHALL 在 `user_data/` 下创建以用户 ID 命名的子文件夹
3. THE User_Data_Store SHALL 在每个用户文件夹下维护以下子目录结构：`config/`（配置文件）、`images/`（图生图照片）、`logs/`（用户日志）
4. WHEN 用户上传图生图照片, THE User_Data_Store SHALL 将照片保存到该用户的 `images/` 子目录中
5. THE User_Data_Store SHALL 确保用户 A 无法访问用户 B 的数据目录中的文件
6. IF 用户数据目录不存在, THEN THE User_Data_Store SHALL 自动创建所需的目录结构

### 需求 6：聊天时加载用户配置

**用户故事：** 作为一个已登录用户，我想要在与机器人聊天时自动使用我保存的配置，以便获得个性化的聊天体验。

#### 验收标准

1. WHEN 用户发起聊天请求, THE System SHALL 根据用户身份加载该用户的 Merged_Config
2. WHEN 用户的 Merged_Config 中包含自定义 LLM 配置, THE System SHALL 使用该配置创建对应的 LLM Provider 实例
3. WHEN 用户的 Merged_Config 中包含自定义 TTS 配置, THE System SHALL 使用该配置创建对应的 TTS Manager 实例
4. WHEN 用户的 Merged_Config 中包含自定义图像生成配置, THE System SHALL 使用该配置创建对应的 ImageGeneration Manager 实例
5. WHEN 用户的 Merged_Config 中包含自定义系统提示词, THE System SHALL 使用该提示词替代全局系统提示词
6. THE System SHALL 对用户配置和资源实例进行缓存，避免每次聊天请求都重新加载和创建

### 需求 7：前端用户配置界面

**用户故事：** 作为一个已登录用户，我想要在前端界面中查看和修改我的个人配置，以便自定义机器人的行为。

#### 验收标准

1. WHILE 用户未登录, THE System SHALL 将前端页面重定向到登录页面
2. WHEN 用户登录成功, THE System SHALL 在前端展示该用户的当前配置（合并后的生效值）
3. WHEN 用户在前端修改配置并保存, THE System SHALL 仅将修改的字段发送到后端保存为用户自定义配置
4. THE System SHALL 在前端配置界面中明确标识哪些配置项是用户自定义的、哪些是继承自全局默认值
5. WHEN 用户点击"重置为默认"按钮, THE System SHALL 删除该用户对应的自定义配置项并刷新界面显示全局默认值

### 需求 8：管理员用户管理

**用户故事：** 作为管理员，我想要查看和管理所有注册用户，以便进行用户维护和配置下发。

#### 验收标准

1. WHEN 管理员请求用户列表, THE Admin_Panel SHALL 返回所有注册用户的基本信息（用户名、昵称、QQ ID、状态、创建时间）
2. WHEN 管理员禁用某用户, THE System SHALL 将该用户的 is_active 状态设为 0，使其无法登录
3. WHEN 管理员为某用户下发配置, THE Config_Service SHALL 将配置保存到该用户的配置记录中
4. WHEN 管理员删除某用户, THE System SHALL 同时删除该用户的账号信息、配置记录和用户数据目录
5. WHEN 管理员通过 QQ 用户 ID 查询用户, THE System SHALL 返回对应的用户信息和配置
