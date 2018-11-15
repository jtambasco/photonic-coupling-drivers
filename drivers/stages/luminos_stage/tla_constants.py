from .zaber import serial as zs
from collections import OrderedDict

_instruction_fields = (
        'Instruction Name',
        'Command #',
        'Command Data',
        'Command Type',
        'Reply Data'
    )
_instruction_fields_key = OrderedDict(zip(_instruction_fields, \
        range(len(_instruction_fields))))

commands = (
    ('Reset','0','Ignored','Command','None'),
    ('Home','1','Ignored','Command','Final position (in this case 0)'),
    ('Renumber','2','Ignored','Command','Device Id'),
    ('Move Tracking','8','n/a','Reply','Tracking Position'),
    ('Limit Active','9','n/a','Reply','Final Position'),
    ('Manual Move Tracking','10','n/a','Reply','Tracking Position'),
    ('Store Current Position','16','Address','Command','Address'),
    ('Return Stored Position','17','Address','Command','Stored Position'),
    ('Move To Stored Position','18','Address','Command','Final Position'),
    ('Move Absolute','20','Absolute Position','Command','Final Position'),
    ('Move Relative','21','Relative Position','Command','Final Position'),
    ('Move At Constant Speed','22','Speed','Command','Speed'),
    ('Stop','23','Ignored','Command','Final Position'),
    ('Read Or Write Memory','35','Data','Command','Data'),
    ('Restore Settings','36','Peripheral Id','Command','Peripheral Id'),
    ('Set Microstep Resolution','37','Microsteps','Setting','Microsteps'),
    ('Set Running Current','38','Value','Setting','Value'),
    ('Set Hold Current','39','Value','Setting','Value'),
    ('Set Device Mode','40','Mode','Setting','Mode'),
    ('Set Home Speed','41','Speed','Setting','Speed'),
    ('Set Target Speed','42','Speed','Setting','Speed'),
    ('Set Acceleration','43','Acceleration','Setting','Acceleration'),
    ('Set Maximum Position','44','Range','Setting','Range'),
    ('Set Current Position','45','New Position','Setting','New Position'),
    ('Set Maximum Relative Move','46','Range','Setting','Range'),
    ('Set Home Offset','47','Offset','Setting','Offset'),
    ('Set Alias Number','48','Alias Number','Setting','Alias Number'),
    ('Set Lock State','49','Lock Status','Command','Lock Status'),
    ('Return Device Id','50','Ignored','Read-Only Setting','Device Id'),
    ('Return Firmware Version','51','Ignored','Read-Only Setting','Version'),
    ('Return Power Supply Voltage','52','Ignored','Read-Only Setting','Voltage'),
    ('Return Setting','53','Setting Number','Command','Setting Value'),
    ('Return Status','54','Ignored','Read-Only Setting','Status'),
    ('Echo Data','55','Data','Command','Data'),
    ('Return Current Position','60','Ignored','Read-Only Setting','Position'),
    ('Error','255','n/a','Reply','Error Code')
)

def get_command_names():
    command_names = tuple(c[0] for c in commands)
    return command_names

def get_command_full(name):
    command_names = get_command_names()
    idx = command_names.index(name)
    return commands[idx]

def get_command_number(name):
    command_full = get_command_full(name)
    idx = _instruction_fields_key['Command #']
    return command_full[idx]

def get_command_data(name):
    command_full = get_command_full(name)
    idx = _instruction_fields_key['Command Data']
    return command_full[idx]

def get_command_type(name):
    command_full = get_command_full(name)
    idx = _instruction_fields_key['Command Type']
    return command_full[idx]

def get_reply_data(name):
    command_full = get_command_full(name)
    idx = _instruction_fields_key['Reply Data']
    return command_full[idx]

def binary_command(device_index, command_name, command_data=None):
    command_number = get_command_number(command_name)
    if command_data is None:
        cd = -1
        assert get_command_data(command_name) == 'Ignored', \
                'No data given for a command that requires data.'
    else:
        cd = command_data
    command = zs.BinaryCommand(device_index, int(command_number), int(cd))
    return command

def send_command(port, device_index, command_name, command_data=None):
    bc = binary_command(device_index, command_name, command_data)

    # Clear the buffer before sending command to avoid unexpected responses.
    bytes_in_buffer = port._ser.in_waiting
    if bytes_in_buffer:
        port._ser.read(bytes_in_buffer)

    port.write(bc)
