# -*- coding: utf-8 -*-

from datetime import datetime

class MultiObjectiveRanker:
    def __init__(self):
        self.sort_modes = {
            'comprehensive': self._comprehensive_sort,
            'similarity': self._similarity_sort,
            'rating': self._rating_sort,
            'newest': self._newest_sort
        }
    
    def get_supported_sort_modes(self):
        return [
            {'mode': 'comprehensive', 'name': '综合排序', 'description': '基于加权效用函数排序（相似度+评分+新鲜度）'},
            {'mode': 'similarity', 'name': '相似度排序', 'description': '基于相似度与重叠系数排序'},
            {'mode': 'rating', 'name': '评分排序', 'description': '按图书评分从高到低排序'},
            {'mode': 'newest', 'name': '最新排序', 'description': '按出版日期从新到旧排序'}
        ]
    
    def sort_recommendations(self, recommendations, mode='comprehensive'):
        if mode not in self.sort_modes:
            mode = 'comprehensive'
        return self.sort_modes[mode](recommendations)
    
    def _comprehensive_sort(self, recommendations):
        return sorted(recommendations, key=lambda x: x.get('utility_score', 0), reverse=True)
    
    def _similarity_sort(self, recommendations):
        return sorted(recommendations, key=lambda x: x.get('similarity_score', x.get('final_score', 0)), reverse=True)
    
    def _rating_sort(self, recommendations):
        return sorted(recommendations, key=lambda x: x.get('rating', 0) or 0, reverse=True)
    
    def _newest_sort(self, recommendations):
        def parse_date(rec):
            date_str = rec.get('publication_date', '')
            if not date_str:
                return datetime.min
            try:
                return datetime.strptime(date_str[:10], '%Y-%m-%d')
            except:
                return datetime.min
        return sorted(recommendations, key=parse_date, reverse=True)
