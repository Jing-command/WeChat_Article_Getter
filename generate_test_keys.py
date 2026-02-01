"""快速生成测试激活码"""
from activation_key_generator import ActivationKeyGenerator

# 初始化生成器
generator = ActivationKeyGenerator()

print("=" * 60)
print("微信文章下载器 - 激活码快速生成工具")
print("=" * 60)

# 生成单次下载激活码
print("\n正在生成 5 个单次下载激活码...")
single_keys = generator.generate_key("single", 5)
print("\n✅ 单次下载激活码 (S- 开头):")
for i, key in enumerate(single_keys, 1):
    print(f"  {i}. {key}")

# 生成批量下载激活码
print("\n正在生成 5 个批量下载激活码...")
batch_keys = generator.generate_key("batch", 5)
print("\n✅ 批量下载激活码 (B- 开头):")
for i, key in enumerate(batch_keys, 1):
    print(f"  {i}. {key}")

# 显示统计
print("\n" + "=" * 60)
stats = generator.get_stats()
print("📊 激活码统计:")
print(f"  单次下载: {stats['single']['unused']} 可用 / {stats['single']['total']} 总数")
print(f"  批量下载: {stats['batch']['unused']} 可用 / {stats['batch']['total']} 总数")
print("=" * 60)

print("\n✨ 激活码已保存到 activation_keys.json")
print("💡 提示：每个激活码只能使用一次")
