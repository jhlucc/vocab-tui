import curses
import time
import random
from datetime import datetime, timedelta
from typing import Dict, Any


class BossScreen:
    """老板键伪装屏幕（时间基于当前本地时间）"""

    def __init__(self, stdscr, style: str = "tail", boss_quit_enabled: bool = False):
        self.stdscr = stdscr
        self.style = (style or "tail").lower()
        self.boss_quit_enabled = bool(boss_quit_enabled)
        self.height, self.width = stdscr.getmaxyx()

        # 初始化颜色（尽量容错）
        try:
            curses.start_color()
            if not hasattr(curses, 'has_colors') or curses.has_colors():
                curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)   # 普通
                curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)   # INFO/标题
                curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)    # DEBUG/可执行
                curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # WARNING
        except Exception:
            pass

    # --------------------- 公共入口 ---------------------
    def enter(self):
        """进入伪装屏幕"""
        if self.style == "ls":
            self._show_ls_screen()
        else:
            self._show_tail_screen()

    # --------------------- tail -f 伪装 ---------------------
    def _show_tail_screen(self):
        """显示 tail -f 风格的伪装屏幕（时间=当前本地时间）"""
        self.stdscr.clear()

        # 先生成一批“历史日志”行，时间从当前往前倒退
        current_lines = self._make_initial_tail_lines(max(5, min(self.height - 2, 60)))

        # 非阻塞读取，循环滚动
        self.stdscr.nodelay(True)
        try:
            while True:
                self.stdscr.clear()

                # 标题
                title = "tail -f /var/log/application.log"
                try:
                    self.stdscr.addstr(0, 0, title[:self.width - 1], curses.color_pair(2))
                except Exception:
                    pass

                # 日志内容
                for i, line in enumerate(current_lines):
                    if i + 1 >= self.height:
                        break
                    color = curses.color_pair(1)
                    if "ERROR" in line or "WARNING" in line:
                        color = curses.color_pair(4)
                    elif "INFO" in line:
                        color = curses.color_pair(2)
                    elif "DEBUG" in line:
                        color = curses.color_pair(3)
                    try:
                        self.stdscr.addstr(i + 1, 0, line[:self.width - 1], color)
                    except Exception:
                        pass

                self.stdscr.refresh()

                # 按键（非阻塞）
                try:
                    key = self.stdscr.getch()
                    if key != -1 and self._handle_key(key):
                        break
                except Exception:
                    pass

                # 模拟新日志行（当前时间）
                time.sleep(0.5)
                if random.random() < 0.7:  # 70% 概率产生新日志
                    new_line = self._generate_log_line()
                    current_lines.append(new_line)
                    # 保持在屏幕大小之内
                    if len(current_lines) >= self.height - 1:
                        current_lines.pop(0)
        finally:
            # 恢复阻塞读取，避免回到主程序后继续吞键
            self.stdscr.nodelay(False)

    def _make_initial_tail_lines(self, n: int):
        """生成 n 行初始日志，时间从当前往前倒退（每行~1秒间隔）"""
        now = datetime.now()
        lines = []
        # 为了看起来连贯，我们逆序生成，再正序返回
        for i in range(n, 0, -1):
            ts = now - timedelta(seconds=i)
            lines.append(self._generate_log_line(at=ts))
        return lines

    def _generate_log_line(self, at: datetime | None = None) -> str:
        """生成一行随机日志，时间戳=当前或传入时间"""
        dt = at or datetime.now()
        stamp = dt.strftime("%Y-%m-%d %H:%M:%S")

        log_types = ["INFO", "DEBUG", "WARNING"]
        log_type = random.choice(log_types)
        messages = [
            "Application started successfully",
            "Loading configuration from config.json",
            "Database connection established",
            "Processing user request",
            "Cache refresh completed",
            "Background task completed",
            "Request processed in 125ms",
            "Cleaning up temporary files",
            "System status: healthy",
            "Service heartbeat OK",
        ]
        msg = random.choice(messages)
        return f"[{stamp}] {log_type}: {msg}"

    # --------------------- ls -la 伪装 ---------------------
    def _show_ls_screen(self):
        """显示 ls -la 风格的伪装屏幕（时间=当前本地时间或最近几分钟内）"""
        self.stdscr.clear()

        # 构造“当前目录”的伪造列表
        files = self._fake_ls_entries()

        # 标题
        try:
            self.stdscr.addstr(0, 0, "ls -la /home/user/project"[:self.width - 1], curses.color_pair(2))
            self.stdscr.addstr(1, 0, f"total {len(files) * 4}")
        except Exception:
            pass

        # 文件列表
        for i, file_line in enumerate(files):
            if i + 2 >= self.height:
                break
            color = curses.color_pair(1)
            if file_line.startswith('d'):         # 目录
                color = curses.color_pair(2)
            elif file_line[3:6].find('x') >= 0:   # 可执行
                color = curses.color_pair(3)
            try:
                self.stdscr.addstr(i + 2, 0, file_line[:self.width - 1], color)
            except Exception:
                pass

        # 提示符
        prompt_line = min(len(files) + 3, self.height - 1)
        if prompt_line < self.height:
            try:
                self.stdscr.addstr(prompt_line, 0, "user@server:~/project$ ", curses.color_pair(2))
            except Exception:
                pass

        self.stdscr.refresh()

        # 等待按键（阻塞）
        while True:
            key = self.stdscr.getch()
            if self._handle_key(key):
                break

    def _fake_ls_entries(self):
        """生成类似 `ls -la` 的行，时间基于当前时间（最近几分钟）"""
        now = datetime.now()

        def month_abbr(m: int) -> str:
            months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            return months[m-1]

        def fmt_time(dt: datetime) -> str:
            # 类似 ls: "Sep 17 14:30"
            return f"{month_abbr(dt.month)} {dt.day:2d} {dt.strftime('%H:%M')}"

        # 先放 . 和 ..
        entries = []
        entries.append(f"drwxr-xr-x  3 user user    4096 {fmt_time(now)} .")
        entries.append(f"drwxr-xr-x 15 user user    4096 {fmt_time(now - timedelta(minutes=1))} ..")

        # 其他文件/目录，时间在最近 0~9 分钟随机
        names = [
            (True,  "config"),          # 目录
            (False, ".bash_logout"),
            (False, ".bashrc"),
            (True,  ".cache"),
            (False, ".profile"),
            (False, "application.log"),
            (False, "backup_script.sh"),  # 可执行
            (True,  "temp"),
            (False, "data.json"),
            (False, "error.log"),
            (False, "main_app"),          # 可执行
            (False, "report.txt"),
        ]
        for is_dir, name in names:
            dt = now - timedelta(minutes=random.randint(0, 9), seconds=random.randint(0, 59))
            size = random.randint(512, 16384)
            if is_dir:
                perm = "drwxr-xr-x"
            else:
                # 随机可执行
                exec_bit = random.random() < 0.25 or name.endswith((".sh", "_app"))
                perm = " -rwxr-xr-x" if exec_bit else " -rw-r--r--"
                perm = perm[1:]  # 去掉前导空格
            entries.append(f"{perm:10s}  1 user user {size:7d} {fmt_time(dt)} {name}")
        return entries

    # --------------------- 按键处理 ---------------------
    def _handle_key(self, key: int) -> bool:
        """处理按键，返回 True 表示退出伪装屏幕"""
        # 识别所有常见 Tab 表示
        if key in (
            getattr(curses, "KEY_TAB", -1),
            getattr(curses, "KEY_BTAB", -2),
            ord('\t'), 9
        ):
            return True

        # q 键退出程序（如果启用）
        if key in (ord('q'), ord('Q')) and self.boss_quit_enabled:
            raise SystemExit("Boss key quit")

        return False


class BossConfig:
    """老板键配置（备用，不强制使用）"""

    def __init__(self):
        self.boss_key = "TAB"
        self.boss_style = "tail"  # "tail" 或 "ls"
        self.boss_quit_enabled = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boss_key": self.boss_key,
            "boss_style": self.boss_style,
            "boss_quit_enabled": self.boss_quit_enabled
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BossConfig':
        config = cls()
        config.boss_key = data.get("boss_key", "TAB")
        config.boss_style = data.get("boss_style", "tail")
        config.boss_quit_enabled = data.get("boss_quit_enabled", False)
        return config

