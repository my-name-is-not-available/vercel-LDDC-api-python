# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
import sys
from importlib.util import find_spec
from pathlib import Path
from threading import Thread

__author__ = "沉默の金"
__license__ = "GPL-3.0-only"
__copyright__ = "Copyright (C) 2024 沉默の金 <cmzj@cmzj.org>"
name = "LDDC"  # 程序名称(用于common.args检查运行模式)
if find_spec("LDDC") is None:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
# ruff: noqa: E402
from LDDC.common.args import args
from LDDC.common.translator import load_translation
from LDDC.common.version import __version__
from LDDC.common.thread import cleanup as thread_cleanup
from LDDC.gui.service import LDDCService

# 移除GUI相关的资源加载

if __name__ == "__main__":
    if args.get_service_port:
        # 如果是获取服务端口,则只需实例化LDDCService,然后退出
        LDDCService()
        sys.exit()

    # 启动服务线程
    service = LDDCService()
    service_thread = Thread(target=service.run)
    service_thread.daemon = True
    service_thread.start()

    # 加载翻译
    load_translation(False)

    # 在非GUI模式下，我们不需要显示主窗口
    # 保持程序运行
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("程序被用户中断")
    finally:
        # 清理线程资源
        thread_cleanup()
        from LDDC.gui.view.main_window import main_window

        main_window.show()

    # 检查更新
    from LDDC.common.data.config import cfg

    if cfg["auto_check_update"]:
        from LDDC.gui.view.update import check_update

        check_update(True, QApplication.translate("CheckUpdate", "LDDC主程序"), "chenmozhijin/LDDC", __version__)

    # 进入事件循环
    sys.exit(app.exec())
