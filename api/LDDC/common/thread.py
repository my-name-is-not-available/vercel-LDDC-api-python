# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
import queue
from collections.abc import Callable, Iterable
from functools import partial, wraps
from threading import Event, Lock, Thread, ThreadPoolExecutor
from typing import Any

from .logger import logger
from .models import P, T

exit_event = Event()

# 使用ThreadPoolExecutor替代QThreadPool
threadpool = ThreadPoolExecutor(max_workers=8)


def is_exited() -> bool:
    return exit_event.is_set()


def set_exited() -> None:
    exit_event.set()


# 创建一个队列用于主线程任务处理
main_thread_queue = queue.Queue()

# 主线程处理函数
def main_thread_handler():
    while not exit_event.is_set():
        try:
            # 阻塞等待任务，但定期检查是否退出
            task = main_thread_queue.get(timeout=0.1)
            if task is None:  # 终止信号
                break
            mutex, func, ret = task
            try:
                result = func()
                ret.append(True)
                ret.append(result)
            except Exception as e:
                ret.append(False)
                ret.append(e)
            finally:
                mutex.release()
                main_thread_queue.task_done()
        except queue.Empty:
            continue

# 启动主线程处理线程
main_thread_handler_thread = Thread(target=main_thread_handler, daemon=True)
main_thread_handler_thread.start()


def in_main_thread(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """在主线程运行函数(堵塞、支持返回值)"""
    # 由于我们不再有Qt的主线程概念，我们假设调用此函数的线程就是主线程
    # 在非Qt环境中，我们直接执行函数
    return func(*args, **kwargs)


# 信号发射器类，用于线程间通信
class SignalEmitter:
    def __init__(self):
        self.success_callbacks = []
        self.error_callbacks = []

    def connect_success(self, callback):
        self.success_callbacks.append(callback)

    def connect_error(self, callback):
        self.error_callbacks.append(callback)

    def emit_success(self, result):
        for callback in self.success_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.exception(f"Success callback error: {e}")

    def emit_error(self, exception):
        for callback in self.error_callbacks:
            try:
                callback(exception)
            except Exception as e:
                logger.exception(f"Error callback error: {e}")


# 任务运行器函数，在线程池中执行任务
def task_runner(func, emitter):
    if is_exited():
        return
    try:
        result = func()
        if is_exited():
            return
        emitter.emit_success(result)  # 成功时调用回调
    except Exception as e:
        emitter.emit_error(e)  # 失败时调用回调
        logger.exception(e)


# 主函数，支持在其他线程中执行任务
def in_other_thread(
    func: Callable[..., T],  # 要执行的函数
    callback: Callable[[T], Any] | Iterable[Callable[[T], Any]] | None,  # 成功时的回调
    error_handling: Callable[[Exception], Any] | Iterable[Callable[[Exception], Any]] | None,  # 错误处理
    *args: Any,  # func 的位置参数
    **kwargs: Any,  # func 的关键字参数
) -> None:
    # 创建信号发射器
    emitter = SignalEmitter()

    # 将回调函数连接到 success 信号
    if callback is not None:
        if isinstance(callback, Iterable):
            for cb in callback:
                emitter.connect_success(cb)
        else:
            emitter.connect_success(callback)

    # 将错误处理函数连接到 error 信号
    if error_handling is not None:
        if isinstance(error_handling, Iterable):
            for eh in error_handling:
                emitter.connect_error(eh)
        else:
            emitter.connect_error(error_handling)

    # 提交任务到线程池
    threadpool.submit(task_runner, partial(func, *args, **kwargs), emitter)


class CrossThreadSignalObject:
    def __init__(self):
        self.signal_callbacks = []

    def connect(self, callback):
        self.signal_callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in self.signal_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.exception(f"Signal emit error: {e}")


def cross_thread_func(func: Callable[P, T]) -> Callable[P, None | T]:
    orig_thread = Thread.current_thread()

    def _callback(func: Callable, args: tuple, kwargs: dict) -> None:
        func(*args, **kwargs)

    # 在非Qt环境中，我们简化跨线程调用
    @wraps(func)
    def cross_thread_callback(*args: P.args, **kwargs: P.kwargs) -> None | T:
        if Thread.current_thread() != orig_thread:
            # 将调用放入队列，由主线程处理
            main_thread_queue.put((Lock(), partial(_callback, func, args, kwargs), []))
        else:
            return func(*args, **kwargs)
        return None

    return cross_thread_callback


# 清理函数，确保线程池正确关闭
def cleanup():
    set_exited()
    threadpool.shutdown(wait=True)
    # 发送终止信号给主线程处理线程
    main_thread_queue.put(None)
    if main_thread_handler_thread.is_alive():
        main_thread_handler_thread.join(timeout=1.0)

# 注册退出处理
exit_event.set = exit_event.set
exit_event.is_set = exit_event.is_set

# 保持原有接口
def set_exited():
    exit_event.set()


def is_exited():
    return exit_event.is_set()


# 在程序退出时清理资源
import atexit
atexit.register(cleanup)
