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
# ==========================================

# ----------------- 数学与真人模拟算法 -----------------
# ==================== 核心数学与缓动算法 ====================
def generate_bezier_curve(start_pt, p1, p2, end_pt, steps=40):
    """
    生成三次贝塞尔曲线的点阵序列，并配合 ease_out 缓动算法，
    模拟人类滑动时的“中间快、两头慢（尤其是收尾慢）”的物理特性。
    """
    points = []
    for i in range(steps + 1):
        # 原始的线性时间 t (0 到 1)
        linear_t = i / steps
        
        # 关键：引入 ease-out 缓动函数
        # 让 t 的增长在末端变缓，从而导致采样的点在轨迹末端更密集，滑动表现出自然减速。
        t = 1 - math.pow(1 - linear_t, 3) 
        
        # 三次贝塞尔曲线公式
        x = (1 - t)**3 * start_pt[0] + 3 * (1 - t)**2 * t * p1[0] + 3 * (1 - t) * t**2 * p2[0] + t**3 * end_pt[0]
        y = (1 - t)**3 * start_pt[1] + 3 * (1 - t)**2 * t * p1[1] + 3 * (1 - t) * t**2 * p2[1] + t**3 * end_pt[1]
        
        points.append((int(x), int(y)))
    return points


# ==================== 终极原生贝塞尔滑动 ====================
def native_safe_bezier_swipe(driver, duration_ms=800):
    """
    100% 硬件级原生滑动 + 真实人类贝塞尔弧线算法。
    严格在 Webview 容器内部滑动，防止误触 iOS 系统级手势。
    """
    current_context = driver.context
    driver.switch_to.context("NATIVE_APP")
    
    try:
        # 1. 找到原生网页容器，获取它的真实物理边界
        native_webview = driver.find_element(AppiumBy.CLASS_NAME, "XCUIElementTypeWebView")
        rect = native_webview.rect
        
        # 2. 规划绝对安全的滑动起止点区域 (限制在容器内部的 20% ~ 80% 之间)
        # 真人滑动往往是从中间偏下一点开始，向上拨动
        start_x = rect['x'] + (rect['width'] / 2)
        end_x = start_x # 理论上的垂直终点，稍后会被贝塞尔曲线弯曲
        
        start_y = rect['y'] + (rect['height'] * 0.8)
        end_y = rect['y'] + (rect['height'] * 0.2)
        
        print(f"[*] 准备执行原生防风控滑动 (时长 {duration_ms}ms)...")

        # 3. 灵魂注入：生成人类手抖控制点
        # 随机生成两个偏离中心直线的控制点，制造出左偏或右偏的弧度
        # offset_x 越大，滑动的弧线越弯 (模拟大拇指画圆弧)
        offset_x = random.randint(30, 100) * random.choice([1, -1]) 
        
        # 控制点1 (靠近起点处，发生较大偏离)
        p1 = (start_x + offset_x, start_y + (end_y - start_y) * 0.2)
        # 控制点2 (靠近终点处，拉回或反向偏离，形成 S 型或 C 型)
        p2 = (start_x - (offset_x * random.uniform(0.5, 1.0)), start_y + (end_y - start_y) * 0.7)
        
        # 提取 40 个轨迹点 (帧率越高越平滑)
        path_points = generate_bezier_curve((start_x, start_y), p1, p2, (end_x, end_y), steps=40)
        
        # 4. 执行底层 W3C Pointer 触摸流
        actions = ActionBuilder(driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
        pointer = actions.pointer_action
        
        # 手指按在起点
        pointer.move_to_location(path_points[0][0], path_points[0][1])
        pointer.pointer_down()
        
        # 模拟真人按压下去的一瞬间肉体迟钝 (极小停顿)
        pointer.pause(random.uniform(0.02, 0.08))
        
        # 计算每个采样点之间需要停顿多久 (总时间 / 步数)
        # 这里用的是匀速发包，但因为前面算法点的密度不一样，物理上就形成了变速滑动！
        step_pause = duration_ms / len(path_points) / 1000.0 
        
        # 沿着贝塞尔曲线的轨迹点移动
        for point in path_points[1:]:
            pointer.move_to_location(point[0], point[1])
            pointer.pause(step_pause)
            
        # 滑动结束后，真人往往不会立刻抬手，会有一个极短的停顿(压制屏幕惯性)
        pointer.pause(random.uniform(0.05, 0.15))
        pointer.pointer_up()
        
        # 提交给底层 iOS XCUITest 驱动执行
        actions.perform()
        
        print(f"[+] 贝塞尔弧线滑动完成！(轨迹点数: {len(path_points)})")
        
    except Exception as e:
        print(f"[-] 原生滑动执行失败: {e}")
    finally:
        # 无论如何，最后切回原先的上下文 (WEBVIEW)，保证后面的 find_element 不会报错
        driver.switch_to.context(current_context)
        time.sleep(random.uniform(0.8, 1.5))

# def human_tap_element_area(driver, web_element, debug_mode=True):
#     """
#     纯 JS 高级注入点击法（含可视化调试 + 极致事件容错）
#     """
#     print(f"[*] 准备执行高防真JS点击 (调试模式: {'开启' if debug_mode else '关闭'})...")
    
#     driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", web_element)
#     time.sleep(1) 

#     js_code = """
#     var el = arguments[0];
#     var isDebug = arguments[1];
    
#     var rect = el.getBoundingClientRect();
#     var safeX = rect.width * 0.15;
#     var safeY = rect.height * 0.15;
    
#     var targetX = rect.left + safeX + Math.random() * (rect.width - safeX * 2);
#     var targetY = rect.top + safeY + Math.random() * (rect.height - safeY * 2);
    
#     // ================= 可视化调试模块 =================
#     if (isDebug) {
#         el.style.outline = '3px solid red';
#         el.style.backgroundColor = 'rgba(255, 0, 0, 0.2)';
        
#         var dot = document.createElement('div');
#         dot.style.position = 'fixed';
#         dot.style.left = targetX + 'px';
#         dot.style.top = targetY + 'px';
#         dot.style.width = '14px';
#         dot.style.height = '14px';
#         dot.style.backgroundColor = 'blue';
#         dot.style.border = '2px solid white';
#         dot.style.borderRadius = '50%';
#         dot.style.zIndex = '2147483647';
#         dot.style.transform = 'translate(-50%, -50%)';
#         dot.style.pointerEvents = 'none'; // 鼠标穿透
        
#         document.body.appendChild(dot);
#     }
#     // =================================================

#     // ================= 高防真 + 容错点击模块 =================
#     var eventConfig = {
#         bubbles: true,
#         cancelable: true,
#         view: window,
#         clientX: targetX,
#         clientY: targetY,
#         pageX: targetX + window.scrollX,
#         pageY: targetY + window.scrollY,
#         isPrimary: true,
#         pointerType: 'touch'
#     };
    
#     // 1. 发送 Pointer 事件 (现代浏览器通用触摸标准)
#     try { el.dispatchEvent(new PointerEvent('pointerdown', eventConfig)); } catch(e) {}
    
#     // 2. 发送 Touch 事件 (加入 try-catch 拦截你刚刚遇到的报错)
#     try { el.dispatchEvent(new TouchEvent('touchstart', eventConfig)); } catch(e) {}
    
#     // 3. 抬起动作
#     try { el.dispatchEvent(new PointerEvent('pointerup', eventConfig)); } catch(e) {}
#     try { el.dispatchEvent(new TouchEvent('touchend', eventConfig)); } catch(e) {}
    
#     // 4. 发送最核心的 Mouse / Click 事件触发跳转
#     try { el.dispatchEvent(new MouseEvent('mousedown', eventConfig)); } catch(e) {}
#     try { el.dispatchEvent(new MouseEvent('mouseup', eventConfig)); } catch(e) {}
#     try { el.dispatchEvent(new MouseEvent('click', eventConfig)); } catch(e) {}
#     // =================================================
    
#     return {x: targetX, y: targetY};
#     """
    
#     # 执行这段 JS 代码
#     result = driver.execute_script(js_code, web_element, debug_mode)
    
#     print(f"[*] 网页内真实落点已生成: (X:{int(result['x'])}, Y:{int(result['y'])})")
    
#     if debug_mode:
#         print("👀 [DEBUG] 已在模拟器上绘制【红框】和【蓝点】，请观察！暂停 4 秒...")
#         time.sleep(4) 
#     else:
#         time.sleep(1)

def human_tap_element_area(driver, web_element, debug_mode=True):
    """
    终极防风控：百分比映射原生硬件点击法 + 可视化调试 (保证 isTrusted = true)
    - JS 负责计算安全随机点、绘制红框蓝点、并返回百分比。
    - NATIVE_APP 负责接收百分比，换算绝对坐标并发射真实硬件触控。
    """
    print(f"[*] 准备执行原生硬件点击 (调试模式: {'开启' if debug_mode else '关闭'})...")

    # 1. 瞬间滚动到屏幕正中央
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", web_element)
    time.sleep(1) 

    # 2. [在 WEBVIEW 内] 用 JS 计算百分比并绘制调试画面
    js_code = """
    var el = arguments[0];
    var isDebug = arguments[1];
    
    var rect = el.getBoundingClientRect();
    
    // 规避边界死角，向内收缩 15%，生成一个绝对安全的随机落点
    var safeX = rect.width * 0.15;
    var safeY = rect.height * 0.15;
    var targetX = rect.left + safeX + Math.random() * (rect.width - safeX * 2);
    var targetY = rect.top + safeY + Math.random() * (rect.height - safeY * 2);

    // ================= 可视化调试模块 =================
    if (isDebug) {
        // 画出元素的红色边框和浅红底色
        el.style.outline = '3px solid red';
        el.style.backgroundColor = 'rgba(255, 0, 0, 0.2)';
        
        // 创建一个蓝色的点，代表我们算出来的随机落点
        var dot = document.createElement('div');
        dot.style.position = 'fixed'; // 固定相对于可视区域
        dot.style.left = targetX + 'px';
        dot.style.top = targetY + 'px';
        dot.style.width = '14px';
        dot.style.height = '14px';
        dot.style.backgroundColor = 'blue';
        dot.style.border = '2px solid white';
        dot.style.borderRadius = '50%';
        dot.style.zIndex = '2147483647';
        dot.style.transform = 'translate(-50%, -50%)';
        dot.style.pointerEvents = 'none'; // 关键：让这个圆点鼠标穿透，防止挡住稍后的原生点击！
        
        document.body.appendChild(dot);
    }
    // =================================================

    // 获取当前网页真实的内部可视窗口宽高
    var vw = window.innerWidth || document.documentElement.clientWidth;
    var vh = window.innerHeight || document.documentElement.clientHeight;

    // 返回 X 和 Y 占据当前可视窗口的百分比
    return {
        pct_x: targetX / vw,
        pct_y: targetY / vh
    };
    """
    
    # 执行 JS，拿回计算出的百分比
    pct_result = driver.execute_script(js_code, web_element, debug_mode)
    pct_x = pct_result['pct_x']
    pct_y = pct_result['pct_y']
    
    print(f"[*] 元素位于网页视口相对位置: X轴 {pct_x*100:.1f}%, Y轴 {pct_y*100:.1f}%")

    # 如果开启了调试模式，在这里暂停 3 秒，让你用眼睛确认蓝点是不是在红框里
    if debug_mode:
        print("👀 [DEBUG] 已绘制【红框】和【蓝点】，请观察落点位置！等待 3 秒后执行原生物理敲击...")
        time.sleep(3)

    # 3. 记录当前环境，并立即切换到原生系统环境准备打击
    current_context = driver.context
    driver.switch_to.context("NATIVE_APP")
    
    try:
        # 4. [在 NATIVE_APP 内] 寻找装载这个网页的原生容器框
        native_webview = driver.find_element(AppiumBy.CLASS_NAME, "XCUIElementTypeWebView")
        wv_rect = native_webview.rect
        
        # 5. 原生容器宽/高 × 百分比 = 绝对精准的物理屏幕坐标！
        final_x = wv_rect['x'] + (wv_rect['width'] * pct_x)
        final_y = wv_rect['y'] + (wv_rect['height'] * pct_y)
        
        print(f"[*] 成功映射物理屏幕绝对坐标: (X:{int(final_x)}, Y:{int(final_y)})")

        # 6. 发送 iOS 硬件底层触控指令 (敲击我们算出来的蓝点位置)
        actions = ActionBuilder(driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
        actions.pointer_action.move_to_location(int(final_x), int(final_y))
        actions.pointer_action.pointer_down()
        actions.pointer_action.pause(random.uniform(0.05, 0.15)) # 真人肉体按压停顿
        actions.pointer_action.pointer_up()
        actions.perform()
        
        print("[+] 硬件级原生点击指令已下发！")
        
    except Exception as e:
        print(f"[-] 原生映射点击失败 (可能是没找到 Webview 容器): {e}")
    finally:
        # 7. 无论如何，点完立刻把控制权交还给网页
        driver.switch_to.context(current_context)
        # 点击后给页面一点反应/跳转的时间
        time.sleep(1)


# ----------------- 核心业务逻辑 -----------------
def execute_web_automation(real_udid):
    """执行复杂的网页自动化流程"""
    options = XCUITestOptions()
    options.platform_name = "iOS"
    
    options.automation_name = "XCUITest"
    options.udid = real_udid
    options.bundle_id = MINIBROWSER_BUNDLE_ID
    options.no_reset = True # 绝对不能重启，直接接管命令行启动的浏览器
    options.new_command_timeout = 100 
    options.set_capability("webviewAtomWaitTimeout", 15000)
    options.set_capability("unexpectedAlertBehaviour", "accept")
    # 添加这一行：
    options.set_capability("appium:showXcodeLog", True)
    #options.set_capability("appium:usePrebuiltWDA", True)
    options.platform_version = "16.4" 
    #options.set_capability("appium:sdkVersion", "16.4")
    # 强制指定 SDK 路径，避开自动寻找
    options.set_capability("appium:sdkVersion", "16.4")
    # 强制指定构建的目标版本
    options.set_capability("appium:platformVersion", "16.4")

    print("[4] 正在附加 Appium 接管浏览器...")
    driver = webdriver.Remote('http://127.0.0.1:4723', options=options)
    
    try:
        # 1. 切换到 Webview
        time.sleep(3) # 等待渲染
        contexts = driver.contexts
        webview = next((c for c in contexts if "WEBVIEW" in c), None)
        if not webview:
            print("[-] 未找到网页上下文！")
            return
        driver.switch_to.context(webview)
        print("[+] 成功进入网页环境")

        wait = WebDriverWait(driver, 15)

        # 2. 点击 id="link"
        print("[*] 寻找并点击 clickme 标签...")
        clickme_btn = wait.until(EC.presence_of_element_located((By.ID, "link")))
        #clickme_btn.click()
        human_tap_element_area(driver, clickme_btn)

        # 2. 重新接入后，现在查询 URL 就是绝对安全的了
        print("[*] 验证目标网页 URL...")
        print("[*] 假装真人正在认真看页面 (30~61秒)...")

        time.sleep(random.uniform(35, 61))

        wait = WebDriverWait(driver, 15) # 重新初始化 Wait
        wait.until(EC.url_contains("sec.myrathis.com"))
        print("[+] 网页 URL 验证通过！")
        

        # 3. 模拟真人滑动
        # ================= 全部改用 NATIVE 原生滑动的阅读逻辑 =================
        print("[*] 开始执行纯原生硬件“呼吸式”滑动浏览...")
        
        read_steps = random.randint(2,4)
        for i in range(read_steps):
            sleep_time = random.uniform(1, 3)
            print(f"    - 真人正在阅读... 停留 {int(sleep_time)} 秒")
            time.sleep(sleep_time)
            
            # [调用 NATIVE 硬件级安全滑动]
            # 注意：这个函数内部会自动切 NATIVE 滑动，滑完又会自动切回当前 WEBVIEW，非常省心！
            native_safe_bezier_swipe(driver, duration_ms=random.randint(300, 1200))
            print("    - 完成一次原生硬件屏幕滑动")
            
        print("[+] 页面阅读完毕！")
        # ===============================================================

        # # 5. 随机寻找游戏卡片并点击
        # if random.random() < 0.75:
        #     print("[*] 75%寻找游戏卡片...")
        #     #game_cards = driver.find_elements(By.CSS_SELECTOR, "div.game-card.home-page-card")
        #     game_cards = driver.find_elements(By.CSS_SELECTOR, "div.card")

        #     if game_cards:
        #         print("[+] 存在游戏卡片")
        #         target_card = random.choice(game_cards)
        #         # 为了防止元素在屏幕外，用 JS 把它平滑滚动到视野中央
        #         driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", target_card)
        #         time.sleep(2)
        #         print("[+] 点击选中的游戏卡片...")
        #         human_tap_element_area(driver, target_card)

        #         # 模拟滑动
        #         # ================= 全部改用 NATIVE 原生滑动的阅读逻辑 =================
        #         print("[*] 开始执行纯原生硬件“呼吸式”滑动浏览...")
        #         read_steps = random.randint(2, 4)
        #         for i in range(read_steps):
        #             sleep_time = random.uniform(3, 5)
        #             print(f"    - 真人正在阅读... 停留 {int(sleep_time)} 秒")
        #             time.sleep(sleep_time)
        #             # [调用 NATIVE 硬件级安全滑动]
        #             # 注意：这个函数内部会自动切 NATIVE 滑动，滑完又会自动切回当前 WEBVIEW，非常省心！
        #             native_safe_bezier_swipe(driver, duration_ms=random.randint(600, 1200))
        #             print("    - 完成一次原生硬件屏幕滑动")
        #         print("[+] 页面阅读完毕！")
        #     else:
        #         print("[-] 当前页面没有找到游戏卡片")
        # else:
        #     print("[-] 25% 不点击游戏卡片.")

        # 6. 15% 概率盲点广告区域 (无需切入 iframe)
        # if random.random() < 1.0:
        #     print("[*] 🎲 触发 15% 概率，准备盲点广告区域...")
        #     try:
        #         # 关键区别：我们直接找 <iframe> 标签本身！
        #         # 这能保证我们获取到的宽和高，就是那张广告图片真实的面积，绝对不会点偏到外面的空白 div 上去
        #         ad_frames = driver.find_elements(By.CSS_SELECTOR, "iframe[id*='ads_iframe']")
        #         print('1-----')
        #         if not ad_frames:
        #             print("[-] 当前页面未找到 iframe 广告位。")
        #         else:
        #             print('2-----')
        #             target_frame = random.choice(ad_frames)
        #             print('3-----')
        #             if target_frame.is_displayed():
        #                 print(f"[+] 锁定目标广告框，执行物理盲点打击！")    
        #                 # 直接调用原生百分比映射点击法！
        #                 # 底层驱动只会向 iOS 屏幕的那个 (X, Y) 坐标发送一次真实的触摸信号。
        #                 # 只要那个位置在视觉上显示着广告，iOS 系统就会自动把点击事件传递进 iframe 内部触发跳转。
        #                 human_tap_element_area(driver, target_frame, debug_mode=False)
                        
        #                 print("[+] 🎯 广告盲点任务执行完毕！")

        #                 read_steps = random.randint(3,6)
        #                 for i in range(read_steps):
        #                     sleep_time = random.uniform(3, 5)
        #                     print(f"    - 真人正在阅读... 停留 {int(sleep_time)} 秒")
        #                     time.sleep(sleep_time)
                            
        #                     # [调用 NATIVE 硬件级安全滑动]
        #                     # 注意：这个函数内部会自动切 NATIVE 滑动，滑完又会自动切回当前 WEBVIEW，非常省心！
        #                     native_safe_bezier_swipe(driver, duration_ms=random.randint(300, 1200))
        #                     print("    - 完成一次原生硬件屏幕滑动")
                            
        #                 print("[+] 页面阅读完毕！")

        #             else:
        #                 print("[-] 选中的广告区域处于隐藏状态，已放弃。")
                        
        #     except Exception as e:
        #         print(f"[-] 盲点广告区域时发生意外错误: {e}")
        # else:
        #     print("[*] 🛡️ 未触发 iframe 广告点击概率 (85% 安全略过)")

        def find_and_tap_lazy_element(driver, elements_list, max_swipes=5):
            """
            终极懒加载元素寻找法：
            模拟真人不断向下拨动屏幕，直到目标元素进入视野并被完全渲染。
            """
            if not elements_list:
                return False
                
            # 随机选定一个目标 (假设这个目标在页面很靠下的地方)
            target_element = random.choice(elements_list)
            print(f"[*] 锁定了一个隐藏目标，准备执行真人拉网式搜索...")
            
            # 1. 尝试使用传统的 JS 滚动 (如果页面标准，这一步就搞定了)
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", target_element)
            time.sleep(1.5)
            
            # 2. 暴力真人找寻机制 (如果没滚到位，或者没渲染出来)
            swipe_count = 0
            is_ready_to_click = False
            
            while swipe_count < max_swipes:
                # 获取该元素此刻在整个网页绝对高度中的位置
                try:
                    # 这里的 rect 取的是元素距离整个文档顶部的距离，以及它的宽高
                    rect = target_element.rect 
                    
                    # 检查它是否具备可点击的物理形态
                    if target_element.is_displayed() and rect['width'] > 10 and rect['height'] > 10:
                        print(f"[+] 第 {swipe_count} 次探索：目标已成功渲染！大小 {rect['width']}x{rect['height']}。")
                        
                        # 再次执行精准微调，把它挪到屏幕中央
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", target_element)
                        time.sleep(1)
                        
                        is_ready_to_click = True
                        break # 找到了，跳出寻找循环
                except Exception as e:
                    pass # 捕获可能出现的 StaleElement 异常
                    
                print(f"    - 目标未显示或处于屏幕外，向下滑动屏幕寻找 (第 {swipe_count + 1} 次)...")
                
                # --- 核心：切到原生环境，像真人一样往上拨动屏幕 (即页面向下滚动) ---
                current_context = driver.context
                driver.switch_to.context("NATIVE_APP")
                
                window_size = driver.get_window_size()
                w, h = window_size['width'], window_size['height']
                
                # 原生滑动：从屏幕偏下处往上滑，幅度不要太大，防止滑过头
                native_safe_bezier_swipe(driver, duration_ms=random.randint(600, 1000))
                
                driver.switch_to.context(current_context)
                # -----------------------------------------------------------------
                
                # 给页面 2 秒钟的时间加载新滑出来的内容 (极度关键的懒加载等待时间)
                time.sleep(2)
                swipe_count += 1
                
            # 3. 评判寻找结果并执行打击
            if is_ready_to_click:
                print(f"[+] 目标锁定在视野中，准备执行物理盲点打击！")
                human_tap_element_area(driver, target_element, debug_mode=False)
                return True
            else:
                print(f"[-] 在滑动了 {max_swipes} 次后，目标仍未渲染成型，放弃攻击。")
                return False

        def safe_execute_js(driver, js_code, element=None):
            """
            异步火炮 (Fire and Forget):
            将 JS 任务包装为异步闭包，绝不阻塞 Python 线程。
            无论网页多卡，都会在 0.1 秒内返回！
            """
            async_wrapper = """
            var callback = arguments[arguments.length - 1]; // Appium 注入的回调钩子
            var elem = arguments[0]; // 传进来的元素
            
            // 把危险的动作放进 setTimeout，让它脱离当前主线程立即返回
            setTimeout(function() {
                try {
                    // 在闭包内执行你想执行的代码
                    """ + js_code + """
                } catch(e) { console.log('Safe JS Error:', e); }
            }, 0);
            
            // 毫不犹豫地向 Python 报告成功，摆脱死锁！
            callback("SUCCESS"); 
            """
    
            try:
                # 使用 execute_async_script 替代 execute_script
                if element:
                    driver.execute_async_script(async_wrapper, element)
                else:
                    driver.execute_async_script(async_wrapper)
            except Exception as e:
                print(f"[!] 异步执行 JS 时遭遇底层断联，已强制放行: {e}")


        # 6. 15% 概率盲点广告区域 (完美应对懒加载)
        if random.random() < 0.20:
            print("[*] 🎲 触发 15% 概率，准备盲点广告区域...")
            try:
                # 寻找所有广告 iframe 占位符
                ad_frames = driver.find_elements(By.CSS_SELECTOR, "iframe[id*='ads_iframe']")
                
                if not ad_frames:
                    print("[-] 当前页面未找到 iframe 广告位。")
                else:
                    if not ad_frames:
                            print("[-] 当前页面未找到 iframe 广告位。")
                    else:
                        # 直接调用我们刚刚写的这个无敌函数！
                        # 它会自动负责往下划屏幕、等待懒加载、判断大小、最终点击！
                        success = find_and_tap_lazy_element(driver, ad_frames, max_swipes=4)
                
                        if success:
                            print("[+] 🎯 广告盲点任务执行完毕！")
                            time.sleep(random.uniform(35, 61))
                            read_steps = random.randint(3,6)
                            for i in range(read_steps):
                                sleep_time = random.uniform(3, 5)
                                print(f"    - 真人正在阅读... 停留 {int(sleep_time)} 秒")
                                time.sleep(sleep_time)
                                # [调用 NATIVE 硬件级安全滑动]
                                # 注意：这个函数内部会自动切 NATIVE 滑动，滑完又会自动切回当前 WEBVIEW，非常省心！
                                native_safe_bezier_swipe(driver, duration_ms=random.randint(300, 1200))
                                print("    - 完成一次原生硬件屏幕滑动")
                            print("[+] 页面阅读完毕！")
                        else:
                            print("[-] 广告点击任务被安全放弃。")
                    # target_frame = random.choice(ad_frames)
                    # print(f"[*] 随机选中了一个广告占位符，强制滚动至此以触发懒加载渲染...")
                    
                    # # 1. 核心改变：先强制滚动过去！
                    # # 使用防卡死的异步 JS 将元素拉到屏幕正中央
                    # safe_execute_js(driver, "elem.scrollIntoView({behavior: 'smooth', block: 'center'});", target_frame)
                    
                    # # 2. 给它充足的时间去请求广告图片并渲染 (这一步极其关键)
                    # print("[*] 等待 3 秒钟，让广告商下发并渲染图片...")
                    # time.sleep(3) 
                    
                    # # 3. 此时再来检查它是否真的被渲染出来了
                    # # 除了检查 is_displayed，最好检查一下它的物理长宽是否大于 10 像素
                    # # (有些广告被 AdBlock 拦截后，虽然 is_displayed，但长宽是 0x0)
                    # rect = target_frame.rect
                    # is_visible = target_frame.is_displayed()
                    
                    # if is_visible and rect['width'] > 10 and rect['height'] > 10:
                    #     print(f"[+] 广告渲染成功！真实大小: {rect['width']}x{rect['height']}。准备执行物理盲点打击！")
                        
                    #     # 4. 执行原生物理点击
                    #     human_tap_element_area(driver, target_frame, debug_mode=False)
                        
                    #     print("[+] 🎯 广告盲点任务执行完毕！")

                    #     read_steps = random.randint(3,6)
                    #     for i in range(read_steps):
                    #         sleep_time = random.uniform(3, 5)
                    #         print(f"    - 真人正在阅读... 停留 {int(sleep_time)} 秒")
                    #         time.sleep(sleep_time)
                            
                    #         # [调用 NATIVE 硬件级安全滑动]
                    #         # 注意：这个函数内部会自动切 NATIVE 滑动，滑完又会自动切回当前 WEBVIEW，非常省心！
                    #         native_safe_bezier_swipe(driver, duration_ms=random.randint(300, 1200))
                    #         print("    - 完成一次原生硬件屏幕滑动")
                            
                    #     print("[+] 页面阅读完毕！")
                    # else:
                    #     print(f"[-] 滚动后广告仍未渲染 (可能为空白、未填充或被拦截)，大小: {rect['width']}x{rect['height']}，放弃点击。")
                        
            except Exception as e:
                print(f"[-] 盲点广告区域时发生意外错误: {e}")
        else:
            print("[*] 🛡️ 未触发 iframe 广告点击概率 (85% 安全略过)")    

    except Exception as e:
        print(f"[-] 自动化执行中发生错误: {e}")
    finally:
        driver.quit()


# 5. 每个任务运行的时间 (秒)
TASK_DURATION = 30 
# ==========================================

def fetch_task():
    """从接口获取指纹任务"""
    print(f"\n[1] 正在向 {API_URL} 请求新任务...")
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status() # 如果返回状态码不是 200，则抛出异常
        task_data = response.json()
        
        # 简单校验接口返回的数据是否包含我们要的指纹字段
        if not task_data:
            print("[-] 接口返回空数据，稍后重试...")
            return None
            
        print("[+] 成功获取指纹任务数据！")
        return task_data
    except Exception as e:
        print(f"[-] 网络请求失败: {e}")
        return None

#保存配置信息
def save_config(data):
    """将指纹数据写入 config.json"""
    print(f"[2] 正在生成配置文件: {CONFIG_FILE_PATH}")
    try:
        # 如果目录不存在，自动创建目录
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
            
        # 将数据写入 json 文件，保证中文字符不乱码，并格式化美观
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print("[+] 配置文件写入成功！")
        return True
    except Exception as e:
        print(f"[-] 写入配置文件失败: {e}")
        return False
    
def run_minibrowser():
    """注入环境变量并启动 Minibrowser"""
    print("[3] 准备启动模拟器及 Minibrowser...")
    
    # 拷贝当前系统的环境变量
    env = os.environ.copy()
    
    # 注入你的自定义环境变量 (替代 shell 里的 export/前置赋值)
    env["ALIDOA_VERSION"] = "iPhone 14"
    # 注意：根据你的命令，这里传入的是目录路径，而不是具体的文件路径
    env["SIMCTL_CHILD_CONFIG"] = CONFIG_DIR 

    # 构建启动命令
    cmd = [
        "./Tools/Scripts/run-minibrowser", 
        "--release", 
        "--ios-simulator", 
        TARGET_URL
    ]

    try:
        # subprocess.Popen 是非阻塞启动，脚本会继续往下走
        print(f"执行命令: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd, 
            env=env, 
            cwd=PROJECT_ROOT_DIR # 指定执行命令的工作目录
        )
        return process
    except Exception as e:
        print(f"[-] 启动脚本失败: {e}")
        print(f"    请检查 PROJECT_ROOT_DIR 路径是否正确。")
        return None
    

"""
# 组装参数
将 原始的后台数据结构 转换成需要的 config.json
"""
def build_config_payload(raw_task_data):
    """
    严格清洗并映射 JSON 数据。
    不使用兜底数据，如果核心层级或字段缺失，直接返回 None。
    """
    # 1. 强校验：检查基础节点格式是否存在
    if not isinstance(raw_task_data, dict):
        print("[-] 接口返回的不是有效 JSON 对象，放弃任务。")
        return None

    data_node = raw_task_data.get("data")
    if not isinstance(data_node, dict):
        print("[-] 数据格式不对：缺少 data 节点，放弃任务。")
        return None

    auto_ads_node = data_node.get("autoAdsUserAgent")
    if not isinstance(auto_ads_node, dict):
        print("[-] 数据格式不对：缺少 autoAdsUserAgent 节点，放弃任务。")
        return None

    # 2. 强校验：检查核心指纹字段是否下发 (这里以 userAgent 和 screen 为例)
    if "userAgent" not in auto_ads_node or "screen" not in auto_ads_node:
        print("[-] 数据格式不对：缺少核心指纹字段 (userAgent 或 screen)，放弃任务。")
        return None

    # 3. 提取数据 (确保不会因为字段为空而报错)
    raw_locale = auto_ads_node.get("appLocale", "")
    raw_lang = auto_ads_node.get("acceptLang", "")
    screen_node = auto_ads_node.get("screen", {})

    # 4. 严格按照要求组装 config.json
    target_config = {
        # 动态提取部分
        "appLocale": raw_locale.split(",")[0] if raw_locale else "",
        "acceptLang": {
            "js": raw_lang.split(",")[0] if raw_lang else "",
            "http": raw_lang
        },
        "timeZone": auto_ads_node.get("timeZone", ""),
        "userAgent": auto_ads_node.get("userAgent", ""),
        "screen": {
            # 确保即使 screen 下面没有 width，也能安全提取并转为整形
            "width": int(screen_node.get("viewportWidth", 0)),  # with 修改为 viewportWidth
            "height": int(screen_node.get("viewportHeight", 0)) # height 修改为 viewportHeight
        },
        "proxy": auto_ads_node.get("proxy", ""),
        
        # 静态必需部分 (minibrowser 底层要求的格式规范)
        "navigator": {
            "hardwareConcurrency": 8
        },
        "intercept": {
            "host": "m.facebook.com",
            "str":f"<a id=\"link\" href=\"{H5_GAME_URL}\">ClickMe</a>"
        }
    }

    # 可选：如果某个提取出来的字段为空，你也可以选择在这里 return None
    # if not target_config["userAgent"] or target_config["screen"]["width"] == 0:
    #     print("[-] 提取到了空的核心指纹数据，放弃任务。")
    #     return None

    return target_config

# 解析 iPhone的版本
def extract_device_version(raw_task_data):
    """从深层 JSON 提取 FBDV 字段并转换为 iPhone 14 格式"""
    # 路径更新为匹配新的 JSON 结构
    ua_node = raw_task_data.get("data", {}).get("autoAdsUserAgent", {})
    user_agent = ua_node.get("userAgent", "")
    
    match = re.search(r'FBDV/([^;]+)', user_agent)
    if match:
        raw_device = match.group(1) # 例如 "iPhone15,2"
        clean_match = re.search(r'(iPhone)(\d+)', raw_device)
        if clean_match:
            return f"{clean_match.group(1)} {clean_match.group(2)}" # 变成 "iPhone 15"
        return raw_device
    return "iPhone 14"

def wait_and_get_booted_udid(timeout=30):
    """
    智能等待模拟器彻底启动，并动态获取真实的 UDID
    """
    print(f"[*] 正在等待模拟器开机并获取 UDID (最多等待 {timeout} 秒)...")
    for i in range(timeout):
        try:
            # 调用苹果底层的 simctl 命令查询设备列表
            output = subprocess.check_output(['xcrun', 'simctl', 'list', 'devices'], text=True)
            for line in output.splitlines():
                # 寻找状态为 (Booted) 的那一行
                if "(Booted)" in line:
                    # 用正则把 UDID 提取出来
                    match = re.search(r'([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})', line)
                    if match:
                        real_udid = match.group(1)
                        print(f"[+] 模拟器已就绪！获取到真实 UDID: {real_udid}")
                        return real_udid
        except Exception:
            pass
        
        time.sleep(1)
        
    print("[-] 等待模拟器启动超时！")
    return None

# ----------------- 调度主控 (同之前) -----------------
def main_loop():
    os.makedirs(BASE_TEMP_CONFIG_DIR, exist_ok=True)
    task_count = 1

    while True:
        print(f"\n" + "="*50)
        print(f"🚀 开始执行第 {task_count} 轮任务")
        print("="*50)

        # 1. 获取任务数据 (拿到的是原始庞大 JSON)
        raw_task_data = fetch_task()
        if not raw_task_data:
            time.sleep(5)
            continue

        # ================== 核心防呆校验 ==================
        # 2. 尝试解析并组装指纹
        config_payload = build_config_payload(raw_task_data)
        
        # 如果格式不对，build_config_payload 会返回 None
        if config_payload is None:
            print("[-] 解析任务数据失败或格式异常，跳过本次任务...")
            time.sleep(3) # 稍微休息下，防止接口一直错导致死循环狂刷
            continue # <--- 核心：直接跳过，进入下一次大循环
        # =================================================

        # 2. 生成随机隔离目录
        random_folder_name = f"task_{uuid.uuid4().hex[:8]}"
        current_task_dir = os.path.join(BASE_TEMP_CONFIG_DIR, random_folder_name)
        os.makedirs(current_task_dir, exist_ok=True)

        # 3. 写入 config.json
        config_file_path = os.path.join(current_task_dir, "config.json")
        try:
            with open(config_file_path, 'w', encoding='utf-8') as f:
                # 写入清洗后的数据
                json.dump(config_payload, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[-] 写入配置失败: {e}")
            shutil.rmtree(current_task_dir, ignore_errors=True)
            continue

        # ================= 核心修改区域 =================
        # 4. 配置环境变量
        env = os.environ.copy()
        
        # 动态提取版本号
        alidoa_version = extract_device_version(raw_task_data)
        env["ALIDOA_VERSION"] = alidoa_version
        env["SIMCTL_CHILD_ALIDOA_CONFIG_PATH"] = current_task_dir
        #env["SIMCTL_CHILD_CONFIG"] = current_task_dir 
        
        print(f"[3] 成功提取机型: {alidoa_version}")
        print(f"[3] 注入环境变量并启动 Minibrowser...")
        # ===============================================
        minibrowser_path = os.path.join(PROJECT_ROOT_DIR, "Tools", "Scripts", "run-minibrowser")
        cmd = [minibrowser_path, "--release", "--ios-simulator", TARGET_URL]
        
        process = None
        try:
            process = subprocess.Popen(cmd, env=env, cwd=PROJECT_ROOT_DIR)
            time.sleep(38)

            real_udid = wait_and_get_booted_udid(timeout=40)

            if not real_udid:
                print("[-] 无法获取模拟器 UDID，放弃当前任务")
                continue # 跳过本轮
                
            # 再额外给 3 秒钟让浏览器界面彻底渲染出来
            time.sleep(3)
            
            # 执行自动化点击滑动
            execute_web_automation(real_udid)
            
        except Exception as e:
            print(f"[-] 任务执行异常: {e}")
            
        finally:
            print("[5] 测试结束，执行无痕清理工作...")
            # if process:
            #     try:
            #         process.terminate()
            #         process.wait(timeout=5)
            #     except Exception:
            #         process.kill()
                    
            # print(f"[*] 正在删除隔离目录: {current_task_dir}")
            # shutil.rmtree(current_task_dir, ignore_errors=True)

            # 第一步：终止通过 subprocess 启动的 minibrowser 进程
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
            
            # ================= 核心新增：彻底关闭 iOS 虚拟机 =================
            if 'real_udid' in locals() and real_udid:
                print(f"[*] 正在向 iOS 模拟器发送硬关机指令 (UDID: {real_udid})...")
                try:
                    # 调用苹果系统底层命令，强制关闭指定的模拟器
                    subprocess.run(["xcrun", "simctl", "shutdown", real_udid], check=True, timeout=10)
                    print("[+] 模拟器已成功关机！")
                except subprocess.TimeoutExpired:
                    print("[-] 模拟器关机超时！尝试暴力杀死进程...")
                    os.system("killall Simulator 2>/dev/null") # 备用的暴力清理手段
                except Exception as e:
                    print(f"[-] 模拟器关机失败: {e}")
            else:
                print("[-] 未获取到 UDID，可能无法精准关闭模拟器，执行保底清理...")
                os.system("killall Simulator 2>/dev/null")
            # =================================================================

            # 第三步：彻底删除刚才生成的随机指纹配置文件夹
            print(f"[*] 正在删除隔离目录及指纹缓存: {current_task_dir}")
            shutil.rmtree(current_task_dir, ignore_errors=True)
            
            # 短暂休眠，给系统一点时间彻底释放内存和句柄，迎接下一个全新的虚拟机
            time.sleep(3)
            
        task_count += 1
        print("[+] 本轮任务清理完毕，3 秒后进入下一轮...")
        time.sleep(15)

if __name__ == "__main__":
    main_loop()