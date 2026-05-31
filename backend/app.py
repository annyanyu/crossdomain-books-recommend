# -*- coding: utf-8 -*-
"""
图书推荐系统 - Flask后端服务

功能：
1. 提供图书列表API
2. 提供图书详情API
3. 提供推荐API（集成跨领域推荐算法）
4. 提供多目标排序功能
5. 提供推荐理由生成API（集成LLM）

作者：四人小组
日期：2026-03-25
"""

import os
import sys
import json
import logging
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

from sqlalchemy import create_engine, text
import pandas as pd

from app.services.recommender import CrossDomainRecommender
from app.services.ranker import MultiObjectiveRanker
from app.services.llm_service import create_llm_service, get_cached_reason, TemplateLLM
from app.services.douban_scraper import DoubanScraper
from app.services.book_processor import BookProcessor
from app.services.also_like_mapper import AlsoLikeMapper

app = Flask(__name__)
CORS(app)

app.config['JSON_AS_ASCII'] = False

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def safe_json_loads(value, default=None):
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

_recommender_instance = None
_ranker_instance = None
_llm_service_instance = None
_book_processor_instance = None
_douban_scraper_instance = None

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

def get_llm_service():
    global _llm_service_instance
    
    if _llm_service_instance is None:
        config = load_config()
        llm_config = config.get('llm', {})
        _llm_service_instance = create_llm_service(llm_config)
        logger.info(f"[LLM服务] 初始化完成, provider={llm_config.get('provider', 'template')}")
    
    return _llm_service_instance

def get_book_processor():
    global _book_processor_instance

    if _book_processor_instance is None:
        config = load_config()
        db_config = config['database']
        _book_processor_instance = BookProcessor(db_config)

    return _book_processor_instance

def get_douban_scraper():
    global _douban_scraper_instance

    if _douban_scraper_instance is None:
        _douban_scraper_instance = DoubanScraper(timeout=15, max_retries=3)

    return _douban_scraper_instance

def _check_duplicate(book_data: dict, engine) -> tuple:
    """
    检查书籍是否已存在
    返回: (是否重复, 已有book_id或None)
    """
    with engine.connect() as conn:
        if book_data.get('URL'):
            result = conn.execute(
                text("SELECT book_id FROM books WHERE URL = :url LIMIT 1"),
                {'url': book_data['URL']}
            ).fetchone()
            if result:
                return True, result[0]

        if book_data.get('title') and book_data.get('authors'):
            authors_json = json.dumps(book_data['authors'], ensure_ascii=False)
            result = conn.execute(
                text("SELECT book_id FROM books WHERE title = :title AND authors = :authors LIMIT 1"),
                {'title': book_data['title'], 'authors': authors_json}
            ).fetchone()
            if result:
                return True, result[0]

    return False, None

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
                'beta': beta if beta else recommender.beta,
                'has_reason_support': True
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        app.logger.error(f"[推荐API] 错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recommend-reason', methods=['POST'])
def get_recommend_reason():
    """
    推荐理由生成API
    
    请求体:
    {
        "source_book_id": 1,
        "recommended_book_id": 2,
        "similarity_data": {
            "semantic_similarity": 0.85,
            "keyword_similarity": 0.72,
            "overlap_count": 1,
            "overlap_coefficient": 0.75,
            "combined_similarity": 0.80
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': '请求体不能为空'}), 400
        
        source_book_id = data.get('source_book_id')
        recommended_book_id = data.get('recommended_book_id')
        similarity_data = data.get('similarity_data', {})
        beta = data.get('beta', 0.25)
        
        if not source_book_id or not recommended_book_id:
            return jsonify({'success': False, 'error': '缺少source_book_id或recommended_book_id'}), 400
        
        logger.info(f"[推荐理由API] source_book_id={source_book_id}, recommended_book_id={recommended_book_id}, beta={beta}")
        
        engine = get_db_engine()
        source_book = None
        recommended_book = None
        
        with engine.connect() as conn:
            query = text("""
                SELECT book_id, title, authors, domain_tags, book_intro, keywords, rating
                FROM books WHERE book_id = :book_id
            """)
            
            result = conn.execute(query, {'book_id': source_book_id})
            row = result.fetchone()
            if row:
                source_book = {
                    'book_id': row[0],
                    'title': row[1],
                    'authors': safe_json_loads(row[2]),
                    'domain_tags': safe_json_loads(row[3]),
                    'book_intro': row[4] or '',
                    'keywords': safe_json_loads(row[5]),
                    'rating': row[6]
                }
            
            result = conn.execute(query, {'book_id': recommended_book_id})
            row = result.fetchone()
            if row:
                recommended_book = {
                    'book_id': row[0],
                    'title': row[1],
                    'authors': safe_json_loads(row[2]),
                    'domain_tags': safe_json_loads(row[3]),
                    'book_intro': row[4] or '',
                    'keywords': safe_json_loads(row[5]),
                    'rating': row[6]
                }
        
        if not source_book:
            return jsonify({'success': False, 'error': f'源图书不存在: book_id={source_book_id}'}), 404
        if not recommended_book:
            return jsonify({'success': False, 'error': f'推荐图书不存在: book_id={recommended_book_id}'}), 404
        
        llm_service = get_llm_service()
        
        try:
            reason = get_cached_reason(
                source_book_id=source_book_id,
                recommended_book_id=recommended_book_id,
                beta=beta,
                llm_service=llm_service,
                source_book=source_book,
                recommended_book=recommended_book,
                similarity_data=similarity_data
            )
            
            is_fallback = isinstance(llm_service, TemplateLLM)
            
            logger.info(f"[推荐理由API] 生成成功 | 源书:《{source_book['title']}》→ 推荐书:《{recommended_book['title']}》| 降级:{is_fallback}")
            
            return jsonify({
                'success': True,
                'data': {
                    'reason': reason,
                    'source_book_id': source_book_id,
                    'recommended_book_id': recommended_book_id,
                    'is_fallback': is_fallback
                }
            })
        except Exception as llm_error:
            logger.warning(f"[推荐理由API] LLM调用失败，尝试降级: {llm_error}")
            
            config = load_config()
            fallback_provider = config.get('llm', {}).get('fallback_provider', 'template')
            
            if fallback_provider == 'template':
                fallback_service = TemplateLLM()
                reason = fallback_service.generate_reason(source_book, recommended_book, similarity_data)
                
                logger.info(f"[推荐理由API] 降级生成成功 | 源书:《{source_book['title']}》→ 推荐书:《{recommended_book['title']}》")
                
                return jsonify({
                    'success': True,
                    'data': {
                        'reason': reason,
                        'source_book_id': source_book_id,
                        'recommended_book_id': recommended_book_id,
                        'is_fallback': True
                    }
                })
            else:
                raise llm_error
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"[推荐理由API] 错误: {e}")
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

@app.route('/api/books/add', methods=['POST'])
def add_book():
    """新书添加API：豆瓣URL爬取 → 数据处理 → 入库 → 更新推荐索引"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求数据为空'}), 400

        douban_url = data.get('douban_url', '').strip()
        if not douban_url:
            return jsonify({'success': False, 'error': '请输入豆瓣书籍详情页URL'}), 400

        is_valid, result = DoubanScraper.validate_url(douban_url)
        if not is_valid:
            return jsonify({'success': False, 'error': result}), 400

        logger.info(f"[新书添加] 开始处理: URL={douban_url}")

        scraper = get_douban_scraper()
        book_data = scraper.scrape_book(douban_url)
        logger.info(f"[新书添加] 爬取完成: 《{book_data.get('title')}》")

        engine = get_db_engine()
        is_dup, existing_id = _check_duplicate(book_data, engine)
        if is_dup:
            logger.info(f"[新书添加] 书籍已存在: book_id={existing_id}")
            return jsonify({
                'success': False,
                'error': f'该书籍已在系统中存在（ID: {existing_id}）',
                'existing_book_id': existing_id
            }), 409

        processor = get_book_processor()
        processed_data = processor.process_new_book(book_data)
        logger.info(f"[新书添加] 数据处理完成: 《{processed_data.get('title')}》")

        authors_json = processed_data.get('authors', [])
        if isinstance(authors_json, list):
            authors_json = json.dumps(authors_json, ensure_ascii=False)

        insert_query = text("""
            INSERT INTO books (
                title, cover_image, authors, publisher, publication_date, rating,
                URL, book_intro, also_like,
                keywords, embedding, keywords_embeddings, domain_tags
            ) VALUES (
                :title, :cover_image, :authors, :publisher, :publication_date, :rating,
                :url, :book_intro, :also_like,
                :keywords, :embedding, :keywords_embeddings, :domain_tags
            )
        """)

        insert_params = {
            'title': processed_data.get('title', ''),
            'cover_image': processed_data.get('cover_image'),
            'authors': authors_json,
            'publisher': processed_data.get('publisher'),
            'publication_date': processed_data.get('publication_date'),
            'rating': processed_data.get('rating'),
            'url': processed_data.get('URL'),
            'book_intro': processed_data.get('books_intro'),
            'also_like': json.dumps(processed_data.get('also_like', []), ensure_ascii=False) if isinstance(processed_data.get('also_like'), list) else processed_data.get('also_like', '[]'),
            'keywords': processed_data.get('keywords', '[]'),
            'embedding': processed_data.get('embedding', '[]'),
            'keywords_embeddings': processed_data.get('keywords_embeddings', '[]'),
            'domain_tags': processed_data.get('domain_tags', '[]'),
        }

        with engine.begin() as conn:
            result = conn.execute(insert_query, insert_params)
            new_book_id = result.lastrowid

        logger.info(f"[新书添加] 数据库写入成功: book_id={new_book_id}")

        # 写入 also_like 关系到 book_also_like 表
        # 兼容多种also_like格式：JSON数组、管道符分隔字符串、Python列表
        _also_like_raw = processed_data.get('also_like', [])
        also_like_list = []
        if isinstance(_also_like_raw, list):
            also_like_list = [str(item).strip() for item in _also_like_raw if str(item).strip()]
        elif isinstance(_also_like_raw, str):
            _raw = _also_like_raw.strip()
            if _raw:
                try:
                    _parsed = json.loads(_raw)
                    if isinstance(_parsed, list):
                        also_like_list = [str(item).strip() for item in _parsed if str(item).strip()]
                except (json.JSONDecodeError, TypeError):
                    if '|' in _raw:
                        also_like_list = [name.strip() for name in _raw.split('|') if name.strip()]
                    else:
                        also_like_list = [_raw]
        if also_like_list:
            try:
                mapper = AlsoLikeMapper(engine)
                mapper.build_title_index()
                with engine.begin() as conn:
                    for book_name in also_like_list:
                        match_result = mapper.match_book_name(book_name)
                        conn.execute(
                            text("INSERT INTO book_also_like (source_book_id, target_book_id, target_book_name, match_type, match_score) VALUES (:sid, :tid, :tname, :mtype, :mscore)"),
                            {'sid': new_book_id, 'tid': match_result['target_book_id'], 'tname': book_name, 'mtype': match_result['match_type'], 'mscore': match_result['match_score']}
                        )
                logger.info(f"[新书添加] also_like关系写入: {len(also_like_list)}条")
            except Exception as e:
                logger.warning(f"[新书添加] also_like关系写入失败（不影响数据入库）: {e}")

        try:
            recommender, _ = get_recommender()
            recommender.add_book_to_index({
                'book_id': new_book_id,
                'title': processed_data.get('title', ''),
                'embedding': json.loads(processed_data.get('embedding', '[]')),
                'keywords_embeddings': json.loads(processed_data.get('keywords_embeddings', '[]')),
                'domain_tags': json.loads(processed_data.get('domain_tags', '[]')),
            })
            logger.info(f"[新书添加] 推荐索引更新成功: book_id={new_book_id}")
        except Exception as e:
            logger.warning(f"[新书添加] 推荐索引更新失败（不影响数据入库）: {e}")

        try:
            processor.add_to_corpus_cache(processed_data)
        except Exception as e:
            logger.warning(f"[新书添加] 语料库缓存更新失败: {e}")

        return jsonify({
            'success': True,
            'data': {
                'book_id': new_book_id,
                'title': processed_data.get('title', ''),
                'authors': processed_data.get('authors', []),
                'domain_tags': json.loads(processed_data.get('domain_tags', '[]')),
                'keywords': json.loads(processed_data.get('keywords', '[]'))[:5],
            }
        })

    except ValueError as e:
        logger.warning(f"[新书添加] 参数错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except RuntimeError as e:
        logger.error(f"[新书添加] 运行时错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 422
    except Exception as e:
        logger.error(f"[新书添加] 未知错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'系统错误: {str(e)}'}), 500

def preload_recommender():
    print("正在预加载推荐器数据，请稍候...")
    try:
        recommender, ranker = get_recommender()
        print(f"推荐器数据加载完成！共加载 {len(recommender.books_data)} 本图书")
    except Exception as e:
        print(f"预加载推荐器数据失败: {e}")

if __name__ == '__main__':
    preload_recommender()
    
    config = load_config()
    server_config = config.get('server', {})
    app.run(
        host=server_config.get('host', '0.0.0.0'),
        port=server_config.get('port', 5000),
        debug=server_config.get('debug', True)
    )
