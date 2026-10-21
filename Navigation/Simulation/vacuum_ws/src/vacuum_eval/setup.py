from setuptools import find_packages, setup

package_name = 'vacuum_eval'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', ['config/eval_defaults.yaml', 'config/ddc_no_tf.yaml', 'config/worlds.yaml', 'config/worlds_scenarios.yaml']),
        ('share/' + package_name + '/launch', ['launch/eval_stack.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Vacuum Robot Team',
    maintainer_email='team@swachh-boudhik-yantra.local',
    description='Evaluation tooling for the Swachh Boudhik Yantra simulation',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'ground_truth_node = vacuum_eval.ground_truth_node:main',
            'odom_noise_node = vacuum_eval.odom_noise_node:main',
            'recorder_node = vacuum_eval.recorder_node:main',
            'run_episode = vacuum_eval.run_episode:main',
            'compute_metrics = vacuum_eval.compute_metrics:main',
            'run_batch = vacuum_eval.run_batch:main',
            'goal_sender = vacuum_eval.goal_sender:main',
            'responsiveness_test = vacuum_eval.responsiveness_test:main',
            'dynamic_mover = vacuum_eval.dynamic_mover:main',
        ],
    },
)
