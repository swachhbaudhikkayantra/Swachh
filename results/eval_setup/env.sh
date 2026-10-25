# source this in every eval terminal
source /opt/ros/jazzy/setup.bash
source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml ROS_DOMAIN_ID=0
export VACUUM_GZ_HEADLESS_RENDERING=1      # no display on this SSH-only account
cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
post() { python3 -m vacuum_eval.compute_metrics "$1" && python3 -m vacuum_eval.diagnose "$1" --png "$1/diagnose.png"; }
