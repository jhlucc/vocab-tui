#!/usr/bin/env python3
import curses
import random
import sys
import time
import os
import subprocess
from typing import Callable, List, Optional, Tuple

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
        """判断是否按下 Tab（UI.get_key 遇到 Tab 返回整数键值 9 或 KEY_TAB/KEY_BTAB）"""
        if time.time() - self._last_boss_ts < 0.12:  # 防抖：120ms
            return False
        return isinstance(key, int) and (
            key == 9 or key == ord('\t') or
            (hasattr(curses, "KEY_TAB") and key == curses.KEY_TAB) or
            (hasattr(curses, "KEY_BTAB") and key == curses.KEY_BTAB)  # 兼容 Shift+Tab
        )

    def _boss_key(self):
        """进入老板键伪装屏幕，并在退出后恢复现场"""
        snapshot = self.ui.create_snapshot(self.app)
        style = self.app.config.boss_style
        allow_quit = self.app.config.boss_quit_enabled
        BossScreen(self.ui.stdscr, style=style, boss_quit_enabled=allow_quit).enter()

        # 清空输入缓冲，避免“回来的第一下又被 Tab 带走”
        try:
            curses.flushinp()
        except Exception:
            pass
        self._last_boss_ts = time.time()

        self.ui.restore_from_snapshot(self.app, snapshot, list(self.app.words))
    # ------------------------------------------------

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

    def _handle_global_key(
        self,
        key,
        *,
        after_boss: Optional[Callable[[], None]] = None,
        after_theme: Optional[Callable[[], None]] = None,
    ) -> bool:
        """处理全局快捷键，返回是否已消费该按键"""

        if self._is_tab(key):
            self._boss_key()
            if after_boss:
                after_boss()
            return True
        if key == 'f6':
            self._cycle_theme()
            if after_theme:
                after_theme()
            return True
        return False

    # ---------- 初始化/保存 ----------
    def initialize(self):
        """初始化应用与数据文件"""
        if not self.storage.file_exists():
            print("未找到 words.csv 文件，正在创建示例文件...")
            if self.storage.create_sample_words_file():
                print("示例文件创建成功！")
            else:
                print("创建示例文件失败！")
                return False

        # 加载单词和进度（下次启动会自动导入 progress.json）
        self.app.words = self.storage.load_words()
        self.app.progress = self.storage.load_progress()

        if not self.app.words:
            print("未能加载任何单词，请检查 words.csv 文件格式")
            return False

        return True

    def save_progress(self):
        """保存进度"""
        self.storage.save_progress(self.app.progress)

    # ---------- AI 讲解（学习模式：单词） ----------
    def _resolve_word_ai_script(self) -> Optional[str]:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(base_dir, "word_ai.py")
        if os.path.exists(script_path):
            return script_path
        return None

    def _run_word_ai_command(
        self,
        script_path: str,
        word: str,
        extra_args: List[str],
        timeout: int,
    ) -> Tuple[bool, str, str]:
        cmd = [sys.executable, script_path, word, *extra_args]
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")

        try:
            proc = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return False, "", "timeout"
        except Exception as exc:
            return False, f"运行出错：{exc!r}", "error"

        if proc.returncode != 0:
            out = (proc.stdout or "") + (proc.stderr or "")
            message = (
                f"[word_ai 运行失败]\n命令: {' '.join(cmd)}\n"
                f"返回码: {proc.returncode}\n\n{out}"
            )
            return False, message, "failed"

        return True, proc.stdout.strip() or "(无输出)", "success"

    def _ai_help_for_current_word(self):
        """调用 word_ai.py 获取当前单词的讲解，并以弹窗显示"""
        w = self.app.get_current_word()
        if not w:
            self.ui.show_message("没有当前单词", 4)
            return

        script_path = self._resolve_word_ai_script()
        if not script_path:
            self.ui.show_message("未找到 word_ai.py（请把脚本放在同目录）", 4)
            return

        # 提示“正在获取…”
        self.ui.show_waiting(f"正在获取 AI 讲解：{w.word} ...")

        ok, content, reason = self._run_word_ai_command(
            script_path,
            w.word,
            ["--plain"],
            timeout=90,
        )

        if not ok:
            if reason == "timeout":
                content = "请求超时（>90s）。你可以稍后重试，或检查网络/密钥是否可用。"
            elif not content:
                content = "运行 word_ai.py 失败。"

        # 弹窗滚动查看；支持 Tab 老板键与 F6 切主题
        title = f"AI 讲解 - {w.word}"
        self.ui.show_scrollable_text(
            title=title,
            content=content,
            boss_cb=self._boss_key,
            theme_cycle_cb=self._cycle_theme,
        )

    # ---------- 批量：错题本 AI 笔记 ----------
    def run_batch_ai_notes(self):
        """
        批量为“错题本”中的单词生成 AI 笔记（保存为 ai_notes/<word>.md）
        - 默认跳过已存在的笔记文件
        - q/ESC 终止；Tab 老板键；F6 切主题
        """
        # 准备集合
        error_words = self.app.filter_error_words()
        if not error_words:
            self.ui.show_message("错题本为空，无需生成。", 4)
            return

        script_path = self._resolve_word_ai_script()
        if not script_path:
            self.ui.show_message("未找到 word_ai.py（请把脚本放在同目录）", 4)
            return

        # 运行参数
        base_dir = os.path.dirname(os.path.abspath(__file__))
        out_dir = os.path.join(base_dir, "ai_notes")
        os.makedirs(out_dir, exist_ok=True)
        skip_existing = True

        total = len(error_words)
        logs: List[str] = []
        aborted = False
        title = "批量生成错题本 AI 笔记"

        # 初始渲染
        self.ui.draw_batch_progress(title, logs, 0, total)

        for idx, w in enumerate(error_words, start=1):
            word_text = w.word
            md_path = os.path.join(out_dir, f"{word_text}.md")

            # 轮询按键（非阻塞）
            key = self.ui.get_key_nonblocking()
            if key is not None:
                def redraw_pending():
                    self.ui.draw_batch_progress(title, logs, idx - 1, total)

                handled = self._handle_global_key(
                    key,
                    after_boss=redraw_pending,
                    after_theme=redraw_pending,
                )

                if not handled and key in ('q', 'esc'):
                    logs.append(f"[abort] 用户终止，已完成 {idx-1}/{total}")
                    aborted = True
                    break

            # 跳过已存在
            if skip_existing and os.path.exists(md_path):
                logs.append(f"[skip] {word_text}（已存在 {os.path.basename(md_path)}）")
                self.ui.draw_batch_progress(title, logs, idx, total)
                continue

            # 执行脚本
            ok, message, reason = self._run_word_ai_command(
                script_path,
                word_text,
                ["--save"],
                timeout=120,
            )

            if ok:
                logs.append(f"[ok]   {word_text}")
            else:
                summary = (message or "").strip().replace("\n", " ")
                if reason == "timeout":
                    logs.append(f"[timeout] {word_text} >120s")
                elif reason == "error":
                    logs.append(f"[error] {word_text}  {summary[:120]}")
                else:
                    logs.append(f"[fail] {word_text}  {summary[:120]}")

            # 刷新界面
            self.ui.draw_batch_progress(title, logs, idx, total)

        # 总结
        if not aborted:
            done = sum(1 for ln in logs if ln.startswith("[ok]"))
            fail = sum(1 for ln in logs if ln.startswith("[fail]") or ln.startswith("[error]") or ln.startswith("[timeout]"))
            skip = sum(1 for ln in logs if ln.startswith("[skip]"))
            logs.append(f"--- 完成：ok={done}  fail={fail}  skip={skip} / 共 {total}")
        else:
            logs.append("--- 已中断")

        self.ui.show_scrollable_text(
            title="批量生成结果",
            content="\n".join(logs) if logs else "(无日志)",
            boss_cb=self._boss_key,
            theme_cycle_cb=self._cycle_theme,
        )

    # ---------------- 主菜单 / 学习模式 ----------------
    def _start_learning_session(self, *, error_only: bool = False):
        backup_words = None
        original_error_mode = self.app.error_mode

        if error_only:
            error_words = self.app.filter_error_words()
            if not error_words:
                self.ui.show_message("没有错题本内容！", 4)
                return
            backup_words = list(self.app.words)
            self.app.words = error_words

        try:
            self.app.error_mode = error_only
            self.app.current_index = 0
            self.app.show_meaning = False
            self.run_learning()
        finally:
            if backup_words is not None:
                self.app.words = backup_words
            self.app.error_mode = original_error_mode

    def _confirm_exit(self) -> bool:
        if self.ui.confirm_exit():
            self.save_progress()
            return True
        return False

    def _handle_learning_key(self, key) -> bool:
        if key == 's':
            self.next_word()
        elif key == 'w':
            self.prev_word()
        elif key == 'p':
            self.app.show_meaning = not self.app.show_meaning
        elif key == ',':
            self.app.toggle_starred()
            self.save_progress()
        elif key in ('enter', 'space'):
            self._mark_current_word(True)
        elif key == 'x':
            self._mark_current_word(False)
        elif key == 'r':
            self.shuffle_words()
        elif key == 't':
            self.run_typing_mode()
        elif key == 'g':
            self._ai_help_for_current_word()
        elif key == 'h':
            self.ui.show_help()
        elif key == '.':
            return False
        elif key == 'q':
            if self._confirm_exit():
                sys.exit(0)
        return True

    def run_main_menu(self):
        """运行主菜单"""
        while True:
            choice = self.ui.show_main_menu()

            if self._handle_global_key(choice):
                continue

            if choice == '1':
                self._start_learning_session(error_only=False)
            elif choice == '2':
                self._start_learning_session(error_only=True)
            elif choice == '3':
                stats = self.app.get_stats()
                self.ui.show_stats(stats)
            elif choice == '4':
                self.run_typing_mode()
            elif choice == '5':
                self.run_batch_ai_notes()
            elif choice in ('6', 'q'):
                if self._confirm_exit():
                    break
            elif choice == 'h':
                self.ui.show_help()

    def run_learning(self):
        """运行学习模式（浏览式）"""
        if not self.app.words:
            self.ui.show_message("没有可学习的单词！", 4)
            return

        while True:
            self.ui.show_learning_screen(self.app)
            key = self.ui.get_key()

            if self._handle_global_key(key):
                continue

            if not self._handle_learning_key(key):
                break

    # ---------------- 拼写模式（中文 → 英文） ----------------
    def run_typing_mode(self):
        """
        拼写模式：显示中文释义，在输入框拼英文单词。
        ⚠️ 在本模式中，所有字母都当作普通输入；不拦截 r/x/q/s/w/g 等字母。
        控制键仅：Enter 判定、Backspace 删除、ESC 退出、Tab 老板键、F2 切换提示、↑/↓ 上下词（可选）。
        """
        if not self.app.words:
            self.ui.show_message("没有可学习的单词！", 4)
            return

        typed = ""           # 当前输入
        feedback = ""        # 反馈信息（正确/错误）
        show_hint = True     # 是否显示音标（提示）
        stay_on_wrong = False  # 写错是否停留当前词（可改成配置）

        while True:
            self.ui.show_typing_screen(self.app, typed, feedback, show_hint)
            key = self.ui.get_key()

            def clear_feedback():
                nonlocal feedback
                feedback = ""

            if self._handle_global_key(key, after_boss=clear_feedback):
                continue

            # —— 控制键（仅以下这些） ——
            if key == 'esc':
                # 仅 ESC 退出拼写模式
                break
            if key == 'h':
                self.ui.show_help()
                continue
            if key == 'f2':
                # F2 切换提示（避免与字母冲突）
                show_hint = not show_hint
                continue
            if key == 'up':
                # 上一词（可选）
                typed, feedback = "", ""
                self.prev_word()
                continue
            if key == 'down':
                # 下一词（可选）
                typed, feedback = "", ""
                self.next_word()
                continue

            # —— 输入与判定 ——
            if key == 'backspace':
                typed = typed[:-1]
            elif key == 'enter':
                current = self.app.get_current_word()
                target = current.word if current else ""
                if typed.strip().lower() == (target or "").lower():
                    self._mark_current_word(True)
                    feedback = "✅ 正确"
                    typed = ""
                else:
                    self._mark_current_word(False, advance=not stay_on_wrong)
                    feedback = f"❌ 不对，答案：{target}"
                    typed = ""
            else:
                # 其他任何可打印字符（含中文/字母/数字/符号），都当作输入
                if isinstance(key, str) and key not in ('', '\n', '\r'):
                    typed += key

    # ---------------- 公共小功能 ----------------
    def _mark_current_word(self, known: bool, advance: bool = True):
        if known:
            self.app.mark_known()
        else:
            self.app.mark_unknown()
        self.save_progress()
        if advance:
            self.next_word()

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
        """主函数（curses包装）"""
        self.ui = UI(stdscr)
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)  # 提高 KEY_TAB/KEY_BTAB/功能键 识别稳定性
        # 应用配置中的主题
        self._apply_theme_from_config()
        self.run_main_menu()


def main():
    """程序入口点"""
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
