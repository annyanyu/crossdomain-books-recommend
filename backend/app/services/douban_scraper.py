# -*- coding: utf-8 -*-
"""
豆瓣书籍数据爬取模块
从豆瓣书籍详情页提取结构化书籍信息
"""

import json
import logging
import re
import time
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DoubanScraper:
    """
    豆瓣书籍页面爬取器

    从豆瓣书籍详情页提取完整书籍信息，包括：
    书名、封面、作者、出版社、出版日期、评分、ISBN、简介、作者简介、标签
    """

    DOUBAN_BOOK_PATTERN = re.compile(r'^https?://book\.douban\.com/subject/(\d+)/?$')
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]

    def __init__(self, timeout: int = 15, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self._ua_index = 0

    def _get_headers(self) -> Dict[str, str]:
        ua = self.USER_AGENTS[self._ua_index % len(self.USER_AGENTS)]
        self._ua_index += 1
        return {
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }

    @staticmethod
    def validate_url(url: str) -> Tuple[bool, Optional[str]]:
        """
        验证豆瓣书籍URL格式
        返回: (是否有效, 豆瓣book_id或错误信息)
        """
        if not url or not url.strip():
            return False, 'URL不能为空'
        url = url.strip()
        match = DoubanScraper.DOUBAN_BOOK_PATTERN.match(url)
        if match:
            return True, match.group(1)
        return False, 'URL格式不正确，请输入有效的豆瓣书籍详情页地址（如 https://book.douban.com/subject/1234567/）'

    def scrape_book(self, url: str) -> Dict:
        """
        主入口：爬取豆瓣页面并返回结构化数据

        参数:
            url: 豆瓣书籍详情页URL

        返回:
            结构化书籍数据字典

        异常:
            ValueError: URL格式错误
            RuntimeError: 页面请求失败或解析失败
        """
        is_valid, result = self.validate_url(url)
        if not is_valid:
            raise ValueError(result)

        douban_id = result
        normalized_url = f'https://book.douban.com/subject/{douban_id}/'

        html = self._fetch_page(normalized_url)
        if self._is_captcha_page(html):
            raise RuntimeError('豆瓣暂时限制访问（触发验证码），请稍后重试')

        raw_data = self._parse_html(html, normalized_url)
        cleaned_data = self._clean_data(raw_data)
        cleaned_data['douban_id'] = douban_id

        if not cleaned_data.get('title'):
            raise RuntimeError('无法提取书籍名称，页面结构可能已变化')

        logger.info(f"[豆瓣爬取] 成功: 《{cleaned_data['title']}》| douban_id={douban_id}")
        return cleaned_data

    def _fetch_page(self, url: str) -> str:
        """发送HTTP请求获取页面HTML（带重试和随机延迟）"""
        import random

        last_error = None
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    delay = random.uniform(2, 5)
                    logger.info(f"[豆瓣爬取] 第{attempt + 1}次重试，等待{delay:.1f}秒...")
                    time.sleep(delay)

                resp = self.session.get(
                    url,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                    allow_redirects=True
                )

                if resp.status_code == 404:
                    raise RuntimeError('豆瓣页面不存在（404）')
                if resp.status_code == 403:
                    raise RuntimeError('豆瓣拒绝访问（403），可能触发反爬限制')
                if resp.status_code != 200:
                    raise RuntimeError(f'HTTP请求失败，状态码: {resp.status_code}')

                resp.encoding = 'utf-8'
                return resp.text

            except requests.Timeout:
                last_error = RuntimeError('请求超时，请检查网络连接')
                logger.warning(f"[豆瓣爬取] 请求超时 (尝试 {attempt + 1}/{self.max_retries})")
            except requests.ConnectionError:
                last_error = RuntimeError('网络连接失败')
                logger.warning(f"[豆瓣爬取] 连接失败 (尝试 {attempt + 1}/{self.max_retries})")
            except RuntimeError:
                raise
            except Exception as e:
                last_error = RuntimeError(f'请求异常: {str(e)}')
                logger.warning(f"[豆瓣爬取] 请求异常: {e} (尝试 {attempt + 1}/{self.max_retries})")

        raise last_error or RuntimeError('请求失败，已达最大重试次数')

    @staticmethod
    def _is_captcha_page(html: str) -> bool:
        """检测是否为验证码页面"""
        if len(html) < 500:
            return True
        captcha_indicators = ['sec.douban.com', 'captcha-verify', '验证码']
        html_lower = html.lower()
        return any(indicator in html_lower for indicator in captcha_indicators)

    def _parse_html(self, html: str, url: str) -> Dict:
        """解析HTML页面，提取书籍信息"""
        soup = BeautifulSoup(html, 'lxml')
        data = {'URL': url}

        data['title'] = self._extract_title(soup)
        data['cover_image'] = self._extract_cover(soup)
        data['rating'] = self._extract_rating(soup)

        info_data = self._extract_info_block(soup)
        data.update(info_data)

        data['books_intro'] = self._extract_content_intro(soup)
        data['author_intro'] = self._extract_author_intro(soup)
        data['tags'] = self._extract_tags(soup)
        data['also_like'] = self._extract_also_like(soup)

        return data

    @staticmethod
    def _extract_title(soup) -> str:
        el = soup.select_one('#wrapper h1 span')
        return el.get_text(strip=True) if el else ''

    @staticmethod
    def _extract_cover(soup) -> str:
        el = soup.select_one('#mainpic img')
        if el:
            return el.get('src') or el.get('data-src') or ''
        return ''

    @staticmethod
    def _extract_rating(soup) -> Optional[float]:
        el = soup.select_one('.rating_num')
        if el:
            text = el.get_text(strip=True)
            try:
                rating = float(text)
                if 0 <= rating <= 10:
                    return rating
            except ValueError:
                pass
        return None

    @staticmethod
    def _extract_info_block(soup) -> Dict:
        """提取 #info 区域的结构化信息（作者、出版社、出版日期、ISBN等）"""
        data = {
            'authors': [],
            'publisher': None,
            'publication_date': None,
            'isbn': None,
        }

        info_el = soup.select_one('#info')
        if not info_el:
            return data

        text = info_el.get_text()

        authors = []
        author_els = info_el.select('a')
        for a in author_els:
            href = a.get('href', '')
            if '/author/' in href or '/search/' in href:
                name = a.get_text(strip=True)
                if name and name not in ('更多', '等'):
                    authors.append(name)

        if not authors:
            match = re.search(r'作者[:：]\s*([\u4e00-\u9fa5a-zA-Z·\s]+?)(?:\n|$)', text)
            if match:
                author_str = match.group(1).strip()
                authors = [a.strip() for a in re.split(r'[/、,，]', author_str) if a.strip()]

        data['authors'] = authors

        pub_match = re.search(r'出版社[:：]\s*([^\n]+)', text)
        if pub_match:
            data['publisher'] = pub_match.group(1).strip()

        date_match = re.search(r'出版年[:：]\s*([^\n]+)', text)
        if date_match:
            data['publication_date'] = date_match.group(1).strip()

        isbn_match = re.search(r'ISBN[:：]\s*(\d[\d\-]+)', text)
        if isbn_match:
            data['isbn'] = isbn_match.group(1).strip()

        return data

    @staticmethod
    def _extract_content_intro(soup) -> str:
        el = soup.select_one('#link-report .intro')
        if not el:
            el = soup.select_one('#link-report')
        if el:
            all_intros = el.select('.intro')
            if len(all_intros) > 1:
                return all_intros[-1].get_text(strip=True)
            return el.get_text(strip=True)
        return ''

    @staticmethod
    def _extract_author_intro(soup) -> str:
        el = soup.select_one('.related_info .intro')
        if el:
            all_intros = el.select('.intro')
            if len(all_intros) > 1:
                return all_intros[-1].get_text(strip=True)
            return el.get_text(strip=True)
        return ''

    @staticmethod
    def _extract_tags(soup) -> List[str]:
        tags = []
        tag_els = soup.select('.indent span.tag a, #db-tags-section a')
        for el in tag_els:
            tag_text = el.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)
        return tags[:10]

    @staticmethod
    def _extract_also_like(soup) -> List[str]:
        """解析豆瓣页面中'喜欢这本书的人也喜欢'区域的书籍列表"""
        book_names = []

        # 策略1: #db-rec-section 下的 dl.clearfix dd a
        rec_section = soup.select_one('#db-rec-section')
        if rec_section:
            links = rec_section.select('dl.clearfix dd a')
            for a in links:
                name = a.get_text(strip=True)
                if name:
                    book_names.append(name)

        # 策略2: .recommendations .content a
        if not book_names:
            links = soup.select('.recommendations .content a')
            for a in links:
                name = a.get_text(strip=True)
                if name:
                    book_names.append(name)

        # 策略3: 所有包含"喜欢"文本的 section 中的链接
        if not book_names:
            sections = soup.find_all('section')
            for section in sections:
                section_text = section.get_text()
                if '喜欢' in section_text:
                    links = section.select('a')
                    for a in links:
                        name = a.get_text(strip=True)
                        if name:
                            book_names.append(name)

        return book_names[:12]

    def _clean_data(self, raw_data: Dict) -> Dict:
        """数据清洗与标准化"""
        cleaned = {}

        cleaned['title'] = self._clean_text(raw_data.get('title', ''))
        cleaned['cover_image'] = raw_data.get('cover_image', '')
        cleaned['URL'] = raw_data.get('URL', '')

        authors = raw_data.get('authors', [])
        cleaned['authors'] = [self._clean_author(a) for a in authors if self._clean_author(a)]

        cleaned['publisher'] = self._clean_text(raw_data.get('publisher'))

        pub_date = raw_data.get('publication_date')
        cleaned['publication_date'] = self._normalize_date(pub_date) if pub_date else None

        rating = raw_data.get('rating')
        cleaned['rating'] = rating

        cleaned['isbn'] = raw_data.get('isbn')
        cleaned['books_intro'] = self._clean_text(raw_data.get('books_intro'))
        cleaned['author_intro'] = self._clean_text(raw_data.get('author_intro'))
        cleaned['tags'] = raw_data.get('tags', [])

        cleaned['also_like'] = raw_data.get('also_like', [])
        cleaned['short_reviews'] = []
        cleaned['reviews'] = []
        cleaned['reading_notes'] = []

        return cleaned

    @staticmethod
    def _clean_text(text) -> str:
        if not text:
            return ''
        text = str(text).strip()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'<[^>]+>', '', text)
        return text

    @staticmethod
    def _clean_author(author: str) -> str:
        if not author:
            return ''
        author = author.strip()
        author = re.sub(r'^(作者[:：]\s*|著\s*$)', '', author)
        author = re.sub(r'\s*[等]?\s*$', '', author)
        return author.strip()

    @staticmethod
    def _normalize_date(date_str: str) -> Optional[str]:
        """
        将豆瓣日期格式标准化为 YYYY-MM-DD
        支持: 2023-1, 2023年1月, 2023/1/1, 2023-1-1, 2023.1 等
        """
        if not date_str:
            return None
        date_str = date_str.strip()

        match = re.match(r'(\d{4})[年/\-.](\d{1,2})[月/\-.]?(\d{1,2})?', date_str)
        if match:
            year = match.group(1)
            month = match.group(2).zfill(2)
            day = (match.group(3) or '1').zfill(2)
            return f'{year}-{month}-{day}'

        match = re.match(r'(\d{4})', date_str)
        if match:
            return f'{match.group(1)}-01-01'

        return None

    LATEST_URL = 'https://book.douban.com/latest'
    SUBCATEGORIES = [
        '全部', '文学', '小说', '历史文化', '社会纪实',
        '科学新知', '艺术设计', '商业经管', '绘本漫画',
    ]

    def scrape_latest_books(self, subcat: Optional[str] = None, max_pages: int = 1) -> Dict:
        """
        爬取豆瓣新书速递列表页，提取图书详情页URL和基本信息

        参数:
            subcat: 分类名称，如"文学"、"小说"等，None或"全部"表示不限分类
            max_pages: 抓取页数，最大5页

        返回:
            {"total": int, "books": [{"detail_url": str, "title": str, ...}, ...]}

        异常:
            RuntimeError: 列表页请求失败或触发验证码
        """
        import random

        max_pages = min(max(1, max_pages), 5)
        all_books = []
        seen_urls = set()

        for page in range(1, max_pages + 1):
            params = {'p': page}
            if subcat and subcat != '全部':
                params['subcat'] = subcat

            url = self.LATEST_URL
            if params:
                query = '&'.join(f'{k}={v}' for k, v in params.items())
                url = f'{self.LATEST_URL}?{query}'

            logger.info(f"[新书速递] 抓取第{page}页: {url}")

            if page > 1:
                delay = random.uniform(2, 4)
                time.sleep(delay)

            html = self._fetch_page(url)
            if self._is_captcha_page(html):
                raise RuntimeError('豆瓣暂时限制访问（触发验证码），请稍后重试')

            books = self._parse_latest_page(html)
            for book in books:
                if book['detail_url'] not in seen_urls:
                    seen_urls.add(book['detail_url'])
                    all_books.append(book)

            logger.info(f"[新书速递] 第{page}页解析到{len(books)}本书，累计{len(all_books)}本")

        return {'total': len(all_books), 'books': all_books}

    def _parse_latest_page(self, html: str) -> List[Dict]:
        """解析新书速递列表页HTML，提取每本书的详情URL和基本信息"""
        soup = BeautifulSoup(html, 'lxml')
        books = []

        items = soup.select('#content .grid-168 .media')
        if not items:
            items = soup.select('#content .grid-16-8 .media')
        if not items:
            items = soup.select('.article .media')

        for item in items:
            book = self._parse_latest_item(item)
            if book and book.get('detail_url'):
                books.append(book)

        if not books:
            books = self._parse_latest_fallback(soup)

        return books

    @staticmethod
    def _parse_latest_item(item) -> Optional[Dict]:
        """解析单个书籍条目"""
        book = {
            'detail_url': '',
            'title': '',
            'cover_image': '',
            'rating': None,
            'authors': [],
            'publisher': '',
            'publication_date': '',
        }

        title_el = item.select_one('a.fleft')
        if not title_el:
            title_el = item.select_one('h2 a')
        if not title_el:
            title_el = item.select_one('.title a')
        if not title_el:
            return None

        href = title_el.get('href', '')
        if '/subject/' not in href:
            return None

        if href.startswith('http'):
            book['detail_url'] = href.rstrip('/')
        else:
            book['detail_url'] = f'https://book.douban.com{href}'.rstrip('/')

        book['title'] = title_el.get_text(strip=True)

        cover_el = item.select_one('img')
        if cover_el:
            book['cover_image'] = cover_el.get('src') or cover_el.get('data-src') or ''

        rating_el = item.select_one('.rating-value')
        if not rating_el:
            rating_el = item.select_one('.rating_nums')
        if rating_el:
            try:
                book['rating'] = float(rating_el.get_text(strip=True))
            except (ValueError, TypeError):
                pass

        meta_el = item.select_one('.meta')
        if not meta_el:
            meta_el = item.select_one('.color-gray')
        if meta_el:
            meta_text = meta_el.get_text(strip=True)
            parts = [p.strip() for p in re.split(r'[/｜|]', meta_text) if p.strip()]
            author_parts = []
            for part in parts:
                if re.match(r'\d{4}', part):
                    date_match = re.match(r'(\d{4}[-/年]\d{1,2}[-/月]?\d{0,2}日?)', part)
                    if date_match:
                        book['publication_date'] = date_match.group(1)
                elif re.search(r'出版社|出版集团', part):
                    book['publisher'] = re.sub(r'^[\s/]+', '', part)
                elif not re.match(r'^[\d.]+元', part) and not re.match(r'^(平装|精装| Hardcover|Paperback)', part, re.IGNORECASE):
                    author_parts.append(part)
            if author_parts:
                book['authors'] = [a.strip() for a in re.split(r'[,，、]', author_parts[0]) if a.strip()]

        return book

    @staticmethod
    def _parse_latest_fallback(soup) -> List[Dict]:
        """备用解析策略：从页面中所有包含 /subject/ 的链接提取"""
        books = []
        seen = set()

        for a in soup.select('a[href*="/subject/"]'):
            href = a.get('href', '')
            if '/subject/' not in href:
                continue

            if href.startswith('http'):
                detail_url = href.rstrip('/')
            else:
                detail_url = f'https://book.douban.com{href}'.rstrip('/')

            subject_match = re.search(r'/subject/(\d+)', detail_url)
            if not subject_match:
                continue

            douban_id = subject_match.group(1)
            if douban_id in seen:
                continue
            seen.add(douban_id)

            title = a.get_text(strip=True)
            if not title or len(title) > 100:
                continue

            books.append({
                'detail_url': detail_url,
                'title': title,
                'cover_image': '',
                'rating': None,
                'authors': [],
                'publisher': '',
                'publication_date': '',
            })

        return books
