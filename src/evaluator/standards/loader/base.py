from abc import ABC, abstractmethod

from evaluator.standards.models import StandardSet


class StandardSetLoader(ABC):
    """标准集加载器的抽象基类"""
    
    @abstractmethod
    def load(self) -> StandardSet:
        """加载标准集"""
        pass

    @abstractmethod
    async def aload(self) -> StandardSet:
        """加载标准集"""
        pass

