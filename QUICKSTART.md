# 激活码系统 - 快速入门指南

## 🚀 5分钟快速开始

### 1️⃣ 生成激活码（管理员操作）

**最快方法 - 运行快速生成脚本：**
```bash
python generate_test_keys.py
```

输出示例：
```
✅ 单次下载激活码 (S- 开头):
  1. S-92A0-30A0-46E5-F35D
  2. S-7D46-DE7C-96D5-005F
  ...

✅ 批量下载激活码 (B- 开头):
  1. B-F763-C5D7-2338-B7BA
  2. B-4A04-F876-E4F0-AFCC
  ...
```

### 2️⃣ 使用激活码（用户操作）

1. 打开网站：https://jing-command.me
2. 在"激活码"输入框输入激活码
3. 填写其他必要信息（Token、Cookies、链接）
4. 点击"开始下载"

**重要规则：**
- 📄 **单次下载** → 使用 `S-` 开头的激活码
- 📦 **批量下载** → 使用 `B-` 开头的激活码
- ⚠️ 每个激活码只能使用一次

---

## 📖 三种生成激活码的方法

### 方法1：快速生成脚本（推荐）
```bash
python generate_test_keys.py
```
一次生成 5个单次 + 5个批量激活码

### 方法2：交互式命令行
```bash
python activation_key_generator.py
```
进入菜单选择操作：
1. 生成单次下载激活码
2. 生成批量下载激活码
3. 查看所有激活码
4. 验证激活码
5. 退出

### 方法3：Python代码
```python
from activation_key_generator import ActivationKeyGenerator

generator = ActivationKeyGenerator()

# 生成单次下载激活码
single_keys = generator.generate_key("single", 10)
print(single_keys)

# 生成批量下载激活码
batch_keys = generator.generate_key("batch", 5)
print(batch_keys)
```

---

## 🔍 常用操作

### 查看所有可用激活码
```python
from activation_key_generator import ActivationKeyGenerator

generator = ActivationKeyGenerator()

# 查看未使用的激活码
unused = generator.list_keys(show_used=False)
for key in unused:
    print(f"{key['key']} - {key['type']}")
```

### 查看统计信息
```python
stats = generator.get_stats()
print(f"单次下载: {stats['single']['unused']} 可用")
print(f"批量下载: {stats['batch']['unused']} 可用")
```

### 验证激活码
```python
is_valid = generator.verify_key("S-92A0-30A0-46E5-F35D", "single")
print("有效" if is_valid else "无效")
```

---

## ⚠️ 注意事项

1. **激活码格式**：`[S|B]-XXXX-XXXX-XXXX-XXXX`
2. **类型匹配**：单次用S-，批量用B-
3. **一次性使用**：激活码使用后自动失效
4. **数据保存**：所有激活码保存在 `activation_keys.json`
5. **备份建议**：定期备份 `activation_keys.json` 文件

---

## 🎯 使用示例

### 场景1：为10个用户生成单次下载激活码
```bash
python activation_key_generator.py
# 选择 1，输入 10
```

### 场景2：为5个VIP用户生成批量下载激活码
```bash
python activation_key_generator.py
# 选择 2，输入 5
```

### 场景3：检查某个激活码是否还能用
```bash
python activation_key_generator.py
# 选择 4，输入激活码
```

---

## 💡 快速命令参考

| 操作 | 命令 |
|------|------|
| 快速生成测试激活码 | `python generate_test_keys.py` |
| 交互式管理 | `python activation_key_generator.py` |
| 查看使用示例 | `python activation_examples.py` |
| 查看详细文档 | 阅读 `ACTIVATION_KEY_GUIDE.md` |
| 启动Web服务 | `python web_app.py` |

---

## 📞 故障排除

### 问题：激活码无效
**检查清单：**
- [ ] 格式是否正确（X-XXXX-XXXX-XXXX-XXXX）
- [ ] 类型是否匹配（单次用S-，批量用B-）
- [ ] 是否已被使用（查看 activation_keys.json）

### 问题：如何重置激活码
编辑 `activation_keys.json`，找到对应激活码：
```json
{
  "key": "S-XXXX-XXXX-XXXX-XXXX",
  "used": false,        ← 改为 false
  "used_at": null       ← 改为 null
}
```

---

## 📦 文件说明

```
activation_key_generator.py     # 核心生成器模块
generate_test_keys.py           # 快速生成脚本
activation_examples.py          # 使用示例代码
activation_keys.json            # 激活码存储（自动生成）
ACTIVATION_KEY_GUIDE.md         # 详细文档
ACTIVATION_IMPLEMENTATION_SUMMARY.md  # 实现总结
```

---

## ✅ 测试清单

- [x] 生成单次下载激活码
- [x] 生成批量下载激活码
- [x] 在Web界面输入激活码
- [x] 验证单次下载（S-激活码）
- [x] 验证批量下载（B-激活码）
- [x] 测试类型不匹配时的错误提示
- [x] 测试激活码使用后不能重复使用
- [x] 测试格式错误时的提示

---

**快速链接：**
- 📚 [详细使用文档](ACTIVATION_KEY_GUIDE.md)
- 📝 [实现总结](ACTIVATION_IMPLEMENTATION_SUMMARY.md)
- 🌐 [网站地址](https://jing-command.me)

**需要帮助？** 查看文档或运行 `python activation_examples.py` 查看示例。
