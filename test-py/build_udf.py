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

# Connect to the session
solver_connected = pyfluent.connect_to_fluent(ip="localhost", password="yk3b7ykz", port=56147)
print(solver_connected.health_check.check_health())

# 调用 udf-builder/udf_builder_line.py 中的函数，编译并加载UDF

solver_connected.settings.setup.user_defined.load(library_name = 'libudf')
solver_connected.settings.setup.user_defined.unload(library_name = 'libudf')