"""地点显示名统一：常见国际通信节点城市的外文名、缩写和城区名统一成中文城市名；全大写外文名改成首字母大写。

只用于两段式按层取值后的显示和同地合并；原文写法保留在报告说明里。表里只收无歧义的写法，
收不到的地名原样输出（不猜）。
"""
import re

# 标准中文名: 外文名、常见缩写、城区／区县名（城区归到所属城市）
_CITIES = {
    "香港": ["Hong Kong", "HongKong", "HK", "HKG", "Kennedy Town", "Sheung Wan", "Wan Chai", "Causeway Bay",
             "Chai Wan", "Quarry Bay", "Kwun Tong", "Kowloon", "Kowloon Bay", "Tsuen Wan", "Kwai Chung", "Tseung Kwan O",
             "Sha Tin", "Shatin", "Tai Po", "Fo Tan", "Mong Kok", "Tsim Sha Tsui", "Cyberport", "坚尼地城", "将军澳",
             "葵涌", "荃湾", "观塘", "沙田", "柴湾", "九龙", "中环", "湾仔"],
    "澳门": ["Macau", "Macao"],
    "台北": ["Taipei"],
    "新加坡": ["Singapore", "SG", "SIN", "Jurong", "Tuas", "Changi", "Loyang", "Tai Seng", "Ayer Rajah"],
    "吉隆坡": ["Kuala Lumpur", "KL", "Cyberjaya"],
    "雅加达": ["Jakarta"],
    "曼谷": ["Bangkok", "BKK"],
    "胡志明市": ["Ho Chi Minh City", "Ho Chi Minh", "HCMC", "HCM", "Saigon", "SGN"],
    "河内": ["Hanoi", "Ha Noi"],
    "马尼拉": ["Manila"],
    "金边": ["Phnom Penh"],
    "万象": ["Vientiane"],
    "仰光": ["Yangon"],
    "东京": ["Tokyo"],
    "大阪": ["Osaka"],
    "首尔": ["Seoul"],
    "釜山": ["Busan"],
    "孟买": ["Mumbai"],
    "钦奈": ["Chennai"],
    "新德里": ["New Delhi"],
    "卡拉奇": ["Karachi"],
    "迪拜": ["Dubai"],
    "富查伊拉": ["Fujairah"],
    "多哈": ["Doha"],
    "利雅得": ["Riyadh"],
    "吉达": ["Jeddah"],
    "伊斯坦布尔": ["Istanbul"],
    "开罗": ["Cairo"],
    "约翰内斯堡": ["Johannesburg"],
    "开普敦": ["Cape Town"],
    "内罗毕": ["Nairobi"],
    "拉各斯": ["Lagos"],
    "伦敦": ["London"],
    "巴黎": ["Paris"],
    "马赛": ["Marseille"],
    "法兰克福": ["Frankfurt", "Frankfurt am Main", "FRA"],
    "柏林": ["Berlin"],
    "慕尼黑": ["Munich", "München"],
    "阿姆斯特丹": ["Amsterdam", "AMS"],
    "布鲁塞尔": ["Brussels"],
    "苏黎世": ["Zurich", "Zürich"],
    "日内瓦": ["Geneva"],
    "维也纳": ["Vienna"],
    "米兰": ["Milan"],
    "马德里": ["Madrid"],
    "斯德哥尔摩": ["Stockholm"],
    "哥本哈根": ["Copenhagen"],
    "赫尔辛基": ["Helsinki"],
    "华沙": ["Warsaw"],
    "布拉格": ["Prague"],
    "莫斯科": ["Moscow"],
    "新西伯利亚": ["Novosibirsk"],
    "鄂木斯克": ["Omsk"],
    "彼尔姆": ["Perm"],
    "乌兰巴托": ["Ulaanbaatar", "Ulan Bator"],
    "阿拉木图": ["Almaty"],
    "纽约": ["New York", "New York City", "NYC"],
    "洛杉矶": ["Los Angeles"],
    "旧金山": ["San Francisco"],
    "圣何塞": ["San Jose"],
    "西雅图": ["Seattle"],
    "芝加哥": ["Chicago"],
    "达拉斯": ["Dallas"],
    "迈阿密": ["Miami"],
    "阿什本": ["Ashburn"],
    "多伦多": ["Toronto"],
    "温哥华": ["Vancouver"],
    "蒙特利尔": ["Montreal"],
    "墨西哥城": ["Mexico City"],
    "圣保罗": ["Sao Paulo", "São Paulo"],
    "悉尼": ["Sydney"],
    "墨尔本": ["Melbourne"],
    "珀斯": ["Perth"],
    "奥克兰": ["Auckland"],
}


def _key(name):
    return re.sub(r"[\s.\-_'’]+", "", name).lower()


_ALIASES = {_key(alias): city for city, aliases in _CITIES.items() for alias in [city, *aliases]}


def display_place(name):
    """返回统一后的显示名；表里没有的原样返回（多词全大写的外文地名改成首字母大写）。线路段“甲–乙段”逐端统一。"""
    if not name:
        return name
    if name.endswith("段") and "–" in name:
        ends = name[:-1].split("–")
        return "–".join(display_place(e) for e in ends) + "段"
    city = _ALIASES.get(_key(name))
    if city:
        return city
    words = name.split(" ")
    if name.isascii() and name.isupper() and len(words) > 1 and all(w.isalpha() and len(w) > 2 for w in words):
        # 只改多词全大写地名（NEW BRUNSWICK）；单词全大写多半是缩写（OTDR、POP），不动
        return " ".join(w.capitalize() for w in name.split(" "))
    return name


_PROVINCE = re.compile(r"^.{2,8}?(?:省|自治区|特别行政区)")
_CITY = re.compile(r"^(.{2,6}?)市")
_COUNTY = re.compile(r"(?:自治州|地区|盟)(.{2,4}?)(?:县|旗)")


def address_city(text):
    """工单系统“故障地址”字段（如“江苏省南京市”“上海市市辖区”“云南省西双版纳傣族自治州勐腊县”）里的城市名。

    只认国内行政区划写法；“海外”、空值和认不出的返回 None（不猜）。
    """
    t = re.sub(r"\s+", "", text or "")
    if not t or t == "海外":
        return None
    if t in _CITIES:
        return t  # 香港、澳门这类直接写城市名的
    rest = _PROVINCE.sub("", t)
    m = _CITY.match(rest)
    if m:
        return m.group(1)
    m = _COUNTY.search(rest)
    return m.group(1) if m else None
