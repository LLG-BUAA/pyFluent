import ansys.fluent.core as pyfluent

from ansys.fluent.core import (
    session,
    fluent_connection,
)

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
)

# Connect to the session
solver_connected = pyfluent.connect_to_fluent(ip="localhost", password="yxy317t8", port=57957)
print(solver_connected.health_check.check_health())

write_case_filename="F:\pyFluent\output\SYS-2-38.cas.h5"
try:
    solver_connected.settings.file.write_case(file_name=write_case_filename)
except Exception as e:
    print(f"Error writing case file: {e}")

write_data_filename="F:\pyFluent\output\SYS-2-38.dat.h5"
try:
    solver_connected.settings.file.write_data(file_name=write_data_filename)
except Exception as e:
    print(f"Error writing data file: {e}")

# 打印 solver_connected 对象的属性和方法，确认连接正常
print("Solver Connected Object:", solver_connected)
print("Type of Solver Connected:", type(solver_connected))

solver_connected._fluent_connection.exit()