#!/usr/bin/env python3
# FIXED: ParameterValue wrapper — required in ROS2 Jazzy for XML parameters
# Without this, launch parses URDF XML as YAML and throws an error.
"""
sim.launch.py — MASTER simulation launch file (Stage 3)
────────────────────────────────────────────────────
Orchestrates the complete simulation stack in this order:

  1. robot_state_publisher  — reads URDF, publishes /robot_description + TF
  2. Gazebo Harmonic        — physics simulation (loads gz_ros2_control plugin)
  3. ros_gz_bridge          — /clock + camera topics (Stage 3)
  4. spawn_robot            — places the robot into Gazebo (delayed 3s)
  5. controllers            — spawns JSB + diff_drive_controller + camera diag
  6. RViz2 (optional)       — visualisation

Stage 3 changes:
  - D435i RGB-D camera sensor active (rgbd_camera plugin)
  - 5 camera topics bridged (image, depth, points, 2x camera_info)
  - camera_diagnostics_node started at t=10s

Launch arguments:
  use_sim_time       [true]           — all nodes use /clock from Gazebo
  use_rviz           [true]           — launch RViz2 alongside Gazebo
  world              [room]           — shorthand: room/apartment/office/corridor/
                                        empty_room/cluttered_room/two_rooms_door/
                                        multi_room_loop/maze_dead_ends/symmetric_hall
  headless           [false]         — gz server only (-r -s), no GUI
  world_file         [empty_world.sdf]— override with absolute SDF path
  spawn_x/y/yaw      [0.0]           — robot initial pose
  enable_odom_noise  [false]          — Gaussian noise on /odom_noisy
  enable_diagnostics [true]           — enable motion diagnostics node
  enable_camera_diagnostics [true]    — forwarded to controllers.launch.py
  render_gpu         [false]          — true = gz uses Mesa d3d12 (WSL2 GPU) via
                                        GALLIUM_DRIVER=d3d12 (gz process only)
  gpu_adapter        [Intel]          — MESA_D3D12_DEFAULT_ADAPTER_NAME (empty = unset)
                                        On native Linux GPUs (e.g. NVIDIA) leave
                                        render_gpu:=false; nothing is needed.

Usage:
  ros2 launch vacuum_bringup sim.launch.py
  ros2 launch vacuum_bringup sim.launch.py world:=apartment
  ros2 launch vacuum_bringup sim.launch.py world:=office use_rviz:=false
  ros2 launch vacuum_bringup sim.launch.py world_file:=/abs/path/custom.sdf
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    GroupAction,
    LogInfo,
    SetEnvironmentVariable,
    IncludeLaunchDescription,
    OpaqueFunction,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    Command,
    PythonExpression,
)
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.actions import Node


def generate_launch_description():

    # ── Package share directories ──────────────────────────────────
    pkg_description  = get_package_share_directory('vacuum_description')
    pkg_gazebo       = get_package_share_directory('vacuum_gazebo')
    pkg_bringup      = get_package_share_directory('vacuum_bringup')
    pkg_controller   = get_package_share_directory('vacuum_controller')
    pkg_ros_gz_sim   = get_package_share_directory('ros_gz_sim')

    # ── World file map (shorthand -> SDF path) ─────────────────────
    # Add new environments here; world_file arg overrides all.
    WORLD_MAP = {
        'room':      os.path.join(pkg_gazebo, 'worlds', 'empty_world.sdf'),
        'apartment': os.path.join(pkg_gazebo, 'worlds', 'apartment.sdf'),
        'office':    os.path.join(pkg_gazebo, 'worlds', 'office.sdf'),
        'corridor':  os.path.join(pkg_gazebo, 'worlds', 'corridor.sdf'),
        'empty_room': os.path.join(pkg_gazebo, 'worlds', 'empty_room.sdf'),
        'cluttered_room': os.path.join(pkg_gazebo, 'worlds', 'cluttered_room.sdf'),
        'two_rooms_door': os.path.join(pkg_gazebo, 'worlds', 'two_rooms_door.sdf'),
        'multi_room_loop': os.path.join(pkg_gazebo, 'worlds', 'multi_room_loop.sdf'),
        'maze_dead_ends': os.path.join(pkg_gazebo, 'worlds', 'maze_dead_ends.sdf'),
        'symmetric_hall': os.path.join(pkg_gazebo, 'worlds', 'symmetric_hall.sdf'),
    }

    # ── Default paths ──────────────────────────────────────────────
    default_rviz    = os.path.join(pkg_bringup, 'config', 'rviz_config.rviz')
    urdf_file       = os.path.join(pkg_description, 'urdf', 'vacuum.urdf.xacro')
    bridge_config   = os.path.join(pkg_gazebo,  'config', 'gz_bridge.yaml')
    controllers_launch = os.path.join(pkg_controller, 'launch', 'controllers.launch.py')

    # ── Launch arguments ───────────────────────────────────────────
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use Gazebo simulation clock for all ROS2 nodes')
    declare_use_rviz = DeclareLaunchArgument(
        'use_rviz', default_value='true',
        description='Launch RViz2 for visualisation')
    declare_world = DeclareLaunchArgument(
        'world', default_value='room',
        description='World shorthand: room | apartment | office | corridor | empty_room |'
                    ' cluttered_room | two_rooms_door | multi_room_loop | maze_dead_ends | symmetric_hall'
                    ' (ignored if world_file is set)')

    # Dynamic world path resolution based on 'world' argument
    world = LaunchConfiguration('world')
    dynamic_world_default = PythonExpression([
        "'", os.path.join(pkg_gazebo, 'worlds'), "/' + (",
        "'empty_world.sdf' if '", world, "' == 'room' else ",
        "'apartment.sdf' if '", world, "' == 'apartment' else ",
        "'office.sdf' if '", world, "' == 'office' else ",
        "'corridor.sdf' if '", world, "' == 'corridor' else ",
        "'empty_room.sdf' if '", world, "' == 'empty_room' else ",
        "'cluttered_room.sdf' if '", world, "' == 'cluttered_room' else ",
        "'two_rooms_door.sdf' if '", world, "' == 'two_rooms_door' else ",
        "'multi_room_loop.sdf' if '", world, "' == 'multi_room_loop' else ",
        "'maze_dead_ends.sdf' if '", world, "' == 'maze_dead_ends' else ",
        "'symmetric_hall.sdf' if '", world, "' == 'symmetric_hall' else ",
        "'empty_world.sdf')"
    ])

    declare_world_file = DeclareLaunchArgument(
        'world_file', default_value=dynamic_world_default,
        description='Absolute path to the Gazebo .sdf world file (overrides world:=)')
    declare_embed_robot = DeclareLaunchArgument(
        'embed_robot', default_value='true',
        description='true = put the robot in the world file at load (contact sensors work); false = spawn at runtime')
    declare_gz_verbose = DeclareLaunchArgument(
        'gz_verbose', default_value='',
        description="extra gz flag, e.g. '-v 4' to log sensor/system creation")
    declare_headless = DeclareLaunchArgument(
        'headless', default_value='false',
        description='true = gz server only: -r -s (no GUI)')
    declare_spawn_x = DeclareLaunchArgument(
        'spawn_x', default_value='0.0',
        description='Initial X position of the robot')
    declare_spawn_y = DeclareLaunchArgument(
        'spawn_y', default_value='0.0',
        description='Initial Y position of the robot')
    declare_spawn_yaw = DeclareLaunchArgument(
        'spawn_yaw', default_value='0.0',
        description='Initial yaw (heading) of the robot in radians')
    declare_enable_noise = DeclareLaunchArgument(
        'enable_odom_noise', default_value='false',
        description='Enable Gaussian noise on /odom_noisy')
    declare_odom_mode = DeclareLaunchArgument(
        'odom_mode', default_value='clean',
        description='clean | eval (eval = vacuum_eval/odom_noise_node in the odom path)')
    declare_odom_noise = DeclareLaunchArgument(
        'odom_noise', default_value='false',
        description='odom_mode:=eval only: inject drift noise')
    declare_odom_noise_seed = DeclareLaunchArgument(
        'odom_noise_seed', default_value='0')
    declare_extra_bridge = DeclareLaunchArgument(
        'extra_bridge_config', default_value='',
        description='Optional path to a second ros_gz_bridge config_file (e.g. gz_bridge_dynamic.yaml)')
    declare_enable_diagnostics = DeclareLaunchArgument(
        'enable_diagnostics', default_value='true',
        description='Enable motion diagnostics node')

    declare_enable_camera_diagnostics = DeclareLaunchArgument(
        'enable_camera_diagnostics', default_value='true',
        description='Forwarded to controllers.launch.py')
    declare_render_gpu = DeclareLaunchArgument(
        'render_gpu', default_value='false',
        description='true = WSL2 GPU rendering for gz (GALLIUM_DRIVER=d3d12)')
    declare_gpu_adapter = DeclareLaunchArgument(
        'gpu_adapter', default_value='Intel',
        description='MESA_D3D12_DEFAULT_ADAPTER_NAME when render_gpu:=true (empty = leave unset)')

    use_sim_time       = LaunchConfiguration('use_sim_time')
    use_rviz           = LaunchConfiguration('use_rviz')
    world_file         = LaunchConfiguration('world_file')
    spawn_x            = LaunchConfiguration('spawn_x')
    spawn_y            = LaunchConfiguration('spawn_y')
    spawn_yaw          = LaunchConfiguration('spawn_yaw')
    enable_odom_noise  = LaunchConfiguration('enable_odom_noise')
    enable_diagnostics = LaunchConfiguration('enable_diagnostics')

    # ── 1. Robot State Publisher ───────────────────────────────────
    # ParameterValue(value_type=str) is REQUIRED in Jazzy.
    # Without it, launch tries to parse the URDF XML as YAML and fails.
    robot_description_content = ParameterValue(
        Command(['xacro ', urdf_file]),
        value_type=str
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description_content,
            'use_sim_time': use_sim_time,
            'publish_frequency': 50.0,
        }],
    )

    # ── 2. Gazebo Harmonic ─────────────────────────────────────────
    # gz_ros2_control plugin starts automatically when Gazebo loads the URDF.
    # -r flag = run immediately (no pause on startup).
    # Wall/floor textures (relative albedo_map paths in the world files) are found via
    # the worlds directory on GZ_SIM_RESOURCE_PATH.
    texture_path = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        os.path.join(get_package_share_directory('vacuum_gazebo'), 'worlds'))

    # The robot can be baked into the world file at launch ('embed_robot:=true', default).
    # Reason: Gazebo's contact system only creates publishers for sensors on models that
    # exist when the world loads; a robot spawned at runtime never publishes contacts
    # (verified 2026-10-21 with a minimal SDF model). Embedding keeps everything else equal.
    def _launch_gazebo(context):
        import subprocess
        import tempfile
        import xml.etree.ElementTree as ET
        world_path = world_file.perform(context)
        gz_args_world = world_path
        embed = LaunchConfiguration('embed_robot').perform(context).lower() == 'true'
        if embed:
            # unique per-launch dir: no stale files, parallel launches are safe
            out_dir = tempfile.mkdtemp(prefix='vacuum_world_')
            urdf = subprocess.check_output(['xacro', urdf_file], text=True)
            urdf_path = os.path.join(out_dir, 'vacuum_robot.urdf')
            with open(urdf_path, 'w') as f:
                f.write(urdf)
            sdf_txt = subprocess.check_output(['gz', 'sdf', '-p', urdf_path], text=True)
            robot = ET.fromstring(sdf_txt).find('.//model')
            robot.set('name', 'vacuum_robot')
            for old_pose in robot.findall('pose'):
                robot.remove(old_pose)
            pose = ET.Element('pose')
            pose.text = '%s %s 0 0 0 %s' % (
                spawn_x.perform(context), spawn_y.perform(context), spawn_yaw.perform(context))
            robot.insert(0, pose)
            tree = ET.parse(world_path)
            tree.getroot().find('world').append(robot)
            # the baked world lives in /tmp: make relative texture paths absolute
            for tag in ('albedo_map', 'normal_map', 'roughness_map', 'metalness_map'):
                for el in tree.getroot().iter(tag):
                    if el.text and not os.path.isabs(el.text.strip()):
                        el.text = os.path.join(os.path.dirname(world_path), el.text.strip())
            gz_args_world = os.path.join(
                out_dir, os.path.splitext(os.path.basename(world_path))[0] + '_with_robot.sdf')
            tree.write(gz_args_world)
            log_msg = LogInfo(msg='Baked world written to ' + gz_args_world)
        headless_on = LaunchConfiguration('headless').perform(context).lower() == 'true'
        # VACUUM_GZ_HEADLESS_RENDERING=1: EGL headless rendering for the camera on machines
        # without a display (e.g. a GPU workstation over SSH). Off by default: it segfaults on WSL.
        if headless_on and os.environ.get('VACUUM_GZ_HEADLESS_RENDERING') == '1':
            headless_on_args = '-r -s --headless-rendering '
        else:
            headless_on_args = '-r -s '
        gz_args = (headless_on_args if headless_on else '-r ') + \
            LaunchConfiguration('gz_verbose').perform(context) + ' ' + gz_args_world
        gz_include = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')),
            launch_arguments={'gz_args': gz_args, 'on_exit_shutdown': 'true'}.items())
        render_gpu = LaunchConfiguration('render_gpu').perform(context).lower() == 'true'
        if render_gpu:
            adapter = LaunchConfiguration('gpu_adapter').perform(context)
            gpu_actions = [
                LogInfo(msg='render_gpu=true: gz uses GALLIUM_DRIVER=d3d12, adapter=%r'
                            % (adapter or '(default)')),
                SetEnvironmentVariable('GALLIUM_DRIVER', 'd3d12')]
            if adapter:
                gpu_actions.append(
                    SetEnvironmentVariable('MESA_D3D12_DEFAULT_ADAPTER_NAME', adapter))
            # scoped group: env vars apply to the gz process only
            actions = [GroupAction(gpu_actions + [gz_include], scoped=True)]
        else:
            actions = [LogInfo(msg='render_gpu=false: gz uses default Mesa renderer'),
                       gz_include]
        if embed:
            actions.insert(0, log_msg)
        return actions

    # rsp must be up before gz_ros2_control loads (it reads /robot_description), so when the
    # robot is embedded Gazebo starts a few seconds later.
    gazebo = TimerAction(period=3.0, actions=[OpaqueFunction(function=_launch_gazebo)])

    # ── 3. ROS-Gazebo Bridge (/clock only) ─────────────────────────
    # Stage 2: ros2_control publishes /odom, /tf, /joint_states natively.
    # Only /clock still requires bridging for use_sim_time synchronisation.
    ros_gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='ros_gz_bridge',
        parameters=[{'config_file': bridge_config}],
        output='screen',
    )

    # ── 3c. Optional second bridge (dynamic obstacle topics), only if a path is given
    extra_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='ros_gz_bridge_extra',
        parameters=[{'config_file': LaunchConfiguration('extra_bridge_config')}],
        output='screen',
        condition=IfCondition(PythonExpression(
            ["'", LaunchConfiguration('extra_bridge_config'), "' != ''"])),
    )

    # ── 4. Spawn robot (delayed 3s) ────────────────────────────────
    # 3-second delay allows Gazebo physics to fully initialise before spawn.
    # gz_ros2_control::GazeboSimROS2ControlPlugin starts when model spawns.
    spawn_robot = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='ros_gz_sim',
                executable='create',
                name='spawn_vacuum_robot',
                arguments=[
                    '-name',  'vacuum_robot',
                    '-topic', '/robot_description',
                    '-x',     spawn_x,
                    '-y',     spawn_y,
                    '-z',     '0.0',
                    '-Y',     spawn_yaw,
                ],
                output='screen',
                condition=IfCondition(PythonExpression(
                    ["'", LaunchConfiguration('embed_robot'), "'.lower() != 'true'"])),
            )
        ],
    )

    # ── 5. Controllers (from vacuum_controller package) ────────────
    # Controllers are spawned at 5s (JSB) and 6s (DDC) by the included launch.
    # This gives Gazebo + gz_ros2_control time to create /controller_manager.
    controllers = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(controllers_launch),
        launch_arguments={
            'use_sim_time':     use_sim_time,
            'enable_odom_noise': enable_odom_noise,
            'enable_diagnostics': enable_diagnostics,
            'enable_camera_diagnostics': LaunchConfiguration('enable_camera_diagnostics'),
            'odom_mode':         LaunchConfiguration('odom_mode'),
            'odom_noise':        LaunchConfiguration('odom_noise'),
            'odom_noise_seed':   LaunchConfiguration('odom_noise_seed'),
        }.items(),
    )

    # ── 6. RViz2 (conditional) ─────────────────────────────────────
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', default_rviz],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen',
        condition=IfCondition(use_rviz),
    )

    # ── 3b. Ground truth (evaluation): OdometryPublisher plugin in the URDF →
    # /ground_truth/odom_raw (gz_bridge.yaml) → ground_truth_node → /ground_truth/odom
    ground_truth_node = Node(
        package='vacuum_eval',
        executable='ground_truth_node',
        name='ground_truth_node',
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen',
    )

    return LaunchDescription([
        # Declare all arguments first
        declare_use_sim_time,
        declare_use_rviz,
        declare_world,
        declare_world_file,
        declare_headless,
        declare_gz_verbose,
        declare_embed_robot,
        declare_spawn_x,
        declare_spawn_y,
        declare_spawn_yaw,
        declare_enable_noise,
        declare_enable_diagnostics,
        declare_odom_mode,
        declare_odom_noise,
        declare_odom_noise_seed,
        declare_extra_bridge,
        declare_enable_camera_diagnostics,
        declare_render_gpu,
        declare_gpu_adapter,

        # Launch in dependency order
        texture_path,
        robot_state_publisher,  # must be before spawn (provides /robot_description)
        gazebo,
        extra_bridge,
        ros_gz_bridge,          # /clock + camera topics (Stage 3)
        ground_truth_node,      # /ground_truth/odom
        spawn_robot,            # delayed 3s — triggers gz_ros2_control init
        controllers,            # delayed internally (5s JSB, 6s DDC, 10s camera_diag)
        rviz,
    ])
