# 番茄小说下载器主程序
import sys
import argparse
from spider import FanqieSpider, parse_novel_url
from downloader import NovelDownloader


def print_banner():
    """打印程序横幅"""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║              番茄小说下载器 v1.0                          ║
║                                                           ║
║     一个简单易用的番茄小说平台下载工具                    ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


def cmd_download(args):
    """下载小说命令"""
    spider = FanqieSpider()
    downloader = NovelDownloader()

    # 解析小说ID
    novel_id = parse_novel_url(args.url)
    if not novel_id:
        print("错误: 无效的小说URL或ID")
        return

    # 下载小说
    success = downloader.download_novel(
        spider,
        novel_id,
        start_chapter=args.start,
        end_chapter=args.end
    )

    if success:
        # 自动导出
        if args.export:
            downloader.export_to_txt(novel_id, args.output)
        else:
            # 询问是否导出
            export = input("\n是否导出为TXT文件？(y/n): ")
            if export.lower() == 'y':
                downloader.export_to_txt(novel_id)


def cmd_search(args):
    """搜索小说命令"""
    spider = FanqieSpider()
    
    results = spider.search_novel(args.keyword)
    
    if not results:
        print("未找到相关小说")
        return
    
    print(f"\n搜索结果 (关键词: {args.keyword})")
    print("=" * 60)
    
    for idx, novel in enumerate(results, 1):
        print(f"\n{idx}. {novel['title']}")
        print(f"   作者: {novel['author']}")
        print(f"   小说ID: {novel['novel_id']}")
        print(f"   字数: {novel['word_count']:,}")
        print(f"   简介: {novel['description'][:100]}...")


def cmd_list(args):
    """列出小说命令"""
    downloader = NovelDownloader()
    downloader.list_novels()


def cmd_export(args):
    """导出小说命令"""
    downloader = NovelDownloader()
    downloader.export_to_txt(args.novel_id, args.output)


def cmd_delete(args):
    """删除小说命令"""
    downloader = NovelDownloader()
    downloader.delete_novel(args.novel_id)


def main():
    """主函数"""
    print_banner()
    
    parser = argparse.ArgumentParser(
        description='番茄小说下载器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 下载小说（指定URL）
  python main.py download https://fanqienovel.com/page/711914860
  
  # 下载小说（指定小说ID）
  python main.py download 711914860
  
  # 下载指定章节范围
  python main.py download 711914860 --start 1 --end 50
  
  # 下载并自动导出
  python main.py download 711914860 --export
  
  # 搜索小说
  python main.py search 诡秘之主
  
  # 列出已下载的小说
  python main.py list
  
  # 导出已下载的小说
  python main.py export 711914860
  
  # 删除小说
  python main.py delete 711914860
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # download 命令
    download_parser = subparsers.add_parser('download', help='下载小说')
    download_parser.add_argument('url', help='小说URL或ID')
    download_parser.add_argument('--start', type=int, default=1, help='起始章节（默认: 1）')
    download_parser.add_argument('--end', type=int, default=None, help='结束章节（默认: 全部）')
    download_parser.add_argument('--export', action='store_true', help='下载后自动导出')
    download_parser.add_argument('--output', help='导出文件路径')
    download_parser.set_defaults(func=cmd_download)

    # search 命令
    search_parser = subparsers.add_parser('search', help='搜索小说')
    search_parser.add_argument('keyword', help='搜索关键词')
    search_parser.set_defaults(func=cmd_search)

    # list 命令
    list_parser = subparsers.add_parser('list', help='列出已下载的小说')
    list_parser.set_defaults(func=cmd_list)

    # export 命令
    export_parser = subparsers.add_parser('export', help='导出小说为TXT')
    export_parser.add_argument('novel_id', help='小说ID')
    export_parser.add_argument('--output', help='导出文件路径')
    export_parser.set_defaults(func=cmd_export)

    # delete 命令
    delete_parser = subparsers.add_parser('delete', help='删除小说')
    delete_parser.add_argument('novel_id', help='小说ID')
    delete_parser.set_defaults(func=cmd_delete)

    # 如果没有参数，显示帮助
    if len(sys.argv) == 1:
        parser.print_help()
        return

    # 解析参数并执行命令
    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()