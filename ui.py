import curses
from typing import List

from models import VocabApp, Word, Stats, UISnapshot


class UI:
    """基于curses的用户界面"""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.height, self.width = stdscr.getmaxyx()

        # 初始化颜色
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)     # 标题
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)   # 单词
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)    # 释义/正确
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)      # 错误/重要
        curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)  # 音标
        curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLACK)    # 普通文本

    # -------- 快照封装（老板键用） --------
    def create_snapshot(self, app: VocabApp) -> UISnapshot:
        return app.create_snapshot()

    def restore_from_snapshot(self, app: VocabApp, snapshot: UISnapshot, all_words: List[Word]):
        app.restore_from_snapshot(snapshot, all_words)

    # -------- 基础绘制 --------
    def clear_screen(self):
        self.stdscr.clear()

    def draw_border(self):
        self.stdscr.border()

    def print_center(self, y: int, text: str, color_pair: int = 0):
        # 这里简化居中计算（中文宽度在等宽终端里可能更宽，视觉上略偏没关系）
        x = max(0, (self.width - len(text)) // 2)
        if 0 <= y < self.height and x < self.width:
            self.stdscr.addstr(y, x, text[: self.width - x - 1], curses.color_pair(color_pair))

    def print_at(self, y: int, x: int, text: str, color_pair: int = 0):
        if 0 <= y < self.height and 0 <= x < self.width:
            max_len = self.width - x - 1
            if max_len > 0:
                self.stdscr.addstr(y, x, text[:max_len], curses.color_pair(color_pair))

    # -------- 主菜单 / 学习 / 统计 --------
    def show_main_menu(self) -> str:
        self.clear_screen()
        self.draw_border()
        self.print_center(2, "=== 背单词工具 ===", 1)

        menu_options = [
            "1. 开始学习",
            "2. 只学错题本",
            "3. 查看统计",
            "4. 拼写模式（中文→英文）",
            "5. 退出",
        ]
        for i, option in enumerate(menu_options):
            self.print_center(5 + i, option, 6)

        self.print_center(self.height - 3, "请输入选项 (1-5):", 6)
        self.print_center(self.height - 1, "h=帮助 Tab=Boss键 q=退出", 6)
        self.stdscr.refresh()
        return self.get_key()

    def show_learning_screen(self, app: VocabApp):
        self.clear_screen()
        self.draw_border()

        word = app.get_current_word()
        if not word:
            self.print_center(self.height // 2, "没有可学习的单词", 4)
            self.stdscr.refresh()
            return

        progress = app.get_current_progress()
        mode_text = "错题本模式" if app.error_mode else "学习模式"
        self.print_center(1, f"=== {mode_text} ===", 1)

        progress_text = f"单词 {app.current_index + 1}/{len(app.words)}"
        if progress.starred:
            progress_text += " ⭐"
        self.print_at(1, 2, progress_text, 6)

        word_y = 4
        self.print_center(word_y, word.word, 2)

        if app.show_meaning:
            current_y = word_y + 2
            if word.phonetic:
                self.print_center(current_y, word.phonetic, 5)
                current_y += 1
            self.print_center(current_y, word.meaning, 3)
            current_y += 2
            if word.example:
                for line in self.wrap_text(word.example, self.width - 4):
                    if current_y < self.height - 6:
                        self.print_center(current_y, line, 6)
                        current_y += 1
        else:
            self.print_center(word_y + 2, "[按 p 显示释义]", 6)

        stats_y = self.height - 8
        progress_text2 = []
        if progress.seen > 0:
            progress_text2.append(f"已看: {progress.seen}次")
        if progress.known > 0:
            progress_text2.append(f"会了: {progress.known}次")
        if progress.unknown > 0:
            progress_text2.append(f"不会: {progress.unknown}次")
        if progress_text2:
            self.print_center(stats_y, " | ".join(progress_text2), 6)

        help_lines = [
            "操作: s=下一个 w=上一个 p=显示/隐藏释义 r=打乱 t=拼写模式",
            "      空格/Enter=我会了 x=我不会 ,=加入错题本",
        ]
        for i, line in enumerate(help_lines):
            self.print_center(self.height - 4 + i, line, 6)

        self.print_center(self.height - 1, "h=帮助 Tab=Boss键 .=菜单 q=退出", 6)
        self.stdscr.refresh()

    def show_stats(self, stats: Stats):
        self.clear_screen()
        self.draw_border()
        self.print_center(2, "=== 学习统计 ===", 1)
        for i, line in enumerate([
            f"总单词数: {stats.total_words}",
            f"已学习数: {stats.seen_count}",
            f"掌握数量: {stats.known_count}",
            f"待复习数: {stats.unknown_count}",
            f"标星数量: {stats.starred_count}",
        ]):
            color = 3 if "掌握" in line else (4 if "待复习" in line or "标星" in line else 6)
            self.print_center(5 + i, line, color)
        self.print_center(self.height - 3, "按任意键返回主菜单", 6)
        self.stdscr.refresh()
        self.get_key()

    # -------- 拼写模式界面 --------
    def show_typing_screen(self, app: VocabApp, typed: str, feedback: str, show_hint: bool):
        self.clear_screen()
        self.draw_border()

        word = app.get_current_word()
        if not word:
            self.print_center(self.height // 2, "没有可学习的单词", 4)
            self.stdscr.refresh()
            return

        # 标题与进度
        self.print_center(1, "=== 拼写模式（中文→英文） ===", 1)
        self.print_at(1, 2, f"单词 {app.current_index + 1}/{len(app.words)}", 6)

        # 中文提示
        y = 4
        self.print_center(y, word.meaning, 3)
        y += 2

        # 音标提示（可切换）
        if show_hint and word.phonetic:
            self.print_center(y, f"提示: {word.phonetic}", 5)
            y += 2

        # 输入框
        prompt = "请输入英文拼写："
        self.print_center(y, prompt, 6)
        y += 1

        # 显示当前输入（尽量居中）
        display = typed if typed else ""
        self.print_center(y, display + "▌", 2)  # 光标块（绘制用）
        y += 2

        # 反馈
        if feedback:
            color = 3 if feedback.startswith("✅") else 4
            self.print_center(y, feedback, color)
            y += 2

        # 底部帮助：字母全部可输入；仅少数控制键有效
        self.print_center(self.height - 5, "Enter=判定  Backspace=删字  F2=切换提示", 6)
        self.print_center(self.height - 4, "↑/↓=上一/下一词（可选）", 6)
        self.print_center(self.height - 3, "ESC=退出拼写模式", 6)
        self.print_center(self.height - 1, "Tab=Boss键", 6)

        self.stdscr.refresh()

    # -------- 通用消息 / 退出确认 --------
    def show_message(self, message: str, color_pair: int = 6):
        self.clear_screen()
        self.draw_border()
        self.print_center(self.height // 2, message, color_pair)
        self.print_center(self.height // 2 + 2, "按任意键继续...", 6)
        self.stdscr.refresh()
        self.get_key()

    def confirm_exit(self) -> bool:
        self.clear_screen()
        self.draw_border()
        self.print_center(self.height // 2, "确定要退出吗？(y/n)", 6)
        self.stdscr.refresh()
        key = self.get_key()
        return key in ('y', 'Y')

    # -------- 输入：支持宽字符（中文）与常用控制键 --------
    def get_key(self):
        """
        返回：
          - Tab：返回整数(9/KEY_TAB/KEY_BTAB)以便老板键全局识别
          - Enter/Space/Esc 等：返回 'enter'/'space'/'esc'
          - Backspace：返回 'backspace'
          - 功能键：F2->'f2'，方向键↑/↓->'up'/'down'
          - 其他可打印字符（含中文）：返回对应字符
          - 未识别：返回 ''
        """
        try:
            # 优先使用宽字符读取（支持中文）
            try:
                ch = self.stdscr.get_wch()
            except Exception:
                ch = self.stdscr.getch()

            # 宽字符分支
            if isinstance(ch, str):
                if ch in ('\n', '\r'):
                    return 'enter'
                if ch == '\t':
                    return 9  # Tab 仍按整数返回
                if ch in ('\x7f', '\b'):  # 127/8
                    return 'backspace'
                if ch == '\x1b':
                    return 'esc'
                if ch == ' ':
                    return 'space'
                # 普通字符（含中文）
                return ch

            # 功能键分支（整数）
            key = ch
            # Tab / Shift+Tab
            if key in (9, ord('\t')) or (hasattr(curses, 'KEY_TAB') and key == curses.KEY_TAB):
                return key
            if hasattr(curses, 'KEY_BTAB') and key == curses.KEY_BTAB:
                return key
            # F2
            if hasattr(curses, 'KEY_F2') and key == curses.KEY_F2:
                return 'f2'
            # 方向键
            if hasattr(curses, 'KEY_UP') and key == curses.KEY_UP:
                return 'up'
            if hasattr(curses, 'KEY_DOWN') and key == curses.KEY_DOWN:
                return 'down'

            if key in (10, 13):
                return 'enter'
            if key == 32:
                return 'space'
            if key == 27:
                return 'esc'
            if key in (curses.KEY_BACKSPACE, 127, 8):
                return 'backspace'

            # 以下保留为可打印字符映射（学习模式会把这些当快捷键；拼写模式不会拦截）
            if ord(' ') <= key <= 126:
                return chr(key)

            # 其他不可打印
            return ''
        except:
            return ''

    # -------- 工具 --------
    def wrap_text(self, text: str, max_width: int) -> list:
        if len(text) <= max_width:
            return [text]
        lines, words, current = [], text.split(), ""
        for w in words:
            if len(current + " " + w) <= max_width:
                current = (current + " " + w) if current else w
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
        return lines

    def show_help(self):
        help_width, help_height = 60, 18
        start_y = max(1, (self.height - help_height) // 2)
        start_x = max(1, (self.width - help_width) // 2)
        win = curses.newwin(help_height, help_width, start_y, start_x)
        win.border()
        content = [
            "快捷键帮助", "",
            "学习模式:",
            "  s / w        - 下一个 / 上一个",
            "  p            - 显示/隐藏释义",
            "  空格 / Enter - '我会了'",
            "  x            - '我不会'",
            "  ,            - 加入错题本",
            "  r            - 打乱顺序  t - 进入拼写模式", "",
            "拼写模式(中文→英文):",
            "  字母全部可输入（r/x/q/s/w 等不再当快捷键）",
            "  Enter 判定，Backspace 删除，F2 切换提示",
            "  ↑/↓ 上一/下一词（可选），ESC 退出拼写模式", "",
            "其他:",
            "  Tab          - 老板键(伪装屏幕)",
            "  q            - 退出程序（仅学习/主菜单可用）",
            "按任意键关闭帮助"
        ]
        for i, line in enumerate(content):
            if i < help_height - 2:
                color = 1 if i == 0 else (3 if line.endswith(":") else 6)
                x_pos = (help_width - len(line)) // 2 if i == 0 else 2
                win.addstr(i + 1, x_pos, line[:help_width - 4], curses.color_pair(color))
        win.refresh()
        win.getch()
        del win
        self.stdscr.refresh()

