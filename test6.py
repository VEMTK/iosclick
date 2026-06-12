import os
import time
import json
import random
import math
import uuid
import shutil
import requests
import subprocess
import re 
import threading
import string

from appium import webdriver
from appium.options.ios import XCUITestOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.common.actions import interaction
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.action_chains import ActionChains

# ================= 核心配置区域 =================
API_URL = "https://www.autoios.click/api/offer-click-task/next-waiting-task?offerId=1&proxyCountryCode=US"
TARGET_URL = "https://m.facebook.com" # 初始网址
H5_GAME_URL = "https://play.myrathis.com"
USER_HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(USER_HOME, "Documents", "iPhone14")
BASE_TEMP_CONFIG_DIR = os.path.join(USER_HOME, "Documents")
CONFIG_FILE_PATH = os.path.join(CONFIG_DIR, "config.json")
PROJECT_ROOT_DIR = "/Users/robin/src/WebKit"

# !!! 必填：你的 minibrowser 的包名 (Bundle ID) !!!
MINIBROWSER_BUNDLE_ID = "org.gu.MobileMiniBrowser" 

# ================= 并发集群控制区域 =================
CONCURRENT_COUNT = 6               # [核心] 设置同时运行的虚拟机数量！(对应 iPhone 1 到 10)
CLAIMED_UDIDS = set()              # 记录已经被分配出去的 UDID
UDID_LOCK = threading.Lock()       # 互斥锁，防止两个线程抢同一台刚开机的模拟器
# =================================================

# ----------------- 数学与真人模拟算法 -----------------
def generate_bezier_curve(start_pt, p1, p2, end_pt, steps=40):
    points = []
    for i in range(steps + 1):
        linear_t = i / steps
        t = 1 - math.pow(1 - linear_t, 3) 
        x = (1 - t)**3 * start_pt[0] + 3 * (1 - t)**2 * t * p1[0] + 3 * (1 - t) * t**2 * p2[0] + t**3 * end_pt[0]
        y = (1 - t)**3 * start_pt[1] + 3 * (1 - t)**2 * t * p1[1] + 3 * (1 - t) * t**2 * p2[1] + t**3 * end_pt[1]
        points.append((int(x), int(y)))
    return points

def native_safe_bezier_swipe(driver, duration_ms=800):
    current_context = driver.context
    driver.switch_to.context("NATIVE_APP")
    try:
        native_webview = driver.find_element(AppiumBy.CLASS_NAME, "XCUIElementTypeWebView")
        rect = native_webview.rect
        start_x = rect['x'] + (rect['width'] / 2)
        end_x = start_x 
        start_y = rect['y'] + (rect['height'] * 0.8)
        end_y = rect['y'] + (rect['height'] * 0.2)
        
        print(f"[*] 准备执行原生防风控滑动 (时长 {duration_ms}ms)...")
        offset_x = random.randint(30, 100) * random.choice([1, -1]) 
        p1 = (start_x + offset_x, start_y + (end_y - start_y) * 0.2)
        p2 = (start_x - (offset_x * random.uniform(0.5, 1.0)), start_y + (end_y - start_y) * 0.7)
        
        path_points = generate_bezier_curve((start_x, start_y), p1, p2, (end_x, end_y), steps=40)
        
        actions = ActionBuilder(driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
        pointer = actions.pointer_action
        pointer.move_to_location(path_points[0][0], path_points[0][1])
        pointer.pointer_down()
        pointer.pause(random.uniform(0.02, 0.08))
        
        step_pause = duration_ms / len(path_points) / 1000.0 
        for point in path_points[1:]:
            pointer.move_to_location(point[0], point[1])
            pointer.pause(step_pause)
            
        pointer.pause(random.uniform(0.05, 0.15))
        pointer.pointer_up()
        actions.perform()
        print(f"[+] 贝塞尔弧线滑动完成！(轨迹点数: {len(path_points)})")
    except Exception as e:
        print(f"[-] 原生滑动执行失败: {e}")
    finally:
        driver.switch_to.context(current_context)
        time.sleep(random.uniform(0.8, 1.5))

def human_tap_element_area(driver, web_element, debug_mode=True):
    print(f"[*] 准备执行原生硬件点击 (调试模式: {'开启' if debug_mode else '关闭'})...")
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", web_element)
    time.sleep(1) 

    js_code = """
    var el = arguments[0];
    var isDebug = arguments[1];
    var rect = el.getBoundingClientRect();
    var safeX = rect.width * 0.15;
    var safeY = rect.height * 0.15;
    var targetX = rect.left + safeX + Math.random() * (rect.width - safeX * 2);
    var targetY = rect.top + safeY + Math.random() * (rect.height - safeY * 2);

    if (isDebug) {
        el.style.outline = '3px solid red';
        el.style.backgroundColor = 'rgba(255, 0, 0, 0.2)';
        var dot = document.createElement('div');
        dot.style.position = 'fixed'; 
        dot.style.left = targetX + 'px';
        dot.style.top = targetY + 'px';
        dot.style.width = '14px';
        dot.style.height = '14px';
        dot.style.backgroundColor = 'blue';
        dot.style.border = '2px solid white';
        dot.style.borderRadius = '50%';
        dot.style.zIndex = '2147483647';
        dot.style.transform = 'translate(-50%, -50%)';
        dot.style.pointerEvents = 'none'; 
        document.body.appendChild(dot);
    }
    var vw = window.innerWidth || document.documentElement.clientWidth;
    var vh = window.innerHeight || document.documentElement.clientHeight;
    return { pct_x: targetX / vw, pct_y: targetY / vh };
    """
    pct_result = driver.execute_script(js_code, web_element, debug_mode)
    pct_x = pct_result['pct_x']
    pct_y = pct_result['pct_y']
    print(f"[*] 元素位于网页视口相对位置: X轴 {pct_x*100:.1f}%, Y轴 {pct_y*100:.1f}%")

    if debug_mode:
        print("👀 [DEBUG] 已绘制【红框】和【蓝点】，请观察落点位置！等待 3 秒后执行原生物理敲击...")
        time.sleep(3)

    current_context = driver.context
    driver.switch_to.context("NATIVE_APP")
    try:
        native_webview = driver.find_element(AppiumBy.CLASS_NAME, "XCUIElementTypeWebView")
        wv_rect = native_webview.rect
        final_x = wv_rect['x'] + (wv_rect['width'] * pct_x)
        final_y = wv_rect['y'] + (wv_rect['height'] * pct_y)
        print(f"[*] 成功映射物理屏幕绝对坐标: (X:{int(final_x)}, Y:{int(final_y)})")

        actions = ActionBuilder(driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
        actions.pointer_action.move_to_location(int(final_x), int(final_y))
        actions.pointer_action.pointer_down()
        actions.pointer_action.pause(random.uniform(0.05, 0.15)) 
        actions.pointer_action.pointer_up()
        actions.perform()
        print("[+] 硬件级原生点击指令已下发！")
    except Exception as e:
        print(f"[-] 原生映射点击失败 (可能是没找到 Webview 容器): {e}")
    finally:
        driver.switch_to.context(current_context)
        time.sleep(1)

def find_and_tap_lazy_element(driver, elements_list, max_swipes=5):
    if not elements_list:
        return False
    #weights = [0.9] + [0.1 / (len(elements_list) - 1)] * (len(elements_list) - 1)
    target_element = random.choice(elements_list)
    #target_element = random.choices(elements_list, weights=weights)[0]
    print(f"[*] 锁定了一个隐藏目标，准备执行真人拉网式搜索...")
    
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", target_element)
    time.sleep(1.5)
    
    swipe_count = 0
    is_ready_to_click = False
    
    while swipe_count < max_swipes:
        try:
            rect = target_element.rect 
            if target_element.is_displayed() and rect['width'] > 10 and rect['height'] > 10:
                print(f"[+] 第 {swipe_count} 次探索：目标已成功渲染！大小 {rect['width']}x{rect['height']}。")
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", target_element)
                time.sleep(1)
                is_ready_to_click = True
                break 
        except Exception as e:
            pass 
        print(f"    - 目标未显示或处于屏幕外，向下滑动屏幕寻找 (第 {swipe_count + 1} 次)...")
        current_context = driver.context
        driver.switch_to.context("NATIVE_APP")
        
        window_size = driver.get_window_size()
        w, h = window_size['width'], window_size['height']
        
        native_safe_bezier_swipe(driver, duration_ms=random.randint(600, 1000))
        
        driver.switch_to.context(current_context)
        time.sleep(2)
        swipe_count += 1
        
    if is_ready_to_click:
        print(f"[+] 目标锁定在视野中，准备执行物理盲点打击！")
        human_tap_element_area(driver, target_element, debug_mode=False)
        return True
    else:
        print(f"[-] 在滑动了 {max_swipes} 次后，目标仍未渲染成型，放弃攻击。")
        return False

def safe_execute_js(driver, js_code, element=None):
    async_wrapper = """
    var callback = arguments[arguments.length - 1]; 
    var elem = arguments[0]; 
    setTimeout(function() {
        try { """ + js_code + """ } catch(e) { console.log('Safe JS Error:', e); }
    }, 0);
    callback("SUCCESS"); 
    """
    try:
        if element: driver.execute_async_script(async_wrapper, element)
        else: driver.execute_async_script(async_wrapper)
    except Exception as e:
        print(f"[!] 异步执行 JS 时遭遇底层断联，已强制放行: {e}")


def generate_fake_us_user():
    """生成绝对逼真的美国本土虚假用户信息"""
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez"]
    cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose"]
    states = ["NY", "CA", "IL", "TX", "AZ", "PA", "TX", "CA", "TX", "CA"]
    
    fn = random.choice(first_names)
    ln = random.choice(last_names)
    # 模拟真实用户的邮箱习惯带数字
    domain = random.choice(["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"])
    email = f"{fn.lower()}.{ln.lower()}{random.randint(100, 9999)}@{domain}"
    
    # 随机生成美国10位手机号 (避开555等假号码区段)
    phone = f"{random.randint(201, 989)}{random.randint(200, 999)}{random.randint(1000, 9999)}"
    
    address = f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Pine', 'Maple', 'Cedar'])} {random.choice(['St', 'Ave', 'Blvd', 'Rd'])}"
    zip_code = f"{random.randint(10000, 99999)}"
    
    return {
        "firstname": fn,
        "lastname": ln,
        "fullname": f"{fn} {ln}",
        "email": email,
        "phone": phone,
        "address": address,
        "city": random.choice(cities),
        "state": random.choice(states),
        "zip": zip_code,
        "password": "".join(random.choices(string.ascii_letters + string.digits, k=8)) + "A1!" # 强密码
    }

def auto_fill_form(driver, worker_id):
    """启发式智能表单识别与填写"""
    print(f"[Worker-{worker_id}] [*] 启动 AI 启发式表单扫描...")
    
    # 找所有的输入框
    inputs = driver.find_elements(By.TAG_NAME, "input")
    if not inputs:
        print(f"[Worker-{worker_id}] [-] 当前页面未发现标准表单 input，跳过转化步骤。")
        return False
        
    user_info = generate_fake_us_user()
    print(f"[Worker-{worker_id}] [+] 生成转化肉鸡信息: {user_info['fullname']} | {user_info['email']}")
    
    filled_count = 0
    for inp in inputs:
        try:
            # 过滤不可见和特殊类型的 input
            if not inp.is_displayed():
                continue
            type_attr = (inp.get_attribute("type") or "").lower()
            if type_attr in ["hidden", "submit", "button", "checkbox", "radio", "image", "file"]:
                continue
                
            # 提取线索：根据 name, id, placeholder 的英文单词猜测它的含义
            name_attr = (inp.get_attribute("name") or "").lower()
            id_attr = (inp.get_attribute("id") or "").lower()
            ph_attr = (inp.get_attribute("placeholder") or "").lower()
            
            clues = f"{name_attr} {id_attr} {ph_attr}"
            
            val_to_fill = None
            if "email" in clues or type_attr == "email":
                val_to_fill = user_info["email"]
            elif "first" in clues and "name" in clues:
                val_to_fill = user_info["firstname"]
            elif "last" in clues and "name" in clues:
                val_to_fill = user_info["lastname"]
            elif "name" in clues or "user" in clues:
                val_to_fill = user_info["fullname"]
            elif "phone" in clues or "mobile" in clues or "tel" in clues or type_attr == "tel":
                val_to_fill = user_info["phone"]
            elif "zip" in clues or "postal" in clues:
                val_to_fill = user_info["zip"]
            elif "address" in clues:
                val_to_fill = user_info["address"]
            elif "city" in clues:
                val_to_fill = user_info["city"]
            elif "state" in clues or "province" in clues:
                val_to_fill = user_info["state"]
            elif "pass" in clues or type_attr == "password":
                val_to_fill = user_info["password"]
                
            if val_to_fill:
                # 滚动到这个输入框
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", inp)
                time.sleep(0.5)
                
                # 【终极防卡死必杀技】：用 JS 强行赋值并派发原生 Event 事件。
                # 这能完美绕过 iOS 软键盘弹出导致的 Appium 坐标错乱，且能触发前端框架的 onChange 侦听器！
                js_fill = """
                    var el = arguments[0];
                    el.value = arguments[1];
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                """
                driver.execute_script(js_fill, inp, val_to_fill)
                print(f"[Worker-{worker_id}]     ✅ 智能填充 [{clues[:15]}...] -> {val_to_fill}")
                filled_count += 1
                time.sleep(random.uniform(0.5, 1.5)) # 模拟真人打字时间停顿
                
        except Exception as e:
            pass # 某个框报错不影响全局
            
    if filled_count > 0:
        print(f"[Worker-{worker_id}] [+] 表单填写完毕！(共完成 {filled_count} 个字段)")
        # 可选：如果你想自动点击“提交”按钮，可以把这行取消注释
        # try: driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']").click() except: pass
        return True
    else:
        print(f"[Worker-{worker_id}] [-] 未找到语义匹配的输入框。")
        return False

# ----------------- 核心业务逻辑 -----------------
def execute_web_automation(real_udid, worker_id, wda_port, appium_port, webkit_port):
    """执行复杂的网页自动化流程"""
    options = XCUITestOptions()
    options.platform_name = "iOS"
    
    options.automation_name = "XCUITest"
    options.udid = real_udid
    options.bundle_id = MINIBROWSER_BUNDLE_ID
    options.no_reset = True 
    options.new_command_timeout = 100 
    options.set_capability("webviewAtomWaitTimeout", 15000)
    options.set_capability("unexpectedAlertBehaviour", "accept")
    # 是否显示 xcode 错误日志
    #options.set_capability("appium:showXcodeLog", True)
    options.platform_version = "16.4" 
    options.set_capability("appium:sdkVersion", "16.4")
    options.set_capability("appium:platformVersion", "16.4")
    options.set_capability("appium:noReset", True)

    # 【新增并发防止端口冲突配置】
    # options.set_capability("appium:wdaLocalPort", wda_port)
    # options.set_capability("appium:webDriverAgentUrl", f"http://127.0.0.1:{wda_port}")

    # ================= 彻底物理隔离的端口全家桶 =================
    options.set_capability("appium:wdaLocalPort", wda_port)
    options.set_capability("appium:webkitDebugProxyPort", webkit_port)
    options.set_capability("appium:includeSafariInWebviews",True)
    
    # 额外隔离视频流截屏端口，防止多线程找元素时卡死
    mjpeg_port = 9100 + worker_id
    options.set_capability("appium:mjpegServerPort", mjpeg_port)

    options.set_capability("appium:usePrebuiltWDA", True)
    options.set_capability("appium:waitForQuiescence", False)
    options.set_capability("appium:wdaLaunchTimeout", 240000)
    options.set_capability("appium:wdaStartupRetries", 4)
    options.set_capability("appium:wdaStartupRetryInterval", 10000)
    # ==========================================================

    options.set_capability("appium:processArguments", {
        "args": [],
        "env": {
            "DYLD_FRAMEWORK_PATH": "/Users/z16/src/WebKit/WebKitBuild/Release-iphonesimulator"
        }
    })

    print("[4] 正在附加 Appium 接管浏览器...")
    #driver = webdriver.Remote('http://127.0.0.1:4723', options=options)
    driver = webdriver.Remote(f'http://127.0.0.1:{appium_port}', options=options)
    
    try:
        time.sleep(3) 
        print("[*] 正在扫描网页上下文 最高等待 15秒...")
        webview = None
        for attempt in range(15):
            contexts = driver.contexts
            webview = next((c for c in contexts if "WEBVIEW" in c), None)
            if webview:
                break
            time.sleep(2)
        if not webview:
            print("[-] 未找到网页上下文！")
            return

        # 切换到webview的环境    
        driver.switch_to.context(webview)
        print("[+] 成功进入网页环境")

        driver.get("https://m.facebook.com")

        wait = WebDriverWait(driver, 15)

        print("[*] 寻找并点击 clickme 标签...")
        clickme_btn = wait.until(EC.presence_of_element_located((By.ID, "link")))
        human_tap_element_area(driver, clickme_btn)

        print("[*] 验证目标网页 URL...")
        print("[*] 假装真人正在认真看页面 (35~61秒)...")
        time.sleep(random.uniform(35, 61))

        wait = WebDriverWait(driver, 15) 
        wait.until(EC.url_contains("play.myrathis.com"))
        print("[+] 网页 URL 验证通过！")
        
        print("[*] 开始执行纯原生硬件“呼吸式”滑动浏览...")
        
        read_steps = random.randint(2,4)
        for i in range(read_steps):
            sleep_time = random.uniform(1, 3)
            print(f"    - 真人正在阅读... 停留 {int(sleep_time)} 秒")
            time.sleep(sleep_time)
            native_safe_bezier_swipe(driver, duration_ms=random.randint(300, 1200))
            print("    - 完成一次原生硬件屏幕滑动")
            
        print("[+] 页面阅读完毕！")

        if random.random() < 0.20:
            print("[*] 🎲 触发 20% 概率，准备盲点广告区域...")
            try:
                ad_frames = driver.find_elements(By.CSS_SELECTOR, "iframe[id*='ads_iframe']")
                if not ad_frames:
                    print("[-] 当前页面未找到 iframe 广告位。")
                else:
                    success = find_and_tap_lazy_element(driver, ad_frames, max_swipes=4)
                    if success:
                        print("[+] 🎯 广告盲点任务执行完毕！")
                        time.sleep(random.uniform(35, 61))
                        read_steps = random.randint(3,6)
                        for i in range(read_steps):
                            sleep_time = random.uniform(3, 5)
                            print(f"    - 真人正在阅读... 停留 {int(sleep_time)} 秒")
                            time.sleep(sleep_time)
                            native_safe_bezier_swipe(driver, duration_ms=random.randint(300, 1200))
                            print("    - 完成一次原生硬件屏幕滑动")
                        print("[+] 页面阅读完毕！")


                        #随机点击
                        # ================= 1. 随机点击可见的站内链接 =================
                        print(f"[Worker-{worker_id}] [*] 寻找并随机点击页面上的任意可见链接...")
                        try:
                            # 找出所有 <a> 标签
                            links = driver.find_elements(By.TAG_NAME, "a")
                            valid_links = []
                            for link in links:
                                try:
                                    # 必须可见且有一定的面积大小
                                    if link.is_displayed() and link.rect['width'] > 5 and link.rect['height'] > 5:
                                        # 过滤掉锚点链接 (#) 和 无效链接
                                        href = link.get_attribute("href")
                                        if href and not href.startswith("javascript") and not href.endswith("#"):
                                            valid_links.append(link)
                                except Exception:
                                    pass
                                    
                            if valid_links:
                                target_link = random.choice(valid_links)
                                print(f"[Worker-{worker_id}] [+] 发现 {len(valid_links)} 个有效链接，准备随机暴击！")
                                # 同样使用物理硬件级点击，绝对防风控
                                human_tap_element_area(driver, target_link, worker_id, debug_mode=False)
                                
                                # 点击后，给新页面（或新标签页）缓冲加载时间
                                time.sleep(random.uniform(10, 15))
                            else:
                                print(f"[Worker-{worker_id}] [-] 落地页内没有找到可供点击的有效链接。")
                        except Exception as e:
                            print(f"[Worker-{worker_id}] [-] 点击落地页链接时报错: {e}")


                        # ================= 2. 识别表单并填入美国人资料 =================
                        # 如果上面的链接跳转了，这里会自动在跳完的新页面里找表单
                        # 调用刚刚写好的表单填写神器
                        try:
                            auto_fill_form(driver, worker_id)
                            # 填完表单后，假装停留一会儿看看
                            time.sleep(random.uniform(5, 10))
                        except Exception as e:
                            print(f"[Worker-{worker_id}] [-] 填充表单时发生异常: {e}")

                    else:
                        print("[-] 广告点击任务被安全放弃。")
                        
            except Exception as e:
                print(f"[-] 盲点广告区域时发生意外错误: {e}")
        else:
            print("[*] 🛡️ 未触发 iframe 广告点击概率 (85% 安全略过)")    
    except Exception as e:
        print(f"[-] 自动化执行中发生错误: {e}")
    finally:
        driver.quit()


def fetch_task(worker_id):
    print(f"\n[Worker-{worker_id}] [1] 正在向 {API_URL} 请求新任务...")
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status() 
        task_data = response.json()
        if not task_data:
            print(f"[Worker-{worker_id}] [-] 接口返回空数据，稍后重试...")
            return None
        print(f"[Worker-{worker_id}] [+] 成功获取指纹任务数据！")
        return task_data
    except Exception as e:
        print(f"[Worker-{worker_id}] [-] 网络请求失败: {e}")
        return None

def save_config(data):
    print(f"[2] 正在生成配置文件: {CONFIG_FILE_PATH}")
    try:
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print("[+] 配置文件写入成功！")
        return True
    except Exception as e:
        print(f"[-] 写入配置文件失败: {e}")
        return False
    
def build_config_payload(raw_task_data, worker_id):
    if not isinstance(raw_task_data, dict):
        print(f"[Worker-{worker_id}] [-] 接口返回的不是有效 JSON 对象，放弃任务。")
        return None
    data_node = raw_task_data.get("data")
    if not isinstance(data_node, dict):
        print(f"[Worker-{worker_id}] [-] 数据格式不对：缺少 data 节点，放弃任务。")
        return None
    auto_ads_node = data_node.get("autoAdsUserAgent")
    if not isinstance(auto_ads_node, dict):
        print(f"[Worker-{worker_id}] [-] 数据格式不对：缺少 autoAdsUserAgent 节点，放弃任务。")
        return None
    if "userAgent" not in auto_ads_node or "screen" not in auto_ads_node:
        print(f"[Worker-{worker_id}] [-] 数据格式不对：缺少核心指纹字段，放弃任务。")
        return None

    raw_locale = auto_ads_node.get("appLocale", "")
    raw_lang = auto_ads_node.get("acceptLang", "")
    screen_node = auto_ads_node.get("screen", {})

    target_config = {
        "appLocale": raw_locale.split(",")[0] if raw_locale else "",
        "acceptLang": {
            "js": raw_lang.split(",")[0] if raw_lang else "",
            "http": raw_lang
        },
        "timeZone": auto_ads_node.get("timeZone", ""),
        "userAgent": auto_ads_node.get("userAgent", ""),
        "screen": {
            "width": int(screen_node.get("viewportWidth", 0)),  
            "height": int(screen_node.get("viewportHeight", 0)) 
        },
        "proxy": auto_ads_node.get("proxy", ""),
        "navigator": { "hardwareConcurrency": 8 },
        "intercept": {
            "host": "m.facebook.com",
            "str":f"<a id=\"link\" href=\"{H5_GAME_URL}\">ClickMe</a>"
        }
    }
    return target_config


# def wait_and_get_booted_udid(timeout=30, worker_id=0):
#     print(f"[Worker-{worker_id}] [*] 正在等待模拟器开机并获取 UDID (最多等待 {timeout} 秒)...")
#     for i in range(timeout):
#         try:
#             output = subprocess.check_output(['xcrun', 'simctl', 'list', 'devices'], text=True)
#             for line in output.splitlines():
#                 if "(Booted)" in line:
#                     match = re.search(r'([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})', line)
#                     if match:
#                         real_udid = match.group(1)
#                         # --- 并发防抢锁 ---
#                         with UDID_LOCK:
#                             if real_udid not in CLAIMED_UDIDS:
#                                 CLAIMED_UDIDS.add(real_udid)
#                                 print(f"[Worker-{worker_id}] [+] 模拟器已就绪！获取到专属 UDID: {real_udid}")
#                                 return real_udid
#         except Exception:
#             pass
#         time.sleep(1)
#     print(f"[Worker-{worker_id}] [-] 等待模拟器启动超时！")
#     return None


def wait_and_get_booted_udid(target_device_name, timeout=40, worker_id=0):
    """
    智能等待专属模拟器彻底启动，精准匹配设备名称并动态获取 UDID。
    """
    print(f"[Worker-{worker_id}] [*] 正在寻找专属模拟器 [{target_device_name}] 并等待开机...")
    for i in range(timeout):
        try:
            # 调用苹果底层的 simctl 命令查询设备列表
            output = subprocess.check_output(['xcrun', 'simctl', 'list', 'devices'], text=True)
            for line in output.splitlines():
                # --- 核心修改：必须同时满足“名字匹配”和“状态是 Booted” ---
                if target_device_name in line and "(Booted)" in line:
                    match = re.search(r'([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})', line)
                    if match:
                        real_udid = match.group(1)
                        print(f"[Worker-{worker_id}] [+] 专属模拟器已就绪！成功获取 UDID: {real_udid}")
                        return real_udid
                else:
                    time.sleep(2)
        except Exception:
            pass
        
        time.sleep(1)
        
    print(f"[Worker-{worker_id}] [-] 等待专属模拟器 [{target_device_name}] 启动超时！")
    return None

def kill_port_process(port):
    try:
        # 查找占用该端口的进程 ID (PID)
        cmd = f"lsof -t -i:{port}"
        pid = subprocess.check_output(cmd, shell=True).decode().strip()
        if pid:
            # 强行杀死残留进程
            os.system(f"kill -9 {pid}")
            print(f"[Worker] 成功清理残留端口: {port}")
    except subprocess.CalledProcessError:
        # 如果端口没被占用，会抛出异常，直接忽略即可
        pass

def is_appium_running(port):
    """
    检查指定端口的 Appium 服务是否存活且就绪
    """
    try:
        # Appium 启动后会开放 /status 接口，设置 2 秒超时防止死锁
        response = requests.get(f"http://127.0.0.1:{port}/status", timeout=2)
        if response.status_code == 200:
            return True
    except Exception:
        # 如果连接被拒(ECONNREFUSED)或超时，说明没启动或卡死了
        pass
    return False

#设计一个map   worker_id -> udid 
WORKER_UDID_MAP = {
    0: "D9B9E375-A4CB-4A88-AF8A-21E5318284ED",  # Worker-0 绑定的模拟器
    1: "AB2D0058-2CC5-45BA-BA2B-5FF42C22E86C",  # Worker-1 绑定的模拟器
    2: "31FB00AE-AB66-4DEF-9A72-BD982BFEC54E",  # Worker-2 绑定的模拟器
    3: "EC008957-AC59-4729-B45F-E4615657E0DE",
    4: "13D6FD84-F586-4256-81C1-1F022D9C4E3B",
    5: "98EEDBB2-AE1A-4BC7-A814-A9C88AFC0135",
    6: "6EA68C95-7A99-433E-84BD-67347E36A42F",
    7: "25DE4F2D-1D4F-4E81-BC2D-5BD00D05D610",
    8: "B884455E-488E-404A-AD40-A2785CB7ABD3",
    9: "A8F1173F-D9AA-4F59-9061-1E446AE27FA9",
    
}    

def get_real_udid_from_work_id(worker_id):
    """
        根据worker_id获取udid
    """
    return WORKER_UDID_MAP.get(worker_id)
#

# ----------------- 线程守护引擎 -----------------
def worker_loop(worker_id):
    # 创建配置存储的目录
    os.makedirs(BASE_TEMP_CONFIG_DIR, exist_ok=True)
    task_count = 1
    # ==================== 【核心变更】固定机型绑定 ====================
    # worker_id 是从 0 开始的 (0, 1, 2...)
    # 强制将 worker_id=0 绑定给 "iPhone 1"，worker_id=1 绑定给 "iPhone 2"
    alidoa_version = f"iPhone {worker_id + 1}"
    print(f"[主控分配] Worker-{worker_id} 终身绑定专属机型: {alidoa_version}")
    
    # ================= 核心新增：全隔离端口分配 =================
    appium_port = 47200 + worker_id    # 专属的 Appium Server 端口
    wda_port = 8200 + worker_id        # 专属的底层控制端口
    webkit_port = 27700 + worker_id    # 专属的网页调试端口
    # ==========================================================

    # 生成目录
    #random_folder_name = f"task_w{worker_id}_{uuid.uuid4().hex[:8]}"
    random_folder_name = f"iPhone{worker_id + 1}ForWebKitDevelopment"
    # appium_process进程
    appium_process = None

    # 清理端口 防止端口没关闭
    kill_port_process(wda_port)
    time.sleep(1)
    kill_port_process(webkit_port)
    time.sleep(1)
    kill_port_process(appium_port)
    time.sleep(1)

    while True:
        #
        process = None
        real_udid = None
        try:
            # 1. 抓取任务,写入配置文件
            print(f"\n" + "="*50)
            print(f"[Worker-{worker_id}] 🚀 开始执行第 {task_count} 轮任务")
            print("="*50)
            raw_task_data = fetch_task(worker_id)
            if not raw_task_data:
                time.sleep(5)
                continue
            config_payload = build_config_payload(raw_task_data, worker_id)
            if config_payload is None:
                print(f"[Worker-{worker_id}] [-] 解析任务数据失败或格式异常，跳过本次任务...")
                time.sleep(3) 
                continue 

            
            current_task_dir = os.path.join(BASE_TEMP_CONFIG_DIR, random_folder_name)
            os.makedirs(current_task_dir, exist_ok=True)

            config_file_path = os.path.join(current_task_dir, "config.json")
            try:
                # 覆盖文件
                with open(config_file_path, 'w', encoding='utf-8') as f:
                    json.dump(config_payload, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"[Worker-{worker_id}] [-] 写入配置失败: {e}")
                shutil.rmtree(current_task_dir, ignore_errors=True)
                continue

            # # 2. 启动虚拟机
            # env = os.environ.copy()
            # # 将线程专属的固定机型注入环境变量
            # env["ALIDOA_VERSION"] = alidoa_version
            # env["SIMCTL_CHILD_ALIDOA_CONFIG_PATH"] = current_task_dir
            # env["ALIDOA_IOS_VERSION"] = "16.4"
            # print(f"[Worker-{worker_id}] [3] 注入机型环境变量: {alidoa_version} 并启动 Minibrowser...")
            # minibrowser_path = os.path.join(PROJECT_ROOT_DIR, "Tools", "Scripts", "run-minibrowser")
            # cmd = [minibrowser_path, "--release", "--ios-simulator", TARGET_URL]
            
            try:
                # ================== 核心新增：启动前强制销毁旧的专属模拟器 ==================
                # 拼装你的模拟器专属名称，例如: "iPhone 1 For WebKit Development"
                target_device_name = f"{alidoa_version} For WebKit Development"
                # 给苹果底层服务 2 秒钟的时间去清理磁盘和句柄
                time.sleep(5) 

                # ================= 核心新增：启动专属 Appium =================
                print(f"[Worker-{worker_id}] 🚀 启动专属 Appium Server (端口: {appium_port})...")
                if is_appium_running(appium_port):
                    print(f"[Worker-{worker_id}] ⚡ 专属 Appium (端口: {appium_port}) 存活健康，跳过启动直接复用！")
                else:
                    print(f"[Worker-{worker_id}] 🚀 端口 {appium_port} 空闲，正在拉起新的 Appium Server...")
                    import signal 
                    appium_process = subprocess.Popen(
                        ["appium", "-p", str(appium_port)],
                        stdout=subprocess.DEVNULL, # 不打印 Appium 日志，保持控制台清爽
                        stderr=subprocess.DEVNULL,
                        preexec_fn=os.setsid
                    )
                    # 给全新启动的 Appium 5秒钟的缓冲时间
                    time.sleep(5) 
                # ==========================================================

                #process = subprocess.Popen(cmd, env=env, cwd=PROJECT_ROOT_DIR)
                #time.sleep(35)
                
                # 查询 udid
                # test6 这个版本 udid 号写死,避免重复启动虚拟机损耗资源
                real_udid = get_real_udid_from_work_id(worker_id = worker_id)
                #real_udid = wait_and_get_booted_udid(target_device_name,timeout=40, worker_id=worker_id)

                if not real_udid:
                    print(f"[Worker-{worker_id}] [-] 无法获取模拟器 UDID，放弃当前任务")
                    continue 
                time.sleep(3)

                # 执行网页中的逻辑
                #execute_web_automation(real_udid,worker_id,wda_port)
                execute_web_automation(real_udid, worker_id, wda_port, appium_port, webkit_port)

            except Exception as e:
                print(f"[Worker-{worker_id}] [-] 任务执行异常: {e}")
            task_count += 1
            print(f"[Worker-{worker_id}] [+] 本轮任务清理完毕，15 秒后进入下一轮...")
            time.sleep(15)
        except Exception as e:
            print(f"[Worker-{worker_id}] [-] 任务执行异常2: {e}")
             # # ================= 核心新增：关闭专属 Appium =================
            if appium_process:
                try:
                    os.killpg(os.getpgid(appium_process.pid), signal.SIGTERM)
                except Exception:
                    pass
            # # ==========================================================
        finally:
            # test6 测试采用不关机的策略 只关 app
            print(f"[Worker-{worker_id}] [5] 测试结束，执行无痕清理工作...")
            print(f"[Worker-{worker_id}] 🔪 正在模拟器内强制终结 Minibrowser 进程...")
            print(f"xcrun simctl terminate {real_udid} {MINIBROWSER_BUNDLE_ID} 2>/dev/null")
            os.system(f"xcrun simctl terminate {real_udid} {MINIBROWSER_BUNDLE_ID} 2>/dev/null")

            # if process:
            #     try:
            #         process.terminate()
            #         process.wait(timeout=5)
            #     except Exception:
            #         process.kill()
            # print(f"[Worker-{worker_id}] [*] 正在向 iOS 模拟器发送硬关机指令 (UDID: {real_udid})...")
            # try:
            #     subprocess.run(["xcrun", "simctl", "shutdown", real_udid], check=True, timeout=10)
            #     print(f"[Worker-{worker_id}] [+] 模拟器已成功关机！")
            # except subprocess.TimeoutExpired:
            #     print(f"[Worker-{worker_id}] [-] 模拟器关机超时！尝试暴力杀死进程...")
            #     os.system(f"xcrun simctl shutdown {real_udid} 2>/dev/null") 
            # except Exception as e:
            #     print(f"[Worker-{worker_id}] [-] 模拟器关机失败: {e}")

            # print(f"[Worker-{worker_id}] [*] 正在删除隔离目录及指纹缓存: {current_task_dir}")
            # shutil.rmtree(current_task_dir, ignore_errors=True)
            time.sleep(6)

if __name__ == "__main__":
    os.makedirs(BASE_TEMP_CONFIG_DIR, exist_ok=True)
    
    # print("🧹 [主控] 启动前环境大扫除：正在关闭所有可能残留的模拟器...")
    # os.system("killall Simulator 2>/dev/null")
    # time.sleep(2)
    
    print(f"🌟 [主控] 准备并发启动 {CONCURRENT_COUNT} 个测试集群节点！")
    threads = []
    
    for i in range(CONCURRENT_COUNT):
        t = threading.Thread(target=worker_loop, args=(i, ))
        t.daemon = True #守护进程
        t.start()
        threads.append(t)
        
        # ⚠️ 错峰启动极度关键！给 Mac CPU 充足的时间拉起一台模拟器
        if i < CONCURRENT_COUNT - 1:
            print(f"⏳ [主控] Worker-{i} 已派发，缓冲 35 秒后启动下一台...")
            time.sleep(35) 
            
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 [主控] 收到强制停止指令，正在退出全局监控...")
        #os.system("killall Simulator 2>/dev/null")