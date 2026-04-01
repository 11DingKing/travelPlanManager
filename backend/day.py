"""
旅行计划管理器
功能：目的地管理、日期安排、行程规划、住宿信息、物品清单、预算计算
UI：左右分栏布局 - 左侧菜单固定，右侧显示内容
"""

import json
import os
import logging
import re
import shutil
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('travel_manager.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Validator:
    """输入校验类"""
    DATE_PATTERN = r'^\d{4}-\d{2}-\d{2}$'
    TIME_PATTERN = r'^\d{2}:\d{2}$'
    
    @staticmethod
    def validate_date(date_str):
        if not re.match(Validator.DATE_PATTERN, date_str):
            return False, "日期格式错误，请使用 YYYY-MM-DD 格式"
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True, ""
        except ValueError:
            return False, "无效的日期，请检查年月日是否正确"
    
    @staticmethod
    def validate_time(time_str):
        if not re.match(Validator.TIME_PATTERN, time_str):
            return False, "时间格式错误，请使用 HH:MM 格式"
        try:
            datetime.strptime(time_str, '%H:%M')
            return True, ""
        except ValueError:
            return False, "无效的时间，请检查时分是否正确"
    
    @staticmethod
    def validate_time_range(start_time, end_time):
        valid, msg = Validator.validate_time(start_time)
        if not valid:
            return False, f"开始时间: {msg}"
        valid, msg = Validator.validate_time(end_time)
        if not valid:
            return False, f"结束时间: {msg}"
        if start_time >= end_time:
            return False, "开始时间不能晚于或等于结束时间"
        return True, ""
    
    @staticmethod
    def validate_date_range(start_date, end_date):
        valid, msg = Validator.validate_date(start_date)
        if not valid:
            return False, f"开始日期: {msg}"
        valid, msg = Validator.validate_date(end_date)
        if not valid:
            return False, f"结束日期: {msg}"
        if start_date > end_date:
            return False, "开始日期不能晚于结束日期"
        return True, ""
    
    @staticmethod
    def validate_not_empty(value, field_name):
        if not value or not value.strip():
            return False, f"{field_name}不能为空"
        return True, ""
    
    @staticmethod
    def validate_positive_number(value, field_name):
        try:
            num = float(value)
            if num < 0:
                return False, f"{field_name}不能为负数"
            return True, num
        except (ValueError, TypeError):
            return False, f"{field_name}必须是有效数字"


class Attraction:
    """景点类"""
    def __init__(self, name, ticket_price=0, open_time="", note="", start_time="", end_time=""):
        self.name = name
        self.ticket_price = ticket_price
        self.open_time = open_time
        self.note = note
        self.start_time = start_time
        self.end_time = end_time
    
    def to_dict(self):
        return {"name": self.name, "ticket_price": self.ticket_price, 
                "open_time": self.open_time, "note": self.note,
                "start_time": self.start_time, "end_time": self.end_time}
    
    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data.get("ticket_price", 0), 
                   data.get("open_time", ""), data.get("note", ""),
                   data.get("start_time", ""), data.get("end_time", ""))
    
    def format_line(self):
        time_info = f" [{self.start_time}-{self.end_time}]" if self.start_time and self.end_time else ""
        return f"    📍 {self.name}{time_info} | ¥{self.ticket_price} | {self.open_time} | {self.note}"


class DayPlan:
    """每日行程类"""
    def __init__(self, day_number, description=""):
        self.day_number = day_number
        self.description = description
        self.attractions = []
    
    def _check_time_conflict(self, new_attr):
        """检查新景点与已有景点是否有时间段冲突"""
        if not new_attr.start_time or not new_attr.end_time:
            return False, None
        for existing_attr in self.attractions:
            if not existing_attr.start_time or not existing_attr.end_time:
                continue
            if not (new_attr.end_time <= existing_attr.start_time or new_attr.start_time >= existing_attr.end_time):
                return True, existing_attr
        return False, None
    
    def add_attraction(self, attraction):
        has_conflict, conflict_attr = self._check_time_conflict(attraction)
        if has_conflict:
            msg = f"时间冲突！'{attraction.name}' ({attraction.start_time}-{attraction.end_time}) 与 '{conflict_attr.name}' ({conflict_attr.start_time}-{conflict_attr.end_time}) 时间段重叠"
            logger.warning(msg)
            return False, msg
        self.attractions.append(attraction)
        logger.info(f"添加景点: {attraction.name}")
        return True, "添加成功"
    
    def remove_attraction(self, name):
        before = len(self.attractions)
        self.attractions = [a for a in self.attractions if a.name != name]
        if len(self.attractions) < before:
            logger.info(f"删除景点: {name}")
    
    def to_dict(self):
        return {"day_number": self.day_number, "description": self.description,
                "attractions": [a.to_dict() for a in self.attractions]}
    
    @classmethod
    def from_dict(cls, data):
        plan = cls(data["day_number"], data.get("description", ""))
        for attr_data in data.get("attractions", []):
            plan.attractions.append(Attraction.from_dict(attr_data))
        return plan


class PackingItem:
    """物品清单项"""
    def __init__(self, name, packed=False):
        self.name = name
        self.packed = packed
    
    def to_dict(self):
        return {"name": self.name, "packed": self.packed}
    
    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data.get("packed", False))


class Accommodation:
    """住宿信息类"""
    def __init__(self, name, address="", phone="", price=0):
        self.name = name
        self.address = address
        self.phone = phone
        self.price = price
    
    def to_dict(self):
        return {"name": self.name, "address": self.address, 
                "phone": self.phone, "price": self.price}
    
    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data.get("address", ""), 
                   data.get("phone", ""), data.get("price", 0))


class Budget:
    """预算类"""
    def __init__(self):
        self.transportation = 0
        self.accommodation = 0
        self.food = 0
        self.tickets = 0
        self.other = 0
    
    def total(self):
        return self.transportation + self.accommodation + self.food + self.tickets + self.other
    
    def to_dict(self):
        return {"transportation": self.transportation, "accommodation": self.accommodation,
                "food": self.food, "tickets": self.tickets, "other": self.other}
    
    @classmethod
    def from_dict(cls, data):
        budget = cls()
        budget.transportation = data.get("transportation", 0)
        budget.accommodation = data.get("accommodation", 0)
        budget.food = data.get("food", 0)
        budget.tickets = data.get("tickets", 0)
        budget.other = data.get("other", 0)
        return budget


class TravelPlan:
    """旅行计划类"""
    def __init__(self, plan_id, destination, start_date, end_date):
        self.plan_id = plan_id
        self.destination = destination
        self.start_date = start_date
        self.end_date = end_date
        self.day_plans = []
        self.packing_list = []
        self.accommodation = None
        self.budget = Budget()
    
    def add_day_plan(self, day_plan):
        self.day_plans.append(day_plan)
        self.day_plans.sort(key=lambda x: x.day_number)
        logger.info(f"计划#{self.plan_id} 添加 Day {day_plan.day_number}")
    
    def remove_day_plan(self, day_number):
        before = len(self.day_plans)
        self.day_plans = [d for d in self.day_plans if d.day_number != day_number]
        if len(self.day_plans) < before:
            logger.info(f"计划#{self.plan_id} 删除 Day {day_number}")
    
    def get_day_plan(self, day_number):
        for plan in self.day_plans:
            if plan.day_number == day_number:
                return plan
        return None
    
    def add_packing_item(self, item):
        self.packing_list.append(item)
        logger.info(f"计划#{self.plan_id} 添加物品: {item.name}")
    
    def remove_packing_item(self, name):
        before = len(self.packing_list)
        self.packing_list = [i for i in self.packing_list if i.name != name]
        if len(self.packing_list) < before:
            logger.info(f"计划#{self.plan_id} 删除物品: {name}")
    
    def mark_item_packed(self, name, packed=True):
        for item in self.packing_list:
            if item.name == name:
                item.packed = packed
                logger.info(f"计划#{self.plan_id} 物品 {name} 标记为 {'已打包' if packed else '未打包'}")
                return True
        return False
    
    def to_dict(self):
        return {
            "plan_id": self.plan_id, "destination": self.destination,
            "start_date": self.start_date, "end_date": self.end_date,
            "day_plans": [d.to_dict() for d in self.day_plans],
            "packing_list": [i.to_dict() for i in self.packing_list],
            "accommodation": self.accommodation.to_dict() if self.accommodation else None,
            "budget": self.budget.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data):
        plan = cls(data["plan_id"], data["destination"], data["start_date"], data["end_date"])
        for day_data in data.get("day_plans", []):
            plan.day_plans.append(DayPlan.from_dict(day_data))
        for item_data in data.get("packing_list", []):
            plan.packing_list.append(PackingItem.from_dict(item_data))
        if data.get("accommodation"):
            plan.accommodation = Accommodation.from_dict(data["accommodation"])
        if data.get("budget"):
            plan.budget = Budget.from_dict(data["budget"])
        return plan


class TravelManager:
    """旅行计划管理器"""
    def __init__(self, data_file="travel_plans.json"):
        self.data_file = data_file
        self.plans = {}
        self.next_id = 1
        self.load_data()
    
    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.next_id = data.get("next_id", 1)
                    for plan_data in data.get("plans", []):
                        plan = TravelPlan.from_dict(plan_data)
                        self.plans[plan.plan_id] = plan
                logger.info(f"成功加载 {len(self.plans)} 个旅行计划")
            except Exception as e:
                logger.error(f"加载数据失败: {e}")
    
    def save_data(self):
        try:
            data = {"next_id": self.next_id, "plans": [p.to_dict() for p in self.plans.values()]}
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
    
    def add_plan(self, destination, start_date, end_date):
        plan = TravelPlan(self.next_id, destination, start_date, end_date)
        self.plans[self.next_id] = plan
        logger.info(f"创建计划 #{self.next_id}: {destination}")
        self.next_id += 1
        self.save_data()
        return plan
    
    def delete_plan(self, plan_id):
        if plan_id in self.plans:
            del self.plans[plan_id]
            logger.info(f"删除计划 #{plan_id}")
            self.save_data()
            return True
        return False
    
    def get_plan(self, plan_id):
        return self.plans.get(plan_id)
    
    def update_plan(self, plan_id, **kwargs):
        plan = self.plans.get(plan_id)
        if plan:
            for key in ["destination", "start_date", "end_date"]:
                if key in kwargs:
                    setattr(plan, key, kwargs[key])
            self.save_data()
            return True
        return False
    
    def list_all_plans(self):
        return list(self.plans.values())
    
    def search_by_destination(self, destination):
        return [p for p in self.plans.values() if destination.lower() in p.destination.lower()]
    
    def search_by_date(self, date):
        return [p for p in self.plans.values() if p.start_date <= date <= p.end_date]


class ScreenUI:
    """分栏式终端UI - 左侧菜单固定，右侧显示内容"""
    
    MENU_WIDTH = 32
    
    @staticmethod
    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def get_terminal_size():
        size = shutil.get_terminal_size((100, 30))
        return size.columns, size.lines
    
    @staticmethod
    def _display_width(text):
        """计算显示宽度（中文字符占2格）"""
        width = 0
        for char in text:
            # 中文字符范围
            if '\u4e00' <= char <= '\u9fff' or '\u3000' <= char <= '\u303f' or '\uff00' <= char <= '\uffef':
                width += 2
            else:
                width += 1
        return width
    
    @staticmethod
    def _pad_to_width(text, target_width):
        """填充文本到指定显示宽度"""
        current_width = ScreenUI._display_width(text)
        if current_width >= target_width:
            return text
        return text + ' ' * (target_width - current_width)
    
    @staticmethod
    def draw_split_screen(menu_lines, content_lines, title=""):
        """绘制左右分栏界面"""
        ScreenUI.clear_screen()
        width, height = ScreenUI.get_terminal_size()
        content_width = width - ScreenUI.MENU_WIDTH - 4
        
        # 标题
        print('=' * width)
        header = f"旅行计划管理器 {title}"
        print(header)
        print('=' * width)
        
        # 计算显示行数
        display_lines = height - 8
        
        # 复制列表避免修改原始数据
        menu_copy = list(menu_lines)
        content_copy = list(content_lines)
        
        # 补齐行数
        while len(menu_copy) < display_lines:
            menu_copy.append("")
        while len(content_copy) < display_lines:
            content_copy.append("")
        
        # 绘制左右分栏
        for i in range(display_lines):
            menu_text = menu_copy[i] if i < len(menu_copy) else ""
            content_text = content_copy[i] if i < len(content_copy) else ""
            
            # 填充到固定宽度
            menu_padded = ScreenUI._pad_to_width(menu_text, ScreenUI.MENU_WIDTH)
            content_padded = ScreenUI._pad_to_width(content_text, content_width)
            
            print(f"|{menu_padded}| {content_padded}|")
        
        print('=' * width)


def get_main_menu():
    """获取主菜单行"""
    return [
        "+------------------------------+",
        "|         主菜单               |",
        "+------------------------------+",
        "|  1. 添加新旅行计划           |",
        "|  2. 查看所有计划             |",
        "|  3. 查看计划详情             |",
        "|  4. 修改计划                 |",
        "|  5. 删除计划                 |",
        "|  6. 按目的地搜索             |",
        "|  7. 按日期搜索               |",
        "|  8. 管理行程安排             |",
        "|  9. 管理物品清单             |",
        "| 10. 管理住宿信息             |",
        "| 11. 管理预算                 |",
        "+------------------------------+",
        "|  0. 退出                     |",
        "+------------------------------+",
    ]


def get_day_menu():
    """行程管理子菜单"""
    return [
        "+------------------------------+",
        "|      行程安排管理            |",
        "+------------------------------+",
        "|  1. 添加每日行程             |",
        "|  2. 删除每日行程             |",
        "|  3. 添加景点                 |",
        "|  4. 删除景点                 |",
        "+------------------------------+",
        "|  0. 返回                     |",
        "+------------------------------+",
    ]


def get_packing_menu():
    """物品清单子菜单"""
    return [
        "+------------------------------+",
        "|      物品清单管理            |",
        "+------------------------------+",
        "|  1. 添加物品                 |",
        "|  2. 删除物品                 |",
        "|  3. 标记已打包               |",
        "|  4. 取消打包标记             |",
        "+------------------------------+",
        "|  0. 返回                     |",
        "+------------------------------+",
    ]


def get_budget_menu():
    """预算管理子菜单"""
    return [
        "+------------------------------+",
        "|        预算管理              |",
        "+------------------------------+",
        "|  1. 设置交通费用             |",
        "|  2. 设置住宿费用             |",
        "|  3. 设置餐饮费用             |",
        "|  4. 设置门票费用             |",
        "|  5. 设置其他费用             |",
        "|  6. 查看预算汇总             |",
        "+------------------------------+",
        "|  0. 返回                     |",
        "+------------------------------+",
    ]


def format_plan_detail(plan):
    """格式化计划详情为行列表"""
    lines = [
        f"旅行计划 #{plan.plan_id}",
        "",
        f"目的地: {plan.destination}",
        f"日期: {plan.start_date} 至 {plan.end_date}",
        "",
    ]
    
    if plan.accommodation:
        a = plan.accommodation
        lines.append(f"住宿: {a.name}")
        lines.append(f"  地址: {a.address}")
        lines.append(f"  电话: {a.phone} | {a.price}元/晚")
        lines.append("")
    
    lines.append("【行程安排】")
    if plan.day_plans:
        for day in plan.day_plans:
            lines.append(f"  Day {day.day_number}: {day.description}")
            for attr in day.attractions:
                time_info = f" [{attr.start_time}-{attr.end_time}]" if attr.start_time and attr.end_time else ""
                info = f"    - {attr.name}{time_info} | {attr.ticket_price}元"
                if attr.open_time:
                    info += f" | {attr.open_time}"
                if attr.note:
                    info += f" | 备注: {attr.note}"
                lines.append(info)
    else:
        lines.append("  暂无行程安排")
    
    lines.append("")
    lines.append("【物品清单】")
    if plan.packing_list:
        packed = sum(1 for i in plan.packing_list if i.packed)
        lines.append(f"  ({packed}/{len(plan.packing_list)} 已打包)")
        for item in plan.packing_list:
            status = "[v]" if item.packed else "[ ]"
            lines.append(f"  {status} {item.name}")
    else:
        lines.append("  暂无物品")
    
    lines.append("")
    lines.append("【预算明细】")
    b = plan.budget
    lines.append(f"  交通: {b.transportation}元")
    lines.append(f"  住宿: {b.accommodation}元")
    lines.append(f"  餐饮: {b.food}元")
    lines.append(f"  门票: {b.tickets}元")
    lines.append(f"  其他: {b.other}元")
    lines.append(f"  ----------------")
    lines.append(f"  总计: {b.total()}元")
    
    return lines


def format_plan_list(plans):
    """格式化计划列表"""
    if not plans:
        return ["暂无计划"]
    lines = [f"所有旅行计划 ({len(plans)})", ""]
    for p in plans:
        lines.append(f"#{p.plan_id} {p.destination}")
        lines.append(f"   {p.start_date} ~ {p.end_date}")
        lines.append("")
    return lines


def get_input(prompt, default=""):
    value = input(f"> {prompt}").strip()
    return value if value else default


def get_date_input(prompt):
    while True:
        value = input(f"> {prompt}").strip()
        if not value:
            print("日期不能为空")
            continue
        valid, msg = Validator.validate_date(value)
        if valid:
            return value
        print(msg)


def get_float_input(prompt, default=0):
    while True:
        value = input(f"> {prompt}").strip()
        if not value:
            return default
        valid, result = Validator.validate_positive_number(value, "数值")
        if valid:
            return result
        print(result)


def get_time_input(prompt, optional=True):
    while True:
        value = input(f"> {prompt}").strip()
        if not value and optional:
            return ""
        if not value and not optional:
            print("时间不能为空")
            continue
        valid, msg = Validator.validate_time(value)
        if valid:
            return value
        print(msg)


def get_int_input(prompt, default=0):
    while True:
        value = input(f"> {prompt}").strip()
        if not value:
            return default
        try:
            num = int(value)
            if num < 0:
                print("请输入非负整数")
                continue
            return num
        except ValueError:
            print("请输入有效整数")


def manage_day_plans(manager, plan_id, content_lines):
    """管理每日行程"""
    plan = manager.get_plan(plan_id)
    if not plan:
        return ["计划不存在！"]
    
    while True:
        # 更新右侧内容
        content = [f"当前计划: {plan.destination}", ""]
        content.extend(format_plan_detail(plan))
        
        ScreenUI.draw_split_screen(get_day_menu(), content, "- 行程管理")
        choice = get_input("请选择: ")
        
        if choice == "1":
            day_num = get_int_input("请输入天数 (如第1天输入1): ")
            if day_num <= 0:
                print("天数必须大于0")
                get_input("按回车继续...")
                continue
            if plan.get_day_plan(day_num):
                plan.remove_day_plan(day_num)
            desc = get_input("请输入当天描述: ")
            plan.add_day_plan(DayPlan(day_num, desc))
            manager.save_data()
            print(f"已添加 Day {day_num}")
            get_input("按回车继续...")
        
        elif choice == "2":
            day_num = get_int_input("请输入要删除的天数: ")
            if day_num <= 0:
                print("天数必须大于0")
                get_input("按回车继续...")
                continue
            if plan.get_day_plan(day_num):
                plan.remove_day_plan(day_num)
                manager.save_data()
                print(f"已删除 Day {day_num}")
            else:
                print(f"Day {day_num} 不存在")
            get_input("按回车继续...")
        
        elif choice == "3":
            day_num = get_int_input("请输入天数: ")
            if day_num <= 0:
                print("天数必须大于0")
                get_input("按回车继续...")
                continue
            day_plan = plan.get_day_plan(day_num)
            if not day_plan:
                print(f"Day {day_num} 不存在，请先添加该天行程")
                get_input("按回车继续...")
                continue
            name = get_input("景点名称: ")
            if not name:
                print("景点名称不能为空")
                get_input("按回车继续...")
                continue
            
            while True:
                start_time = get_time_input("开始时间 (HH:MM，留空跳过): ", optional=True)
                end_time = get_time_input("结束时间 (HH:MM，留空跳过): ", optional=True)
                if start_time and end_time:
                    valid, msg = Validator.validate_time_range(start_time, end_time)
                    if valid:
                        break
                    print(msg)
                else:
                    break
            
            price = get_float_input("门票价格 (默认0): ", 0)
            open_time = get_input("开放时间: ")
            note = get_input("备注: ")
            success, msg = day_plan.add_attraction(Attraction(name, price, open_time, note, start_time, end_time))
            manager.save_data()
            print(msg)
            get_input("按回车继续...")
        
        elif choice == "4":
            day_num = get_int_input("请输入天数: ")
            if day_num <= 0:
                print("天数必须大于0")
                get_input("按回车继续...")
                continue
            day_plan = plan.get_day_plan(day_num)
            if not day_plan:
                print(f"Day {day_num} 不存在")
                get_input("按回车继续...")
                continue
            if not day_plan.attractions:
                print("该天没有景点")
                get_input("按回车继续...")
                continue
            print("当前景点:")
            for i, attr in enumerate(day_plan.attractions, 1):
                print(f"  {i}. {attr.name}")
            name = get_input("要删除的景点名称: ")
            if not name:
                continue
            # 检查景点是否存在
            found = any(a.name == name for a in day_plan.attractions)
            if found:
                day_plan.remove_attraction(name)
                manager.save_data()
                print(f"已删除景点: {name}")
            else:
                print(f"景点 '{name}' 不存在")
            get_input("按回车继续...")
        
        elif choice == "0":
            break
    
    return format_plan_detail(plan)


def manage_packing_list(manager, plan_id, content_lines):
    """管理物品清单"""
    plan = manager.get_plan(plan_id)
    if not plan:
        return ["计划不存在！"]
    
    while True:
        content = [f"当前计划: {plan.destination}", ""]
        content.append("物品清单:")
        if plan.packing_list:
            packed = sum(1 for i in plan.packing_list if i.packed)
            content.append(f"({packed}/{len(plan.packing_list)} 已打包)")
            for item in plan.packing_list:
                status = "[v]" if item.packed else "[ ]"
                content.append(f"  {status} {item.name}")
        else:
            content.append("  暂无物品")
        
        ScreenUI.draw_split_screen(get_packing_menu(), content, "- 物品清单")
        choice = get_input("请选择: ")
        
        if choice == "1":
            name = get_input("物品名称: ")
            if name:
                plan.add_packing_item(PackingItem(name))
                manager.save_data()
        
        elif choice == "2":
            name = get_input("要删除的物品名称: ")
            plan.remove_packing_item(name)
            manager.save_data()
        
        elif choice == "3":
            name = get_input("要标记的物品名称: ")
            if plan.mark_item_packed(name, True):
                manager.save_data()
        
        elif choice == "4":
            name = get_input("要取消标记的物品名称: ")
            if plan.mark_item_packed(name, False):
                manager.save_data()
        
        elif choice == "0":
            break
    
    return format_plan_detail(plan)


def manage_accommodation(manager, plan_id, content_lines):
    """管理住宿信息"""
    plan = manager.get_plan(plan_id)
    if not plan:
        return ["计划不存在！"]
    
    content = [f"当前计划: {plan.destination}", ""]
    if plan.accommodation:
        a = plan.accommodation
        content.append(f"当前住宿: {a.name}")
        content.append(f"地址: {a.address}")
        content.append(f"电话: {a.phone}")
        content.append(f"价格: {a.price}元/晚")
    content.append("")
    content.append("设置新住宿信息:")
    
    ScreenUI.draw_split_screen(get_main_menu(), content, "- 住宿管理")
    
    name = get_input("酒店/民宿名称: ")
    if not name:
        return content_lines
    address = get_input("地址: ")
    phone = get_input("联系电话: ")
    price = get_float_input("每晚价格: ", 0)
    
    plan.accommodation = Accommodation(name, address, phone, price)
    manager.save_data()
    
    return ["住宿信息已保存"] + format_plan_detail(plan)


def manage_budget(manager, plan_id, content_lines):
    """管理预算"""
    plan = manager.get_plan(plan_id)
    if not plan:
        return ["计划不存在！"]
    
    while True:
        b = plan.budget
        content = [
            f"当前计划: {plan.destination}", "",
            "预算明细", "",
            f"  交通费用: {b.transportation}元",
            f"  住宿费用: {b.accommodation}元",
            f"  餐饮费用: {b.food}元",
            f"  门票费用: {b.tickets}元",
            f"  其他费用: {b.other}元",
            "  ----------------",
            f"  总预算: {b.total()}元",
        ]
        
        ScreenUI.draw_split_screen(get_budget_menu(), content, "- 预算管理")
        choice = get_input("请选择: ")
        
        if choice == "1":
            plan.budget.transportation = get_float_input("交通费用: ", b.transportation)
            manager.save_data()
        elif choice == "2":
            plan.budget.accommodation = get_float_input("住宿费用: ", b.accommodation)
            manager.save_data()
        elif choice == "3":
            plan.budget.food = get_float_input("餐饮费用: ", b.food)
            manager.save_data()
        elif choice == "4":
            plan.budget.tickets = get_float_input("门票费用: ", b.tickets)
            manager.save_data()
        elif choice == "5":
            plan.budget.other = get_float_input("其他费用: ", b.other)
            manager.save_data()
        elif choice == "6":
            pass  # 已经显示在右侧
        elif choice == "0":
            break
    
    return format_plan_detail(plan)


def main():
    """主函数"""
    manager = TravelManager()
    logger.info("程序启动")
    
    # 右侧内容区域
    content_lines = ["欢迎使用旅行计划管理器！", "", "请从左侧菜单选择操作"]
    
    while True:
        ScreenUI.draw_split_screen(get_main_menu(), content_lines)
        choice = get_input("请选择操作: ")
        
        if choice == "1":
            content_lines = ["【添加新旅行计划】", ""]
            ScreenUI.draw_split_screen(get_main_menu(), content_lines)
            destination = get_input("目的地: ")
            valid, msg = Validator.validate_not_empty(destination, "目的地")
            if not valid:
                content_lines = [msg]
                continue
            start_date = get_date_input("开始日期 (YYYY-MM-DD): ")
            end_date = get_date_input("结束日期 (YYYY-MM-DD): ")
            valid, msg = Validator.validate_date_range(start_date, end_date)
            if not valid:
                content_lines = [msg]
                continue
            plan = manager.add_plan(destination, start_date, end_date)
            content_lines = [f"计划已创建，ID: {plan.plan_id}"] + format_plan_detail(plan)
        
        elif choice == "2":
            content_lines = format_plan_list(manager.list_all_plans())
        
        elif choice == "3":
            plan_id = get_int_input("请输入计划ID: ")
            plan = manager.get_plan(plan_id)
            if plan:
                content_lines = format_plan_detail(plan)
            else:
                content_lines = ["计划不存在"]
        
        elif choice == "4":
            plan_id = get_int_input("请输入计划ID: ")
            plan = manager.get_plan(plan_id)
            if plan:
                content_lines = [f"当前: {plan.destination} | {plan.start_date} ~ {plan.end_date}", ""]
                ScreenUI.draw_split_screen(get_main_menu(), content_lines)
                destination = get_input("新目的地 (回车保持不变): ")
                start_date = get_input("新开始日期 (回车保持不变): ")
                end_date = get_input("新结束日期 (回车保持不变): ")
                updates = {}
                
                # 获取最终的日期值（新值或原值）
                final_start = start_date if start_date else plan.start_date
                final_end = end_date if end_date else plan.end_date
                
                if destination:
                    updates["destination"] = destination
                if start_date:
                    valid, msg = Validator.validate_date(start_date)
                    if not valid:
                        content_lines = [msg]
                        continue
                    updates["start_date"] = start_date
                if end_date:
                    valid, msg = Validator.validate_date(end_date)
                    if not valid:
                        content_lines = [msg]
                        continue
                    updates["end_date"] = end_date
                
                # 校验日期范围
                valid, msg = Validator.validate_date_range(final_start, final_end)
                if not valid:
                    content_lines = [msg]
                    continue
                
                if updates:
                    manager.update_plan(plan_id, **updates)
                    content_lines = ["已更新"] + format_plan_detail(manager.get_plan(plan_id))
            else:
                content_lines = ["计划不存在"]

        
        elif choice == "5":
            plan_id = get_int_input("请输入要删除的计划ID: ")
            confirm = get_input("确认删除? (y/n): ")
            if confirm.lower() == 'y':
                if manager.delete_plan(plan_id):
                    content_lines = ["已删除"]
                else:
                    content_lines = ["计划不存在"]
        
        elif choice == "6":
            keyword = get_input("请输入目的地关键词: ")
            results = manager.search_by_destination(keyword)
            content_lines = [f"搜索结果 ({len(results)} 条):"]
            for p in results:
                content_lines.append(f"  #{p.plan_id} | {p.destination}")
                content_lines.append(f"     {p.start_date} ~ {p.end_date}")
        
        elif choice == "7":
            date = get_date_input("请输入日期 (YYYY-MM-DD): ")
            results = manager.search_by_date(date)
            content_lines = [f"搜索结果 ({len(results)} 条):"]
            for p in results:
                content_lines.append(f"  #{p.plan_id} | {p.destination}")
                content_lines.append(f"     {p.start_date} ~ {p.end_date}")
        
        elif choice == "8":
            plan_id = get_int_input("请输入计划ID: ")
            content_lines = manage_day_plans(manager, plan_id, content_lines)
        
        elif choice == "9":
            plan_id = get_int_input("请输入计划ID: ")
            content_lines = manage_packing_list(manager, plan_id, content_lines)
        
        elif choice == "10":
            plan_id = get_int_input("请输入计划ID: ")
            content_lines = manage_accommodation(manager, plan_id, content_lines)
        
        elif choice == "11":
            plan_id = get_int_input("请输入计划ID: ")
            content_lines = manage_budget(manager, plan_id, content_lines)
        
        elif choice == "0":
            ScreenUI.clear_screen()
            print("\n感谢使用，祝旅途愉快！")
            logger.info("程序退出")
            break
        
        else:
            content_lines = ["无效选择，请重新输入"]


if __name__ == "__main__":
    main()
