# Telegram商户机器人系统业务流程分析文档 (V2.0)

## 目录
1. [系统概述](#系统概述)
2. [核心业务流程](#核心业务流程)
3. [数据库架构](#数据库架构)
4. [功能区域详解](#功能区域详解)

---

## 系统概述

### 系统定位
新版系统是一个为商家/老师（统称“商户”）提供**自动化帖子发布和管理**的Telegram机器人平台。它旨在通过高度自动化的流程，帮助商户准备、提交并最终在指定频道发布标准化的推广信息，同时赋予管理员对内容的完全控制权。

### 主要用户角色
- **商户用户 (商家/老师)**: 内容的提供者。通过机器人提交个人资料、服务介绍、价格、图片/视频等，并设定期望的发布时间。
- **系统管理员**: 系统的管理者和审核者。通过Web后台生成绑定码、审核商户提交的内容、批准发布、并管理帖子的生命周期（如到期时间）。

### 核心业务价值
1.  **永久身份**: 商户与平台建立永久ID绑定，业务信息不随TG账号变动而丢失。
2.  **流程自动化**: 从绑定到信息提交，再到定时发布，全程由机器人和后台服务驱动，效率高。
3.  **质量控制**: 管理员的审核与批准机制，确保了发布内容的质量与合规性。
4.  **生命周期管理**: 帖子从创建到发布，再到过期，都有明确的状态和管理方式。

---

## 核心业务流程

商家/老师上榜与发布的完整业务流程，涉及客服、商户、机器人、后台服务和管理员五个角色，分为以下五个阶段：

### 阶段一：获取绑定码 (线下/手动)
1.  **客服沟通**: 商户与客服沟通，了解上榜需求和费用。
2.  **自动付款**: 客服引导商户通过一个独立的自动发卡/付款机器人（如 `@faka`）完成支付。
3.  **获取凭证**: 支付成功后，付款机器人自动向商户发送一个一次性的、唯一的**绑定码**（例如 `SFIUZ3`）。

### 阶段二：绑定与信息收集 (Bot端)
1.  **激活机器人**: 客服引导商户打开主业务机器人（`@xiaojisystembot`）。
2.  **执行绑定**: 商户发送 `/bind <绑定码>` 命令。
3.  **创建永久ID**: 机器人后台服务验证绑定码的有效性。验证通过后，立即在 `merchants` 表中创建一个新的记录，生成一个**永久的、唯一的商户ID**（如 `1`, `2`, `3`...），并将商户当前的 `telegram_chat_id` 与之关联。绑定码被标记为已使用。
4.  **引导信息收集**: 机器人回复“绑定成功”，并开始通过一系列按钮和对话，引导商户提交以下信息：
    *   名称
    *   Telegram 用户名 (`@handle`)
    *       地区（城市 -> 地区）
    *   两种服务的价格
    *   优点、缺点、基本功介绍
    *   最多6张宣传图片或视频（后台仅保存`file_id`，Web端通过代理路由实时获取）
    *   期望的帖子发布时间
5.  **提交待审**: 所有信息收集完毕后，系统将该商户帖子的状态（`status`）设置为 `pending_approval`。

### 阶段三：审核与批准 (Web管理端)
1.  **内容审核**: 管理员在Web后台的“待审批”列表中，可以看到新提交的商户信息。
2.  **查看与修改**: 管理员点击查看详情，可以预览最终的帖子效果，并有权修改商户提交的任何文本信息。
3.  **设置到期时间**: 管理员为该帖子设置一个到期时间 `expiration_time`，默认为30天后。
4.  **批准发布**: 确认所有内容无误后，管理员点击“**批准发布**”按钮。后台将该帖子的 `status` 更新为 `approved`。

### 阶段四：自动发布 (后端服务)
1.  **定时扫描**: 一个独立的后端服务（定时任务/Cron Job）会定期（例如每分钟）扫描 `merchants` 表。
2.  **寻找任务**: 该服务会寻找所有 `status` 为 `approved` 且 `publish_time` 已到或已过的帖子。
3.  **执行发布**: 对每个找到的帖子，服务会：
    *   读取其所有数据（文本、媒体文件ID）。
    *   使用标准模板生成最终的帖子内容。
    *   调用Telegram API将帖子发布到指定频道。
    *   发布成功后，将帖子的 `status` 更新为 `published`。

### 阶段五：商户看板与生命周期结束 (Bot端与后端)
1.  **商户看板**: 已发布的商户可以通过 `/panel` 命令，在机器人处查看自己帖子的到期时间，以及未来的评价、活动、数据等功能入口。
2.  **服务到期处理**: 后端服务的另一个调度任务会每日检查，寻找 `status` 为 `published` 且 `expiration_time`（服务到期时间）已过的帖子，并触发一个**后续处理流程**（具体行为待定），以反映服务周期结束。

### 阶段六：双向评价与确认 (Bot端与后端)
1.  **用户评价**: 订单完成后，机器人引导用户对商家进行多维度评分和可选的文字评价。评价数据存入`reviews`表，状态为“待商家确认”。
2.  **商家确认**: 机器人通知商家有新的评价待确认。商家在Bot内点击按钮，确认该评价的真实性。
3.  **激励发放**: 评价被确认后，系统为用户发放积分和经验。
4.  **分数计算**: 每日的定时任务会聚合所有**已确认**的评价，更新商家的平均分。
5.  **商家评价用户 (预留)**: 商家确认后，可继续对用户进行评价。

### 阶段六：双向评价与确认 (Bot端与后端)
1.  **用户评价**: 订单完成后，机器人引导用户对商家进行多维度评分和可选的文字评价。评价数据存入`reviews`表，状态为“待商家确认”。
2.  **商家确认**: 机器人通知商家有新的评价待确认。商家在Bot内点击按钮，确认该评价的真实性。
3.  **激励发放**: 评价被确认后，系统为用户发放积分和经验。
4.  **分数计算**: 每日的定时任务会聚合所有**已确认**的评价，更新商家的平均分。
5.  **商家评价用户 (预留)**: 商家确认后，可继续对用户进行评价。

---

## 数据库架构

为支撑上述流程，核心数据库表结构设计如下：

#### 1. `merchants` (商家/老师信息表)
```sql
CREATE TABLE merchants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,      -- 永久唯一ID, 自动增长
    telegram_chat_id BIGINT NOT NULL,          -- 当前绑定的TG账号ID, 可修改
    name TEXT,                                 -- 商家/老师名称
    username TEXT,                             -- TG用户名 (@handle)
    district_id INTEGER,                       -- 地区ID (关联到districts表)
    price_1 INTEGER,                           -- 价格1
    price_2 INTEGER,                           -- 价格2
    advantages TEXT,                           -- 优点描述
    disadvantages TEXT,                        -- 缺点描述
    basic_skills TEXT,                         -- 自填基本功
    status TEXT NOT NULL DEFAULT 'pending_submission', -- 帖子状态: pending_submission, pending_approval, approved, published, expired
    publish_time DATETIME,                     -- 期望发布时间
    expiration_time DATETIME,                  -- 服务到期时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. `media` (媒体文件表)
```sql
CREATE TABLE media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,              -- 关联到 merchants.id
    telegram_file_id TEXT NOT NULL,            -- Telegram文件的唯一ID
    media_type TEXT NOT NULL,                  -- 文件类型: 'photo' 或 'video'
    sort_order INTEGER DEFAULT 0,              -- 媒体文件排序
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);
```

#### 3. `binding_codes` (绑定码表)
```sql
CREATE TABLE binding_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,                 -- 唯一的绑定码字符串
    is_used BOOLEAN DEFAULT FALSE,             -- 是否已被使用
    used_by_merchant_id INTEGER,               -- 关联到使用的 merchants.id
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 功能区域详解

### 1. 商户与帖子管理区域
- **核心功能**: 管理从商户信息提交到帖子发布的整个生命周期。
- **技术实现**: Bot端通过FSM状态机进行信息收集；Web端提供CRUD操作界面；后端服务通过状态（`status`）驱动自动化流程。

### 2. 管理员控制区域
- **核心功能**: 内容审核、发布批准、生命周期控制（设置到期时间）。
- **技术实现**: Web后台提供安全的、基于表单的操作界面，所有关键操作直接更新数据库中的记录状态或时间戳。
