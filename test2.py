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
import threading # <--- [新增] 并发需要的线程模块

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
H5_GAME_URL = "https://sec.myrathis.com"
USER_HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(USER_HOME, "Documents", "iPhone14")
BASE_TEMP_CONFIG_DIR = os.path.join(USER_HOME, "Documents", "TempConfigs")
CONFIG_FILE_PATH = os.path.join(CONFIG_DIR, "config.json")
#PROJECT_ROOT_DIR = "/Users/mac2/src/WebKit"
PROJECT_ROOT_DIR = "/Users/robin/src/WebKit"

# !!! 必填：你的 minibrowser 的包名 (Bundle ID) !!!
# 可以用 xcrun simctl listapps booted 命令查看
#MINIBROWSER_BUNDLE_ID = "org.webkit.MobileMiniBrowser"
MINIBROWSER_BUNDLE_ID = "org.gu.MobileMiniBrowser" 

# ================= 并发集群控制区域 =================
CONCURRENT_COUNT = 1               # [核心] 设置你想同时运行的虚拟机数量！
CLAIMED_UDIDS = set()              # 记录已经被分配出去的 UDID
UDID_LOCK = threading.Lock()       # 互斥锁，防止两个线程抢同一台刚开机的模拟器
# =================================================

# ----------------- 数学与真人模拟算法 -----------------
# ==================== 核心数学与缓动算法 ====================
def generate_bezier_curve(start_pt, p1, p2, end_pt, steps=40):
    points = []
    for i in range(steps + 1):
        linear_t = i / steps
        t = 1 - math.pow(1 - linear_t, 3) 
        x = (1 - t)**3 * start_pt[0] + 3 * (1 - t)**2 * t * p1[0] + 3 * (1 - t) * t**2 * p2[0] + t**3 * end_pt[0]
        y = (1 - t)**3 * start_pt[1] + 3 * (1 - t)**2 * t * p1[1] + 3 * (1 - t) * t**2 * p2[1] + t**3 * end_pt[1]
        points.append((int(x), int(y)))
    return points

# ==================== 终极原生贝塞尔滑动 ====================
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


# ----------------- 核心业务逻辑 -----------------
def execute_web_automation(real_udid, worker_id, wda_port):
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
    #options.set_capability("appium:showXcodeLog", True)
    options.platform_version = "16.4" 
    options.set_capability("appium:sdkVersion", "16.4")
    options.set_capability("appium:platformVersion", "16.4")
    
    # 【新增并发防止端口冲突配置】
    # options.set_capability("appium:wdaLocalPort", wda_port)
    # options.set_capability("appium:webDriverAgentUrl", f"http://127.0.0.1:{wda_port}")
    # options.set_capability("appium:usePrebuiltWDA", True)

    print(f"[Worker-{worker_id}] [4] 正在附加 Appium 接管浏览器...")
    driver = webdriver.Remote('http://127.0.0.1:4723', options=options)
    
    try:
        time.sleep(3) 
        contexts = driver.contexts
        webview = next((c for c in contexts if "WEBVIEW" in c), None)
        if not webview:
            print("[-] 未找到网页上下文！")
            return
        driver.switch_to.context(webview)
        print(f"[Worker-{worker_id}] [+] 成功进入网页环境")

        wait = WebDriverWait(driver, 15)

        print(f"[Worker-{worker_id}] [*] 寻找并点击 clickme 标签...")
        clickme_btn = wait.until(EC.presence_of_element_located((By.ID, "link")))
        human_tap_element_area(driver, clickme_btn)

        print(f"[Worker-{worker_id}] [*] 验证目标网页 URL...")
        print(f"[Worker-{worker_id}] [*] 假装真人正在认真看页面 (30~61秒)...")

        time.sleep(random.uniform(35, 61))

        wait = WebDriverWait(driver, 15) 
        wait.until(EC.url_contains("sec.myrathis.com"))
        print(f"[Worker-{worker_id}] [+] 网页 URL 验证通过！")
        
        print(f"[Worker-{worker_id}] [*] 开始执行纯原生硬件“呼吸式”滑动浏览...")
        
        read_steps = random.randint(2,4)
        for i in range(read_steps):
            sleep_time = random.uniform(1, 3)
            print(f"[Worker-{worker_id}]     - 真人正在阅读... 停留 {int(sleep_time)} 秒")
            time.sleep(sleep_time)
            native_safe_bezier_swipe(driver, duration_ms=random.randint(300, 1200))
            print(f"[Worker-{worker_id}]     - 完成一次原生硬件屏幕滑动")
            
        print(f"[Worker-{worker_id}] [+] 页面阅读完毕！")

        # 嵌套函数原样保留
        def find_and_tap_lazy_element(driver, elements_list, max_swipes=5):
            if not elements_list:
                return False
            target_element = random.choice(elements_list)
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

        if random.random() < 0.20:
            print(f"[Worker-{worker_id}] [*] 🎲 触发 15% 概率，准备盲点广告区域...")
            try:
                ad_frames = driver.find_elements(By.CSS_SELECTOR, "iframe[id*='ads_iframe']")
                if not ad_frames:
                    print(f"[Worker-{worker_id}] [-] 当前页面未找到 iframe 广告位。")
                else:
                    success = find_and_tap_lazy_element(driver, ad_frames, max_swipes=4)
                    if success:
                        print(f"[Worker-{worker_id}] [+] 🎯 广告盲点任务执行完毕！")
                        time.sleep(random.uniform(35, 61))
                        read_steps = random.randint(3,6)
                        for i in range(read_steps):
                            sleep_time = random.uniform(3, 5)
                            print(f"[Worker-{worker_id}]     - 真人正在阅读... 停留 {int(sleep_time)} 秒")
                            time.sleep(sleep_time)
                            native_safe_bezier_swipe(driver, duration_ms=random.randint(300, 1200))
                            print(f"[Worker-{worker_id}]     - 完成一次原生硬件屏幕滑动")
                        print(f"[Worker-{worker_id}] [+] 页面阅读完毕！")
                    else:
                        print(f"[Worker-{worker_id}] [-] 广告点击任务被安全放弃。")
            except Exception as e:
                print(f"[Worker-{worker_id}] [-] 盲点广告区域时发生意外错误: {e}")
        else:
            print(f"[Worker-{worker_id}] [*] 🛡️ 未触发 iframe 广告点击概率 (85% 安全略过)")    

    except Exception as e:
        print(f"[Worker-{worker_id}] [-] 自动化执行中发生错误: {e}")
    finally:
        driver.quit()

# 5. 每个任务运行的时间 (秒)
TASK_DURATION = 30 
# ==========================================

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
    
def run_minibrowser():
    print("[3] 准备启动模拟器及 Minibrowser...")
    env = os.environ.copy()
    env["ALIDOA_VERSION"] = "iPhone 14" # alidoa_version  #"iPhone 14"
    env["SIMCTL_CHILD_CONFIG"] = CONFIG_DIR 
    cmd = ["./Tools/Scripts/run-minibrowser", "--release", "--ios-simulator", TARGET_URL]
    try:
        print(f"执行命令: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, env=env, cwd=PROJECT_ROOT_DIR)
        return process
    except Exception as e:
        print(f"[-] 启动脚本失败: {e}")
        return None

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

def extract_device_version(raw_task_data):
    ua_node = raw_task_data.get("data", {}).get("autoAdsUserAgent", {})
    user_agent = ua_node.get("userAgent", "")
    match = re.search(r'FBDV/([^;]+)', user_agent)
    if match:
        raw_device = match.group(1) 
        clean_match = re.search(r'(iPhone)(\d+)', raw_device)
        if clean_match: return f"{clean_match.group(1)} {clean_match.group(2)}" 
        return raw_device
    return "iPhone 14"

def wait_and_get_booted_udid(timeout=30, worker_id=0):
    print(f"[Worker-{worker_id}] [*] 正在等待模拟器开机并获取 UDID (最多等待 {timeout} 秒)...")
    for i in range(timeout):
        try:
            output = subprocess.check_output(['xcrun', 'simctl', 'list', 'devices'], text=True)
            for line in output.splitlines():
                if "(Booted)" in line:
                    match = re.search(r'([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})', line)
                    if match:
                        real_udid = match.group(1)
                        # --- 并发防抢锁 ---
                        with UDID_LOCK:
                            if real_udid not in CLAIMED_UDIDS:
                                CLAIMED_UDIDS.add(real_udid)
                                print(f"[Worker-{worker_id}] [+] 模拟器已就绪！获取到专属 UDID: {real_udid}")
                                return real_udid
        except Exception:
            pass
        time.sleep(1)
    print(f"[Worker-{worker_id}] [-] 等待模拟器启动超时！")
    return None

# ----------------- 并发线程循环主控 -----------------
def worker_loop(worker_id):
    """
    原 main_loop 的多线程形态。每个线程执行自己独立的自动化闭环。
    """
    wda_port = 8200 + worker_id 
    os.makedirs(BASE_TEMP_CONFIG_DIR, exist_ok=True)
    task_count = 1

    while True:
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

        random_folder_name = f"task_w{worker_id}_{uuid.uuid4().hex[:8]}"
        current_task_dir = os.path.join(BASE_TEMP_CONFIG_DIR, random_folder_name)
        os.makedirs(current_task_dir, exist_ok=True)

        config_file_path = os.path.join(current_task_dir, "config.json")
        try:
            with open(config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config_payload, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[Worker-{worker_id}] [-] 写入配置失败: {e}")
            shutil.rmtree(current_task_dir, ignore_errors=True)
            continue

        env = os.environ.copy()
        alidoa_version = extract_device_version(raw_task_data)
        
        # ==================== 恢复你的原版逻辑 ====================
        env["ALIDOA_VERSION"] =  alidoa_version #"iPhone 14" #alidoa_version 
        env["SIMCTL_CHILD_ALIDOA_CONFIG_PATH"] = current_task_dir
        env["ALIDOA_IOS_VERSION"] = "16.4"
        #env["SIMCTL_CHILD_CONFIG"] = current_task_dir 
        # ==========================================================
        
        print(f"[Worker-{worker_id}] [3] 成功提取机型: {alidoa_version}")
        print(f"[Worker-{worker_id}] [3] 注入环境变量并启动 Minibrowser...")
        
        minibrowser_path = os.path.join(PROJECT_ROOT_DIR, "Tools", "Scripts", "run-minibrowser")
        cmd = [minibrowser_path, "--release", "--ios-simulator", TARGET_URL]
        
        process = None
        real_udid = None
        try:
            process = subprocess.Popen(cmd, env=env, cwd=PROJECT_ROOT_DIR)
            time.sleep(38)

            real_udid = wait_and_get_booted_udid(timeout=40, worker_id=worker_id)

            if not real_udid:
                print(f"[Worker-{worker_id}] [-] 无法获取模拟器 UDID，放弃当前任务")
                continue 
                
            time.sleep(3)
            
            # 执行自动化点击滑动，传入并发端口
            execute_web_automation(real_udid, worker_id, wda_port)
            
        except Exception as e:
            print(f"[Worker-{worker_id}] [-] 任务执行异常: {e}")
            
        finally:
            print(f"[Worker-{worker_id}] [5] 测试结束，执行无痕清理工作...")
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
            
            if 'real_udid' in locals() and real_udid:
                print(f"[Worker-{worker_id}] [*] 正在向 iOS 模拟器发送硬关机指令 (UDID: {real_udid})...")
                try:
                    subprocess.run(["xcrun", "simctl", "shutdown", real_udid], check=True, timeout=10)
                    print(f"[Worker-{worker_id}] [+] 模拟器已成功关机！")
                except subprocess.TimeoutExpired:
                    print(f"[Worker-{worker_id}] [-] 模拟器关机超时！尝试暴力杀死进程...")
                    os.system("killall Simulator 2>/dev/null") 
                except Exception as e:
                    print(f"[Worker-{worker_id}] [-] 模拟器关机失败: {e}")
                
                # 清理 UDID 锁
                with UDID_LOCK:
                    if real_udid in CLAIMED_UDIDS:
                        CLAIMED_UDIDS.remove(real_udid)
            else:
                print(f"[Worker-{worker_id}] [-] 未获取到 UDID，执行保底清理...")
                os.system("killall Simulator 2>/dev/null")

            print(f"[Worker-{worker_id}] [*] 正在删除隔离目录及指纹缓存: {current_task_dir}")
            shutil.rmtree(current_task_dir, ignore_errors=True)
            
            time.sleep(3)
            
        task_count += 1
        print(f"[Worker-{worker_id}] [+] 本轮任务清理完毕，3 秒后进入下一轮...")
        time.sleep(15)

if __name__ == "__main__":
    os.makedirs(BASE_TEMP_CONFIG_DIR, exist_ok=True)
    print("🧹 [主控] 启动前环境大扫除：正在关闭所有残留的模拟器...")
    os.system("killall Simulator 2>/dev/null")
    time.sleep(2)
    
    print(f"🌟 [主控] 准备并发启动 {CONCURRENT_COUNT} 个测试集群节点！")
    threads = []
    
    for i in range(CONCURRENT_COUNT):
        t = threading.Thread(target=worker_loop, args=(i, ))
        t.daemon = True 
        t.start()
        threads.append(t)
        
        # 错峰启动，防止同时开机瞬间卡死 Mac CPU
        if i < CONCURRENT_COUNT - 1:
            print(f"⏳ [主控] Worker-{i} 已派发，缓冲 20 秒后启动下一台...")
            time.sleep(20) 
            
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 [主控] 收到强制停止指令，正在退出全局监控...")
        os.system("killall Simulator 2>/dev/null")