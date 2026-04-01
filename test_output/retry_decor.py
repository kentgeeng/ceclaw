"""
重試裝飾器模組

提供 @retry 裝飾器，支援指數退避機制，用於處理暫時性失敗的函數呼叫。
"""

import time
import random
from functools import wraps
from typing import Callable, Optional, TypeVar, Any

# 定義泛型，讓裝飾器能保留原函數的型別
F = TypeVar('F', bound=Callable[..., Any])


def retry(
    max_attempts: int = 5,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable[[F], F]:
    """
    重試裝飾器
    
    當函數執行失敗時，會依指數退避策略重試執行。
    
    Args:
        max_attempts: 最大重試次數（包含初次執行），預設為 5
        delay: 初始延遲時間（秒），預設為 1.0
        backoff: 退避倍數，每次重試延遲時間會乘以此值，預設為 2.0
        exceptions: 需要重試的例外類型元組，預設為所有例外
    
    Returns:
        裝飾後的函數
    
    Example:
        >>> @retry(max_attempts=3, delay=0.5, backoff=2.0)
        >>> def unstable_function():
        >>>     if random.random() < 0.5:
        >>>         raise ConnectionError("連線失敗")
        >>>     return "成功"
        >>> 
        >>> result = unstable_function()
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Optional[Exception] = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        # 加入隨機 jitter 避免驚群效應
                        jitter = random.uniform(0, 0.1 * current_delay)
                        print(f"[{func.__name__}] 第 {attempt} 次失敗，{current_delay + jitter:.2f} 秒後重試")
                        time.sleep(current_delay + jitter)
                        current_delay *= backoff
                    else:
                        print(f"[{func.__name__}] 已達到最大重試次數 {max_attempts}")
            
            # 所有重試都失敗時拋出最後一次例外
            if last_exception:
                raise last_exception
            # 理論上不會到達這裡，但為了型別檢查需要
            raise RuntimeError("重試邏輯異常")
        
        return wrapper  # type: ignore
    return decorator


# 測試程式碼
if __name__ == "__main__":
    print("測試重試裝飾器")
    print("=" * 50)
    
    # 測試 1: 成功的情況
    @retry(max_attempts=3, delay=0.5, backoff=2.0)
    def always_succeed():
        print("  執行成功！")
        return "成功"
    
    print("\n測試 1: 總是成功的函數")
    result = always_succeed()
    print(f"結果: {result}")
    
    # 測試 2: 失敗的情況
    attempt_count_2 = [0]  # 使用列表來模擬 nonlocal
    
    @retry(max_attempts=3, delay=0.5, backoff=2.0)
    def always_fail():
        attempt_count_2[0] += 1
        print(f"  第 {attempt_count_2[0]} 次嘗試失敗")
        raise ValueError("模擬失敗")
    
    print("\n測試 2: 總是失敗的函數")
    try:
        always_fail()
    except ValueError as e:
        print(f"最終拋出例外: {e}")
        print(f"總共嘗試了 {attempt_count_2[0]} 次")
    
    # 測試 3: 部分成功的情況
    attempt_count_3 = [0]  # 使用列表來模擬 nonlocal
    
    @retry(max_attempts=5, delay=0.2, backoff=2.0)
    def eventually_succeed():
        attempt_count_3[0] += 1
        if attempt_count_3[0] < 3:
            print(f"  第 {attempt_count_3[0]} 次嘗試失敗")
            raise ConnectionError("連線失敗")
        print(f"  第 {attempt_count_3[0]} 次嘗試成功")
        return "終於成功了"
    
    print("\n測試 3: 部分失敗後成功的函數")
    result = eventually_succeed()
    print(f"結果: {result}")
    print(f"總共嘗試了 {attempt_count_3[0]} 次")
    
    print("\n" + "=" * 50)
    print("測試完成")
