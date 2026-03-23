import ansys.fluent.core as pyfluent

from ansys.fluent.core.launcher.launch_options import (
    Dimension,
    FluentLinuxGraphicsDriver,
    FluentMode,
    FluentWindowsGraphicsDriver,
    LaunchMode,
    Precision,
    UIMode,
    _get_fluent_launch_mode,
    _get_running_session_mode,
    get_remote_grpc_options,
    Solver,
)

# Fluent启动工作区
workspace = r"F:\pyFluent\workspace"

#fluent启动界面，2d双精度，4核，mode="solver"求解模式，show_gui=True同步显示fluent
solver = pyfluent.launch_fluent(dimension=Dimension.TWO, precision=Precision.DOUBLE,
                                processor_count=16, ui_mode=UIMode.GUI, 
                                mode=FluentMode.SOLVER, cleanup_on_exit=True,
                                py=False,
                                cwd=workspace)


ip = solver.connection_properties.ip # str
password = solver.connection_properties.password # str
port = solver.connection_properties.port # int
print(f"IP: {ip}, Port: {port}, Password: {password}")

# IP: localhost, Port: 49449, Password: ynasx230
# IP 往往是 localhost，端口号和密码需要记录，无法在fluent日志中看到
# 以便在后续的连接中使用，管理现有的会话，或者在其他脚本中连接到同一个会话继续操作

import_filename="D:\Workshop\Workbench\DPM\dpm-v1-1_files\dp0\FLU-4\Fluent\SYS-2-38.cas.h5"
#读入网格
# solver.file.read(file_type="case", file_name=import_filename)
# 打印 solver_connected 对象的属性和方法，确认连接正常

print("Solver Connected Object:", solver)
print("Type of Solver Connected:", type(solver))




import time
max = 5

print("Starting countdown...")

while (max > 0):
    print(f"Max: {max}")
    # 延迟1秒
    time.sleep(1)

    if max == 3:
        print("Exiting Fluent session...")
        solver.exit()  # 退出Fluent会话

    max -= 1