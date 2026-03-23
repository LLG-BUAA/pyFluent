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
solver_connected = pyfluent.connect_to_fluent(ip="localhost", password="9tududec", port=50650)
print(solver_connected.health_check.check_health())

import_filename="D:\Workshop\Workbench\DPM\dpm-v1-1_files\dp0\FLU-4\Fluent\SYS-2-38.cas.h5"
#读入网格
# solver_connected.settings.file.read(file_type="case", file_name=import_filename)

solver_connected.exit()