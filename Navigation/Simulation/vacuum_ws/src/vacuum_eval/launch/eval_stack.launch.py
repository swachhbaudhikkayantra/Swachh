#!/usr/bin/env python3
"""eval_stack.launch.py - evaluation nodes (spec 02): recorder."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch_ros.actions import Node


def _start(context):
    extra = [m.strip() for m in context.launch_configurations.get('extra_models', '').split(',')
             if m.strip()]
    params = {'use_sim_time': True, 'run_dir': context.launch_configurations['run_dir']}
    if extra:
        params['extra_models'] = extra
    return [Node(package='vacuum_eval', executable='recorder_node', name='recorder_node',
                 output='screen', parameters=[params])]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('run_dir', default_value='/tmp/eval_run'),
        DeclareLaunchArgument('extra_models', default_value='',
                              description='comma-separated dynamic model names'),
        OpaqueFunction(function=_start),
    ])
