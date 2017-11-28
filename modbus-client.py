#!/usr/bin/env python

from time import sleep
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.mei_message import *
from pymodbus.exceptions import *
from ModbusSocketFramerHMAC import ModbusSocketFramerHMAC as ModbusFramer
#depuracion
import logging
logging.basicConfig()
log = logging.getLogger()
#log.setLevel(logging.DEBUG)

IP_SLAVE = "localhost"

COIL_PUERTA = 0
MAX_TEMP = 40
MIN_TEMP = 35

def cerrarPuerta(client):
    log.debug("Cerrando puerta")
    values = client.write_coil(COIL_PUERTA, False)
    if type(values) is ModbusIOException:
	raise Exception('Disconnected')
    return 0

def abrirPuerta(client):
    log.debug("Abriendo puerta")
    values = client.write_coil(COIL_PUERTA, True)
    if type(values) is ModbusIOException:
	raise Exception('Disconnected')
    return 0


def leerTemperatura(client):
    log.debug("Leyendo temperatura")
    values = client.read_holding_registers(address=0x00, count=2)
    if type(values) is ModbusIOException:
	raise Exception('Disconnected')
    temp, hum = values.registers
    return temp

def puertaAbierta(client):
    log.debug("Leyendo estado de la puerta")
    return client.read_coils(COIL_PUERTA).getBit(0)

def main():
    log.debug("Conectando al esclavo")
    client = ModbusTcpClient(IP_SLAVE, framer=ModbusFramer)

    connected = client.connect()
    while not connected:
        print "Connection failed"
        sleep(5)
        connected = client.connect()

    log.debug("Conexion establecidad, leyendo informacion del dispositivo")
    rq = ReadDeviceInformationRequest()
    rr = client.execute(rq)
    print "Conectado a dispositivo " + rr.information[0]


    while True:
        try:
            temp = leerTemperatura(client)
            estadoPuerta = puertaAbierta(client)
    
            print "Temperatura: " , temp, "Puerta abierta? ", estadoPuerta
            if temp > MAX_TEMP:
                abrirPuerta(client)
            if temp < MIN_TEMP:
                cerrarPuerta(client)
        except Exception as e:
            print "reconectando"
            client = ModbusTcpClient(IP_SLAVE)

        sleep(2)


if __name__ == "__main__":
     main()

