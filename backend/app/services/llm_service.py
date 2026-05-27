# -*- coding: utf-8 -*-
"""
LLM服务模块
支持多后端切换：智谱GLM-4-Flash / DeepSeek / Ollama / 模板降级
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] [%(name)s] %(levelname)s - %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class LLMService(ABC):
    """LLM服务基类"""

    @abstractmethod
    def generate_reason(self, source_book: Dict, recommended_book: Dict,
                        similarity_data: Dict) -> str:
        """
        生成推荐理由

        Args:
            source_book: 源图书信息（用户选中的书）
            recommended_book: 推荐图书信息
            similarity_data: 相似度数据

        Returns:
            推荐理由文本
        """
        pass

    def _build_prompt(self, source_book: Dict, recommended_book: Dict,
                      similarity_data: Dict) -> str:
        source_title = source_book.get('title', '未知')
        source_authors = self._format_authors(source_book.get('authors', []))
        source_domain_tags = self._format_tags(source_book.get('domain_tags', []))
        source_intro = self._truncate_intro(source_book.get('book_intro', ''), 150)

        rec_title = recommended_book.get('title', '未知')
        rec_authors = self._format_authors(recommended_book.get('authors', []))
        rec_domain_tags = self._format_tags(recommended_book.get('domain_tags', []))
        rec_intro = self._truncate_intro(recommended_book.get('book_intro', ''), 150)
        rec_rating = recommended_book.get('rating', '暂无')

        semantic_sim = similarity_data.get('semantic_similarity', 0)
        keyword_sim = similarity_data.get('keyword_similarity', 0)
        overlap_count = similarity_data.get('overlap_count', 0)

        cross_type = "完全跨域" if overlap_count == 0 else "部分跨域"

        prompt = f"""你是一位专业的图书推荐顾问。请根据以下信息，为推荐书籍生成一段简洁的推荐理由（80-120字）。

【用户选中的书籍】
书名：《{source_title}》
作者：{source_authors}
领域：{source_domain_tags}
简介：{source_intro}

【推荐书籍】
书名：《{rec_title}》
作者：{rec_authors}
领域：{rec_domain_tags}
简介：{rec_intro}
评分：{rec_rating}

【关联分析数据】
语义相似度：{semantic_sim:.4f}
关键词相似度：{keyword_sim:.4f}
领域重叠数：{overlap_count}
跨域类型：{cross_type}

请从以下三个角度阐述推荐理由：
1. 推荐书籍的核心内容与价值
2. 两本书之间的知识关联（主题相关性/知识延续/观点互补/场景关联）
3. 对用户的参考价值

要求：语言简洁专业，避免空洞表述，直接点明关联点。"""

        return prompt

    def _format_authors(self, authors) -> str:
        if isinstance(authors, list):
            return '、'.join(authors) if authors else '未知作者'
        if isinstance(authors, str):
            try:
                author_list = json.loads(authors)
                return '、'.join(author_list) if author_list else '未知作者'
            except (json.JSONDecodeError, TypeError):
                return authors if authors else '未知作者'
        return '未知作者'

    def _format_tags(self, tags) -> str:
        if isinstance(tags, list):
            return '、'.join(tags) if tags else '未分类'
        if isinstance(tags, str):
            try:
                tag_list = json.loads(tags)
                return '、'.join(tag_list) if tag_list else '未分类'
            except (json.JSONDecodeError, TypeError):
                return tags if tags else '未分类'
        return '未分类'

    def _truncate_intro(self, intro: str, max_len: int = 150) -> str:
        if not intro:
            return '暂无简介'
        intro = intro.strip().replace('\n', ' ').replace('\r', '')
        if len(intro) > max_len:
            return intro[:max_len] + '...'
        return intro


class ZhipuLLM(LLMService):
    """智谱GLM-4-Flash实现"""

    def __init__(self, api_key: str, base_url: str = "https://open.bigmodel.cn/api/paas/v4",
                 model: str = "glm-4-flash", max_tokens: int = 200,
                 temperature: float = 0.7, timeout: int = 10):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self._client = None
        logger.info(f"[智谱LLM] 初始化: model={model}, base_url={base_url}")

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=self.timeout
                )
                logger.info("[智谱LLM] OpenAI客户端创建成功")
            except ImportError:
                logger.error("[智谱LLM] openai库未安装，请运行: pip install openai")
                raise
        return self._client

    def generate_reason(self, source_book: Dict, recommended_book: Dict,
                        similarity_data: Dict) -> str:
        prompt = self._build_prompt(source_book, recommended_book, similarity_data)

        start_time = time.time()
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位专业的图书推荐顾问，擅长分析书籍间的知识关联并生成简洁有力的推荐理由。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            reason = response.choices[0].message.content.strip()
            elapsed = time.time() - start_time
            logger.info(f"[智谱LLM] 生成成功 | 耗时:{elapsed:.2f}s | 字数:{len(reason)} | "
                        f"源书:《{source_book.get('title', '?')}》→ 推荐书:《{recommended_book.get('title', '?')}》")
            logger.debug(f"[智谱LLM] 生成内容: {reason[:100]}...")
            return reason

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[智谱LLM] 生成失败 | 耗时:{elapsed:.2f}s | 错误:{e}")
            raise


class DeepSeekLLM(LLMService):
    """DeepSeek实现（当前阶段不使用，保留接口）"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com",
                 model: str = "deepseek-chat", max_tokens: int = 200,
                 temperature: float = 0.7, timeout: int = 10):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self._client

    def generate_reason(self, source_book: Dict, recommended_book: Dict,
                        similarity_data: Dict) -> str:
        prompt = self._build_prompt(source_book, recommended_book, similarity_data)
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位专业的图书推荐顾问，擅长分析书籍间的知识关联并生成简洁有力的推荐理由。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
        return response.choices[0].message.content.strip()


class OllamaLLM(LLMService):
    """Ollama本地模型实现"""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "qwen2.5:7b", max_tokens: int = 200,
                 temperature: float = 0.7, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    def generate_reason(self, source_book: Dict, recommended_book: Dict,
                        similarity_data: Dict) -> str:
        import requests

        prompt = self._build_prompt(source_book, recommended_book, similarity_data)

        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一位专业的图书推荐顾问，擅长分析书籍间的知识关联并生成简洁有力的推荐理由。"},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature
                }
            },
            timeout=self.timeout
        )

        result = response.json()
        return result['message']['content'].strip()


class TemplateLLM(LLMService):
    """模板降级实现 — 当LLM API不可用时基于规则生成推荐理由"""

    def generate_reason(self, source_book: Dict, recommended_book: Dict,
                        similarity_data: Dict) -> str:
        source_title = source_book.get('title', '未知')
        rec_title = recommended_book.get('title', '未知')
        rec_authors = self._format_authors(recommended_book.get('authors', []))

        source_tags = source_book.get('domain_tags', [])
        rec_tags = recommended_book.get('domain_tags', [])
        if isinstance(source_tags, str):
            try:
                source_tags = json.loads(source_tags)
            except (json.JSONDecodeError, TypeError):
                source_tags = []
        if isinstance(rec_tags, str):
            try:
                rec_tags = json.loads(rec_tags)
            except (json.JSONDecodeError, TypeError):
                rec_tags = []

        overlap_count = similarity_data.get('overlap_count', 0)
        semantic_sim = similarity_data.get('semantic_similarity', 0)
        keyword_sim = similarity_data.get('keyword_similarity', 0)

        source_tag_str = '、'.join(source_tags[:3]) if source_tags else '综合领域'
        rec_tag_str = '、'.join(rec_tags[:3]) if rec_tags else '综合领域'

        new_domains = set(rec_tags) - set(source_tags)
        new_domain_str = '、'.join(list(new_domains)[:2]) if new_domains else ''

        if overlap_count == 0:
            cross_desc = f"《{rec_title}》属于{rec_tag_str}领域，与您选择的《{source_title}》({source_tag_str})形成完全跨域互补"
            if new_domain_str:
                cross_desc += f"，可拓展您在{new_domain_str}方向的认知"
        elif overlap_count == 1:
            cross_desc = f"《{rec_title}》与《{source_title}》在部分领域存在交集，同时拓展了{rec_tag_str}的新视角"
        else:
            cross_desc = f"《{rec_title}》与《{source_title}》在{source_tag_str}领域有较强关联，可深化该方向理解"

        if semantic_sim > 0.7:
            sim_desc = "两书在语义层面高度相关"
        elif semantic_sim > 0.4:
            sim_desc = "两书在内容层面存在一定关联"
        else:
            sim_desc = "两书提供了不同视角的思考"

        if keyword_sim > 0.5:
            key_desc = "，关键词匹配度较高"
        else:
            key_desc = ""

        reason = f"{cross_desc}。{sim_desc}{key_desc}，推荐阅读以拓宽知识视野。"

        logger.info(f"[模板降级] 生成推荐理由 | 源书:《{source_title}》→ 推荐书:《{rec_title}》| 跨域数:{overlap_count}")
        return reason


def create_llm_service(config: Dict) -> LLMService:
    """
    工厂方法：根据配置创建LLM服务实例

    Args:
        config: llm配置段字典

    Returns:
        LLMService实例
    """
    provider = config.get('provider', 'template')
    logger.info(f"[LLM工厂] 创建LLM服务: provider={provider}")

    if provider == 'zhipu':
        return ZhipuLLM(
            api_key=config.get('api_key', ''),
            base_url=config.get('base_url', 'https://open.bigmodel.cn/api/paas/v4'),
            model=config.get('model', 'glm-4-flash'),
            max_tokens=config.get('max_tokens', 200),
            temperature=config.get('temperature', 0.7),
            timeout=config.get('timeout', 10)
        )
    elif provider == 'deepseek':
        return DeepSeekLLM(
            api_key=config.get('api_key', ''),
            base_url=config.get('base_url', 'https://api.deepseek.com'),
            model=config.get('model', 'deepseek-chat'),
            max_tokens=config.get('max_tokens', 200),
            temperature=config.get('temperature', 0.7),
            timeout=config.get('timeout', 10)
        )
    elif provider == 'ollama':
        return OllamaLLM(
            base_url=config.get('base_url', 'http://localhost:11434'),
            model=config.get('model', 'qwen2.5:7b'),
            max_tokens=config.get('max_tokens', 200),
            temperature=config.get('temperature', 0.7),
            timeout=config.get('timeout', 30)
        )
    else:
        logger.info("[LLM工厂] 使用模板降级方案")
        return TemplateLLM()


_reason_cache = {}


def get_cached_reason(source_book_id: int, recommended_book_id: int,
                      beta: float, llm_service: LLMService,
                      source_book: Dict, recommended_book: Dict,
                      similarity_data: Dict) -> str:
    """
    获取推荐理由（带缓存）

    Args:
        source_book_id: 源图书ID
        recommended_book_id: 推荐图书ID
        beta: beta参数
        llm_service: LLM服务实例
        source_book: 源图书信息
        recommended_book: 推荐图书信息
        similarity_data: 相似度数据

    Returns:
        推荐理由文本
    """
    cache_key = f"{source_book_id}_{recommended_book_id}_{beta}"

    if cache_key in _reason_cache:
        logger.info(f"[推荐理由缓存] 命中缓存: {cache_key}")
        return _reason_cache[cache_key]

    reason = llm_service.generate_reason(source_book, recommended_book, similarity_data)
    _reason_cache[cache_key] = reason

    return reason
