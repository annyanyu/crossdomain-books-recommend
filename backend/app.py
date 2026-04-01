# -*- coding: utf-8 -*-
"""
后端API服务
用于测试数据库连接并提供图书数据
"""

import sys
import os
# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify
from flask_cors import CORS
import pymysql
from config import get_config_manager

app = Flask(__name__)

# 启用CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 加载配置
config = get_config_manager()
db_config = config.get_database_config()

# 数据库连接函数
def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(
        host=db_config['host'],
        port=db_config['port'],
        user=db_config['user'],
        password=db_config['password'],
        database=db_config['database'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route('/api/books', methods=['GET'])
def get_books():
    """获取图书列表"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 查询前10本书
            sql = f"SELECT id, 书名, 作者, 出版社, 出版年, 评分 FROM {db_config['table']} LIMIT 10"
            cursor.execute(sql)
            books = cursor.fetchall()
        conn.close()
        return jsonify({
            'success': True,
            'data': books,
            'message': '获取图书列表成功'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'data': [],
            'message': f'数据库连接失败: {str(e)}'
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    try:
        conn = get_db_connection()
        conn.ping()
        conn.close()
        return jsonify({
            'success': True,
            'message': '数据库连接正常'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'数据库连接失败: {str(e)}'
        })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)