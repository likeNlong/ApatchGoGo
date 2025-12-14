import os
import subprocess
import loguru
import time
import uiautomator2 as u2

logger = loguru.logger
logger.add("phone_apatch_log.log")

def open_oem():
    d = u2.connect()
    # 清除后台确保没干扰
    d.app_stop("com.android.settings")
    d.press("home")
    d.app_start("com.android.settings")
    # 翻到系统并点击
    find_click("系统",d)
    # 翻到开发人员选项
    find_click("开发者选项",d)

    oem_sw = get_switch_state("OEM 解锁",d)

    if oem_sw:
        state = oem_sw.info.get("checked")
        if state:
            logger.info("【OEM 解锁】--已开启")
        else:
            logger.warning("【OEM 解锁】--未开启，尝试开启中🛠️")
            oem_sw.click()
            android_click("启用",d)
            logger.info('【OEM 解锁】--已打开')

def android_click(shell,d):
    if d(text=shell).wait(timeout=3):
        d(text=shell).click()
    else:
        logger.error(f"未找到元素--【{shell}】")

def find_click(mytext,d):
    if not d(text=mytext).exists(timeout=3):
        d(scrollable=True).scroll.to(text=mytext)
    android_click(mytext,d)
    logger.info(f'找到并点击--【{mytext}】')

def get_switch_state(keyword,d):

    # 1. 滚动找到文本
    if not d(text=keyword).exists(timeout=2):
        try:
            d(scrollable=True).scroll.to(text=keyword)
        except:
            logger.error(f"未找到 {keyword}")
            return None

    # 2. 获取文本控件 bounds
    obj = d(text=keyword)
    if not obj.exists:
        logger.error(f"{keyword} 文本存在但无法访问")
        return None

    bounds = obj.info.get("bounds")
    if not bounds:
        logger.error("无法获取控件 bounds")
        return None

    top = bounds["top"]
    bottom = bounds["bottom"]

    # 获取所有switch控件，根据高度判断是否跟目标文本处在同一水平线
    switches = d(className="android.widget.Switch")
    for sw in switches:
        sw_bounds = sw.info.get("bounds", {})
        if not sw_bounds:
            continue

        y_center = (sw_bounds["top"] + sw_bounds["bottom"]) / 2

        # 判断是否在同一行
        if top <= y_center <= bottom:
            state = sw.info.get("checked")
            logger.info(f"{keyword} 开关状态: {state}")
            return sw

    logger.error(f"未找到 {keyword} 对应的 Switch 控件")
    return None

def adb_shell(cmd):
    full_cmd = f"tools\\adb.exe {cmd}"
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    logger.info(f'执行--【{full_cmd}】')
    return result.stdout


def click_ui(
        d,
        by: str,
        value: str,
        timeout: float = 10.0
):
    start = time.time()

    while time.time() - start < timeout:
        try:
            if by == "desc":
                obj = d(description=value)
            elif by == "text_contains":
                obj = d(textContains=value)
            elif by == "id":
                obj = d(resourceId=value)
            else:
                raise ValueError(f"未知定位方式: {by}")

            if obj.exists:
                obj.click()
                return True

        except Exception:
            pass

        time.sleep(0.3)

    raise TimeoutError(f"点击失败: {by}={value}")

def fastboot_shell(cmd):
    full_cmd = f"tools\\fastboot.exe {cmd}"
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    logger.info(f'执行--【{full_cmd}】')
    return result.stdout.strip()

def wait_for_fastboot(timeout=30):
    """等待手机进入 fastboot 模式"""
    print("等待手机进入 fastboot 模式...")
    for i in range(timeout):
        out = subprocess.run("tools\\fastboot.exe devices",capture_output=True)
        fast_stdout = out.stdout.decode().strip()
        if "fastboot" in fast_stdout:  # fastboot devices 有输出表示设备已连接
            logger.info(f'检测到设备--{fast_stdout}')
            return True
        time.sleep(1)
    logger.error("等待超时，没有检测到 fastboot 设备")
    return False

def wait_for_adb(timeout=30):
    """等待手机进入 fastboot 模式"""
    print("等待手机进入 adb 模式...")
    for i in range(timeout):
        out = subprocess.run("tools\\adb.exe devices",capture_output=True)
        fast_stdout = out.stdout.decode().strip()
        if "device" in fast_stdout:  # fastboot devices 有输出表示设备已连接
            logger.info(f'检测到设备--{fast_stdout}')
            return True
        time.sleep(1)
    logger.error("等待超时，没有检测到 adb 设备")
    return False

def adb_install(apk_name, timeout=60):
    """
    安装 apks 目录下的 APK，持续判断是否安装成功。

    :param apk_name: APK 文件名 e.g. "Apatch.apk"
    :param timeout: 等待安装成功的最大秒数
    :return: True / False
    """
    apk_path = os.path.join("apks", apk_name)

    if not os.path.exists(apk_path):
        logger.error(f"APK 不存在: {apk_path}")
        return False

    # 执行安装命令
    install_cmd = f"tools\\adb.exe install -r \"{apk_path}\""
    logger.info(f"开始安装 APK：{apk_name}")
    logger.info(f"执行命令：{install_cmd}")

    result = subprocess.run(
        install_cmd,
        shell=True,
        capture_output=True,
        text=True
    )

    # 打印 stdout / stderr（fastboot/adb 有时输出在 stderr）
    stdout = result.stdout.strip() if result.stdout else ""
    stderr = result.stderr.strip() if result.stderr else ""

    if stdout:
        logger.info(f"ADB install 输出：{stdout}")
    if stderr:
        logger.warning(f"ADB install 错误输出：{stderr}")

    # 初步判断是否成功
    if "Success" not in stdout and "Success" not in stderr:
        logger.warning("install 完成，但未返回 Success，开始通过包名验证……")
        return False
    return True

#解锁命令，先重启然后发送fastboot命令
def unlock():
    adb_shell('reboot bootloader')
    # fastboot发送解锁命令
    if wait_for_fastboot():
        fastboot_shell("flashing unlock")
        logger.info("发送解锁命令--等待解锁")
        print("----------------")
        logger.info("💡请调节[音量键]调至【Unlock the bootloader】然后按[电源键]解锁即可,会自动跳回【bootloader】模式，不要自己开机")
    print("----------------------")
    input("请解锁成功后自动跳回【bootloader】后输入任意按键继续...")
    print("----------------------")
    logger.info("尝试自动开机")
    fastboot_shell("reboot")
    print("-----------------------")
    print("❗解锁后需要重新开启开发者模式和usb调试")
    input("请【初始配置完并开启usb调试后】输入任意按键继续...")
    print("-----------------------")

def apatch_ios(secret):

    #安装apatch
    logger.info("⚓安装Apatch")
    print('开始安装')
    adb_install("apatch.apk")

    #将images.img文件push到用户目录
    logger.info("push img到用户下载目录")
    adb_shell("push iso\\boot.img ./sdcard/Download/")
    # adb_shell("push iso\\AlwaysTrustUserCerts_v1.3.zip ./sdcard/Download/")
    adb_shell("push iso\\MoveCertificate-v1.5.5.zip ./sdcard/Download/")


    build_self = adb_shell("shell getprop ro.build.display.id")
    logger.info(f"当前系统Build号为{build_self}")
    print(f"❗❗❗请确保当前image.iso为对应版本号的img，否则有变砖风险")
    #打开apatch
    d = u2.connect()
    d.app_start("me.bmax.apatch")
    logger.info("开启手动设置apatch密码，并修补iso")
    click_ui(d,'desc','安装')
    click_ui(d,'text_contains','选取要修补的')
    click_ui(d,'desc','显示根目录')
    time.sleep(2)
    d(resourceId="android:id/title",textContains="下载",className="android.widget.TextView").click()
    click_ui(d,'text_contains','boot.img')
    d(className="android.widget.EditText", index=2).set_text(secret)
    time.sleep(2)
    click_ui(d,'text_contains', '开始修补')

    #  20秒内判断是否修补成功
    end_time = time.time() + 20
    while time.time() < end_time:
        obj = d(
            className="android.widget.TextView",
            textContains='Successfully Patched'
        )
        if obj.exists:
            break
        else:
            time.sleep(0.5)



    logger.info("将修补后的iso拉取到本地")
    files = adb_shell("shell ls /sdcard/Download/").splitlines()
    # 找到以 apatch 开头的文件
    apatch_file = next((f for f in files if f.startswith("apatch")), None)

    adb_shell(f"pull ./sdcard/Download/{apatch_file} iso\\{apatch_file}")

    return apatch_file


def ios_repair(apatch_file):
    logger.info("重启到bootloader准备刷入修补后的iso")
    adb_shell("reboot bootloader")
    if wait_for_fastboot():
        full_cmd = f"tools\\fastboot.exe flash boot iso\\{apatch_file}"
        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
        logger.info(result.stderr.strip())
        if "Finished" in result.stderr:
            logger.info("🎉apatch刷入成功，正在重启...")
        time.sleep(1)
        fastboot_shell("reboot")

        print("----------------------")
        print("💡请进入apatch后手动激活，激活后在【系统模块】安装TrustUserCerts插件...")
        print("----------------------")
    else:
        logger.error("fastboot未检测出设备")


if __name__ == '__main__':

    print('----------------------')
    print('请仔细阅读工具使用说明，刷机有风险，若发生变砖情况概不负责！！！')
    print('----------------------')

    secret = 'zhuying666'
    print(secret)
    # # 确保打开oem，如果未打开自动开启
    # open_oem()
    # # 重启到bootloader发送解锁BL命令
    # unlock()
    # 自动安装apatch，手动操作修补完后继续自动pull修补后的文件到本地
    apatch_file = apatch_ios(secret)

    if apatch_file:
        # 自动重启到bootloader刷入修补后的文件，完成apatch内核刷入
        ios_repair(apatch_file)
