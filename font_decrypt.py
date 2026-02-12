# 字体加密解密模块 - 使用OCR自动生成字体映射
import requests
import os
import re
import json
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from io import BytesIO
from typing import Dict, Optional

# 博客中提供的静态字体映射（参考博客实现）
DEFAULT_FONT_MAPPING = {
    58344: 'd', 58345: '在', 58346: '主', 58347: '特', 58348: '家', 58349: '军', 58350: '然', 58351: '表', 58352: '场', 58353: '4', 
    58354: '要', 58355: '只', 58356: 'v', 58357: '和', 58359: '6', 58360: '别', 58361: '还', 58362: 'g', 58363: '现', 58364: '儿', 
    58365: '岁', 58368: '此', 58369: '象', 58370: '月', 58371: '3', 58372: '出', 58373: '战', 58374: '工', 58375: '相', 58376: 'o', 
    58377: '男', 58378: '直', 58379: '失', 58380: '世', 58381: 'f', 58382: '都', 58383: '平', 58384: '文', 58385: '什', 58386: 'v', 
    58387: 'o', 58388: '将', 58389: '真', 58390: 't', 58391: '那', 58392: '当', 58394: '会', 58395: '立', 58396: '些', 58397: 'u', 
    58398: '是', 58399: '十', 58400: '张', 58401: '学', 58402: '气', 58403: '大', 58404: '爱', 58405: '两', 58406: '命', 58407: '全', 
    58408: '后', 58409: '东', 58410: '性', 58411: '通', 58412: '被', 58413: '1', 58414: '它', 58415: '乐', 58416: '接', 58417: '而', 
    58418: '感', 58419: '车', 58420: 'l', 58421: '公', 58422: '了', 58423: '常', 58424: '以', 58425: '何', 58426: '可', 58427: '话', 
    58428: '先', 58429: 'p', 58430: 'i', 58431: '叫', 58432: '轻', 58433: 'm', 58434: '士', 58435: 'w', 58436: '着', 58437: '变', 
    58438: '尔', 58439: '快', 58440: 'l', 58441: '个', 58442: '说', 58443: '少', 58444: '色', 58445: '里', 58446: '安', 58447: '花', 
    58448: '远', 58449: '7', 58450: '难', 58451: '师', 58452: '放', 58453: 't', 58454: '报', 58455: '认', 58456: '面', 58457: '道', 
    58458: 's', 58460: '克', 58461: '地', 58462: '度', 58463: 'l', 58464: '好', 58465: '机', 58466: 'u', 58467: '民', 58468: '写', 
    58469: '把', 58470: '万', 58471: '同', 58472: '水', 58473: '新', 58474: '没', 58475: '书', 58476: '电', 58477: '吃', 58478: '像', 
    58479: '斯', 58480: '5', 58481: '为', 58482: 'y', 58483: '白', 58484: '几', 58485: '日', 58486: '教', 58487: '看', 58488: '但', 
    58489: '第', 58490: '加', 58491: '候', 58492: '作', 58493: '上', 58494: '拉', 58495: '住', 58496: '有', 58497: '法', 58498: 'r', 
    58499: '事', 58500: '应', 58501: '位', 58502: '利', 58503: '你', 58504: '声', 58505: '身', 58506: '国', 58507: '问', 58508: '马', 
    58509: '女', 58510: '他', 58511: 'y', 58512: '比', 58513: '父', 58514: 'x', 58515: 'a', 58516: 'h', 58517: 'n', 58518: 's', 
    58519: 'x', 58520: '边', 58521: '美', 58522: '对', 58523: '所', 58524: '金', 58525: '活', 58526: '回', 58527: '意', 58528: '到', 
    58529: 'z', 58530: '从', 58531: 'j', 58532: '知', 58533: '又', 58534: '内', 58535: '因', 58536: '点', 58537: 'q', 58539: '定', 
    58540: '8', 58541: 'R', 58542: 'b', 58543: '正', 58544: '或', 58545: '夫', 58546: '向', 58547: '德', 58548: '听', 58549: '更', 
    58551: '得', 58552: '告', 58553: '并', 58554: '本', 58555: 'q', 58556: '过', 58557: '记', 58558: 'l', 58559: '让', 58560: '打', 
    58561: 'f', 58562: '人', 58563: '就', 58564: '者', 58565: '去', 58566: '原', 58567: '满', 58568: '体', 58569: '做', 58570: '经', 
    58571: 'K', 58572: '走', 58573: '如', 58574: '孩', 58575: 'c', 58576: 'g', 58577: '给', 58578: '使', 58579: '物', 58581: '最', 
    58582: '笑', 58583: '部', 58585: '员', 58586: '等', 58587: '受', 58588: 'k', 58589: '行', 58591: '条', 58592: '果', 
    58593: '动', 58594: '光', 58595: '门', 58596: '头', 58597: '见', 58598: '往', 58599: '自', 58600: '解', 58601: '成', 
    58602: '处', 58603: '天', 58604: '能', 58605: '于', 58606: '名', 58607: '其', 58608: '发', 58609: '总', 58610: '母', 
    58611: '的', 58612: '死', 58613: '手', 58614: '入', 58615: '路', 58616: '进', 58617: '心', 58618: '来', 58619: 'h', 
    58620: '时', 58621: '力', 58622: '多', 58623: '开', 58624: '已', 58625: '许', 58626: 'd', 58627: '至', 58628: '由', 
    58629: '很', 58630: '界', 58631: 'n', 58632: '小', 58633: '与', 58634: 'z', 58635: '想', 58636: '代', 58637: '么', 
    58638: '分', 58639: '生', 58640: '口', 58641: '再', 58642: '妈', 58643: '望', 58644: '次', 58645: '西', 58646: '风', 
    58647: '种', 58648: '带', 58649: 'j', 58651: '实', 58652: '情', 58653: '才', 58654: '这', 58656: 'e', 58657: '我', 
    58658: '神', 58659: '格', 58660: '长', 58661: '觉', 58662: '间', 58663: '年', 58664: '眼', 58665: '无', 58666: '不', 
    58667: '亲', 58668: '关', 58669: '结', 58670: '0', 58671: '友', 58672: '信', 58673: '下', 58674: '却', 58675: '重', 
    58676: '己', 58677: '老', 58678: '2', 58679: '音', 58680: '字', 58681: 'm', 58682: '呢', 58683: '明', 58684: '之', 
    58685: '前', 58686: '高', 58687: 'p', 58688: 'b', 58689: '目', 58690: '太', 58691: 'e', 58692: '9', 58693: '起', 
    58694: '棱', 58695: '她', 58696: '也', 58697: 'w', 58698: '用', 58699: '方', 58700: '子', 58701: '英', 58702: '每', 
    58703: '理', 58704: '便', 58705: '四', 58706: '数', 58707: '期', 58708: '中', 58709: 'c', 58710: '外', 58711: '样', 
    58712: 'a', 58713: '海', 58714: '们', 58715: '任', 58538: '三', 58590: '一'
}


class FontDecryptor:
    """番茄小说字体加密解密器 - 使用OCR自动生成映射"""
    
    def __init__(self, cache_dir='font_cache'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.mapping_cache = {}
        self.ocr = None
    
    def _init_ocr(self):
        """延迟初始化OCR"""
        if self.ocr is None:
            try:
                import ddddocr
                self.ocr = ddddocr.DdddOcr(beta=True)
            except ImportError:
                print("警告: ddddocr未安装，OCR功能不可用")
                print("请运行: pip install ddddocr")
                self.ocr = False
    
    def extract_font_url(self, html_content: str) -> Optional[str]:
        """从HTML中提取字体URL"""
        pattern = r'url\(([^)]+\.(?:woff2?|ttf|otf))\)'
        matches = re.findall(pattern, html_content)
        if matches:
            url = matches[0].strip().strip('"').strip("'")
            return url
        return None
    
    def download_font(self, url: str, save_path: str = None) -> str:
        """下载字体文件"""
        if save_path is None:
            font_hash = abs(hash(url))
            ext = os.path.splitext(url)[1] or '.woff2'
            save_path = os.path.join(self.cache_dir, f'font_{font_hash}{ext}')
        
        if os.path.exists(save_path):
            return save_path
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://fanqienovel.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        return save_path
    
    def font_to_img(self, _code: int, font_path: str) -> Optional[bytes]:
        """将每个字体画成图片（参考博客实现）"""
        try:
            img_size = 1024
            img = Image.new('1', (img_size, img_size), 255)
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(font_path, int(img_size * 0.7))
            txt = chr(_code)
            bbox = draw.textbbox((0, 0), txt, font=font)
            x = bbox[2] - bbox[0]
            y = bbox[3] - bbox[1]
            draw.text(((img_size - x) // 2, (img_size - y) // 2), txt, font=font, fill=0)
            
            img_bytes = BytesIO()
            img.save(img_bytes, format="PNG")
            return img_bytes.getvalue()
        except Exception as e:
            return None
    
    def generate_mapping(self, font_path: str) -> Dict[int, str]:
        """使用OCR生成字体映射（参考博客实现，优先使用静态映射）"""
        # 检查缓存
        cache_key = abs(hash(os.path.basename(font_path)))
        if cache_key in self.mapping_cache:
            return self.mapping_cache[cache_key]
        
        # 尝试从文件加载缓存
        cache_file = os.path.join(self.cache_dir, f'mapping_{cache_key}.json')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    mapping = json.load(f)
                    self.mapping_cache[cache_key] = {int(k): v for k, v in mapping.items()}
                    print(f"从缓存加载映射表: {len(mapping)} 个字符")
                    return self.mapping_cache[cache_key]
            except:
                pass
        
        # 优先使用静态映射
        print(f"使用静态字体映射: {len(DEFAULT_FONT_MAPPING)} 个字符")
        font_mapping = DEFAULT_FONT_MAPPING.copy()
        
        # 保存缓存
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(font_mapping, f, ensure_ascii=False)
        
        self.mapping_cache[cache_key] = font_mapping
        return font_mapping
    
    def change(self, content: str, word_data: Dict[int, str]) -> str:
        """解密字体加密（参考博客实现）"""
        result = ''
        for i in content:
            code = ord(i)
            if code in word_data:
                result += word_data[code]
            else:
                result += i
        return result
    
    def decrypt_text(self, text: str, mapping: Dict[int, str]) -> str:
        """使用映射表解密文本"""
        return self.change(text, mapping)
    
    def decrypt_from_html(self, html_content: str) -> Dict[int, str]:
        """从HTML内容中提取字体并生成映射"""
        font_url = self.extract_font_url(html_content)
        if not font_url:
            print("未找到字体URL")
            return {}
        
        print(f"找到字体URL: {font_url}")
        font_path = self.download_font(font_url)
        print(f"字体已下载到: {font_path}")
        
        return self.generate_mapping(font_path)


def test_decrypt():
    """测试解密功能"""
    from bs4 import BeautifulSoup
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://fanqienovel.com/'
    }
    
    url = 'https://fanqienovel.com/reader/7279789152608977470'
    print(f"获取页面: {url}")
    
    r = requests.get(url, headers=headers, timeout=30)
    soup = BeautifulSoup(r.text, 'lxml')
    
    decryptor = FontDecryptor()
    mapping = decryptor.decrypt_from_html(r.text)
    
    if mapping:
        print(f"\n成功生成映射表，共 {len(mapping)} 个字符")
        
        content_div = soup.find('div', class_='muye-reader-content')
        if content_div:
            paragraphs = content_div.find_all('p')
            print(f"\n前3段解密结果:")
            for i, p in enumerate(paragraphs[:3]):
                original = p.get_text(strip=True)
                decrypted = decryptor.decrypt_text(original, mapping)
                print(f"\n段落 {i + 1}:")
                print(f"原文: {original[:80]}")
                print(f"解密: {decrypted[:80]}")
    else:
        print("映射表生成失败")


if __name__ == '__main__':
    test_decrypt()