# -*- coding: utf-8 -*-
"""
配置管理模块
用于加载和管理项目配置

作者：系统自动生成
日期：2026-03-25
"""

import json
import os
from typing import Dict, Any


class ConfigManager:
    """
    配置管理器类
    负责加载和提供项目配置
    """
    
    def __init__(self, config_path: str = None):
        """
        初始化配置管理器
        
        参数:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        if config_path is None:
            # 尝试多个可能的配置文件位置
            possible_paths = [
                'config.json',
                os.path.join(os.path.dirname(__file__), 'config.json'),
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
        
        if config_path is None or not os.path.exists(config_path):
            raise FileNotFoundError(
                f"配置文件未找到！请先复制 config.example.json 为 config.json 并修改其中的配置。\n"
                f"尝试查找的路径: {possible_paths}"
            )
        
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        从文件加载配置
        
        返回:
            配置字典
        """
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_database_config(self) -> Dict[str, Any]:
        """
        获取数据库配置
        
        返回:
            数据库配置字典
        """
        return self._config.get('database', {})
    
    def get_recommender_config(self) -> Dict[str, Any]:
        """
        获取推荐器配置
        
        返回:
            推荐器配置字典
        """
        return self._config.get('recommender', {})
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        参数:
            key: 配置键，支持点号分隔的嵌套键，如 'database.host'
            default: 默认值
            
        返回:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value


# 全局配置管理器实例
_config_manager = None


def get_config_manager(config_path: str = None) -> ConfigManager:
    """
    获取全局配置管理器实例（单例模式）
    
    参数:
        config_path: 配置文件路径
        
    返回:
        ConfigManager 实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager


if __name__ == '__main__':
    # 测试配置管理器
    try:
        config = get_config_manager()
        print("配置加载成功！")
        print("\n数据库配置:")
        db_config = config.get_database_config()
        for key, value in db_config.items():
            if key == 'password':
                value = '***'
            print(f"  {key}: {value}")
        
        print("\n推荐器配置:")
        rec_config = config.get_recommender_config()
        for key, value in rec_config.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"错误: {e}")
