# -*- coding: utf-8 -*-
"""
图书推荐系统 - Flask后端服务

功能：
1. 提供图书列表API
2. 提供图书详情API
3. 提供推荐API（集成跨领域推荐算法）
4. 提供多目标排序功能

作者：四人小组
日期：2026-03-25
"""

import os
import sys
import json
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

from sqlalchemy import create_engine, text
import pandas as pd

from app.services.recommender import CrossDomainRecommender
from app.services.ranker import MultiObjectiveRanker

app = Flask(__name__)
CORS(app)

app.config['JSON_AS_ASCII'] = False

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def safe_json_loads(value, default=None):
    """安全的JSON解析函数"""
    if default is None:
        default = []
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_db_engine():
    config = load_config()
    db_config = config['database']
    connection_str = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}?charset=utf8mb4"
    return create_engine(connection_str)

# 缓存推荐器实例
_recommender_instance = None
_ranker_instance = None

def get_recommender():
    global _recommender_instance, _ranker_instance
    
    if _recommender_instance is None or _ranker_instance is None:
        config = load_config()
        db_config = config['database']
        rec_config = config.get('recommender', {'alpha': 0.4, 'a': 0.6, 'beta': 0.25})
        
        _recommender_instance = CrossDomainRecommender(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            table=db_config.get('table', 'books'),
            alpha=rec_config.get('alpha', 0.4),
            a=rec_config.get('a', 0.6),
            beta=rec_config.get('beta', 0.25)
        )
        
        _ranker_instance = MultiObjectiveRanker()
    
    return _recommender_instance, _ranker_instance

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/books', methods=['GET'])
def get_books():
    try:
        engine = get_db_engine()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '')
        sort_mode = request.args.get('sort_mode', 'comprehensive')
        
        offset = (page - 1) * per_page
        
        order_by = "book_id"
        if sort_mode == 'rating':
            order_by = "rating DESC"
        elif sort_mode == 'newest':
            order_by = "publication_date DESC"
        
        with engine.connect() as conn:
            if search:
                query = text(f"""
                    SELECT book_id, title, authors, publisher, publication_date, rating, 
                           cover_image, book_intro, domain_tags
                    FROM books 
                    WHERE title LIKE :search OR authors LIKE :search
                    ORDER BY {order_by}
                    LIMIT :limit OFFSET :offset
                """)
                result = conn.execute(query, {
                    'search': f'%{search}%',
                    'limit': per_page,
                    'offset': offset
                })
                
                count_query = text("SELECT COUNT(*) FROM books WHERE title LIKE :search OR authors LIKE :search")
                total = conn.execute(count_query, {'search': f'%{search}%'}).scalar()
            else:
                query = text(f"""
                    SELECT book_id, title, authors, publisher, publication_date, rating, 
                           cover_image, book_intro, domain_tags
                    FROM books 
                    ORDER BY {order_by}
                    LIMIT :limit OFFSET :offset
                """)
                result = conn.execute(query, {'limit': per_page, 'offset': offset})
                
                count_query = text("SELECT COUNT(*) FROM books")
                total = conn.execute(count_query).scalar()
            
            books = []
            for row in result:
                book = {
                    'book_id': row[0],
                    'title': row[1],
                    'authors': json.loads(row[2]) if row[2] else [],
                    'publisher': row[3],
                    'publication_date': str(row[4]) if row[4] else None,
                    'rating': row[5],
                    'cover_image': row[6],
                    'book_intro': row[7],
                    'domain_tags': json.loads(row[8]) if row[8] else []
                }
                books.append(book)
        
        return jsonify({
            'success': True,
            'data': {
                'books': books,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/books/<int:book_id>', methods=['GET'])
def get_book_detail(book_id):
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            query = text("""
                SELECT book_id, title, authors, publisher, publication_date, rating,
                       cover_image, book_intro, author_intro, URL, domain_tags,
                       keywords, also_like, short_reviews, reviews
                FROM books WHERE book_id = :book_id
            """)
            result = conn.execute(query, {'book_id': book_id})
            row = result.fetchone()
            
            if not row:
                return jsonify({'success': False, 'error': '图书不存在'}), 404
            
            book = {
                'book_id': row[0],
                'title': row[1],
                'authors': safe_json_loads(row[2]),
                'publisher': row[3],
                'publication_date': str(row[4]) if row[4] else None,
                'rating': row[5],
                'cover_image': row[6],
                'book_intro': row[7],
                'author_intro': row[8],
                'URL': row[9],
                'domain_tags': safe_json_loads(row[10]),
                'keywords': safe_json_loads(row[11]),
                'also_like': safe_json_loads(row[12]),
                'short_reviews': safe_json_loads(row[13]),
                'reviews': safe_json_loads(row[14])
            }
        
        return jsonify({'success': True, 'data': book})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recommend/<int:book_id>', methods=['GET'])
def get_recommendations(book_id):
    try:
        recommender, ranker = get_recommender()
        
        top_k = int(request.args.get('top_k', 10))
        sort_mode = request.args.get('sort_mode', 'comprehensive')
        cross_domain = request.args.get('cross_domain', 'false').lower() == 'true'
        beta_str = request.args.get('beta', None)
        beta = float(beta_str) if beta_str else None
        
        app.logger.info(f"[推荐API] book_id={book_id}, top_k={top_k}, sort_mode={sort_mode}, cross_domain={cross_domain}, beta={beta}")
        
        if cross_domain:
            recommendations = recommender.get_cross_domain_recommendations(book_id, top_k=top_k * 2, beta=beta)
        else:
            recommendations = recommender.get_recommendations(book_id, top_k=top_k * 2, beta=beta)
        
        app.logger.info(f"[推荐API] 获取到 {len(recommendations)} 条候选推荐")
        
        engine = get_db_engine()
        with engine.connect() as conn:
            for rec in recommendations:
                query = text("SELECT rating, publication_date, cover_image, publisher FROM books WHERE book_id = :book_id")
                result = conn.execute(query, {'book_id': rec['book_id']})
                row = result.fetchone()
                if row:
                    rec['rating'] = row[0]
                    rec['publication_date'] = str(row[1]) if row[1] else None
                    rec['cover_image'] = row[2]
                    rec['publisher'] = row[3]
        
        for rec in recommendations:
            rating = rec.get('rating', 0) or 0
            pub_date_str = rec.get('publication_date', '')
            normalized_rating = rating / 10.0 if rating else 0.0
            normalized_freshness = 0.0
            if pub_date_str:
                try:
                    from datetime import datetime
                    pub_date = datetime.strptime(pub_date_str[:10], '%Y-%m-%d')
                    years_old = (datetime.now() - pub_date).days / 365.25
                    normalized_freshness = max(0.0, 1.0 - years_old / 30.0)
                except:
                    pass
            
            w_sim = 0.7
            w_rating = 0.2
            w_fresh = 0.1
            
            combined_sim = rec.get('combined_similarity', 0) or 0
            overlap_coeff = rec.get('overlap_coefficient', 1) or 1
            
            similarity_score = combined_sim * overlap_coeff
            utility_score = w_sim * similarity_score + w_rating * normalized_rating + w_fresh * normalized_freshness
            
            rec['similarity_score'] = similarity_score
            rec['utility_score'] = utility_score
            rec['normalized_rating'] = normalized_rating
            rec['normalized_freshness'] = normalized_freshness
        
        sorted_recommendations = ranker.sort_recommendations(recommendations, sort_mode)
        final_recs = sorted_recommendations[:top_k]
        
        domain_distribution = {}
        for rec in final_recs:
            for tag in rec.get('domain_tags', []):
                domain_distribution[tag] = domain_distribution.get(tag, 0) + 1
        
        app.logger.info(f"[推荐API] 最终返回 {len(final_recs)} 条推荐, 领域分布: {domain_distribution}")
        
        return jsonify({
            'success': True,
            'data': {
                'recommendations': final_recs,
                'source_book_id': book_id,
                'sort_mode': sort_mode,
                'cross_domain': cross_domain,
                'domain_distribution': domain_distribution,
                'total_candidates': len(recommendations),
                'beta': beta if beta else recommender.beta
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        app.logger.error(f"[推荐API] 错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sort-modes', methods=['GET'])
def get_sort_modes():
    try:
        ranker = MultiObjectiveRanker()
        modes = ranker.get_supported_sort_modes()
        return jsonify({'success': True, 'data': modes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            total_books = conn.execute(text("SELECT COUNT(*) FROM books")).scalar()
            avg_rating = conn.execute(text("SELECT AVG(rating) FROM books WHERE rating IS NOT NULL")).scalar()
            
            domain_query = text("SELECT domain_tags FROM books WHERE domain_tags IS NOT NULL AND domain_tags != '[]'")
            result = conn.execute(domain_query)
            all_tags = set()
            for row in result:
                tags = json.loads(row[0])
                all_tags.update(tags)
            
            total_domains = len(all_tags)
        
        return jsonify({
            'success': True,
            'data': {
                'total_books': total_books,
                'avg_rating': round(avg_rating, 2) if avg_rating else 0,
                'total_domains': total_domains
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def preload_recommender():
    """预加载推荐器数据"""
    print("正在预加载推荐器数据，请稍候...")
    try:
        recommender, ranker = get_recommender()
        print(f"推荐器数据加载完成！共加载 {len(recommender.books_data)} 本图书")
    except Exception as e:
        print(f"预加载推荐器数据失败: {e}")

if __name__ == '__main__':
    # 预加载推荐器数据
    preload_recommender()
    
    config = load_config()
    server_config = config.get('server', {})
    app.run(
        host=server_config.get('host', '0.0.0.0'),
        port=server_config.get('port', 5000),
        debug=server_config.get('debug', True)
    )
