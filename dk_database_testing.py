#!/usr/bin/env python3

"""
Manual testing helpers for dk_database outputs
"""
from typing import Any

from sofia_utils.io import write_to_json_string
from sofia_utils.printing import print_sep
from wa_agents.basemodels import ServerTextMsg

from dk_database import DomainKnowledgeDataBase


MODEL   = "T40"
OPTIONS = { "list_messages"       : False,
            "get_joint_diagnosis" : False,
            "get_components"      : False,
            "debug"               : True }

messages = {}
messages["T40"] = {
    "gnss_trajectory" :                         0,
    "abnormal_vibration" :                      0,
    "arm_1_not_securely_fastened" :             0,
    "arm_2_not_securely_fastened" :             0,
    "arm_3_not_securely_fastened" :             0,
    "esc_1_disconnected" :                      0,
    "esc_5_disconnected" :                      0,
    "esc_7_throttle_backup" :                   0,
    "warning_no_liquid_payload" :               0,
    "flow_meter_disconnected" :                 0,
    "single_point_hall_sensor_disconnected" :   0,
    "centrifugal_nozzle_1_low_voltage" :        0,
    "centrifugal_nozzle_2_low_voltage" :        0,
    "pump_1_stuck" :                            0,
    "pump_2_stuck" :                            0,
    "pump_1_disconnected" :                     0,
    "pump_2_disconnected" :                     0,
    "error_radar_raster" :                      0
}
messages["T50"] = {
    "route_mode" :                              0,
    "abnormal_vibration" :                      0,
    "esc_1_connection" :                        0,
    "esc_5_connection" :                        0,
    "arm_4_motor_and_nozzle_esc_selfcheck" :    0,
    "warning_no_liquid_payload" :               0,
    "flow_meter_connection" :                   0,
    "sensor_liquid_level_connection" :          0,
    "centrifugal_nozzle_arm_3_low_voltage" :    0,
    "centrifugal_nozzle_arm_4_low_voltage" :    0,
    "pump_1_stuck" :                            0,
    "pump_2_stuck" :                            0,
    "pump_1_connection" :                       0,
    "pump_2_connection" :                       0,
    "error_radar_upward" :                      0
}
components = {}
components["T40"] = {
    "cable_spraying_signal" :                   0,
    "cable_spraying_adaptive" :                 0
}

if __name__ == "__main__" :
    
    dkdb  = DomainKnowledgeDataBase()
    dkdb.set_model(MODEL)
    dkdb.debug = OPTIONS["debug"]
    
    def show_result( label : str, error : bool, payload : Any) -> None :
        print_sep()
        print(label)
        if error :
            print(str(payload))
        else :
            print(write_to_json_string(payload))
        print_sep()
        return
    
    def demo_get_joint_diagnosis( message_codes : list[str]) -> None :
        
        label = "get_joint_diagnosis[" + ", ".join(message_codes) + "]"
        show_result( label, *dkdb.get_joint_diagnosis(message_codes))
        return
    
    def demo_get_components( component_codes : list[str]) -> None :
        show_result( f"get_components/{component_codes}",
                     *dkdb.get_components(component_codes))
        return
    
    if OPTIONS["list_messages"] :
        msg = ServerTextMsg( origin  = "dk_database_testing.py",
                             case_id = 42,
                             text    = dkdb.list_messages() )
        msg.print()
    
    if OPTIONS["get_joint_diagnosis"] :
        messages = [ key for key, val in messages[MODEL].items() if bool(val) ]
        demo_get_joint_diagnosis(messages)
    
    if OPTIONS["get_components"] :
        components = [ key for key, val in components[MODEL].items() if bool(val) ]
        demo_get_components(components)
