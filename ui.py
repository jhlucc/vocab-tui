import curses
from typing import List, Optional, Callable

from models import VocabApp, Word, Stats, UISnapshot


class UI:
    """基于curses的用户界面（支持多主题 F6 切换 & 可滚动弹窗）"""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.height, self.width = stdscr.getmaxyx()
        curses.start_color()
        try:
            curses.use_default_colors()
        except Exception:
            pass
        # 默认主题初始化（可被 main 按配置覆盖）
        self.apply_theme("mono")

    # ================== 主题相关 ==================
    def available_themes(self) -> List[str]:
        return ["mono", "green", "blue", "amber", "magenta"]

    def apply_theme(self, theme: str):
        """根据 theme 初始化颜色对（1~6固定语义）"""
        t = (theme or "mono").lower()
        # 颜色语义：1=标题 2=单词 3=释义/正确 4=警示/错误 5=音标 6=普通文本
        C = curses
        THEMES = {
            "mono":    {1:(C.COLOR_CYAN, C.COLOR_BLACK), 2:(C.COLOR_YELLOW, C.COLOR_BLACK),
                        3:(C.COLOR_GREEN, C.COLOR_BLACK), 4:(C.COLOR_RED, C.COLOR_BLACK),
                        5:(C.COLOR_MAGENTA, C.COLOR_BLACK), 6:(C.COLOR_WHITE, C.COLOR_BLACK)},
            "green":   {1:(C.COLOR_GREEN, C.COLOR_BLACK), 2:(C.COLOR_GREEN, C.COLOR_BLACK),
                        3:(C.COLOR_GREEN, C.COLOR_BLACK), 4:(C.COLOR_YELLOW, C.COLOR_BLACK),
                        5:(C.COLOR_GREEN, C.COLOR_BLACK), 6:(C.COLOR_GREEN, C.COLOR_BLACK)},
            "blue":    {1:(C.COLOR_CYAN, C.COLOR_BLACK), 2:(C.COLOR_WHITE, C.COLOR_BLACK),
                        3:(C.COLOR_CYAN, C.COLOR_BLACK), 4:(C.COLOR_YELLOW, C.COLOR_BLACK),
                        5:(C.COLOR_BLUE, C.COLOR_BLACK),  6:(C.COLOR_WHITE, C.COLOR_BLACK)},
            "amber":   {1:(C.COLOR_YELLOW, C.COLOR_BLACK), 2:(C.COLOR_YELLOW, C.COLOR_BLACK),
                        3:(C.COLOR_WHITE,  C.COLOR_BLACK), 4:(C.COLOR_RED,    C.COLOR_BLACK),
                        5:(C.COLOR_YELLOW, C.COLOR_BLACK), 6:(C.COLOR_YELLOW, C.COLOR_BLACK)},
            "magenta": {1:(C.COLOR_MAGENTA, C.COLOR_BLACK), 2:(C.COLOR_WHITE,   C.COLOR_BLACK),
                        3:(C.COLOR_CYAN,    C.COLOR_BLACK), 4:(C.COLOR_RED,     C.COLOR_BLACK),
                        5:(C.COLOR_MAGENTA, C.COLOR_BLACK), 6:(C.COLOR_WHITE,   C.COLOR_BLACK)},
        }
        palette = THEMES.get(t, THEMES["mono"])
        for pair_no, (fg, bg) in palette.items():
            curses.init_pair(pair_no, fg, bg)
        self._theme_name = t

    # ================== 快照封装（老板键用） ==================
    def create_snapshot(self, app: VocabApp) -> UISnapshot:
        return app.create_snapshot()

    def restore_from_snapshot(self, app: VocabApp, snapshot: UISnapshot, all_words: List[Word]):
        app.restore_from_snapshot(snapshot, all_words)

    # ================== 基础绘制 ==================
    def clear_screen(self):
        self.stdscr.clear()

    def draw_border(self):
        self.stdscr.border()

    def print_center(self, y: int, text: str, color_pair: int = 0):
        x = max(0, (self.width - len(text)) // 2)
        if 0 <= y < self.height and x < self.width:
            self.stdscr.addstr(y, x, text[: self.width - x - 1], curses.color_pair(color_pair))

    def print_at(self, y: int, x: int, text: str, color_pair: int = 0):
        if 0 <= y < self.height and 0 <= x < self.width:
            max_len = self.width - x - 1
            if max_len > 0:
                self.stdscr.addstr(y, x, text[:max_len], curses.color_pair(color_pair))

    # ================== 主菜单 / 学习 / 统计 ==================
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

        self.print_center(self.height - 3, f"主题: {getattr(self, '_theme_name', 'mono')}  |  请输入选项 (1-5):", 6)
        self.print_center(self.height - 1, "h=帮助 F6=切换主题 Tab=Boss键 q=退出", 6)
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
        if progress.seen > 0:    progress_text2.append(f"已看: {progress.seen}次")
        if progress.known > 0:   progress_text2.append(f"会了: {progress.known}次")
        if progress.unknown > 0: progress_text2.append(f"不会: {progress.unknown}次")
        if progress_text2:
            self.print_center(stats_y, " | ".join(progress_text2), 6)

        help_lines = [
            "操作: s=下一个 w=上一个 p=显示/隐藏释义 r=打乱 t=拼写模式",
            "      空格/Enter=我会了 x=我不会 ,=加入错题本 g=AI讲解",
        ]
        for i, line in enumerate(help_lines):
            self.print_center(self.height - 4 + i, line, 6)

        self.print_center(self.height - 1, f"h=帮助 F6=切换主题 Tab=Boss键 .=菜单 q=退出", 6)
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

    # ================== 拼写模式界面 ==================
    def show_typing_screen(self, app: VocabApp, typed: str, feedback: str, show_hint: bool):
        self.clear_screen()
        self.draw_border()

        word = app.get_current_word()
        if not word:
            self.print_center(self.height // 2, "没有可学习的单词", 4)
            self.stdscr.refresh()
            return

        self.print_center(1, "=== 拼写模式（中文→英文） ===", 1)
        self.print_at(1, 2, f"单词 {app.current_index + 1}/{len(app.words)}", 6)

        y = 4
        self.print_center(y, word.meaning, 3)
        y += 2

        if show_hint and word.phonetic:
            self.print_center(y, f"提示: {word.phonetic}", 5)
            y += 2

        prompt = "请输入英文拼写："
        self.print_center(y, prompt, 6); y += 1
        self.print_center(y, (typed or "") + "▌", 2); y += 2

        if feedback:
            color = 3 if feedback.startswith("✅") else 4
            self.print_center(y, feedback, color); y += 2

        self.print_center(self.height - 5, "Enter=判定  Backspace=删字  F2=切换提示", 6)
        self.print_center(self.height - 4, "↑/↓=上一/下一词（可选）  ESC=退出拼写模式", 6)
        self.print_center(self.height - 1, "F6=切换主题  Tab=Boss键", 6)
        self.stdscr.refresh()

    # ================== 可滚动文本弹窗（用于 AI 讲解） ==================
    def show_waiting(self, text: str):
        """显示不阻塞的“等待中”提示（不读取按键）"""
        self.clear_screen()
        self.draw_border()
        self.print_center(self.height // 2, text, 6)
        self.stdscr.refresh()

    def show_scrollable_text(
        self,
        title: str,
        content: str,
        boss_cb: Optional[Callable[[], None]] = None,
        theme_cycle_cb: Optional[Callable[[], None]] = None,
    ):
        """
        可滚动文本查看器：
          - 滚动：↑/↓、PgUp/PgDn、Home/End
          - 关闭：q / ESC
          - 其他：F6 切主题（若提供回调）、Tab 老板键（若提供回调，返回后继续）
        """
        # 预处理：按屏宽软换行
        inner_w = max(10, self.width - 4)
        lines_raw = content.splitlines() if content else ["(空)"]
        lines: List[str] = []
        for ln in lines_raw:
            if not ln:
                lines.append("")
                continue
            # 简单 wrap
            cur = ln
            while len(cur) > inner_w:
                lines.append(cur[:inner_w])
                cur = cur[inner_w:]
            lines.append(cur)
        total = len(lines)

        offset = 0
        view_h = max(5, self.height - 6)  # 可视行数

        def redraw():
            self.clear_screen()
            self.draw_border()
            self.print_center(1, title, 1)
            # 显示主体
            for i in range(view_h):
                idx = offset + i
                if 0 <= idx < total:
                    self.print_at(3 + i, 2, lines[idx], 6)
            # 底栏
            status = f"{offset + 1}-{min(offset + view_h, total)}/{total}"
            footer = f"↑/↓ PgUp/PgDn Home/End 滚动 | q/ESC 关闭 | Tab=Boss键 | F6=切主题 | 主题:{getattr(self,'_theme_name','mono')}"
            self.print_at(self.height - 3, 2, status, 5)
            self.print_at(self.height - 1, 2, footer, 6)
            self.stdscr.refresh()

        redraw()
        while True:
            key = self.get_key()
            # Tab -> 老板键
            if isinstance(key, int):
                # Tab / Shift+Tab
                if boss_cb and (key == 9 or (hasattr(curses, 'KEY_TAB') and key == curses.KEY_TAB) or
                                (hasattr(curses, 'KEY_BTAB') and key == curses.KEY_BTAB)):
                    boss_cb()
                    try:
                        curses.flushinp()
                    except Exception:
                        pass
                    redraw()
                    continue

            if key == 'up':
                if offset > 0:
                    offset -= 1
                    redraw()
            elif key == 'down':
                if offset < max(0, total - view_h):
                    offset += 1
                    redraw()
            elif key == 'pgup':
                offset = max(0, offset - view_h)
                redraw()
            elif key == 'pgdn':
                offset = min(max(0, total - view_h), offset + view_h)
                redraw()
            elif key == 'home':
                offset = 0
                redraw()
            elif key == 'end':
                offset = max(0, total - view_h)
                redraw()
            elif key == 'f6':
                if theme_cycle_cb:
                    theme_cycle_cb()
                redraw()
            elif key in ('q', 'esc', '.'):
                break
            else:
                # 其余键忽略
                pass

    # ================== 通用消息 / 退出确认 ==================
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

    # ================== 输入：宽字符 + 功能键 ==================
    def get_key(self):
        """
        返回：
          - Tab：返回整数(9/KEY_TAB/KEY_BTAB)
          - Enter/Space/Esc：'enter'/'space'/'esc'
          - Backspace：'backspace'
          - F2/F6：'f2'/'f6'；方向键↑/↓：'up'/'down'；PgUp/PgDn：'pgup'/'pgdn'；Home/End：'home'/'end'
          - 其他可打印字符（含中文）：对应字符
          - 未识别：''
        """
        try:
            try:
                ch = self.stdscr.get_wch()
            except Exception:
                ch = self.stdscr.getch()

            if isinstance(ch, str):
                if ch in ('\n', '\r'): return 'enter'
                if ch == '\t':         return 9
                if ch in ('\x7f', '\b'): return 'backspace'
                if ch == '\x1b':       return 'esc'
                if ch == ' ':          return 'space'
                return ch  # 可打印字符（含中文）

            key = ch
            # Tab / Shift+Tab
            if key in (9, ord('\t')) or (hasattr(curses, 'KEY_TAB') and key == curses.KEY_TAB):
                return key
            if hasattr(curses, 'KEY_BTAB') and key == curses.KEY_BTAB:
                return key
            # 功能键
            if hasattr(curses, 'KEY_F2') and key == curses.KEY_F2:
                return 'f2'
            if hasattr(curses, 'KEY_F6') and key == curses.KEY_F6:
                return 'f6'
            if hasattr(curses, 'KEY_UP') and key == curses.KEY_UP:
                return 'up'
            if hasattr(curses, 'KEY_DOWN') and key == curses.KEY_DOWN:
                return 'down'
            if hasattr(curses, 'KEY_PPAGE') and key == curses.KEY_PPAGE:
                return 'pgup'
            if hasattr(curses, 'KEY_NPAGE') and key == curses.KEY_NPAGE:
                return 'pgdn'
            if hasattr(curses, 'KEY_HOME') and key == curses.KEY_HOME:
                return 'home'
            if hasattr(curses, 'KEY_END') and key == curses.KEY_END:
                return 'end'

            if key in (10, 13): return 'enter'
            if key == 32:       return 'space'
            if key == 27:       return 'esc'
            if key in (curses.KEY_BACKSPACE, 127, 8): return 'backspace'
            if 32 <= key <= 126: return chr(key)
            return ''
        except:
            return ''

    # ================== 工具 ==================
    def wrap_text(self, text: str, max_width: int) -> list:
        if len(text) <= max_width:
            return [text]
        lines, words, current = [], text.split(), ""
        for w in words:
            if len(current + " " + w) <= max_width:
                current = (current + " " + w) if current else w
            else:
                if current: lines.append(current)
                current = w
        if current: lines.append(current)
        return lines

    def show_help(self):
        help_width, help_height = 60, 20
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
            "  r            - 打乱顺序",
            "  t            - 进入拼写模式",
            "  g            - AI 讲解（联网 + 大模型/后备）", "",
            "拼写模式(中文→英文):",
            "  字母全部可输入；Enter 判定，Backspace 删除",
            "  F2 切换音标提示，↑/↓ 上一/下一词，ESC 退出", "",
            "其他:",
            "  F6           - 切换 UI 主题（mono/green/blue/amber/magenta）",
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
