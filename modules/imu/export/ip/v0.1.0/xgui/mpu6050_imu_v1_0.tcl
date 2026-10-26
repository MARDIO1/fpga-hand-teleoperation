# Definitional proc to organize widgets for parameters.
proc init_gui { IPINST } {
  ipgui::add_param $IPINST -name "Component_Name"
  #Adding Page
  set Page_0 [ipgui::add_page $IPINST -name "Page 0"]
  ipgui::add_param $IPINST -name "CLK_HZ" -parent ${Page_0}
  ipgui::add_param $IPINST -name "DEVICE_ADDRESS" -parent ${Page_0}
  ipgui::add_param $IPINST -name "I2C_HZ" -parent ${Page_0}
  ipgui::add_param $IPINST -name "POLL_US" -parent ${Page_0}
  ipgui::add_param $IPINST -name "STARTUP_US" -parent ${Page_0}


}

proc update_PARAM_VALUE.CLK_HZ { PARAM_VALUE.CLK_HZ } {
	# Procedure called to update CLK_HZ when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CLK_HZ { PARAM_VALUE.CLK_HZ } {
	# Procedure called to validate CLK_HZ
	return true
}

proc update_PARAM_VALUE.DEVICE_ADDRESS { PARAM_VALUE.DEVICE_ADDRESS } {
	# Procedure called to update DEVICE_ADDRESS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.DEVICE_ADDRESS { PARAM_VALUE.DEVICE_ADDRESS } {
	# Procedure called to validate DEVICE_ADDRESS
	return true
}

proc update_PARAM_VALUE.I2C_HZ { PARAM_VALUE.I2C_HZ } {
	# Procedure called to update I2C_HZ when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.I2C_HZ { PARAM_VALUE.I2C_HZ } {
	# Procedure called to validate I2C_HZ
	return true
}

proc update_PARAM_VALUE.POLL_US { PARAM_VALUE.POLL_US } {
	# Procedure called to update POLL_US when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.POLL_US { PARAM_VALUE.POLL_US } {
	# Procedure called to validate POLL_US
	return true
}

proc update_PARAM_VALUE.STARTUP_US { PARAM_VALUE.STARTUP_US } {
	# Procedure called to update STARTUP_US when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.STARTUP_US { PARAM_VALUE.STARTUP_US } {
	# Procedure called to validate STARTUP_US
	return true
}


proc update_MODELPARAM_VALUE.CLK_HZ { MODELPARAM_VALUE.CLK_HZ PARAM_VALUE.CLK_HZ } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CLK_HZ}] ${MODELPARAM_VALUE.CLK_HZ}
}

proc update_MODELPARAM_VALUE.I2C_HZ { MODELPARAM_VALUE.I2C_HZ PARAM_VALUE.I2C_HZ } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.I2C_HZ}] ${MODELPARAM_VALUE.I2C_HZ}
}

proc update_MODELPARAM_VALUE.DEVICE_ADDRESS { MODELPARAM_VALUE.DEVICE_ADDRESS PARAM_VALUE.DEVICE_ADDRESS } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.DEVICE_ADDRESS}] ${MODELPARAM_VALUE.DEVICE_ADDRESS}
}

proc update_MODELPARAM_VALUE.STARTUP_US { MODELPARAM_VALUE.STARTUP_US PARAM_VALUE.STARTUP_US } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.STARTUP_US}] ${MODELPARAM_VALUE.STARTUP_US}
}

proc update_MODELPARAM_VALUE.POLL_US { MODELPARAM_VALUE.POLL_US PARAM_VALUE.POLL_US } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.POLL_US}] ${MODELPARAM_VALUE.POLL_US}
}
