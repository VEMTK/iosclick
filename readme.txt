options = XCUITestOptions()
options.udid = 'C0C2CD34-45D0-434A-A458-F780D49E9D63'
options.bundle_id = 'org.webkit.MobileMiniBrowser'
options.no_reset = True
options.set_capability('shouldTerminateApp',False)
options.platform_name = "iOS"
#options.platform_version = "17.0"
options.device_name = "iPhone 14"
options.automation_name = "XCUITest"

print('正在连接 Appium 并接管 App...')
driver = webdriver.Remote('http://127.0.0.1:4723',options = options)