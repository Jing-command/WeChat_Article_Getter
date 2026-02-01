# 激活码系统使用说明

## 功能概述

本系统为微信公众号文章下载器添加了激活码鉴权功能，只有输入有效的激活码才能使用下载功能。

## 激活码类型

### 1. 单次下载激活码（S- 开头）
- 格式：`S-XXXX-XXXX-XXXX-XXXX`
- 用途：下载单篇文章
- 特点：每个激活码只能使用一次

### 2. 批量下载激活码（B- 开头）
- 格式：`B-XXXX-XXXX-XXXX-XXXX`
- 用途：批量下载同一公众号的多篇文章
- 特点：每个激活码只能使用一次

## 生成激活码

### 方法1：命令行交互式生成

```bash
python activation_key_generator.py
```

进入交互式菜单，选择操作：
1. 生成单次下载激活码
2. 生成批量下载激活码
3. 查看所有激活码
4. 验证激活码
5. 退出

### 方法2：通过代码生成

```python
from activation_key_generator import ActivationKeyGenerator

# 初始化生成器
generator = ActivationKeyGenerator()

# 生成5个单次下载激活码
single_keys = generator.generate_key("single", 5)
print("单次下载激活码:", single_keys)

# 生成3个批量下载激活码
batch_keys = generator.generate_key("batch", 3)
print("批量下载激活码:", batch_keys)

# 查看统计
stats = generator.get_stats()
print(stats)
```

## 使用激活码

### 在Web界面中使用

1. 访问下载器网站
2. 在"激活码"输入框中输入激活码
3. 根据下载模式选择对应类型的激活码：
   - **单次下载**：使用 S- 开头的激活码
   - **批量下载**：使用 B- 开头的激活码
4. 填写其他必要信息（Token、Cookies、公众号/文章链接等）
5. 点击"开始下载"

### 激活码验证规则

- 激活码格式必须正确：`[S|B]-XXXX-XXXX-XXXX-XXXX`
- 下载模式与激活码类型必须匹配：
  - 单次下载 → S- 激活码
  - 批量下载/日期范围下载 → B- 激活码
- 每个激活码只能使用一次
- 激活码使用后会自动标记为已使用

## 激活码管理

### 查看所有激活码

```python
from activation_key_generator import ActivationKeyGenerator

generator = ActivationKeyGenerator()

# 查看所有未使用的激活码
unused_keys = generator.list_keys(show_used=False)
for key in unused_keys:
    print(f"{key['key']} - {key['type']} - 创建于 {key['created_at']}")

# 查看所有激活码（包括已使用）
all_keys = generator.list_keys(show_used=True)
```

### 验证激活码

```python
# 验证单次下载激活码
is_valid = generator.verify_key("S-1234-5678-9ABC-DEF0", "single")

# 验证批量下载激活码
is_valid = generator.verify_key("B-1234-5678-9ABC-DEF0", "batch")
```

### 查看统计信息

```python
stats = generator.get_stats()
print(f"单次下载激活码: {stats['single']['unused']} 可用 / {stats['single']['total']} 总数")
print(f"批量下载激活码: {stats['batch']['unused']} 可用 / {stats['batch']['total']} 总数")
```

## 激活码存储

- 激活码保存在 `activation_keys.json` 文件中
- 包含以下信息：
  - `key`: 激活码
  - `type`: 类型（single/batch）
  - `created_at`: 创建时间
  - `used`: 是否已使用
  - `used_at`: 使用时间

示例：
```json
{
  "single": [
    {
      "key": "S-A1B2-C3D4-E5F6-7890",
      "type": "single",
      "created_at": "2026-02-01 12:00:00",
      "used": false,
      "used_at": null
    }
  ],
  "batch": [
    {
      "key": "B-1234-5678-9ABC-DEF0",
      "type": "batch",
      "created_at": "2026-02-01 12:05:00",
      "used": true,
      "used_at": "2026-02-01 13:30:00"
    }
  ]
}
```

## 常见问题

### Q: 激活码无效或已被使用
A: 请确认：
1. 激活码格式正确
2. 激活码类型与下载模式匹配
3. 激活码未被使用过
4. 检查 `activation_keys.json` 确认激活码存在且未标记为已使用

### Q: 如何批量生成激活码？
A: 使用命令行工具或代码指定生成数量：
```bash
python activation_key_generator.py
# 选择选项1或2，输入数量
```

### Q: 如何重置已使用的激活码？
A: 手动编辑 `activation_keys.json`，将对应激活码的 `used` 字段改为 `false`，`used_at` 改为 `null`。

### Q: 激活码丢失了怎么办？
A: 查看 `activation_keys.json` 文件，里面保存了所有生成的激活码。

## 安全建议

1. 妥善保管 `activation_keys.json` 文件
2. 定期备份激活码文件
3. 不要公开分享激活码
4. 建议为不同用户生成不同的激活码
5. 定期清理已使用的激活码记录

## 快速上手示例

```bash
# 1. 生成10个单次下载激活码和5个批量下载激活码
python activation_key_generator.py

# 2. 在交互界面中：
#    - 选择 1，输入 10
#    - 选择 2，输入 5
#    - 选择 3 查看生成的激活码

# 3. 将激活码分发给用户

# 4. 用户在Web界面输入激活码使用
```

## 技术细节

- 激活码使用 SHA256 哈希生成，确保唯一性
- 使用 Python secrets 模块生成加密安全的随机数
- 激活码验证在后端进行，防止前端绕过
- 激活码使用后立即标记，防止重复使用
