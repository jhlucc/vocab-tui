import csv
import json
import os
from typing import List, Dict

from models import Word, WordProgress


class Storage:
    """文件存储管理类"""

    def __init__(self, words_file: str = "words.csv", progress_file: str = "progress.json"):
        self.words_file = words_file
        self.progress_file = progress_file

    def load_words(self) -> List[Word]:
        """从CSV文件加载单词"""
        words = []
        if not os.path.exists(self.words_file):
            return words
        try:
            with open(self.words_file, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    word = Word(
                        word=row['word'].strip(),
                        meaning=row['meaning'].strip(),
                        phonetic=row.get('phonetic', '').strip() or None,
                        example=row.get('example', '').strip() or None
                    )
                    words.append(word)
        except Exception as e:
            print(f"加载单词文件失败: {e}")
        return words

    def load_progress(self) -> Dict[str, WordProgress]:
        """从JSON文件加载学习进度"""
        progress = {}
        if not os.path.exists(self.progress_file):
            return progress
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for word, progress_data in data.items():
                    progress[word] = WordProgress(
                        seen=progress_data.get('seen', 0),
                        known=progress_data.get('known', 0),
                        unknown=progress_data.get('unknown', 0),
                        starred=progress_data.get('starred', False)
                    )
        except Exception as e:
            print(f"加载进度文件失败: {e}")
        return progress

    def save_progress(self, progress: Dict[str, WordProgress]) -> bool:
        """保存学习进度到JSON文件"""
        try:
            data = {}
            for word, wp in progress.items():
                data[word] = {
                    'seen': wp.seen,
                    'known': wp.known,
                    'unknown': wp.unknown,
                    'starred': wp.starred
                }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存进度文件失败: {e}")
            return False

    def create_sample_words_file(self):
        """创建示例单词文件"""
        sample_words = [
            {'word': 'apple', 'meaning': 'n. 苹果', 'phonetic': '/ˈæpəl/', 'example': 'I like to eat an apple every day.'},
            {'word': 'beautiful', 'meaning': 'adj. 美丽的，漂亮的', 'phonetic': '/ˈbjuːtɪfəl/', 'example': 'She is a beautiful girl.'},
            {'word': 'computer', 'meaning': 'n. 计算机，电脑', 'phonetic': '/kəmˈpjuːtər/', 'example': 'I use my computer for work and entertainment.'},
            {'word': 'difficult', 'meaning': 'adj. 困难的，艰难的', 'phonetic': '/ˈdɪfɪkəlt/', 'example': 'This math problem is very difficult.'},
            {'word': 'environment', 'meaning': 'n. 环境', 'phonetic': '/ɪnˈvaɪrənmənt/', 'example': 'We should protect our environment.'},
            {'word': 'fantastic', 'meaning': 'adj. 极好的，了不起的', 'phonetic': '/fænˈtæstɪk/', 'example': 'The movie was fantastic!'},
            {'word': 'government', 'meaning': 'n. 政府', 'phonetic': '/ˈɡʌvərnmənt/', 'example': 'The government made a new policy.'},
            {'word': 'happiness', 'meaning': 'n. 幸福，快乐', 'phonetic': '/ˈhæpɪnəs/', 'example': 'Money cannot buy happiness.'},
        ]
        try:
            with open(self.words_file, 'w', encoding='utf-8', newline='') as f:
                fieldnames = ['word', 'meaning', 'phonetic', 'example']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(sample_words)
            return True
        except Exception as e:
            print(f"创建示例文件失败: {e}")
            return False

    def file_exists(self, filename: str = None) -> bool:
        """检查文件是否存在"""
        if filename is None:
            filename = self.words_file
        return os.path.exists(filename)

