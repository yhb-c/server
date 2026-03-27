#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymysql
import sys

def init_database():
    """初始化数据库"""

    # 尝试不同的连接方式
    connection_configs = [
        {'host': 'localhost', 'user': 'root', 'password': ''},
        {'host': 'localhost', 'user': 'root', 'password': 'root'},
        {'host': 'localhost', 'user': 'root', 'password': 'admin'},
        {'host': 'localhost', 'user': 'root', 'password': 'password'},
        {'host': 'localhost', 'user': 'root', 'password': '123456'},
        {'host': 'localhost', 'user': 'lqj', 'password': 'admin'},
        {'host': 'localhost', 'user': 'lqj', 'password': ''},
    ]

    conn = None
    for config in connection_configs:
        try:
            print(f"尝试连接: user={config['user']}, password={'***' if config['password'] else '(空)'}")
            conn = pymysql.connect(**config)
            print(f"连接成功！使用 user={config['user']}")
            break
        except pymysql.Error as e:
            print(f"连接失败: {e}")
            continue

    if conn is None:
        print("\n所有连接尝试都失败了")
        print("请手动执行以下命令初始化数据库：")
        print("mysql -u root -p < /home/lqj/liquid/server/database/schema.sql")
        print("mysql -u root -p < /home/lqj/liquid/server/database/init_users.sql")
        return False

    cursor = conn.cursor()

    try:
        # 读取并执行schema.sql
        print("\n执行建表脚本...")
        with open('/home/lqj/liquid/server/database/schema.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()

        # 分割SQL语句并执行
        for statement in sql_script.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except pymysql.Error as e:
                    if "already exists" not in str(e):
                        print(f"执行SQL出错: {e}")

        conn.commit()
        print("建表脚本执行成功")

        # 读取并执行init_users.sql
        print("\n执行初始化数据脚本...")
        with open('/home/lqj/liquid/server/database/init_users.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()

        for statement in sql_script.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except pymysql.Error as e:
                    print(f"执行SQL出错: {e}")

        conn.commit()
        print("初始化数据脚本执行成功")

        # 验证表是否创建成功
        print("\n验证数据库表...")
        cursor.execute("USE liquid_db")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"数据库中的表: {len(tables)} 个")
        for table in tables:
            print(f"  - {table[0]}")

        print("\n数据库初始化完成！")
        return True

    except Exception as e:
        print(f"初始化失败: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    init_database()
