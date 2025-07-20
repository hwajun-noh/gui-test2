"""
마이리스트 계약완료 데이터 모듈
"""

from mylist.completed.data.models import CompletedDealModel
from mylist.completed.data.loaders import CompletedDealLoader

__all__ = ['CompletedDealModel', 'CompletedDealLoader'] 