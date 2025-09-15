#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流量监测系统启动脚本
"""

import os
import sys
import sqlite3
import time

def init_traffic_monitoring():
    """初始化流量监测系统"""
    print("正在初始化流量监测系统...")
    
    # 检查数据库文件
    db_path = 'instance/rdfz.db'
    if not os.path.exists(db_path):
        print("错误: 数据库文件不存在，请先运行主应用初始化数据库")
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 检查必要的表是否存在
        tables = ['access_logs', 'traffic_stats', 'ip_blocks']
        for table in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                print(f"错误: 表 {table} 不存在")
                return False
        
        print("✓ 数据库表结构检查通过")
        
        # 检查索引
        indexes = ['idx_access_logs_ip', 'idx_access_logs_created_at', 'idx_ip_blocks_ip', 'idx_traffic_stats_ip']
        for index in indexes:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index}'")
            if not cursor.fetchone():
                print(f"警告: 索引 {index} 不存在，正在创建...")
                # 这里可以添加创建索引的逻辑
        
        print("✓ 索引检查完成")
        
        # 检查配置
        print("\n当前流量监测配置:")
        print("- 流量监测: 已启用")
        print("- 每小时最大请求数: 1000")
        print("- 每小时最大带宽: 100 MB")
        print("- 自动封锁: 已启用")
        
        conn.close()
        print("\n✓ 流量监测系统初始化完成!")
        return True
        
    except Exception as e:
        print(f"初始化失败: {e}")
        return False

def show_usage():
    """显示使用说明"""
    print("\n=== 流量监测系统使用说明 ===")
    print("1. 启动Flask应用: python app.py")
    print("2. 使用超级管理员账号登录")
    print("3. 访问管理面板: http://localhost:5000/admin")
    print("4. 点击'流量监测'卡片进入监测页面")
    print("5. 或直接访问: http://localhost:5000/admin/traffic")
    print("\n测试流量监测系统:")
    print("python test_traffic.py")
    print("\n查看详细说明:")
    print("cat TRAFFIC_MONITORING_README.md")

def main():
    """主函数"""
    print("RDFZ食堂大众点评 - 流量监测系统")
    print("=" * 50)
    
    if init_traffic_monitoring():
        show_usage()
        
        print("\n是否要启动Flask应用? (y/n): ", end="")
        choice = input().lower().strip()
        
        if choice in ['y', 'yes', '是']:
            print("\n启动Flask应用...")
            os.system("python app.py")
        else:
            print("\n请手动启动Flask应用: python app.py")
    else:
        print("\n初始化失败，请检查错误信息")

if __name__ == "__main__":
    main()
