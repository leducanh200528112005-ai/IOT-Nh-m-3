import logging

import paho.mqtt.client as mqtt
from sqlalchemy.exc import SQLAlchemyError

from app.telemetry import save_telemetry

logger = logging.getLogger(__name__)


def create_client(settings, sessions):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=settings.mqtt_client_id)
    client.username_pw_set(settings.mqtt_username, settings.mqtt_password.get_secret_value())
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            logger.error("MQTT connection rejected: %s", reason_code)
            return
        client.subscribe("flood/+/telemetry", qos=1)
        logger.info("MQTT connected; telemetry subscription requested")

    def on_message(client, userdata, message):
        try:
            with sessions() as session:
                save_telemetry(session, message.topic, message.payload)
        except ValueError:
            logger.warning("Rejected telemetry on topic %s", message.topic)
        except SQLAlchemyError:
            logger.exception("Database write failed; MQTT ACK does not guarantee persistence")

    client.on_connect = on_connect
    client.on_message = on_message
    return client
