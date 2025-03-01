import requests
from datetime import datetime
import sys
import re
from urllib.parse import urlparse, parse_qs
import os

BASE_URL = "https://form.qun100.com"

def parse_headers(header_text):
    """解析请求头文本为字典"""
    headers = {}
    try:
        # 按行分割
        lines = [line.strip() for line in header_text.split('\n') if line.strip()]
        
        for line in lines:
            # 跳过空行
            if not line or line.startswith('---'):
                continue
                
            # 按第一个冒号分割
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                headers[key] = value
        
        print_colored("\n✓ 请求头解析成功！", "green")
        return headers
    except Exception as e:
        print_colored(f"\n解析请求头时出错: {str(e)}", "red")
        return None

def get_headers():
    """获取用户输入的请求头"""
    print_colored("\n请粘贴完整的请求头（输入完成后请按两次回车）：", "cyan")
    print_colored("示例格式：\nHost: form.qun100.com\nAuthorization: xxx\n...", "gray", "dim")
    
    lines = []
    while True:
        line = input()
        if not line:  # 空行表示输入结束
            break
        lines.append(line)
    
    header_text = '\n'.join(lines)
    return parse_headers(header_text)

def get_form_profile(form_id):
    """获取表单详细信息
    获取表单的标题、开始时间、结束时间等基本信息
    Args:
        form_id: 表单ID
    Returns:
        form_data: 表单详细信息字典，获取失败返回None
    """
    url = f"{BASE_URL}/v1/form/{form_id}/profile"
    headers = HEADERS.copy()
    headers["Client-Form-Id"] = form_id
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            form_data = data["data"]
            print("\n表单详情：")
            print(f"标题：{form_data.get('title')}")
            
            config = form_data.get("config", {})
            start_time = config.get("actBeginTime")
            end_time = config.get("actEndTime")
            print(f"开始时间：{start_time}")
            print(f"结束时间：{end_time}")
            
            return form_data
        else:
            print(f"获取表单详情失败，错误代码：{data.get('code')}")
            return None
    else:
        print(f"请求失败，状态码：{response.status_code}")
        return None

def get_form_catalog(form_id):
    """获取表单目录信息
    获取表单的所有问题和选项信息
    Args:
        form_id: 表单ID
    Returns:
        list: 问题类型的目录列表，获取失败返回None
    """
    url = f"{BASE_URL}/v1/form/{form_id}/catalog"
    headers = HEADERS.copy()
    headers["Client-Form-Id"] = form_id
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("表单目录获取成功！")
            catalogs = data["data"].get("catalogs", [])
            # 只返回问题类型的目录
            return [c for c in catalogs if c.get("catalogType") == "QUESTION"]
        else:
            print(f"获取表单目录失败，错误代码：{data.get('code')}")
            return None
    else:
        print(f"请求失败，状态码：{response.status_code}")
        return None

def get_option_id_from_response(catalog, target_content):
    """从目录中获取指定选项的ID
    根据选项内容查找对应的选项ID
    Args:
        catalog: 目录数据
        target_content: 目标选项内容
    Returns:
        str: 选项ID，未找到返回None
    """
    try:
        # 获取所有选项类型的条目
        options = [item for item in catalog.get("formCatalogs", []) if item.get("role") == "OPTION"]
        # 查找匹配内容的选项
        for option in options:
            if option.get("content") == target_content:
                return option.get("cid")
    except Exception as e:
        print(f"获取选项ID时出错: {e}")
    return None

def auto_select_choices(catalog_data):
    """自动选择课程
    处理用户输入并自动选择对应的课程
    Args:
        catalog_data: 表单目录数据
    Returns:
        catalogs: 选择的课程列表
        show_questions: 显示的问题列表
    """
    catalogs = []
    show_questions = []
    
    # 获取用户输入
    print_colored("\n请输入您的信息：", "cyan", "bold")
    name = input("姓名: ").strip()
    
    # 显示可选班级
    print_colored("\n可选班级：", "cyan")
    class_options = {}
    for catalog in catalog_data:
        if "学生班级" in str(catalog):
            for option in catalog.get("formCatalogs", []):
                if option.get("role") == "OPTION":
                    class_name = option.get("content")
                    class_id = option.get("cid")
                    if class_name and class_id:
                        class_options[len(class_options) + 1] = (class_name, class_id)
                        print(f"{len(class_options)}. {class_name}")
    
    class_choice = int(input("\n请选择班级编号: "))
    selected_class = class_options.get(class_choice)
    
    if not selected_class:
        print_colored("无效的班级选择！", "red")
        return None, None
    
    # 判断是否是10文及以上的班级
    is_senior_class = any(x in selected_class[0] for x in ["10文", "10理", "11文", "11理"])
        
    # 处理每个问题
    for catalog in catalog_data:
        catalog_id = catalog.get("cid")
        show_questions.append(catalog_id)
        
        if catalog.get("type") == "WORD":
            # 处理姓名输入
            catalogs.append({
                "type": "WORD",
                "cid": catalog_id,
                "value": name
            })
            print(f"\n✓ 已设置姓名: {name}")
            
        elif catalog.get("type") == "RADIO_V2":
            title = next((item.get("content") for item in catalog.get("formCatalogs", []) 
                        if item.get("role") == "TITLE"), "")
            
            if "学生班级" in title:
                # 处理班级选择
                catalogs.append({
                    "type": "RADIO_V2",
                    "cid": catalog_id,
                    "value": {
                        "cid": selected_class[1],
                        "customValue": ""
                    }
                })
                print(f"\n✓ 已选择班级: {selected_class[0]}")
                
            # 根据班级判断可选课程时段
            elif "14:10-14:50" in title or "15:05-15:45" in title or (
                "15:55-16:35" in title and not is_senior_class):
                # 显示该时段可选课程
                print_colored(f"\n{title}可选课程：", "cyan")
                course_options = {}
                for option in catalog.get("formCatalogs", []):
                    if option.get("role") == "OPTION":
                        course_name = option.get("content")
                        course_id = option.get("cid")
                        if course_name and course_id:
                            course_options[len(course_options) + 1] = (course_name, course_id)
                            limit = option.get("config", {}).get("LIMIT", {}).get("content", "无限制")
                            print(f"{len(course_options)}. {course_name} (限额: {limit}人)")
                
                if course_options:
                    course_choice = int(input("\n请选择课程编号: "))
                    selected_course = course_options.get(course_choice)
                    
                    if selected_course:
                        catalogs.append({
                            "type": "RADIO_V2",
                            "cid": catalog_id,
                            "value": {
                                "cid": selected_course[1],
                                "customValue": ""
                            }
                        })
                        print(f"✓ 已选择课程: {selected_course[0]}")
                    else:
                        print_colored("无效的课程选择！", "red")
                        return None, None
            elif "15:55-16:35" in title and is_senior_class:
                print_colored(f"\n{title}: 您所在的班级不能选择此时段的课程", "yellow")
    
    return catalogs, show_questions

def get_new_fid(form_id):
    """生成新的表单提交ID
    通过当前时间戳生成一个唯一的表单提交ID，避免重复提交
    Args:
        form_id: 原始表单ID
    Returns:
        new_fid: 新生成的表单提交ID
    """
    # 获取毫秒级时间戳
    timestamp = int(datetime.now().timestamp() * 1000)
    # 使用时间戳最后5位作为增量，确保每次生成不同的ID
    increment = int(str(timestamp)[-5:])
    # 将原始form_id加上增量得到新的ID
    new_fid = str(int(form_id) + increment)
    return new_fid

def submit_form_data(form_id, catalogs, show_questions):
    """提交表单数据
    处理表单提交，包括获取最新版本、生成提交ID等
    Args:
        form_id: 表单ID
        catalogs: 选择的课程列表
        show_questions: 显示的问题列表
    Returns:
        提交成功返回响应数据，失败返回None
    """
    # 每次提交前重新获取表单信息，确保使用最新版本
    form_data = get_form_profile(form_id)
    if not form_data:
        print_colored("获取表单信息失败", "red")
        return None
        
    # 获取最新的表单版本号，避免版本冲突
    form_version = form_data.get("version", 1)
    
    url = f"{BASE_URL}/v1/{form_id}/form_data"
    headers = HEADERS.copy()
    headers["Client-Form-Id"] = form_id
    
    # 过滤出实际需要显示的问题
    filtered_show_questions = [q for q in show_questions if any(c["cid"] == q for c in catalogs)]
    
    # 生成新的提交ID
    new_fid = get_new_fid(form_id)
    
    # 构建提交数据
    payload = {
        "fid": new_fid,
        "subscribe": {
            "qgPso1tQCJF6E-jChXfP9bvtWFqKvN5wvMDFjCop400": 0,
            "vj0_jH-hZaQ3pSSN_icqYZt5NEZz64vlA8Q3dTfQJ68": 0,
            "9frpvZ2b6QJAUgG83Xkg8uq9g0JqjqqKJ7B7I33G7jE": 0
        },
        "catalogs": catalogs,
        "showQuestions": filtered_show_questions,
        "examUsedTime": None,
        "formVersion": form_version,  # 使用最新版本号
        "userCommonInfo": {}
    }
    
    try:
        # 发送提交请求
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                return data
            else:
                error_msg = data.get('msg', '未知错误')
                print_colored(f"提交失败: {error_msg}", "red")
                # 如果是版本错误，显示详细信息以便调试
                if "版本" in error_msg or "修改" in error_msg:
                    print_colored(f"当前版本: {form_version}", "yellow")
        else:
            try:
                error_data = response.json()
                print_colored(f"提交失败: {error_data.get('message', '未知错误')}", "red")
            except:
                print_colored(f"提交失败: HTTP状态码 {response.status_code}", "red")
        return None
    except Exception as e:
        print_colored(f"提交失败: {str(e)}", "red")
        return None

def print_colored(text, color="white", style="normal", end="\n"):
    """打印彩色文本
    支持多种颜色和样式的文本输出
    Args:
        text: 要打印的文本
        color: 文本颜色，支持red/green/yellow/blue/purple/cyan/white/gray
        style: 文本样式，支持normal/bold/underline/dim
        end: 结束符，默认换行
    """
    colors = {
        "red": "91",
        "green": "92",
        "yellow": "93",
        "blue": "94",
        "purple": "95",
        "cyan": "96",
        "white": "97",
        "gray": "90"
    }
    styles = {
        "normal": "0",
        "bold": "1",
        "underline": "4",
        "dim": "2"
    }
    print(f"\033[{styles[style]};{colors[color]}m{text}\033[0m", end=end, flush=True)

def print_banner():
    """打印程序标题横幅
    使用彩色字符显示程序名称和作者信息
    """
    print_colored("\n┌─────────────────────────────────┐", "cyan", "bold")
    print_colored("│   选修课抢课小助手 Author:Sīmōń   │", "cyan", "bold")
    print_colored("└─────────────────────────────────┘\n", "cyan", "bold")

def print_help():
    """打印使用帮助信息
    显示程序支持的输入格式和操作提示
    """
    print_colored("使用说明：", "yellow", "bold")
    print_colored("  1. 支持的输入格式：", "white", "dim")
    print_colored("     • 完整的19位数字表单fid", "gray")
    print_colored("     • 短链接 (s.qun100.com/link/...)", "gray")
    
    print_colored("\n  2. 操作提示：", "white", "dim")
    print_colored("     • 程序会在问卷开始时自动提交", "gray")
    print_colored("     • 提交成功后手动退出", "gray")
    print_colored("     • 按 Ctrl+C 可随时终止程序", "gray", "bold")
    print()

def print_success_banner():
    """打印成功提示横幅
    使用ASCII字符画显示抢课成功的提示信息
    """
    success_banner = """
    ╔═══════════════════════════════════════╗
    ║                                       ║
    ║            抢课成功！                 ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
    """
    print_colored(success_banner, "green", "bold")

def wait_and_submit(form_id, begin_time, catalogs, show_questions):
    """等待并提交表单
    在指定时间自动开始提交表单，直到提交成功
    Args:
        form_id: 表单ID
        begin_time: 开始时间
        catalogs: 选择的课程列表
        show_questions: 显示的问题列表
    """
    from datetime import datetime
    import time
    
    # 解析开始时间
    begin_datetime = datetime.strptime(begin_time, "%Y-%m-%d %H:%M:%S")
    
    # 显示提交配置信息
    print_colored("\n=== 提交配置 ===", "cyan", "bold")
    print("目标时间:", begin_time)
    print("提交间隔: 0.1秒")
    print("按 Ctrl+C 可随时停止程序")
    
    while True:
        now = datetime.now()
        if now >= begin_datetime:
            # 到达开始时间，开始提交
            print_colored("\n=== 开始提交 ===", "green", "bold")
            submit_count = 0
            start_time = datetime.now()
            
            # 提交前获取最新表单信息
            form_data = get_form_profile(form_id)
            if not form_data:
                print_colored("获取表单信息失败，请检查网络", "red")
                return
                
            # 循环尝试提交，直到成功
            while True:
                submit_count += 1
                print_colored(f"\n第 {submit_count} 次尝试提交...", "yellow")
                print(f"已运行时间: {datetime.now() - start_time}")
                result = submit_form_data(form_id, catalogs, show_questions)
                if result and result.get("code") == 0:
                    # 提交成功，清屏并显示成功信息
                    os.system('cls' if os.name == 'nt' else 'clear')  # 兼容不同操作系统
                    print_success_banner() 
                    print(f"\n总尝试次数: {submit_count}")
                    print(f"总耗时: {datetime.now() - start_time}")
                    print_colored("\n按回车键退出程序...", "cyan")
                    input() 
                    return
                time.sleep(0.1)  # 提交间隔0.1秒，避免请求过于频繁
        else:
            # 未到开始时间，显示倒计时
            time_left = begin_datetime - now
            seconds = int(time_left.total_seconds())
            if seconds > 10:
                # 超过10秒显示时分秒格式
                print_colored(f"\r距离开始还有: {seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}", color="cyan", end="")
                time.sleep(0.1)
            else:
                # 最后10秒显示倒计时
                print_colored(f"\n=== 倒计时最后{seconds}秒 ===", "yellow", "bold")
                for i in range(seconds, 0, -1):
                    print_colored(f"\r{i}...", "red", end="")
                    time.sleep(1)
                print_colored("\n=== 准备开始 ===", "green", "bold")

def validate_form_id(form_id):
    try:
        if not form_id.isdigit() or len(form_id) != 19:
            return False
        return True
    except:
        return False

def extract_form_id_from_url(url):
    try:
        if "s.qun100.com/link/" in url:
            print_colored("\n正在解析短链接...", "cyan")
            response = requests.get(url, allow_redirects=True)
            if response.status_code == 200:
                final_url = response.url
                print("解析成功！")
            else:
                print_colored("短链接解析失败", "red")
                return None
        else:
            final_url = url
            
        # 从URL中提取form_id参数
        parsed_url = urlparse(final_url)
        query_params = parse_qs(parsed_url.query)
        
        # 尝试不同的参数名称
        form_id = None
        for param in ['form_id', 'fid', 'id']:
            if param in query_params:
                form_id = query_params[param][0]
                break
                
        if not form_id:
            match = re.search(r'(\d{19})', final_url)
            if match:
                form_id = match.group(1)
        
        if form_id and validate_form_id(form_id):
            print(f"获取到表单ID: {form_id}")
            return form_id
        else:
            print_colored("未找到有效的表单ID", "red")
            return None
            
    except Exception as e:
        print_colored(f"解析链接出错: {str(e)}", "red")
        return None

def get_name_list(form_id):
    """获取名单完成情况"""
    url = f"{BASE_URL}/v1/{form_id}/name_list/used"
    headers = HEADERS.copy()
    headers["Client-Form-Id"] = form_id
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                name_lists = data["data"]
                if name_lists:
                    name_list = name_lists[0]["nameList"]
                    total = len(name_list)
                    completed = sum(1 for person in name_list if person["status"] == 1)
                    
                    print_colored("\n=== 完成情况统计 ===", "cyan", "bold")
                    print(f"总人数: {total}")
                    print(f"已完成: {completed}")
                    print(f"未完成: {total - completed}")
                    
                    # 打印已完成的名单
                    if completed > 0:
                        print_colored("\n已完成名单:", "green")
                        for person in name_list:
                            if person["status"] == 1:
                                print(f"✓ {person['name']}")
                    
                    return True
            else:
                print_colored(f"获取名单失败: {data.get('msg', '未知错误')}", "red")
        else:
            print_colored(f"请求失败，状态码: {response.status_code}", "red")
    except Exception as e:
        print_colored(f"获取名单时出错: {str(e)}", "red")
    
    return False

def main():
    print_banner()
    print_help()
    
    # 获取请求头
    headers = get_headers()
    if not headers:
        print_colored("请求头获取失败，程序退出", "red")
        return
    
    # 更新全局HEADERS
    global HEADERS
    HEADERS = headers
    
    while True:
        try:
            print_colored("\n请输入表单ID或链接: ", "cyan", end="")
            user_input = input().strip()
            
            form_id = None
            
            # 判断输入类型
            if user_input.startswith('http'):
                # 输入为链接
                form_id = extract_form_id_from_url(user_input)
                if not form_id:
                    print_colored("无法从链接中获取有效的表单ID", "red")
                    continue
            else:
                # 输入为ID
                if not validate_form_id(user_input):
                    print_colored("表单ID格式错误！请输入正确的19位数字ID", "red")
                    continue
                form_id = user_input
            
            print_colored("\n═══ 表单详情 ═══", "cyan", "bold")
            form_data = get_form_profile(form_id)
            if not form_data:
                print_colored("❌ 获取表单失败，请检查ID是否正确", "red")
                continue
            
            # 添加获取名单完成情况
            get_name_list(form_id)
                
            # 检查表单时间
            config = form_data.get("config", {})
            begin_time = config.get("actBeginTime")
            if not begin_time:
                print("无法获取开始时间")
                continue
            
            print_colored("\n═══ 获取目录 ═══", "cyan", "bold")
            catalog_data = get_form_catalog(form_id)
            if not catalog_data:
                continue
            
            print_colored("\n═══ 自动选择 ═══", "cyan", "bold")
            catalogs, show_questions = auto_select_choices(catalog_data)
            
            if catalogs and show_questions:
                print_colored("\n═══ 选择结果 ═══", "cyan", "bold")
                for catalog in catalogs:
                    if catalog["type"] == "WORD":
                        print_colored(f"✓ 姓名: {catalog['value']}", "green")
                    else:
                        print_colored(f"✓ 选项ID: {catalog['value']['cid']}", "green")
                
                print_colored("\n是否确认选择并等待自动提交？(y/n): ", "yellow", end="")
                if input().strip().lower() == 'y':
                    try:
                        wait_and_submit(form_id, begin_time, catalogs, show_questions)
                        sys.exit(0)
                    except KeyboardInterrupt:
                        print_colored("\n\n⚠️ 程序已停止", "yellow", "bold")
                        sys.exit(0)
                else:
                    print_colored("\n已取消操作", "yellow")
                    print_colored("是否重新输入表单ID？(y/n): ", "cyan", end="")
                    if input().strip().lower() != 'y':
                        sys.exit(0)
            else:
                print_colored("❌ 未获取到有效的表单数据", "red")
                continue
                
        except KeyboardInterrupt:
            print_colored("\n\n⚠️ 程序已停止", "yellow", "bold")
            sys.exit(0)
        except Exception as e:
            print_colored(f"\n❌ 发生错误: {str(e)}", "red")
            print_colored("是否重新尝试？(y/n): ", "yellow", end="")
            if input().strip().lower() != 'y':
                sys.exit(0)

if __name__ == "__main__":
    main()
