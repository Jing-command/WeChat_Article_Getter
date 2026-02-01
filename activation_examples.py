"""
激活码系统使用示例
展示如何通过代码管理激活码
"""

from activation_key_generator import ActivationKeyGenerator

def example_1_generate_keys():
    """示例1：生成激活码"""
    print("\n" + "="*60)
    print("示例1：生成激活码")
    print("="*60)
    
    generator = ActivationKeyGenerator()
    
    # 生成单次下载激活码
    print("\n生成 3 个单次下载激活码:")
    single_keys = generator.generate_key("single", 3)
    for i, key in enumerate(single_keys, 1):
        print(f"  {i}. {key}")
    
    # 生成批量下载激活码
    print("\n生成 2 个批量下载激活码:")
    batch_keys = generator.generate_key("batch", 2)
    for i, key in enumerate(batch_keys, 1):
        print(f"  {i}. {key}")


def example_2_verify_keys():
    """示例2：验证激活码"""
    print("\n" + "="*60)
    print("示例2：验证激活码")
    print("="*60)
    
    generator = ActivationKeyGenerator()
    
    # 假设这些激活码已存在
    test_keys = [
        ("S-92A0-30A0-46E5-F35D", "single"),
        ("B-F763-C5D7-2338-B7BA", "batch"),
        ("S-XXXX-XXXX-XXXX-XXXX", "single"),  # 不存在的
    ]
    
    for key, key_type in test_keys:
        is_valid = generator.verify_key(key, key_type)
        type_name = "单次下载" if key_type == "single" else "批量下载"
        status = "✅ 有效" if is_valid else "❌ 无效"
        print(f"{key} ({type_name}): {status}")


def example_3_list_keys():
    """示例3：列出所有激活码"""
    print("\n" + "="*60)
    print("示例3：列出所有激活码")
    print("="*60)
    
    generator = ActivationKeyGenerator()
    
    # 列出未使用的激活码
    print("\n未使用的激活码:")
    unused_keys = generator.list_keys(show_used=False)
    
    if not unused_keys:
        print("  (暂无)")
    else:
        for key_info in unused_keys[:5]:  # 只显示前5个
            type_name = "单次" if key_info['type'] == 'single' else "批量"
            print(f"  {key_info['key']} ({type_name}) - {key_info['created_at']}")
        
        if len(unused_keys) > 5:
            print(f"  ... 还有 {len(unused_keys) - 5} 个")


def example_4_stats():
    """示例4：查看统计信息"""
    print("\n" + "="*60)
    print("示例4：查看统计信息")
    print("="*60)
    
    generator = ActivationKeyGenerator()
    stats = generator.get_stats()
    
    print("\n📊 激活码统计:")
    print(f"  单次下载:")
    print(f"    - 总数: {stats['single']['total']}")
    print(f"    - 已使用: {stats['single']['used']}")
    print(f"    - 可用: {stats['single']['unused']}")
    
    print(f"\n  批量下载:")
    print(f"    - 总数: {stats['batch']['total']}")
    print(f"    - 已使用: {stats['batch']['used']}")
    print(f"    - 可用: {stats['batch']['unused']}")


def example_5_mark_as_used():
    """示例5：手动标记激活码为已使用"""
    print("\n" + "="*60)
    print("示例5：标记激活码为已使用")
    print("="*60)
    
    generator = ActivationKeyGenerator()
    
    # 获取一个未使用的激活码
    unused_keys = generator.list_keys(show_used=False)
    if unused_keys:
        test_key = unused_keys[0]['key']
        print(f"\n标记激活码: {test_key}")
        
        # 标记为已使用
        success = generator.mark_as_used(test_key)
        
        if success:
            print("✅ 标记成功")
        else:
            print("❌ 标记失败")
    else:
        print("\n没有可用的激活码进行测试")


def example_6_complete_workflow():
    """示例6：完整工作流程"""
    print("\n" + "="*60)
    print("示例6：完整工作流程")
    print("="*60)
    
    generator = ActivationKeyGenerator()
    
    # 1. 生成激活码
    print("\n步骤1: 生成激活码")
    keys = generator.generate_key("single", 1)
    new_key = keys[0]
    print(f"  生成的激活码: {new_key}")
    
    # 2. 验证激活码
    print("\n步骤2: 验证激活码")
    is_valid = generator.verify_key(new_key, "single")
    print(f"  验证结果: {'✅ 有效' if is_valid else '❌ 无效'}")
    
    # 3. 模拟使用（标记为已使用）
    print("\n步骤3: 使用激活码（下载完成）")
    generator.mark_as_used(new_key)
    print(f"  激活码已标记为已使用")
    
    # 4. 再次验证（应该失败）
    print("\n步骤4: 再次验证（应该失败）")
    is_valid = generator.verify_key(new_key, "single")
    print(f"  验证结果: {'✅ 有效' if is_valid else '❌ 无效（已使用）'}")


def main():
    """运行所有示例"""
    print("\n" + "="*60)
    print("激活码系统 - 使用示例集合")
    print("="*60)
    
    example_1_generate_keys()
    example_2_verify_keys()
    example_3_list_keys()
    example_4_stats()
    # example_5_mark_as_used()  # 会修改数据，慎用
    # example_6_complete_workflow()  # 会生成新数据
    
    print("\n" + "="*60)
    print("示例运行完成！")
    print("="*60)


if __name__ == "__main__":
    main()
