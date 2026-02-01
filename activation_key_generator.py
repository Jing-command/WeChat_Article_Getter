"""
激活码生成器
用于生成单次下载和批量下载的激活码
"""

import secrets
import hashlib
import json
import os
from datetime import datetime

class ActivationKeyGenerator:
    """激活码生成器"""
    
    def __init__(self, keys_file="activation_keys.json"):
        self.keys_file = keys_file
        self.keys_data = self.load_keys()
    
    def load_keys(self):
        """加载已生成的激活码"""
        if os.path.exists(self.keys_file):
            with open(self.keys_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"single": [], "batch": []}
    
    def save_keys(self):
        """保存激活码到文件"""
        with open(self.keys_file, 'w', encoding='utf-8') as f:
            json.dump(self.keys_data, f, indent=2, ensure_ascii=False)
    
    def generate_key(self, key_type: str, count: int = 1):
        """
        生成激活码
        
        Args:
            key_type: 激活码类型 ('single' 或 'batch')
            count: 生成数量
        
        Returns:
            list: 生成的激活码列表
        """
        if key_type not in ['single', 'batch']:
            raise ValueError("key_type 必须是 'single' 或 'batch'")
        
        keys = []
        prefix = "S-" if key_type == "single" else "B-"
        
        for _ in range(count):
            # 生成随机字节
            random_bytes = secrets.token_bytes(16)
            
            # 使用SHA256哈希并取前16位
            hash_obj = hashlib.sha256(random_bytes)
            hash_hex = hash_obj.hexdigest()[:16].upper()
            
            # 格式化为 XXXX-XXXX-XXXX-XXXX
            formatted_key = f"{prefix}{hash_hex[0:4]}-{hash_hex[4:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}"
            
            # 添加到数据
            key_info = {
                "key": formatted_key,
                "type": key_type,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "used": False,
                "used_at": None
            }
            
            keys.append(formatted_key)
            self.keys_data[key_type].append(key_info)
        
        self.save_keys()
        return keys
    
    def verify_key(self, key: str, key_type: str):
        """
        验证激活码
        
        Args:
            key: 要验证的激活码
            key_type: 期望的类型 ('single' 或 'batch')
        
        Returns:
            bool: 是否有效
        """
        for key_info in self.keys_data[key_type]:
            if key_info["key"] == key and not key_info["used"]:
                return True
        return False
    
    def mark_as_used(self, key: str):
        """标记激活码为已使用"""
        for key_type in ['single', 'batch']:
            for key_info in self.keys_data[key_type]:
                if key_info["key"] == key:
                    key_info["used"] = True
                    key_info["used_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.save_keys()
                    return True
        return False
    
    def list_keys(self, key_type: str = None, show_used: bool = False):
        """
        列出激活码
        
        Args:
            key_type: 类型筛选 ('single', 'batch' 或 None 表示全部)
            show_used: 是否显示已使用的激活码
        
        Returns:
            list: 激活码信息列表
        """
        result = []
        
        types_to_check = [key_type] if key_type else ['single', 'batch']
        
        for ktype in types_to_check:
            for key_info in self.keys_data.get(ktype, []):
                if show_used or not key_info["used"]:
                    result.append(key_info)
        
        return result
    
    def get_stats(self):
        """获取统计信息"""
        stats = {
            "single": {
                "total": len(self.keys_data.get("single", [])),
                "used": sum(1 for k in self.keys_data.get("single", []) if k["used"]),
                "unused": sum(1 for k in self.keys_data.get("single", []) if not k["used"])
            },
            "batch": {
                "total": len(self.keys_data.get("batch", [])),
                "used": sum(1 for k in self.keys_data.get("batch", []) if k["used"]),
                "unused": sum(1 for k in self.keys_data.get("batch", []) if not k["used"])
            }
        }
        return stats


def main():
    """命令行界面"""
    generator = ActivationKeyGenerator()
    
    while True:
        print("\n" + "="*50)
        print("微信文章下载器 - 激活码生成器")
        print("="*50)
        
        # 显示统计
        stats = generator.get_stats()
        print(f"\n📊 当前统计:")
        print(f"  单次下载激活码: {stats['single']['unused']} 可用 / {stats['single']['total']} 总数")
        print(f"  批量下载激活码: {stats['batch']['unused']} 可用 / {stats['batch']['total']} 总数")
        
        print("\n请选择操作:")
        print("  1. 生成单次下载激活码")
        print("  2. 生成批量下载激活码")
        print("  3. 查看所有激活码")
        print("  4. 验证激活码")
        print("  5. 退出")
        
        choice = input("\n请输入选项 (1-5): ").strip()
        
        if choice == "1":
            count = int(input("生成数量: "))
            keys = generator.generate_key("single", count)
            print(f"\n✅ 成功生成 {count} 个单次下载激活码:")
            for key in keys:
                print(f"  {key}")
        
        elif choice == "2":
            count = int(input("生成数量: "))
            keys = generator.generate_key("batch", count)
            print(f"\n✅ 成功生成 {count} 个批量下载激活码:")
            for key in keys:
                print(f"  {key}")
        
        elif choice == "3":
            show_used = input("是否显示已使用的激活码? (y/n): ").strip().lower() == 'y'
            keys = generator.list_keys(show_used=show_used)
            
            if not keys:
                print("\n暂无激活码")
            else:
                print(f"\n{'='*80}")
                print(f"{'激活码':<30} {'类型':<10} {'状态':<10} {'创建时间':<20}")
                print(f"{'='*80}")
                for key_info in keys:
                    key_type_name = "单次下载" if key_info['type'] == 'single' else "批量下载"
                    status = "已使用" if key_info['used'] else "未使用"
                    print(f"{key_info['key']:<30} {key_type_name:<10} {status:<10} {key_info['created_at']:<20}")
                print(f"{'='*80}")
        
        elif choice == "4":
            key = input("请输入要验证的激活码: ").strip()
            
            # 判断类型
            if key.startswith("S-"):
                key_type = "single"
                type_name = "单次下载"
            elif key.startswith("B-"):
                key_type = "batch"
                type_name = "批量下载"
            else:
                print("❌ 无效的激活码格式")
                continue
            
            if generator.verify_key(key, key_type):
                print(f"✅ 激活码有效 (类型: {type_name})")
            else:
                print("❌ 激活码无效或已被使用")
        
        elif choice == "5":
            print("\n再见！")
            break
        
        else:
            print("❌ 无效选项，请重新选择")


if __name__ == "__main__":
    main()
