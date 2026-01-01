import subprocess
import time
import os

def test_exe():
    """测试exe文件是否能正常启动"""
    exe_path = r"F:\Github项目\FXdownloader\dist\FXdownloader.exe"
    
    if not os.path.exists(exe_path):
        print(f"EXE文件不存在: {exe_path}")
        return False
    
    try:
        print(f"启动exe文件: {exe_path}")
        process = subprocess.Popen([exe_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # 等待5秒钟
        time.sleep(5)
        
        # 检查进程是否还在运行
        if process.poll() is None:
            print("进程正在运行中，这可能是正常的")
            # 尝试终止进程
            process.terminate()
            process.wait(timeout=5)
            return True
        else:
            # 进程已退出，获取输出
            stdout, stderr = process.communicate()
            print(f"进程退出码: {process.returncode}")
            if stdout:
                print(f"标准输出:\n{stdout}")
            if stderr:
                print(f"错误输出:\n{stderr}")
            return process.returncode == 0
            
    except Exception as e:
        print(f"测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_exe()
    if success:
        print("测试通过")
    else:
        print("测试失败")