"""
Support for MQTT fans.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/fan.mqtt/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.components.mqtt as mqtt
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_STATE, STATE_ON, STATE_OFF,
    CONF_PAYLOAD_OFF, CONF_PAYLOAD_ON)
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.fan import (SPEED_LOW, SPEED_MEDIUM,
                                          SPEED_HIGH, FanEntity,
                                          SUPPORT_SET_SPEED, SUPPORT_OSCILLATE,
                                          SUPPORT_DIRECTION, SPEED_OFF,
                                          ATTR_SPEED, DIRECTION_FORWARD,
                                          DIRECTION_REVERSE)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_STATE_VALUE_TEMPLATE = 'state_value_template'
CONF_SPEED_STATE_TOPIC = 'speed_state_topic'
CONF_SPEED_COMMAND_TOPIC = 'speed_command_topic'
CONF_SPEED_VALUE_TEMPLATE = 'speed_value_template'
CONF_OSCILLATION_STATE_TOPIC = 'oscillation_state_topic'
CONF_OSCILLATION_COMMAND_TOPIC = 'oscillation_command_topic'
CONF_OSCILLATION_VALUE_TEMPLATE = 'oscillation_value_template'
CONF_PAYLOAD_OSCILLATION_ON = 'payload_oscillation_on'
CONF_PAYLOAD_OSCILLATION_OFF = 'payload_oscillation_off'
CONF_PAYLOAD_LOW_SPEED = 'payload_low_speed'
CONF_PAYLOAD_MEDIUM_SPEED = 'payload_medium_speed'
CONF_PAYLOAD_HIGH_SPEED = 'payload_high_speed'
CONF_SPEED_LIST = 'speeds'
CONF_DIRECTION_STATE_TOPIC = 'direction_state_topic'
CONF_DIRECTION_COMMAND_TOPIC = 'direction_command_topic'
CONF_DIRECTION_VALUE_TEMPLATE = 'direction_value_template'
CONF_PAYLOAD_FORWARD_DIRECTION = 'payload_forward_direction'
CONF_PAYLOAD_REVERSE_DIRECTION = 'payload_reverse_direction'

DEFAULT_NAME = 'MQTT Fan'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_OPTIMISTIC = False

OSCILLATE_ON_PAYLOAD = 'oscillate_on'
OSCILLATE_OFF_PAYLOAD = 'oscillate_off'

#OSCILLATION = 'oscillation'


PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_SPEED_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_SPEED_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_SPEED_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_OSCILLATION_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_OSCILLATION_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_OSCILLATION_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_DIRECTION_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_DIRECTION_COMMAND_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_DIRECTION_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_OSCILLATION_ON,
                 default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OSCILLATION_OFF,
                 default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_LOW_SPEED, default=SPEED_LOW): cv.string,
    vol.Optional(CONF_PAYLOAD_MEDIUM_SPEED, default=SPEED_MEDIUM): cv.string,
    vol.Optional(CONF_PAYLOAD_HIGH_SPEED, default=SPEED_HIGH): cv.string,
    vol.Optional(CONF_SPEED_LIST,
                 default=[SPEED_OFF, SPEED_LOW,
                          SPEED_MEDIUM, SPEED_HIGH]): cv.ensure_list,
    vol.Optional(CONF_PAYLOAD_FORWARD_DIRECTION,
                 default=DIRECTION_FORWARD): cv.string,
    vol.Optional(CONF_PAYLOAD_REVERSE_DIRECTION,
                 default=DIRECTION_REVERSE): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the MQTT fan platform."""
    async_add_devices([MqttFan(
        config.get(CONF_NAME),
        {
            key: config.get(key) for key in (
                CONF_STATE_TOPIC,
                CONF_COMMAND_TOPIC,
                CONF_SPEED_STATE_TOPIC,
                CONF_SPEED_COMMAND_TOPIC,
                CONF_OSCILLATION_STATE_TOPIC,
                CONF_OSCILLATION_COMMAND_TOPIC,
                CONF_DIRECTION_STATE_TOPIC,
                CONF_DIRECTION_COMMAND_TOPIC
            )
        },
        {
            CONF_STATE: config.get(CONF_STATE_VALUE_TEMPLATE),
            ATTR_SPEED: config.get(CONF_SPEED_VALUE_TEMPLATE),
            ATTR_OSCILLATION: config.get(CONF_OSCILLATION_VALUE_TEMPLATE),
            ATTR_DIRECTION: config.get(CONF_DIRECTION_VALUE_TEMPLATE)
        },
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        {
            STATE_ON: config.get(CONF_PAYLOAD_ON),
            STATE_OFF: config.get(CONF_PAYLOAD_OFF),
            OSCILLATE_ON_PAYLOAD: config.get(CONF_PAYLOAD_OSCILLATION_ON),
            OSCILLATE_OFF_PAYLOAD: config.get(CONF_PAYLOAD_OSCILLATION_OFF),
            SPEED_LOW: config.get(CONF_PAYLOAD_LOW_SPEED),
            SPEED_MEDIUM: config.get(CONF_PAYLOAD_MEDIUM_SPEED),
            SPEED_HIGH: config.get(CONF_PAYLOAD_HIGH_SPEED),
            DIRECTION_FORWARD: config.get(CONF_PAYLOAD_FORWARD_DIRECTION),
            DIRECTION_REVERSE: config.get(CONF_PAYLOAD_REVERSE_DIRECTION),
        },
        config.get(CONF_SPEED_LIST),
        config.get(CONF_OPTIMISTIC),
    )])


class MqttFan(FanEntity):
    """A MQTT fan component."""

    def __init__(self, name, topic, templates, qos, retain, payload,
                 speed_list, optimistic):
        """Initialize the MQTT fan."""
        self._name = name
        self._topic = topic
        self._qos = qos
        self._retain = retain
        self._payload = payload
        self._templates = templates
        self._speed_list = speed_list
        self._optimistic = optimistic or topic[CONF_STATE_TOPIC] is None
        self._optimistic_oscillation = (
            optimistic or topic[CONF_OSCILLATION_STATE_TOPIC] is None)
        self._optimistic_speed = (
            optimistic or topic[CONF_SPEED_STATE_TOPIC] is None)
        self._optimistic_dreiction = (
            optimistic or topic[CONF_DIRECTION_STATE_TOPIC] is None)
        self._state = False
        self._speed = None
        self._oscillation = None
        self._direction = None
        self._supported_features = 0
        self._supported_features |= (topic[CONF_OSCILLATION_STATE_TOPIC]
                                     is not None and SUPPORT_OSCILLATE)
        self._supported_features |= (topic[CONF_SPEED_STATE_TOPIC]
                                     is not None and SUPPORT_SET_SPEED)
        self._supported_features |= (topic[CONF_SPEED_DIRECTION_TOPIC]
                                     is not None and SUPPORT_DIRECTION)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe to MQTT events.

        This method is a coroutine.
        """
        templates = {}
        for key, tpl in list(self._templates.items()):
            if tpl is None:
                templates[key] = lambda value: value
            else:
                tpl.hass = self.hass
                templates[key] = tpl.async_render_with_possible_json_value

        @callback
        def state_received(topic, payload, qos):
            """Handle new received MQTT message."""
            payload = templates[CONF_STATE](payload)
            if payload == self._payload[STATE_ON]:
                self._state = True
            elif payload == self._payload[STATE_OFF]:
                self._state = False
            self.hass.async_add_job(self.async_update_ha_state())

        if self._topic[CONF_STATE_TOPIC] is not None:
            yield from mqtt.async_subscribe(
                self.hass, self._topic[CONF_STATE_TOPIC], state_received,
                self._qos)

        @callback
        def speed_received(topic, payload, qos):
            """Handle new received MQTT message for the speed."""
            payload = templates[ATTR_SPEED](payload)
            if payload == self._payload[SPEED_LOW]:
                self._speed = SPEED_LOW
            elif payload == self._payload[SPEED_MEDIUM]:
                self._speed = SPEED_MEDIUM
            elif payload == self._payload[SPEED_HIGH]:
                self._speed = SPEED_HIGH
            self.hass.async_add_job(self.async_update_ha_state())

        if self._topic[CONF_SPEED_STATE_TOPIC] is not None:
            yield from mqtt.async_subscribe(
                self.hass, self._topic[CONF_SPEED_STATE_TOPIC], speed_received,
                self._qos)
        self._speed = SPEED_OFF

        @callback
        def oscillation_received(topic, payload, qos):
            """Handle new received MQTT message for the oscillation."""
            payload = templates[ATTR_OSCILLATING](payload)
            if payload == self._payload[OSCILLATE_ON_PAYLOAD]:
                self._oscillation = True
            elif payload == self._payload[OSCILLATE_OFF_PAYLOAD]:
                self._oscillation = False
            self.hass.async_add_job(self.async_update_ha_state())

        if self._topic[CONF_OSCILLATION_STATE_TOPIC] is not None:
            yield from mqtt.async_subscribe(
                self.hass, self._topic[CONF_OSCILLATION_STATE_TOPIC],
                oscillation_received, self._qos)
        self._oscillation = False

        @callback
        def direction_received(topic, payload, qos):
            """Handle new received MQTT message for the direction."""
            payload = templates[ATTR_DIRECTION](payload)
            if payload == self._payload[DIRECTION_FORWARD]:
                self._direction = DIRECTION_FORWARD
            elif payload == self._payload[DIRECTION_REVERSE]:
                self._direction = DIRECTION_REVERSE
            self.hass.async_add_job(self.async_update_ha_state())

        if self._topic[CONF_DIRECTION_STATE_TOPIC] is not None:
            yield from mqtt.async_subscribe(
                self.hass, self._topic[CONF_DIRECTION_STATE_TOPIC],
                direction_received, self._qos)
        self._direction = DIRECTION_FORWARD

    @property
    def should_poll(self):
        """No polling needed for a MQTT fan."""
        return False

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def name(self) -> str:
        """Get entity name."""
        return self._name

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._speed_list

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def speed(self):
        """Return the current speed."""
        return self._speed

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillation

    @property
    def direction(self):
        """Return the direction state."""
        return self._direction

    @asyncio.coroutine
    def async_turn_on(self, speed: str=None) -> None:
        """Turn on the entity.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._topic[CONF_COMMAND_TOPIC],
            self._payload[STATE_ON], self._qos, self._retain)
        if speed:
            yield from self.async_set_speed(speed)

    @asyncio.coroutine
    def async_turn_off(self) -> None:
        """Turn off the entity.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._topic[CONF_COMMAND_TOPIC],
            self._payload[STATE_OFF], self._qos, self._retain)

    @asyncio.coroutine
    def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan.

        This method is a coroutine.
        """
        if self._topic[CONF_SPEED_COMMAND_TOPIC] is None:
            return

        if speed == SPEED_LOW:
            mqtt_payload = self._payload[SPEED_LOW]
        elif speed == SPEED_MEDIUM:
            mqtt_payload = self._payload[SPEED_MEDIUM]
        elif speed == SPEED_HIGH:
            mqtt_payload = self._payload[SPEED_HIGH]
        else:
            mqtt_payload = speed

        mqtt.async_publish(
            self.hass, self._topic[CONF_SPEED_COMMAND_TOPIC],
            mqtt_payload, self._qos, self._retain)

        if self._optimistic_speed:
            self._speed = speed
            self.hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation.

        This method is a coroutine.
        """
        if self._topic[CONF_OSCILLATION_COMMAND_TOPIC] is None:
            return

        if oscillating is False:
            payload = self._payload[OSCILLATE_OFF_PAYLOAD]
        else:
            payload = self._payload[OSCILLATE_ON_PAYLOAD]

        mqtt.async_publish(
            self.hass, self._topic[CONF_OSCILLATION_COMMAND_TOPIC],
            payload, self._qos, self._retain)

        if self._optimistic_oscillation:
            self._oscillation = oscillating
            self.hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_direction(self, direction: str) -> None:
        """Set direction.

        This method is a coroutine.
        """
        if self._topic[CONF_DIRECTION_COMMAND_TOPIC] is None:
            return

        if direction is DIRECTION_FORWARD:
            payload = self._payload[DIRECTION_FORWARD]
        elif direction is DIRECTION_REVERSE:
            payload = self._payload[DIRECTION_REVERSE]

        mqtt.async_publish(
            self.hass, self._topic[CONF_DIRECTION_COMMAND_TOPIC],
            payload, self._qos, self._retain)

        if self._optimistic_direction:
            self._direction = direction
            self.hass.async_add_job(self.async_update_ha_state())
