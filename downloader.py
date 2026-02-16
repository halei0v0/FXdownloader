# 小说下载和导出模块
import os
from config import DOWNLOAD_DIR, OUTPUT_FORMAT
from database import NovelDatabase


class NovelDownloader:
    def __init__(self):
        self.db = NovelDatabase()
        self.download_ranges = {}  # 记录每个小说的下载范围
        self.current_source = None  # 当前使用的源：'official' 或 'third_party'

    def download_novel(self, spider, novel_id, start_chapter=1, end_chapter=None, source='official'):
        """
        下载小说

        Args:
            spider: 爬虫实例（FanqieSpider 或 ThirdPartyAdapter）
            novel_id: 小说ID
            start_chapter: 起始章节
            end_chapter: 结束章节
            source: 源类型：'official'（官网）或 'third_party'（第三方源）
        """
        self.current_source = source

        print(f"\n{'='*50}")
        print(f"开始下载小说: {novel_id}")
        print(f"下载源: {'官网' if source == 'official' else '第三方源'}")
        print(f"{'='*50}\n")

        # 清除该小说的所有旧数据（包括小说信息和章节）
        print(f"正在清除旧数据...")
        self.db.delete_novel(novel_id)
        print(f"旧数据已清除")

        # 记录下载范围
        download_start = start_chapter

        # 获取小说信息
        novel_info = spider.get_novel_info(novel_id)
        if not novel_info:
            print("获取小说信息失败！")
            return False

        print(f"小说名称: {novel_info['title']}")
        print(f"作者: {novel_info['author']}")
        print(f"字数: {novel_info['word_count']}")
        print(f"章节数: {novel_info['chapter_count']}")
        print()

        # 保存小说信息到数据库
        self.db.save_novel(
            novel_id=novel_info['novel_id'],
            title=novel_info['title'],
            author=novel_info['author'],
            description=novel_info['description'],
            cover_url=novel_info['cover_url'],
            word_count=novel_info['word_count'],
            chapter_count=novel_info['chapter_count']
        )

        # 获取章节列表
        chapters = spider.get_chapter_list(novel_id)
        if not chapters:
            print("获取章节列表失败！")
            return False

        total_chapters = len(chapters)
        print(f"共获取到 {total_chapters} 个章节\n")

        # 确定下载范围
        start_index = max(1, start_chapter) - 1
        end_index = min(total_chapters, end_chapter) if end_chapter else total_chapters
        
        print(f"下载范围: 第 {start_index + 1} 章到第 {end_index} 章")
        print(f"{'='*50}\n")

        # 下载章节
        success_count = 0
        for idx in range(start_index, end_index):
            chapter = chapters[idx]
            chapter_id = chapter['chapter_id']
            chapter_title = chapter['chapter_title']
            chapter_index = chapter['chapter_index']

            print(f"[{chapter_index}/{total_chapters}] 正在下载: {chapter_title}")

            # 获取章节内容（包含标题和内容）
            # 注意：第三方源返回的内容已经是纯文本，不需要字体解密
            chapter_data = spider.get_chapter_content(novel_id, chapter_id)

            if chapter_data:
                # 使用返回的真实标题
                real_title = chapter_data.get('title', chapter_title)
                content = chapter_data.get('content', '')
                word_count = len(content)
                
                # 保存到数据库
                self.db.save_chapter(
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    chapter_title=real_title,
                    chapter_index=chapter_index,
                    content=content,
                    word_count=word_count
                )
                success_count += 1
                print(f"  ✓ 成功下载 - {real_title} ({word_count} 字)")
            else:
                print(f"  ✗ 下载失败")

        print(f"\n{'='*50}")
        print(f"下载完成！成功下载 {success_count}/{end_index - start_index} 个章节")
        print(f"{'='*50}\n")

        # 记录下载范围
        self.download_ranges[novel_id] = (download_start, end_index)

        # 更新小说状态
        if success_count == end_index - start_index:
            self.db.update_novel_status(novel_id, '下载完成')
        else:
            self.db.update_novel_status(novel_id, '部分下载')

        return success_count > 0

    def export_to_txt(self, novel_id, output_path=None):
        """导出为TXT文件"""
        novel = self.db.get_novel(novel_id)
        if not novel:
            print("小说不存在！")
            return False

        # 使用记录的下载范围，如果没有记录则导出所有章节
        if novel_id in self.download_ranges:
            start_index, end_index = self.download_ranges[novel_id]
            chapters = self.db.get_chapters_range(novel_id, start_index, end_index)
            print(f"导出范围: 第{start_index}章 - 第{end_index}章")
        else:
            chapters = self.db.get_chapters(novel_id)
            print(f"导出所有章节")

        if not chapters:
            print("没有可导出的章节！")
            return False

        # 确定输出路径
        if not output_path:
            filename = f"{novel['title']}.txt"
            output_path = os.path.join(DOWNLOAD_DIR, filename)
        elif os.path.isdir(output_path):
            # 如果是文件夹路径，则在文件夹中生成文件名
            filename = f"{novel['title']}.txt"
            output_path = os.path.join(output_path, filename)

        print(f"正在导出到: {output_path}")

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # 写入小说信息
                f.write("=" * 50 + "\n")
                f.write(f"书名: {novel['title']}\n")
                f.write(f"作者: {novel['author']}\n")
                f.write(f"简介: {novel['description']}\n")
                f.write(f"字数: {novel['word_count']:,} 字\n")
                f.write(f"章节数: {novel['chapter_count']} 章\n")
                f.write("=" * 50 + "\n\n")

                # 写入章节内容
                for chapter in chapters:
                    f.write(f"\n{'='*30}\n")
                    f.write(f"{chapter['chapter_title']}\n")
                    f.write(f"{'='*30}\n\n")
                    f.write(chapter['content'])
                    f.write("\n")

            print(f"✓ 导出成功！文件保存到: {output_path}")
            return True

        except PermissionError:
            print(f"✗ 导出失败: 权限不足，无法保存历史记录，请将软件放在C盘以外【不受保护的】磁盘中 {output_path}")
            return False
        except OSError as e:
            print(f"✗ 导出失败: 系统错误 - {e}")
            return False
        except Exception as e:
            print(f"✗ 导出失败: {e}")
            return False

    def list_novels(self):
        """列出所有已下载的小说"""
        novels = self.db.get_all_novels()
        if not novels:
            print("暂无已下载的小说")
            return

        print(f"\n{'='*60}")
        print(f"{'小说列表':^60}")
        print(f"{'='*60}\n")

        for idx, novel in enumerate(novels, 1):
            print(f"{idx}. {novel['title']}")
            print(f"   作者: {novel['author']}")
            print(f"   状态: {novel['status']}")
            print(f"   章节数: {novel['chapter_count']}")
            print(f"   字数: {novel['word_count']:,}")
            print(f"   小说ID: {novel['novel_id']}")
            print()

    def delete_novel(self, novel_id):
        """删除小说"""
        novel = self.db.get_novel(novel_id)
        if not novel:
            print("小说不存在！")
            return False

        confirm = input(f"确定要删除《{novel['title']}》吗？: ")
        if confirm.lower() == 'y':
            self.db.delete_novel(novel_id)
            print(f"✓ 已删除《{novel['title']}》")
            return True
        else:
            print("已取消删除")
            return False