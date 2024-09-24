# -*- coding: utf-8 -*-

"""
Represents an API frame for communicating with RapidHA
"""

import os
import sys
import time
import struct
import threading
import select
import uuid
import logging

import serial
import xbee
from xbee.python2to3 import *
from xbee.backend.base import CommandFrameException
from xbee.thread.base import ThreadQuitException
from xbee.helpers.dispatch import Dispatch

from config import *

STAT_LOGGER = logging.getLogger('zigbee_logger')

class APIFrame(xbee.frame.APIFrame):
    """
    Represents a frame of data to be sent to or which was received from an RapidHA device
    """

    START_BYTE = b'\xF1'

    def __init__(self, data=b''):
        xbee.frame.APIFrame.__init__(self, data)

    def verify(self, chksum):
        total = 0

        # Add together all bytes
        for byte in self.data:
            total += byteToInt(byte)

        # Check result
        return chksum == struct.pack("<H", total)

    def output(self):
        return APIFrame.START_BYTE + self.data

    def __str__(self):
        return ''.join('{:02x}:'.format(ord(x)) for x in self.output())

    def remaining_bytes(self):
        remaining = 5

        if len(self.raw_data) >= 5:
            # Fifth byte is the length of the data
            raw_len = self.raw_data[4]
            data_len = struct.unpack("B", raw_len)[0]

            remaining += data_len

        # Don't forget the checksum
        remaining += 2

        return remaining - len(self.raw_data)

    def parse(self):
        """
        parse: None -> None

        Given a valid API frame, parse extracts the data contained
        inside it and verifies it against its checksum
        """
        if len(self.raw_data) < 7:
            ValueError("parse() may only be called on a frame containing at least 5 bytes of raw data (see fill())")

        # Fifth byte is the length of the data
        raw_len = self.raw_data[4]
        data_len = struct.unpack("B", raw_len)[0]

        # Read the data
        data = self.raw_data[1:5 + data_len]

        chksum = self.raw_data[-2:]

        # Checksum check
        self.data = data
        if not self.verify(chksum):
            raise ValueError("Invalid checksum")


class RapidHA(xbee.thread.base.XBeeBase):

    """
    Protocol interface for RapidHA threading and command parsing
    """

    CONFIGURATION_STATE_FACTORY_DEFAULT        = '\x00'
    CONFIGURATION_STATE_NEEDS_ENDPOINT_CONFIG  = '\x01'
    CONFIGURATION_STATE_CONFIGURED             = '\x02'

    RUNNING_STATE_STARTING    = '\x00'
    RUNNING_STATE_RUNNING     = '\x01'

    DEVICE_ID_ON_OFF_SWITCH             = '\x00\x00'
    DEVICE_ID_LEVEL_CONTROL_SWITCH      = '\x01\x00'
    DEVICE_ID_ON_OFF_OUTPUT             = '\x02\x00'
    DEVICE_ID_LEVEL_CONTROLLABLE_OUTPUT = '\x03\x00'
    DEVICE_ID_SCENE_SELECTOR            = '\x04\x00'
    DEVICE_ID_CONFIGURATION_TOOL        = '\x05\x00'
    DEVICE_ID_REMOTE_CONTROL            = '\x06\x00'
    DEVICE_ID_COMBINED_INTERFACE        = '\x07\x00'
    DEVICE_ID_RANGE_EXTENDER            = '\x08\x00'
    DEVICE_ID_MAINS_POWER_OUTLET        = '\x09\x00'

    HVAC_HEATING_COOLING_UNIT = '\x03\x00'
    HVAC_THERMOSTAT_DEVICE    = '\x03\x01'
    HVAC_TEMPERATURE_SENSOR   = '\x03\x02'
    HVAC_PUMP                 = '\x03\x03'
    HVAC_PUMP_CONTROLLER      = '\x03\x04'
    HVAC_PRESSURE_SENSOR      = '\x03\x05'
    HVAC_FLOW_SENSOR          = '\x03\x06'

    CLUSTER_ID_BASIC          = '\x00\x00'
    CLUSTER_ID_IDENTIFY       = '\x03\x00'
    CLUSTER_ID_GROUPS         = '\x04\x00'
    CLUSTER_ID_SCENES         = '\x05\x00'
    CLUSTER_ID_ON_OFF         = '\x06\x00'
    CLUSTER_ID_LEVEL_CONTROL  = '\x09\x00'
    CLUSTER_ID_TIME           = '\x0A\x00'

    CLUSTER_ID_OTA_UPGRADE    = '\x19\x00'
    CLUSTER_ID_DOOR_LOCK      = '\x01\x01'
    CLUSTER_ID_THERMOSTAT     = '\x01\x02'
    CLUSTER_ID_FAN_CONTROL    = '\x02\x02'
    CLUSTER_ID_THERMOSTAT_UI  = '\x04\x02'

    PROFILE_ID          = '\x04\x01'

    DEVICE_TYPE_FFD     = '\x00'
    DEVICE_TYPE_RFD     = '\x01'

    DEVICE_TYPE_NON_SLEEPY = '\x00'
    DEVICE_TYPE_SLEEPY     = '\x01'

    CLUSTER_TYPE_CLIENT = '\x00'
    CLUSTER_TYPE_SERVER = '\x01'

    FAN_MODE     = '\x00\x00'

    FANMODE_OFF   = '\x00'
    FANMODE_LOW   = '\x01'
    FANMODE_MED   = '\x02'
    FANMODE_HIGH  = '\x03'
    FANMODE_ON    = '\x04'
    FANMODE_AUTO  = '\x05'

    MODE_OFF      = '\x00'
    MODE_AUTO     = '\x01'
    MODE_COOL     = '\x03'
    MODE_HEAT     = '\x04'
    MODE_HEAT_EM  = '\x05'
    MODE_PRE_COOL = '\x06'
    MODE_FAN_ONLY = '\x07'
    MODE_DRY      = '\x08'
    MODE_SLEEP    = '\x09'

    LOCAL_TEMPERATURE              = '\x00\x00'
    ABS_MIN_HEAT_SET_POINT_LIMIT   = '\x03\x00'
    ABS_MAX_HEAT_SET_POINT_LIMIT   = '\x04\x00'
    ABS_MIN_COOL_SET_POINT_LIMIT   = '\x05\x00'
    ABS_MAX_COOL_SET_POINT_LIMIT   = '\x06\x00'
    HVAC_SYSTEM_TYPE_CONFIGURATION = '\x09\x00'
    LOCAL_TEMPERATURE_CALIBRATION  = '\x10\x00'
    OCCUPIED_COOLING_SET_POINT     = '\x11\x00'
    OCCUPIED_HEATING_SET_POINT     = '\x12\x00'
    MIN_HEAT_SET_POINT_LIMIT       = '\x15\x00'
    MAX_HEAT_SET_POINT_LIMIT       = '\x16\x00'
    MIN_COOL_SET_POINT_LIMIT       = '\x17\x00'
    MAX_COOL_SET_POINT_LIMIT       = '\x18\x00'
    MIN_SET_POINT_DEADBAND         = '\x19\x00'
    CONTROL_SEQUENCE_OF_OPERATION  = '\x1B\x00'
    SYSTEM_MODE                    = '\x1C\x00'
    THERMOSTAT_RUNNING_MODE        = '\x1E\x00'
    SET_POINT_HOLD                 = '\x23\x00'
    THERMOSTAT_RUNNING_STATE       = '\x29\x00'

    OPMODE_OFF =  2380
    OPMODE_HEAT = 2300
    OPMODE_COOL = 2390

    ATTRIB_TYPE_NULL     = '\x00'
    ATTRIB_TYPE_BOOL     = '\x10'
    ATTRIB_TYPE_ENUM8    = '\x30'
    ATTRIB_TYPE_ENUM16   = '\x31'

    ATTRIB_TYPE_DATA8    = '\x08'
    ATTRIB_TYPE_DATA16   = '\x09'
    ATTRIB_TYPE_DATA24   = '\x0A'
    ATTRIB_TYPE_DATA32   = '\x0B'
    ATTRIB_TYPE_DATA64   = '\x0F'

    ATTRIB_TYPE_BITMAP8  = '\x18'
    ATTRIB_TYPE_BITMAP16 = '\x19'
    ATTRIB_TYPE_BITMAP24 = '\x1A'
    ATTRIB_TYPE_BITMAP32 = '\x1B'
    ATTRIB_TYPE_BITMAP64 = '\x1F'

    ATTRIB_TYPE_UINT8   = '\x20'
    ATTRIB_TYPE_UINT16  = '\x21'
    ATTRIB_TYPE_UINT24  = '\x22'
    ATTRIB_TYPE_UINT32  = '\x23'
    ATTRIB_TYPE_UINT40  = '\x24'
    ATTRIB_TYPE_UINT48  = '\x25'
    ATTRIB_TYPE_UINT56  = '\x26'
    ATTRIB_TYPE_UINT64  = '\x27'

    ATTRIB_TYPE_INT8    = '\x28'
    ATTRIB_TYPE_INT16   = '\x29'
    ATTRIB_TYPE_INT24   = '\x2A'
    ATTRIB_TYPE_INT32   = '\x2B'
    ATTRIB_TYPE_INT40   = '\x2C'
    ATTRIB_TYPE_INT48   = '\x2D'
    ATTRIB_TYPE_INT56   = '\x2E'
    ATTRIB_TYPE_INT64   = '\x2F'

    api_commands = {

        "reset": [
            {'name': 'id',               'len': 2,   'default': '\x55\x00'},
        ],

        "module_info": [
            {'name': 'id',               'len': 2,   'default': '\x55\x03'},
        ],

        "bootloader_version": [
            {'name': 'id',               'len': 2,   'default': '\x55\x04'},
        ],

        "application_version_count": [
            {'name': 'id',               'len': 2,   'default': '\x55\x06'},
        ],

        "application_verion": [
            {'name': 'id',               'len': 2,   'default': '\x55\x08'},
            {'name': 'version',          'len': 1,   'default': '\x00'},
        ],

        "host_startup_ready": [
            {'name': 'id',               'len': 2,   'default': '\x55\x20'},
        ],

        "startup_sync": [
            {'name': 'id',              'len': 2,    'default': '\x55\x22'},
        ],

        "serial_ack": [
            {'name': 'id',              'len': 2,    'default': '\x55\x30'},
            {'name': 'on',              'len': 1,    'default': '\x01'},
        ],

        "get_serial_ack": [
            {'name': 'id',              'len': 2,    'default': '\x55\x31'},
        ],

        "device_type_write": [
            {'name': 'id',              'len': 2,    'default': '\x03\x00'},
            {'name': 'type',            'len': 1,    'default': None},
            {'name': 'sleepy',          'len': 1,    'default': None},
        ],

        "endpoint_list": [
            {'name': 'id',              'len': 2,    'default': '\x03\x11'},
        ],

        "clear_endpoint_config": [
            {'name': 'id',              'len': 2,    'default': '\x03\x30'},
        ],

        "add_endpoint": [
            {'name': 'id',              'len': 2,    'default': '\x03\x10'},
            {'name': 'endpoint',        'len': 1,    'default': None},
            {'name': 'profile_id',      'len': 2,    'default': None},
            {'name': 'device_id',       'len': 2,    'default': None},
            {'name': 'device_version',  'len': 1,    'default': None},
            {'name': 'server_clusters', 'len': 1,    'default': None},
            {'name': 'cluster_data',    'len': None, 'default': None},
        ],

        "add_attribute_to_cluster": [
            {'name': 'id',              'len': 2,    'default': '\x03\x20'},
            {'name': 'endpoint',        'len': 1,    'default': None},
            {'name': 'custer_id',       'len': 2,    'default': None},
            {'name': 'is_server',       'len': 1,    'default': None},
            {'name': 'attribute_count', 'len': 1,    'default': None},
            {'name': 'attributes',      'len': None, 'default': None},
        ],

        "restore_defaults": [
            {'name': 'id',               'len': 2,   'default': '\x55\x10'},
        ],

        "join_network": [
            {'name': 'id',               'len': 2,   'default': '\x01\x00'},
            {'name': 'channel_mask',     'len': 4,   'default': None       },
            {'name': 'auto_options',     'len': 1,   'default': None       },
            {'name': 'short_pan',        'len': 2,   'default': None       },
            {'name': 'expanded_pan',     'len': 8,   'default': None       },
        ],

        "form_network": [
            {'name': 'id',               'len': 2,   'default': '\x01\x01'},
            {'name': 'channel_mask',     'len': 4,   'default': None       },
            {'name': 'auto_options',     'len': 1,   'default': None       },
            {'name': 'short_pan',        'len': 2,   'default': None       },
            {'name': 'expanded_pan',     'len': 8,   'default': None       },
        ],

        "permit_join": [
            {'name': 'id',               'len': 2,   'default': '\x01\x03'},
            {'name': 'duration',         'len': 1,   'default': '\x3c'      },
        ],

        "leave_network": [
            {'name': 'id',               'len': 2,   'default': '\x01\x04'},
        ],

        "rejoin_network": [
            {'name': 'id',               'len': 2,   'default': '\x01\x05'},
        ],

        "network_status": [
            {'name': 'id',               'len': 2,   'default': '\x01\x08'},
        ],

        "network_auto_join": [
            {'name': 'id',               'len': 2,   'default': '\x01\x11'},
            {'name': 'scan_count',       'len': 1,   'default': None       },
            {'name': 'delay',            'len': 1,   'default': None       },
        ],

        "network_reset_auto_join": [
            {'name': 'id',               'len': 2,   'default': '\x01\x12'},
            {'name': 'scan_count',       'len': 1,   'default': None       },
            {'name': 'delay',            'len': 1,   'default': None       },
        ],

        "send_zcl_unicast": [
            {'name': 'id',               'len': 2,   'default': '\x05\x00'},
            {'name': 'dest_node',        'len': 2,   'default': None       },
            {'name': 'dest_endpoint',    'len': 2,   'default': None       },
            {'name': 'local_endpoint',   'len': 1,   'default': None       },
            {'name': 'cluster',          'len': 2,   'default': None       },
            {'name': 'response_options', 'len': 1,   'default': None       },
            {'name': 'encryption_level', 'len': 1,   'default': None       },
            {'name': 'frame_control',    'len': 1,   'default': None       },
            {'name': 'manufacturer_code','len': 2,   'default': None       },
            {'name': 'transaction_seq',  'len': 1,   'default': None       },
            {'name': 'command',          'len': 1,   'default': None       },
            {'name': 'payload_length',   'len': 1,   'default': None       },
            {'name': 'payload',          'len': None,'default': None       },
        ],

        "send_zcl_multicast": [
            {'name': 'id',               'len': 2,   'default': '\x05\x01'},
            {'name': 'dest_endpoint',    'len': 2,   'default': None       },
            {'name': 'local_endpoint',   'len': 1,   'default': None       },
            {'name': 'radius',           'len': 1,   'default': None       },
            {'name': 'non_member_radius','len': 1,   'default': None       },
            {'name': 'response_options', 'len': 1,   'default': None       },
            {'name': 'frame_control',    'len': 1,   'default': None       },
            {'name': 'manufacturer_code','len': 2,   'default': None       },
            {'name': 'transaction_seq',  'len': 1,   'default': None       },
            {'name': 'command',          'len': 1,   'default': None       },
            {'name': 'payload_length',   'len': 1,   'default': None       },
            {'name': 'payload',          'len': None,'default': None       },
        ],

        "send_zcl_broadcast": [
            {'name': 'id',               'len': 2,   'default': '\x05\x02'},
            {'name': 'broadcast_address','len': 1,   'default': None       },
            {'name': 'dest_endpoint',    'len': 2,   'default': None       },
            {'name': 'local_endpoint',   'len': 1,   'default': None       },
            {'name': 'cluster',          'len': 2,   'default': None       },
            {'name': 'response_options', 'len': 1,   'default': None       },
            {'name': 'frame_control',    'len': 1,   'default': None       },
            {'name': 'manufacturer_code','len': 2,   'default': None       },
            {'name': 'transaction_seq',  'len': 1,   'default': None       },
            {'name': 'command',          'len': 1,   'default': None       },
            {'name': 'payload_length',   'len': 1,   'default': None       },
            {'name': 'payload',          'len': None,'default': None       },
        ],

        "aps_zcl_ack": [
            {'name': 'id',               'len': 2,   'default': '\x05\x10'},
            {'name': 'status',           'len': 1,   'default': None       },
            {'name': 'transaction_seq',  'len': 1,   'default': None       },
        ],

        "read_zcl_attribute": [
            {'name': 'id',               'len': 2,   'default': '\x05\x30'},
            {'name': 'node',             'len': 2,   'default': None      },
            {'name': 'endpoint',         'len': 1,   'default': None      },
            {'name': 'cluster',          'len': 2,   'default': None      },
            {'name': 'is_server',        'len': 1,   'default': None      },
            {'name': 'attrib_count',     'len': 1,   'default': None      },
            {'name': 'attrib_ids',       'len': None,'default': None      },
        ],

        "write_zcl_attribute": [
            {'name': 'id',               'len': 2,   'default': '\x05\x32'},
            {'name': 'node',             'len': 2,   'default': None      },
            {'name': 'endpoint',         'len': 1,   'default': None      },
            {'name': 'cluster',          'len': 2,   'default': None      },
            {'name': 'is_server',        'len': 1,   'default': None      },
            {'name': 'attrib_count',     'len': 1,   'default': None      },
            {'name': 'attrib_value',     'len': None,'default': None      },
        ],

        "ota_image_notification": [
            {'name': 'id',               'len': 2,   'default': '\xB0\x00' },
            {'name': 'node',             'len': 2,   'default': None       },
            {'name': 'eui64',            'len': 8,   'default': None       },
            {'name': 'endpoint',         'len': 1,   'default': None       },
            {'name': 'payload_type',     'len': 1,   'default': None       },
            {'name': 'query_jitter',     'len': 1,   'default': '\x32'     },
            {'name': 'manufacturer_code','len': 2,   'default': None       },
            {'name': 'image_type',       'len': 2,   'default': '\x00\x00' },
            {'name': 'file_version',     'len': 4,   'default': None       },
        ],

        "ota_next_image_response": [
            {'name': 'id',               'len': 2,   'default': '\xB0\x02' },
            {'name': 'node',             'len': 2,   'default': None       },
            {'name': 'eui64',            'len': 8,   'default': None       },
            {'name': 'endpoint',         'len': 1,   'default': None       },
            {'name': 'status',           'len': 1,   'default': None       },
            {'name': 'manufacturer_code','len': 2,   'default': None       },
            {'name': 'image_type',       'len': 2,   'default': '\x00\x00' },
            {'name': 'file_version',     'len': 4,   'default': None       },
            {'name': 'image_size',       'len': 4,   'default': None       },
        ],

        "ota_image_block_success": [
            {'name': 'id',               'len': 2,   'default': '\xB0\x05' },
            {'name': 'node',             'len': 2,   'default': None       },
            {'name': 'eui64',            'len': 8,   'default': None       },
            {'name': 'endpoint',         'len': 1,   'default': None       },
            {'name': 'status',           'len': 1,   'default': '\x00'     },
            {'name': 'manufacturer_code','len': 2,   'default': None       },
            {'name': 'image_type',       'len': 2,   'default': '\x00\x00' },
            {'name': 'file_version',     'len': 4,   'default': None       },
            {'name': 'file_offset',      'len': 4,   'default': None       },
            {'name': 'data_size',        'len': 1,   'default': None       },
            {'name': 'data',             'len': None,'default': None       },
        ],

        "ota_image_block_wait": [
            {'name': 'id',               'len': 2,   'default': '\xB0\x05' },
            {'name': 'node',             'len': 2,   'default': None       },
            {'name': 'eui64',            'len': 8,   'default': None       },
            {'name': 'endpoint',         'len': 1,   'default': None       },
            {'name': 'status',           'len': 1,   'default': '\x97'     },
            {'name': 'time',             'len': 4,   'default': None       },
            {'name': 'request_time',     'len': 4,   'default': None       },
            {'name': 'checksum_lsb',     'len': 1,   'default': None       },
            {'name': 'checksum_msb',     'len': 1,   'default': None       },
        ],

        "ota_image_block_abort": [
            {'name': 'id',               'len': 2,   'default': '\xB0\x05' },
            {'name': 'node',             'len': 2,   'default': None       },
            {'name': 'eui64',            'len': 8,   'default': None       },
            {'name': 'endpoint',         'len': 1,   'default': None       },
            {'name': 'status',           'len': 1,   'default': '\x95'     },
        ],

        "ota_upgrade_end": [
            {'name': 'id',               'len': 2,   'default': '\xB0\x07' },
            {'name': 'node',             'len': 2,   'default': None       },
            {'name': 'eui64',            'len': 8,   'default': None       },
            {'name': 'endpoint',         'len': 1,   'default': None       },
            {'name': 'manufacturer_code','len': 2,   'default': None       },
            {'name': 'image_type',       'len': 2,   'default': '\x00\x00' },
            {'name': 'file_version',     'len': 4,   'default': None       },
            {'name': 'time',             'len': 4,   'default': None       },
            {'name': 'upgrade_time',     'len': 4,   'default': None       },
        ],
    }

    api_responses = {

        '\x55\x21': {
            'name': 'startup_sync',
            'structure': [
                {'name': 'running_state',         'len': 1},
                {'name': 'config_state',          'len': 1},
            ]
        },

        '\x55\x03': {
            'name': 'module_info_response',
            'structure': [
                {'name': 'major_firmware_version',         'len': 1},
                {'name': 'minor_firmware_version',         'len': 1},
                {'name': 'build_firmware_version',         'len': 1},
                {'name': 'application_information',        'len': 2},
                {'name': 'eui64',                          'len': 8},
                {'name': 'hardware_type',                  'len': 1},
                {'name': 'bootloader_type',                'len': 1},
            ]
        },

        '\x55\x05': {
            'name': 'bootloader_version_response',
            'structure': [
                {'name': 'ember_version',    'len': 4},
                {'name': 'mmb_version',      'len': 4},
            ]
        },

        '\x55\x07': {
            'name': 'application_version_count_response',
            'structure': [
                {'name': 'version_count',    'len': 1},
            ]
        },

        '\x55\x09': {
            'name': 'application_version_response',
            'structure': [
                {'name': 'version_count',    'len': 1},
                {'name': 'version_type',     'len': 1},
                {'name': 'version',          'len': None}
            ]
        },

        '\x55\x09': {
            'name': '',
            'structure': [
                {'name': 'version_count',    'len': 1},
                {'name': 'version_type',     'len': 1},
                {'name': 'version',          'len': None}
            ]
        },

        '\x55\x32': {
            'name': 'serial_ack_response',
            'structure': [
                {'name': 'serial_config',    'len': 1},
            ]
        },

        '\x55\x80': {
            'name': 'status_response',
            'structure': [
                {'name': 'status',    'len': 1},
            ]
        },
 
        '\x55\xE0': {
            'name': 'error',
            'structure': [
                {'name': 'error',    'len': 1},
                {'name': 'sub_error','len': 1},
            ]
        },
        
        '\x03\x12': {
            'name': 'endpoint_list_response',
            'structure': [
                {'name': 'endpoints',   'len': 1},
                {'name': 'data',        'len': None}, 
            ]
        },

        '\x01\x09': {
            'name': 'network_status_response',
            'structure': [
                {'name': 'network_status',   'len': 1},
                {'name': 'zigbee_device',    'len': 1},
                {'name': 'channel',          'len': 1},
                {'name': 'node',             'len': 2},
                {'name': 'short_pan',        'len': 2},
                {'name': 'extended_pan',     'len': 8},
                {'name': 'permit_join_time', 'len': 1},
            ]
        },

        '\x01\x10': {
            'name': 'network_device_trust_response',
            'structure': [
                {'name': 'node',   'len': 2},
                {'name': 'eui64',  'len': 8},
                {'name': 'event',  'len': 1},
                {'name': 'parent', 'len': 2},
            ]
        },

        '\x05\x03': {
            'name': 'send_zcl_unicast_response',
            'structure': [
                {'name': 'status',           'len': 1 },
                {'name': 'transaction_seq',  'len': 1 },
            ]
        },

        '\x05\x03': {
            'name': 'send_zcl_broadcast_response',
            'structure': [
                {'name': 'status',           'len': 1 },
                {'name': 'transaction_seq',  'len': 1 },
            ]
        },

        '\x05\x03': {
            'name': 'send_zcl_multicast_response',
            'structure': [
                {'name': 'status',           'len': 1 },
                {'name': 'transaction_seq',  'len': 1 },
            ]
        },

        '\x05\x31': {
            'name': 'read_zcl_attribute_response',
            'structure': [
                {'name': 'node',           'len': 2    },
                {'name': 'endpoint',       'len': 1    },
                {'name': 'cluster',        'len': 2    },
                {'name': 'is_server',      'len': 1    },
                {'name': 'attribute',      'len': 2    },
                {'name': 'zcl_status',     'len': 1    },
                {'name': 'attrib_type',    'len': 1    },
                {'name': 'attrib_value',   'len': None },
            ]
        },

        '\x05\x33': {
            'name': 'write_zcl_attribute_response',
            'structure': [
                {'name': 'node',           'len': 2    },
                {'name': 'endpoint',       'len': 1    },
                {'name': 'cluster',        'len': 2    },
                {'name': 'is_server',      'len': 1    },
                {'name': 'status',         'len': 1    },
                {'name': 'attrib_count',   'len': 1    },
                {'name': 'attrib_records', 'len': None },
            ]
        },

        '\xB0\x01': {
            'name': 'ota_query_next_image_request',
            'structure': [
                {'name': 'node',              'len': 2    },
                {'name': 'eui64',             'len': 8    },
                {'name': 'endpoint',          'len': 1    },
                {'name': 'field_control',     'len': 1    },
                {'name': 'manufacturer_code', 'len': 2    },
                {'name': 'image_type',        'len': 2    },
                {'name': 'file_version',      'len': 4    },
                {'name': 'hardware_version',  'len': None },
            ]
        },

        '\xB0\x03': {
            'name': 'ota_image_block_request',
            'structure': [
                {'name': 'node',              'len': 2    },
                {'name': 'eui64',             'len': 8    },
                {'name': 'endpoint',          'len': 1    },
                {'name': 'field_control',     'len': 1    },
                {'name': 'manufacturer_code', 'len': 2    },
                {'name': 'image_type',        'len': 2    },
                {'name': 'file_version',      'len': 4    },
                {'name': 'file_offset',       'len': 4    },
                {'name': 'max_data_size',     'len': 1    },
            ]
        },

        '\xB0\x06': {
            'name': 'ota_upgrade_end_request',
            'structure': [
                {'name': 'node',              'len': 2    },
                {'name': 'eui64',             'len': 8    },
                {'name': 'endpoint',          'len': 1    },
                {'name': 'status',            'len': 1    },
                {'name': 'manufacturer_code', 'len': 2    },
                {'name': 'image_type',        'len': 2    },
                {'name': 'file_version',      'len': 4    },
            ]
        },
    }

    def __init__(self, *args, **kwargs):
        """
        Constructor combining threading and command parsing
        """
        xbee.thread.base.XBeeBase.__init__(self, *args, **kwargs)
        self.frame_seq = 0

    def start_thread(self):
        if self._callback:
            self._thread_continue = True
            self._thread = threading.Thread(target=self.run, name=self.__class__.__name__)
            self._thread.start()

    @staticmethod
    def unpack_type(type, value):

        """
        Convert value strings to specified attribute data types
        """
        if type == RapidHA.ATTRIB_TYPE_UINT8 or type == RapidHA.ATTRIB_TYPE_BITMAP8 or type == RapidHA.ATTRIB_TYPE_DATA8 or type == RapidHA.ATTRIB_TYPE_ENUM8:
            return struct.unpack("B", value)[0]
        elif type == RapidHA.ATTRIB_TYPE_UINT16 or type == RapidHA.ATTRIB_TYPE_BITMAP16 or type == RapidHA.ATTRIB_TYPE_DATA16 or type == RapidHA.ATTRIB_TYPE_ENUM16:
            return struct.unpack("<H", value)[0]
        elif type == RapidHA.ATTRIB_TYPE_UINT32 or type == RapidHA.ATTRIB_TYPE_BITMAP32 or type == RapidHA.ATTRIB_TYPE_DATA32:
            return struct.unpack("<I", value)[0]
        elif type == RapidHA.ATTRIB_TYPE_UINT64 or type == RapidHA.ATTRIB_TYPE_BITMAP64 or type == RapidHA.ATTRIB_TYPE_DATA64:
            return struct.unpack("<Q", value)[0]
        elif type == RapidHA.ATTRIB_TYPE_INT8:
            return struct.unpack("b", value)[0]
        elif type == RapidHA.ATTRIB_TYPE_INT16:
            return struct.unpack("<h", value)[0]
        elif type == RapidHA.ATTRIB_TYPE_INT32:
            return struct.unpack("<i", value)[0]
        elif type == RapidHA.ATTRIB_TYPE_INT64:
            return struct.unpack("<q", value)[0]
        elif type == RapidHA.ATTRIB_TYPE_NULL:
            return None
        else:
            return value

    def _write(self, data):
        frame = APIFrame(data)
        self.serial.write(frame.output())

    def _wait_for_frame(self):
        frame = APIFrame()

        while True:
            if self._callback and not self._thread_continue:
                raise ThreadQuitException

            if self.serial.inWaiting() == 0:
                 time.sleep(.01)
                 continue

            byte = self.serial.read()

            if byte != APIFrame.START_BYTE:
                continue

            # Save all following bytes, if they are not empty
            if len(byte) == 1:
                frame.fill(byte)

            while(frame.remaining_bytes() > 0):
                byte = self.serial.read()
                if len(byte) == 1:
                    frame.fill(byte)
            try:
                # Try to parse and return result
                frame.parse()

                # Ignore empty frames
                if len(frame.data) == 0:
                    frame = APIFrame()
                    continue
                return frame

            except ValueError as err:
                # Bad frame, so restart
                frame = APIFrame()

    def _split_response(self, data):
        # Fetch the first two bytes, identify the packet
        # If the spec doesn't exist, raise exception
        packet_id = data[0:2]
        try:
            packet = self.api_responses[packet_id]
        except AttributeError:
            raise NotImplementedError("API response specifications could not "
                                      "be found; use a derived class which "
                                      "defines 'api_responses'.")
        except KeyError:
            # Check to see if this ID can be found among transmittable packets
            for cmd_name, cmd in list(self.api_commands.items()):
                if cmd[0]['default'] == data[0:2]:
                    raise CommandFrameException("Incoming frame with id {}{} "
                                                "looks like a command frame of "
                                                "type '{}' (these should not be"
                                                " received). Are you sure your "
                                                "devices are in "
                                                "API mode?".format(
                                                    data[0], data[1], cmd_name)
                                                )

            raise KeyError( "Unrecognized response packet with id bytes {}{}".format(data[0], data[1]))

        # Current byte index in the data stream
        index = 4

        # Result info
        info = {'id': packet['name'], 'frame_id': ord(data[2]) }
        packet_spec = packet['structure']

        # Parse the packet in the order specified
        for field in packet_spec:
            if field['len'] == 'null_terminated':
                field_data = b''

                while data[index:index+1] != b'\x00':
                    field_data += data[index:index+1]
                    index += 1

                index += 1
                info[field['name']] = field_data
            elif field['len'] is not None:
                # Store the number of bytes specified
                # Are we trying to read beyond the last data element?
                expected_len = index + field['len']
                if expected_len > len(data):
                    raise ValueError("Response packet was shorter than "
                                     "expected; expected: {}, got: {} "
                                     "bytes".format(expected_len, len(data))
                                     )

                field_data = data[index:index + field['len']]
                info[field['name']] = field_data

                index += field['len']
            # If the data field has no length specified, store any
            #  leftover bytes and quit
            else:
                field_data = data[index:]

                # Were there any remaining bytes?
                if field_data:
                    # If so, store them
                    info[field['name']] = field_data
                    index += len(field_data)
                break

        # If there are more bytes than expected, raise an exception
        if (index + 2) < len(data):
            raise ValueError("Response packet was longer than expected; "
                             "expected: {}, got: {} bytes {}".format(
                                 index, len(data), str(APIFrame(data)))
                             )

        # Apply parsing rules if any exist
        if 'parsing' in packet:
            for parse_rule in packet['parsing']:
                # Only apply a rule if it is relevant (raw data is available)
                if parse_rule[0] in info:
                    # Apply the parse function to the indicated field and
                    # replace the raw data with the result
                    info[parse_rule[0]] = parse_rule[1](self, info)

        return info

    def _build_command(self, cmd, **kwargs):
        try:
            cmd_spec = self.api_commands[cmd]
        except AttributeError:
            raise NotImplementedError("API command specifications could not be "
                                      "found; use a derived class which defines"
                                      " 'api_commands'.")
        packet = b''

        id_format = cmd_spec[0]

        try:
            if id_format['name'] != 'id':
                 raise NotImplementedError("First command parametere must be name key 'id'")
            command_id = id_format['default']
        except AttributeError:
            raise NotImplementedError("Missing id data command value")

        packet += command_id;

        payload = b''

        for field in cmd_spec[1:]:
            try:
                # Read this field's name from the function arguments dict
                data = kwargs[field['name']]
                if isinstance(data, str):
                    data = stringToBytes(data)

            except KeyError:
                # Data wasn't given
                # Only a problem if the field has a specific length
                if field['len'] is not None:
                    # Was a default value specified?
                    default_value = field['default']
                    if default_value:
                        # If so, use it
                        data = default_value
                    else:
                        # Otherwise, fail
                        raise KeyError(
                            "The expected field {} of length {} "
                            "was not provided".format(
                                field['name'], field['len']
                            )
                        )
                else:
                    # No specific length, ignore it
                    data = None

            # Ensure that the proper number of elements will be written
            if field['len'] and len(data) != field['len']:
                raise ValueError(
                    "The data provided for '{}' was not {} "
                    "bytes long".format(field['name'], field['len'])
                )

            # Add the data to the packet, if it has been specified.
            # Otherwise, the parameter was of variable length, and not given.
            if data:
                payload += data

        self.frame_seq = (self.frame_seq + 1) & 0xFF

        packet += intToByte(self.frame_seq)
        packet += intToByte( len(payload) & 0xFF )
        packet += payload

        checksum = 0
        for byte in packet:
            checksum += ord(byte)

        packet += intToByte( checksum & 0xFF )
        packet += intToByte( (checksum >> 8)  & 0xFF )

        return packet


class RapidHADevice(RapidHA):
    """
    Interface that communicates with the Zigbee MMBNetworks modules.
    """

    STATE_WAITING_STARTUP_SYNC       = 1
    STATE_STARTUP_RESET              = 2
    STATE_SERIAL_ACK                 = 3
    STATE_HOST_STARTUP_READY         = 4
    STATE_HOST_STARTUP_READY_ACK     = 5
    STATE_CONFIGURE_DEVICE_TYPE      = 6
    STATE_CLEAR_ENDPOINTS            = 7
    STATE_ADD_ENDPOINTS_AND_CLUSTERS = 8
    STATE_ADD_ATTRIBUTES             = 9
    STATE_ADD_ATTRIBUTES_ACK         = 10
    STATE_STARTUP_SYNC_COMPLETE      = 11
    STATE_NETWORK_DOWN               = 12
    STATE_NETWORK_UP                 = 13


    def __init__(self, *args, **kwargs):
        """
        Constructor. Initializes Serial interface and runs zigbee setup configuration.
        """
        self.serial = serial.Serial(*args, **kwargs)
        self.dispatch = Dispatch(xbee=self)
        RapidHA.__init__(self, self.serial)

        # Setup callback property post RapidHA constructor to stop thread from auto starting
        self._callback = self.dispatch.dispatch

        def log_error(error):
           STAT_LOGGER.error(str(error)) 

        self._error_callback = log_error

        # Synchronous interface
        self.sync = Synchronous(self)

        self.setup_configuration()

    def run(self):
        """
        Main routine receiving messages
        """
        self._thread_continue = True
        xbee.thread.base.XBeeBase.run(self)

    def setup_configuration(self):
        """
        Kicks off configuration of Zigbee device
        """
        self.config_state = RapidHADevice.STATE_WAITING_STARTUP_SYNC

        # Register default handler
        self.dispatch.register("startup", self.startup_handler, lambda packet: True )


    def halt(self):
        """
        Shutdown thread and serial port
        """
        if self._callback:
            self._thread_continue = False
        self.serial.close()

    def network(self):
        """
        Return if zigbee network is configured and up
        """
        return self.config_state == RapidHADevice.STATE_NETWORK_UP

    def startup_handler(self, name, packet):
        """
        Callback handler to complete device sync handshake.
        Step sequencially through states to configure Zigbee module parameters.
        """

        # Send sync complete message
        if self.config_state == RapidHADevice.STATE_WAITING_STARTUP_SYNC and packet['id'] == 'startup_sync':
            self.reset()
            self.config_state = RapidHADevice.STATE_SERIAL_ACK

        elif self.config_state == RapidHADevice.STATE_SERIAL_ACK and packet['id'] == 'startup_sync':
            self.serial_ack()
            self.config_state = RapidHADevice.STATE_HOST_STARTUP_READY

        elif self.config_state == RapidHADevice.STATE_HOST_STARTUP_READY and packet['frame_id'] == self.frame_seq:
            self.host_startup_ready()
            self.config_state = RapidHADevice.STATE_HOST_STARTUP_READY_ACK

        elif self.config_state == RapidHADevice.STATE_HOST_STARTUP_READY_ACK and packet['id'] == 'startup_sync':

            # If in startup mode 
            if packet['running_state'] == RapidHADevice.RUNNING_STATE_STARTING:

                # If device is already configured
                if packet['config_state'] == RapidHA.CONFIGURATION_STATE_CONFIGURED:
                    self.config_state = RapidHADevice.STATE_STARTUP_SYNC_COMPLETE
                    self.startup_sync()

                # Setup endpoints
                elif packet['config_state'] == RapidHA.CONFIGURATION_STATE_NEEDS_ENDPOINT_CONFIG:
                    self.config_state = RapidHADevice.STATE_CLEAR_ENDPOINTS
                    self.clear_endpoint_config()

                # Setup from factory defaults
                else:
                    self.device_type_write(type = RapidHA.DEVICE_TYPE_FFD, sleepy = RapidHA.DEVICE_TYPE_NON_SLEEPY )
                    self.config_state = RapidHADevice.STATE_CONFIGURE_DEVICE_TYPE
            else:
                self.config_state = RapidHADevice.STATE_STARTUP_SYNC_COMPLETE
                self.startup_sync()

        elif self.config_state == RapidHADevice.STATE_CONFIGURE_DEVICE_TYPE and packet['frame_id'] == self.frame_seq:
            self.config_state = RapidHADevice.STATE_CLEAR_ENDPOINTS
            self.clear_endpoint_config()

        elif self.config_state == RapidHADevice.STATE_CLEAR_ENDPOINTS and packet['frame_id'] == self.frame_seq:
            cluster = RapidHA.CLUSTER_ID_BASIC + RapidHA.CLUSTER_ID_IDENTIFY + RapidHA.CLUSTER_ID_OTA_UPGRADE + '\x03' + RapidHA.CLUSTER_ID_BASIC + RapidHA.CLUSTER_ID_IDENTIFY + RapidHA.CLUSTER_ID_THERMOSTAT

            self.add_endpoint(endpoint = '\x01', profile_id = RapidHA.PROFILE_ID,
            device_id = RapidHA.DEVICE_ID_COMBINED_INTERFACE, device_version = '\x01',
            server_clusters = '\x03', cluster_data = cluster )
            self.config_state = RapidHADevice.STATE_ADD_ATTRIBUTES

        elif self.config_state == RapidHADevice.STATE_ADD_ATTRIBUTES and packet['frame_id'] == self.frame_seq:

            attribs = '\x11\x00' + RapidHA.ATTRIB_TYPE_INT16 + '\x03'
            self.add_attribute_to_cluster(endpoint = '\x01', custer_id = RapidHA.CLUSTER_ID_THERMOSTAT,
                is_server = RapidHA.CLUSTER_TYPE_CLIENT, attribute_count = '\x01', attributes = attribs)

            self.config_state = RapidHADevice.STATE_ADD_ATTRIBUTES_ACK

        elif self.config_state == RapidHADevice.STATE_ADD_ATTRIBUTES_ACK and packet['id'] == 'status_response':
            self.startup_sync()
            self.config_state = RapidHADevice.STATE_STARTUP_SYNC_COMPLETE

        elif self.config_state == RapidHADevice.STATE_STARTUP_SYNC_COMPLETE and packet['id'] == 'network_status_response':

            self.network_state = packet

            # If network is down
            if packet['network_status'] == '\x00':

                # Channel masks 11 - 25
                channels = '\x00\xF8\xFF\x03' 
                self.form_network(channel_mask=channels, auto_options='\x03', short_pan='\x00\x00',
                    expanded_pan='\x00\x00\x00\x00\x00\x00\x00\x00')
                self.config_state = RapidHADevice.STATE_NETWORK_DOWN

            elif packet['network_status'] == '\x01':
                self.config_state = RapidHADevice.STATE_NETWORK_UP
                self.network_state = packet

        elif self.config_state == RapidHADevice.STATE_NETWORK_DOWN and packet['id'] == 'network_status_response':
            self.network_state = packet

            # Network status is up
            if packet['network_status'] == '\x01':
                self.config_state = RapidHADevice.STATE_NETWORK_UP
                self.network_state = packet
                self.unregister_dispatch('startup');

    def add_device(self, callback):
        """
        Opens a window to add a new device to Zigbee network.
        Will send message to callback when device is discovered.
        """
        self.unregister_dispatch('network_device_trust_response')

        self._timeout_timer = getattr(self, '_timeout_timer', None)
        if self._timeout_timer and self._timeout_timer.is_alive():
            self._timeout_timer.cancel()

        # Disable listening for event after 60 secs
        self._timeout_timer = threading.Timer(60, self.unregister_dispatch, ['network_device_trust_response'])
        self._timeout_timer.start()

        def complete(name, packet):
            self.unregister_dispatch('network_device_trust_response')
            callback(name, packet)

        self.dispatch.register('network_device_trust_response', complete, lambda packet: packet['id'] == 'network_device_trust_response' and packet['event'] != '\x03')
        self.permit_join()

    def leave_network_handler(self, callback):
        self.dispatch.register('leave_network', callback,
            lambda packet: packet['id'] == 'network_device_trust_response' and packet['event'] == '\x03')

    def unregister_dispatch(self, name):
        # Remove handler from dispatch
        for handler in (hdl for hdl in self.dispatch.handlers if hdl['name'] == name):
             self.dispatch.handlers.remove(handler)
        self.dispatch.names.discard(name)

    def reconfigure(self):
        """
        Restore device to factory defaults and reconfigure
        """
        self.dispatch.handlers = []
        self.dispatch.names = set()
        self.restore_defaults()
        self.setup_configuration()

class TimeoutError(Exception):
        pass

class Synchronous:
    """
    Synchronous wrapper for the threaded zigbee daemon. Enables calling of the zigbee methods
    with a direct return value. This eliminates having to worry about callbacks and threading.
    """
    def __init__(self, parent):
        self.parent = parent
        self.timeout = 5.0
        self.result = {}

    def __getattr__(self, name):
        """
        Returns wrapped methods for synchronous zigbee calls. Blocks and may raise TimeoutError exception.
        """

        method = getattr(self.parent, name)
        handler_id = str(uuid.uuid4())

        def handler(name, packet):
            self.parent.unregister_dispatch(handler_id)
            self.result[handler_id] = packet 

        def run_synchronous(*args, **kwargs):
            filter = kwargs.pop('filter')

            # Register handler 
            self.parent.dispatch.register(handler_id, handler, filter )

            # Make asychronous call
            method(*args, **kwargs)

            # Wait for response or timeout
            timer = 0.0
            while timer < self.timeout:

                if handler_id in self.result:
                    # Success. Return result.
                    return self.result.pop(handler_id)
                time.sleep(0.05)
                timer += 0.05

            raise TimeoutError('Operation timed out')

        return run_synchronous
