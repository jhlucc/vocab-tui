#!/usr/bin/env python3
import curses
import random
import sys
import time
from typing import Optional

from models import VocabApp
from storage import Storage
from ui import UI
from boss import BossScreen


class VocabTUI:
    """背单词工具主程序"""

    def __init__(self):
        self.storage = Storage()
        self.app = VocabApp()
        self.ui: Optional[UI] = None
        self._last_boss_ts = 0.0  # 老板键防抖时间戳

    # ---------- 老板键判定与处理 ----------
    def _is_tab(self, key) -> bool:
        if time.time() - self._last_boss_ts < 0.12:
            return False
        return isinstance(key, int) and (
            key == 9 or key == ord('\t') or
            (hasattr(curses, "KEY_TAB") and key == curses.KEY_TAB) or
            (hasattr(curses, "KEY_BTAB") and key == curses.KEY_BTAB)
        )

    def _boss_key(self):
        snapshot = self.ui.create_snapshot(self.app)
        style = self.app.config.boss_style
        allow_quit = self.app.config.boss_quit_enabled
        BossScreen(self.ui.stdscr, style=style, boss_quit_enabled=allow_quit).enter()
        try:
            curses.flushinp()
        except Exception:
            pass
        self._last_boss_ts = time.time()
        self.ui.restore_from_snapshot(self.app, snapshot, list(self.app.words))

    # ---------- 主题切换 ----------
    def _apply_theme_from_config(self):
        self.ui.apply_theme(self.app.config.ui_theme)

    def _cycle_theme(self):
        themes = self.ui.available_themes()
        cur = self.app.config.ui_theme
        idx = themes.index(cur) if cur in themes else -1
        new = themes[(idx + 1) if idx + 1 < len(themes) else 0]
        self.app.config.ui_theme = new
        self.ui.apply_theme(new)

    # ---------- 初始化/保存 ----------
    def initialize(self):
        if not self.storage.file_exists():
            print("未找到 words.csv 文件，正在创建示例文件...")
            if self.storage.create_sample_words_file():
                print("示例文件创建成功！")
            else:
                print("创建示例文件失败！")
                return False
        self.app.words = self.storage.load_words()
        self.app.progress = self.storage.load_progress()
        if not self.app.words:
            print("未能加载任何单词，请检查 words.csv 文件格式")
            return False
        return True

    def save_progress(self):
        self.storage.save_progress(self.app.progress)

    # ---------- 主菜单 ----------
    def run_main_menu(self):
        while True:
            choice = self.ui.show_main_menu()

            if self._is_tab(choice):
                self._boss_key()
                continue
            if choice == 'f6':
                self._cycle_theme()
                continue

            if choice == '1':
                self.app.error_mode = False
                self.app.current_index = 0
                self.app.show_meaning = False
                self.run_learning()
            elif choice == '2':
                error_words = self.app.filter_error_words()
                if not error_words:
                    self.ui.show_message("没有错题本内容！", 4)
                else:
                    backup = list(self.app.words)
                    self.app.words = error_words
                    self.app.error_mode = True
                    self.app.current_index = 0
                    self.app.show_meaning = False
                    self.run_learning()
                    self.app.words = backup
            elif choice == '3':
                stats = self.app.get_stats()
                self.ui.show_stats(stats)
            elif choice == '4':
                self.run_typing_mode()
            elif choice == '5' or choice == 'q':
                if self.ui.confirm_exit():
                    self.save_progress()
                    break
            elif choice == 'h':
                self.ui.show_help()

    # ---------- 学习模式 ----------
    def run_learning(self):
        if not self.app.words:
            self.ui.show_message("没有可学习的单词！", 4)
            return

        while True:
            self.ui.show_learning_screen(self.app)
            key = self.ui.get_key()

            if self._is_tab(key):
                self._boss_key()
                continue
            if key == 'f6':
                self._cycle_theme()
                continue

            if key == 's':
                self.next_word()
            elif key == 'w':
                self.prev_word()
            elif key == 'p':
                self.app.show_meaning = not self.app.show_meaning
            elif key == ',':
                self.app.toggle_starred()
                self.save_progress()
            elif key == 'enter' or key == 'space':
                self.app.mark_known()
                self.save_progress()
                self.next_word()
            elif key == 'x':
                self.app.mark_unknown()
                self.save_progress()
                self.next_word()
            elif key == 'r':
                self.shuffle_words()
            elif key == 't':
                self.run_typing_mode()
            elif key == 'h':
                self.ui.show_help()
            elif key == '.':
                break
            elif key == 'q':
                if self.ui.confirm_exit():
                    self.save_progress()
                    sys.exit(0)

    # ---------- 拼写模式 ----------
    def run_typing_mode(self):
        if not self.app.words:
            self.ui.show_message("没有可学习的单词！", 4)
            return

        typed = ""
        feedback = ""
        show_hint = True
        stay_on_wrong = False

        while True:
            self.ui.show_typing_screen(self.app, typed, feedback, show_hint)
            key = self.ui.get_key()

            if self._is_tab(key):
                self._boss_key()
                feedback = ""
                continue
            if key == 'f6':
                self._cycle_theme()
                continue

            if key == 'esc':
                break
            if key == 'h':
                self.ui.show_help()
                continue
            if key == 'f2':
                show_hint = not show_hint
                continue
            if key == 'up':
                typed, feedback = "", ""
                self.prev_word()
                continue
            if key == 'down':
                typed, feedback = "", ""
                self.next_word()
                continue

            if key == 'backspace':
                typed = typed[:-1]
            elif key == 'enter':
                target = self.app.get_current_word().word if self.app.get_current_word() else ""
                if typed.strip().lower() == (target or "").lower():
                    self.app.mark_known()
                    self.save_progress()
                    feedback = "✅ 正确"
                    typed = ""
                    self.next_word()
                else:
                    self.app.mark_unknown()
                    self.save_progress()
                    feedback = f"❌ 不对，答案：{target}"
                    typed = ""
                    if not stay_on_wrong:
                        self.next_word()
            else:
                if isinstance(key, str) and key not in ('', '\n', '\r'):
                    typed += key

    # ---------- 公共小功能 ----------
    def next_word(self):
        if self.app.current_index < len(self.app.words) - 1:
            self.app.current_index += 1
            self.app.show_meaning = False
        else:
            self.ui.show_message("已完成所有单词学习！", 3)
            self.app.current_index = 0
            self.app.show_meaning = False

    def prev_word(self):
        if self.app.current_index > 0:
            self.app.current_index -= 1
            self.app.show_meaning = False

    def shuffle_words(self):
        if len(self.app.words) <= 1:
            return
        current_word = self.app.get_current_word()
        random.shuffle(self.app.words)
        if current_word:
            for i, word in enumerate(self.app.words):
                if word.word == current_word.word:
                    self.app.current_index = i
                    break
        else:
            self.app.current_index = 0
        self.app.show_meaning = False
        self.ui.show_message("单词顺序已打乱！", 3)

    def main(self, stdscr):
        self.ui = UI(stdscr)
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)
        # 应用配置中的主题
        self._apply_theme_from_config()
        self.run_main_menu()


def main():
    try:
        app = VocabTUI()
        if not app.initialize():
            return 1
        random.seed()
        curses.wrapper(app.main)
        return 0
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        return 1
    except Exception as e:
        print(f"程序运行出错: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

