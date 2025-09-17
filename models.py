from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class Word:
    """单词数据结构"""
    word: str
    meaning: str
    phonetic: Optional[str] = None
    example: Optional[str] = None


@dataclass
class WordProgress:
    """单词学习进度"""
    seen: int = 0
    known: int = 0
    unknown: int = 0
    starred: bool = False


@dataclass
class Stats:
    """统计信息"""
    total_words: int = 0
    seen_count: int = 0
    known_count: int = 0
    unknown_count: int = 0
    starred_count: int = 0

    def update_from_progress(self, progress_data: Dict[str, WordProgress]):
        self.total_words = len(progress_data)
        self.seen_count = sum(1 for p in progress_data.values() if p.seen > 0)
        self.known_count = sum(1 for p in progress_data.values() if p.known > 0)
        self.unknown_count = sum(1 for p in progress_data.values() if p.unknown > 0)
        self.starred_count = sum(1 for p in progress_data.values() if p.starred)


@dataclass
class AppConfig:
    """应用配置"""
    boss_key: str = "TAB"
    boss_style: str = "tail"  # "tail" 或 "ls"
    boss_quit_enabled: bool = False
    ui_theme: str = "mono"    # 新增：UI 主题（mono/green/blue/amber/magenta）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boss_key": self.boss_key,
            "boss_style": self.boss_style,
            "boss_quit_enabled": self.boss_quit_enabled,
            "ui_theme": self.ui_theme,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        config = cls()
        config.boss_key = data.get("boss_key", "TAB")
        config.boss_style = data.get("boss_style", "tail")
        config.boss_quit_enabled = data.get("boss_quit_enabled", False)
        config.ui_theme = data.get("ui_theme", "mono")
        return config


@dataclass
class UISnapshot:
    """界面状态快照"""
    current_index: int = 0
    show_meaning: bool = False
    error_mode: bool = False
    words_order: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_index": self.current_index,
            "show_meaning": self.show_meaning,
            "error_mode": self.error_mode,
            "words_order": self.words_order.copy()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UISnapshot':
        return cls(
            current_index=data.get("current_index", 0),
            show_meaning=data.get("show_meaning", False),
            error_mode=data.get("error_mode", False),
            words_order=data.get("words_order", []).copy()
        )


@dataclass
class VocabApp:
    """应用主要数据结构"""
    words: List[Word] = field(default_factory=list)
    progress: Dict[str, WordProgress] = field(default_factory=dict)
    current_index: int = 0
    show_meaning: bool = False
    error_mode: bool = False
    config: AppConfig = field(default_factory=AppConfig)

    def get_current_word(self) -> Optional[Word]:
        if 0 <= self.current_index < len(self.words):
            return self.words[self.current_index]
        return None

    def get_current_progress(self) -> WordProgress:
        word = self.get_current_word()
        if word:
            return self.progress.get(word.word, WordProgress())
        return WordProgress()

    def mark_seen(self):
        word = self.get_current_word()
        if word:
            if word.word not in self.progress:
                self.progress[word.word] = WordProgress()
            self.progress[word.word].seen += 1

    def mark_known(self):
        word = self.get_current_word()
        if word:
            if word.word not in self.progress:
                self.progress[word.word] = WordProgress()
            self.progress[word.word].known += 1
            self.mark_seen()

    def mark_unknown(self):
        word = self.get_current_word()
        if word:
            if word.word not in self.progress:
                self.progress[word.word] = WordProgress()
            self.progress[word.word].unknown += 1
            self.mark_seen()

    def toggle_starred(self):
        word = self.get_current_word()
        if word:
            if word.word not in self.progress:
                self.progress[word.word] = WordProgress()
            self.progress[word.word].starred = not self.progress[word.word].starred

    def get_stats(self) -> Stats:
        stats = Stats()
        stats.update_from_progress(self.progress)
        return stats

    def filter_error_words(self):
        error_words = []
        for word in self.words:
            progress = self.progress.get(word.word, WordProgress())
            if progress.starred or progress.unknown > 0:
                error_words.append(word)
        return error_words

    def create_snapshot(self) -> UISnapshot:
        words_order = [word.word for word in self.words]
        return UISnapshot(
            current_index=self.current_index,
            show_meaning=self.show_meaning,
            error_mode=self.error_mode,
            words_order=words_order
        )

    def restore_from_snapshot(self, snapshot: UISnapshot, all_words: List[Word]):
        self.current_index = snapshot.current_index
        self.show_meaning = snapshot.show_meaning
        self.error_mode = snapshot.error_mode

        if snapshot.words_order:
            word_dict = {word.word: word for word in all_words}
            restored_words = []
            for word_text in snapshot.words_order:
                if word_text in word_dict:
                    restored_words.append(word_dict[word_text])
            if restored_words:
                self.words = restored_words

        if self.current_index >= len(self.words):
            self.current_index = max(0, len(self.words) - 1)

