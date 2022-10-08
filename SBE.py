""" Libreria especifica para la comunicacion RS232 con intrumental de SBE.

    Actualmente en la V 1.1 incorpora los siguientes modelos:

        SBE38 --- Termometro digital
        SBE45 --- Termosalinografo

        SBE45 Interface Box

"""

import os, sys, time
import serial
import logging, logging.handlers
from threading import Thread, Lock
import re

class SBE():
    """
    Comunicacion por comandos con los instrumentos de SBE
    """

    __autor__ = 'Alvaro Cubiella'
    __version__ = 'V0.1'

    def __init__(self, Model = 'SBE45', port = 1, BR = 9600, bytesize= serial.EIGHTBITS, parity = 'N', stopbits = serial.STOPBITS_ONE,  timeout = 2):
        self.__Model = Model
        self.__port = port
        self.__BR = BR
        self.__bytesize = bytesize
        self.__parity = parity
        self.__stopbits = stopbits
        self.__timeout = timeout
        self.buffer = b''
        self.isOpen = False
        self.listening = 0

    def open_device(self):
        # Abro puerto serial
        try:
            self.__device = serial.Serial(port = self.__port, baudrate = self.__BR, bytesize = 8, parity = 'N', stopbits = 1, timeout=2)
            self.isOpen = True
        except IOError:
            print('error al iniciar el %s' %(self.__port))
            raise IOError
        except TimeoutError:
            print('Error Time out puerto')
            raise TimeoutError

    def close_device(self):
        # Cierro puerto serial
        try:
            self.__device.close()
            self.isOpen = False
        except IOError:
            pass

    def clear_buffer(self):
        self.buffer = b''
        time.sleep(0.001)

    def wakeup(self):
        if not self.isOpen:
            self.open_device()
        # Envio un \n para despertar al equipo
        self.clear_buffer()
        self.__device.write(b'\r')
        time.sleep(0.5)
        self.__waitfor(b'>', 2)

    def __waitfor(self, s=None, timeout=2, quiet=0):
        self.listening = 1
        while self.listening:
            self.buffer = self.buffer + self.__device.read(1)
            ind = self.buffer.rfind(s)
            if ind != -1:
                self.listening = 0


    def send_commands(self, commands, timeout = 2, wait = True):
        if not self.isOpen:
            self.open_device()
        time.sleep(1)
        for cmd in commands:
            self.__device.reset_input_buffer()
            self.clear_buffer()
            self.__device.write(cmd.rstrip().encode('ascii', 'ignore') + b'\r\n')
            self.__device.flush()
            #Normalmente usado para los comandos que devuelven el prompt
            if wait:
                self.__waitfor(b'>', 5)
        self.close_device()

class SBE45 (SBE):

    """ Clase que permine manejar la comunicacion con un Termosalinografo modelo SBE45.
    """
    def __init__(self, Model = 'SBE45', port = 'COM1', BR = 9600, bytesize= 8, parity = 'N', stopbits = 1,  timeout = 2):

        # Llamo al constructor SBE
        SBE.__init__(self, Model, port, BR, bytesize, parity, stopbits, timeout)

        self.__Config = { 'AutoRun':None,
                        'xmlcon':None,
                        'Intervalo':None,
                        'Logging':None,
                        'SN':None,
                        'Variables': None,
                        'Modelo': None,
                        'Formato':None
                        }

    def readStatus(self):
        """ Obtiene los parametros de configuracion del instrumento.

        - ['SN']: Numero de serie
        - ['AutoRun']: Numero de serie del instrumento (type <str>)
        - ['Intervalo']: Intervalo de muestreo en segundos (type<str>)
        - ['Logging']: Estado de adquisicion del instrumento (type<bool>)
        - ['Modelo']: Modelo del instrumento (type<str>)
        - ['Variables']: Diccionario con los estados de las variables del TSG:
            - ['Conductividad']: Activado/Desactivado (typo<bool>)
            - ['Salinidad']:     Activado/Desactivado (typo<bool>)
            - ['SV']:            Activado/Desactivado (typo<bool>)

        Para ver los parametros realizar las consultar por medio de las funciones correspondientes:
            SN:         getSerialNumber
            AutoRun:    getAutoRunMode
            Intervalo:  getInterval
            Logging:    getLogging
            Modelo:     getModelo

        """
        self.send_commands(['DS'])
        status = self.buffer.decode('ASCII').splitlines()
        Cond_enable = True
        Sal_enable = True
        SV_enable = True
        autorun_enable = True
        for linea in status:
            try:
                patron = re.compile(r'(?P<Modelo>\w{1,3}\d{1,2}) V (?P<Firmware>\d{1,2}[\.]\d{1,2}\w{1,1})[\|\ ] SERIAL NO. (?P<SN>\d{1,4})')
                if not(re.search(patron, linea.rstrip()) is None):
                    info = re.search(patron, linea)
                    continue
                if 'not logging' in linea:
                    log_data = False
                    continue
                patron = re.compile(r'sample interval = (?P<intervalo>\d{1,3}) seconds')
                if not(re.search(patron, linea.rstrip()) is None):
                    intervalo = re.search(patron, linea)['intervalo']
                    continue
                if not(('do not' in linea) and ('conductivity' in linea)):
                    Cond_enable = False
                    continue
                if not(('do not' in linea) and ('salinity' in linea)):
                    Sal_enable = False
                    continue
                if not(('do not' in linea) and ('sound' in linea)):
                    SV_enable = False
                    continue
                if not(('do not' in linea) and ('sampling' in linea)):
                    autorun_enable = False
                    continue
            except:
                pass
        #Establece el formato de la cadena segun las variables configuradas.

        #Defino el Formato1
        self.__Config['Formato']

        self.__Config['SN'] = info.groupdict()['SN']
        self.__Config['Firmware'] = info.groupdict()['Firmware']
        self.__Config['Modelo'] = info.groupdict()['Modelo']
        self.__Config['Logging'] = log_data
        self.__Config['Intervalo'] = intervalo
        self.__Config['AutoRun'] = autorun_enable
        self.__Config['Variables'] = {'Conductividad':Cond_enable,
                                    'Salinidad':Sal_enable,
                                    'SV': SV_enable}

    def readCoeficient(self):
        self.send_commands(['DC'])
        coefficients = self.buffer.decode('ASCII').splitlines()
        for linea in coefficients:
            linea = linea.rstrip().lstrip()
            try:
                patron = re.compile(r'(?P<Modelo>\w{1,3}\d{1,2}) V (?P<Firmware>\d{1,2}[\.]\d{1,2}\w{1,1})\s{1,4}(?P<SN>\d{1,4})')
                if not(re.search(patron, linea.rstrip()) is None):
                    info = re.search(patron, linea)
                    continue
                patron = re.compile(r'temperature:\s{1,2}(?P<fecha>\d{1,2}[\-]\w{1,3}[\-|+]\d{1,4})')
                if not(re.search(patron, linea.rstrip()) is None):
                    Temp_fecha = re.search(patron, linea)
                    continue
                patron = re.compile(r'TA0 = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-|+]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    TA0 = re.search(patron, linea)
                    continue
                patron = re.compile(r'TA1 = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-|+]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    TA1 = re.search(patron, linea)
                    continue
                patron = re.compile(r'TA2 = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-|+]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    TA2 = re.search(patron, linea)
                    continue
                patron = re.compile(r'TA3 = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-|+]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    TA3 = re.search(patron, linea)
                    continue
                patron = re.compile(r'conductivity:\s{1,2}(?P<fecha>\d{1,2}[\-]\w{1,3}[\-|+]\d{1,4})')
                if not(re.search(patron, linea.rstrip()) is None):
                    Cond_fecha = re.search(patron, linea)
                    continue
                patron = re.compile(r'G = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-|+]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    G = re.search(patron, linea)
                    continue
                patron = re.compile(r'H = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-|+]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    H = re.search(patron, linea)
                    continue
                patron = re.compile(r'I = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-|+]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    I = re.search(patron, linea)
                    continue
                patron = re.compile(r'J = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-|+]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    J = re.search(patron, linea)
                    continue
                patron = re.compile(r'CPCOR = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-|+]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    CPCOR = re.search(patron, linea)
                    continue
                patron = re.compile(r'CTCOR = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-|+]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    CTCOR = re.search(patron, linea)
                    continue
                patron = re.compile(r'WBOTC = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-|+]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    WBOTC = re.search(patron, linea)
                    continue
            except:
                pass
        self.__Config['xmlcon'] = {'Temp':{   'Fecha': Temp_fecha.groupdict()['fecha'],
                                            'TA0':TA0.groupdict()['value'],
                                            'TA1':TA1.groupdict()['value'],
                                            'TA2':TA2.groupdict()['value'],
                                            'TA3':TA3.groupdict()['value']
                                        },
                                'Cond':{'Fecha': Cond_fecha.groupdict()['fecha'],
                                            'G':G.groupdict()['value'],
                                            'H':H.groupdict()['value'],
                                            'I':I.groupdict()['value'],
                                            'J':J.groupdict()['value'],
                                            'CPCOR':CPCOR.groupdict()['value'],
                                            'CTCOR':CTCOR.groupdict()['value'],
                                            'WBOTC':WBOTC.groupdict()['value']
                                        },
                                'info':{    'S/N': info.groupdict()['SN']
                                        }
                        }

    def setOutputFormat(self, value = 0):
        self.send_commands(['OutputFormat=%s'%(value)])

    def setInterval(self, interval = 3):
        self.send_commands(['Interval=%s'%(interval)])
        self.__Config['Intervalo'] = str(interval)

    def setConductividad(self, status=True):
        """
        """
        if status:
            self.send_commands(['OutputCond=Y'])
            self.__Config['Conductividad'] = True
        else:
            self.send_commands(['OutputCond=N'])
            self.__Config['Conductividad'] = False

    def setSalinidad(self, status=True):
        if status:
            self.send_commands(['OutputSal=Y'])
            self.__Config['Salinidad'] = True
        else:
            self.send_commands(['OutputSal=N'])
            self.__Config['Salinidad'] = False

    def setVelocidadSonido(self, status=False):
        if status:
            self.send_commands(['OutputSV=Y'])
            self.__Config['Sound'] = True
        else:
            self.send_commands(['OutputSV=N'])
            self.__Config['Sound'] = False

    def setAutoRun(self, status = True):
        if status:
            self.send_commands(['AutoRun=Y'])
            self.__Config['AutoRun'] = True
        else:
            self.send_commands(['AutoRun=N'])
            self.__Config['AutoRun'] = False

    def setStart(self):
        self.send_commands(['Start'], wait=False)
        time.sleep(0.1)
        self.__Config['Logging'] = True

    def setStop(self):
        self.send_commands(['Stop'])
        self.__Config['Logging'] = False

    #@property
    def getModelo(self):
        return self.__Config['Modelo']

    def getFirmware(self):
        return self.__Config['Firmware']

    def getLogging(self):
        return self.__Config['Logging']

    def getAutoRun(self):
        return self.__Config['AutoRun']

    def getCoefficients(self):
        return self.__Config['xmlcon']

    def getInterval(self):
        return self.__Config['Intervalo']

    def getSerialNumber(self):
        return self.__Config['SN']

    def getStatusConductivity(self):
        return self.__Config['Variables']['Conductividad']

    def getStatusSalinity(self):
        return self.__Config['Variables']['Salinidad']

    def getStatusSV(self):
        return self.__Config['Variables']['SV']


class SBE38 (SBE):

    def __init__(self, Model = 'SBE38', port = 'COM1', BR = 9600, bytesize= 8, parity = 'N', stopbits = 1,  timeout = 2):

        # Llamo al constructor SBE
        SBE.__init__(self, Model, port, BR, bytesize, parity, stopbits, timeout)

        self.__Config = { 'AutoRun':None,
                        'xmlcon':None,
                        'Intervalo':None,
                        'Logging':None,
                        'SN':None,
                        'Modelo': None,
                        'Digitos': None,
                        }

    def readStatus(self):
        self.send_commands(['DS'])
        status = self.buffer.decode('ASCII').splitlines()
        log_data = True
        autorun_enable = True
        for linea in status:
            try:
               patron = re.compile(r'(?P<Modelo>\w{1,3}\s{0,1}\d{1,2}) V (?P<Firmware>\d{1,2}[\.]\d{1,2}\w{0,1})\s{1,6}S/N = (?P<SN>\d{1,6})')
               if not(re.search(patron, linea.rstrip()) is None):
                    info = re.search(patron, linea)
                    continue
               patron = re.compile(r'navg = (?P<navg>\d{1,3})')
               if not(re.search(patron, linea.rstrip()) is None):
                    nAvg = re.search(patron, linea)
                    continue
               if 'not sampling' in linea:
                    log_data = False
                    continue
               if not(('do not' in linea) and ('sampling' in linea)):
                    autorun_enable = False
                    continue
            except:
                pass
        self.__Config['SN'] = info.groupdict()['SN']
        self.__Config['Firmware'] = info.groupdict()['Firmware']
        self.__Config['Modelo'] = info.groupdict()['Modelo']
        self.__Config['Logging'] = log_data
        self.__Config['n_avg'] = nAvg.groupdict()['navg']
        self.__Config['AutoRun'] = autorun_enable

    def readCoeficient(self):
        self.send_commands(['DC'])
        coefficients = self.buffer.decode('ASCII').splitlines()
        for linea in coefficients:
            linea = linea.rstrip().lstrip()
            try:
                patron = re.compile(r'(?P<Modelo>\w{1,3}\d{1,2}) V (?P<Firmware>\d{1,2}[\.]\d{1,2}[\w{1,1}]?)\s{1,5}S/N = (?P<SN>\d{1,4})')
                if not(re.search(patron, linea.rstrip()) is None):
                    info = re.search(patron, linea)
                    continue
                patron = re.compile(r'Cal Date:\s{1,2}(?P<fecha>\d{1,2}[\-]\w{1,3}[\-]\d{1,4})')
                if not(re.search(patron, linea.rstrip()) is None):
                    Temp_fecha = re.search(patron, linea)
                    continue
                patron = re.compile(r'A0 = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    A0 = re.search(patron, linea)
                    continue
                patron = re.compile(r'A1 = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    A1 = re.search(patron, linea)
                    continue
                patron = re.compile(r'A2 = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    A2 = re.search(patron, linea)
                    continue
                patron = re.compile(r'A3 = (?P<value>[\-]?\d{1,2}[\.]\d{1,6}[e][\-]?\d{1,2})')
                if not(re.search(patron, linea.rstrip()) is None):
                    A3 = re.search(patron, linea)
                    continue
                patron = re.compile(r'slope = (?P<value>[\-]?\d{1,2}[\.]\d{1,6})')
                if not(re.search(patron, linea.rstrip()) is None):
                    slope = re.search(patron, linea)
                    continue
                patron = re.compile(r'offset = (?P<value>[\-]?\d{1,2}[\.]\d{1,6})')
                if not(re.search(patron, linea.rstrip()) is None):
                    offset = re.search(patron, linea)
                    continue
            except:
                pass

        self.__Config['xmlcon'] =   {   'SN': info.groupdict()['SN'],
                                        'Fecha': Temp_fecha.groupdict()['fecha'],
                                        'A0': A0.groupdict()['value'],
                                        'A1': A1.groupdict()['value'],
                                        'A2': A2.groupdict()['value'],
                                        'A3': A3.groupdict()['value'],
                                        'slope': slope.groupdict()['value'],
                                        'offset': offset.groupdict()['value']
                                    }
    def setStart(self):
        self.send_commands(['Go'], wait=False)
        time.sleep(0.1)

    def setStop(self):
        self.send_commands(['Stop'])

    def setDigits(self, n_digit = 3):
        """
            Configura la cantidad de digitos.
            n_digit debe ser de tipo integer
        """
        self.send_commands(['Digits=%s' %(str(n_digit))])
        self.__Config['Digitos'] = str(n_digit)

    @property
    def getModelo(self):
        return self.__Config['Modelo']

    def getFirmware(self):
        return self.__Config['Firmware']

    def getLogging(self):
        return self.__Config['Logging']

    def getAutoRun(self):
        return self.__Config['AutoRun']

    def getCoefficients(self):
        return self.__Config['xmlcon']

    def getInterval(self):
        return self.__Config['n_avg']

    def getSerialNumber(self):
        return self.__Config['SN']

class Interface_Box (SBE):

    def __init__(self, Model = 'Interface Box SBE45', port = 'COM1', BR = 9600, bytesize= 8, parity = 'N', stopbits = 1,  timeout = 2):
        # Llamo al constructor SBE
        SBE.__init__(self, Model, port, BR, bytesize, parity, stopbits, timeout)
        self.Mode = None
        self.SBE38 = SBE38(port=port, BR=BR)
        self.SBE45 = SBE45(port=port, BR=BR)

    def getSystem(self):
        self.wakeup()
        self.setModeNormal()
        self.getStatus()
        time.sleep(0.1)
        self.setStop()
        time.sleep(0.1)
        self.Wakeup_SBE45()
        self.SBE45.setStop()
        time.sleep(0.1)
        xmlcon = self.SBE45.getCoeficient()
        self.SBE45.getStatus()
        self.SBE45.setOutputFormat(0)
        self.setModeNormal()
        time.sleep(0.1)
        self.Wakeup_SBE38()
        self.setStop()
        time.sleep(0.1)
        self.SBE38.getStatus()
        time.sleep(0.1)
        self.setModeNormal()

    def setMode(self, mode):
        self.Mode = mode

    def setModeNormal(self):
        self.send_commands(['@'])
        self.setMode('Interface')

    def getMode(self):
        return self.Mode

    def getStatus(self):
        log_data = True
        self.send_commands(['DS'])
        status = self.buffer.decode('ASCII').splitlines()
        try:
            if self.Mode == 'SBE45':
                pass
            elif self.Mode == 'SBE38':
                pass
            else:
                self.Mode  = 'Box'
        except:
            self.Mode == 'None'

    def setSBE45(self):
        if not (self.Mode == 'SBE45'):
            self.setModeNormal()
        self.send_commands(['connect45'])
        self.setMode('SBE45')

    def setSBE38(self):
        if not (self.Mode == 'SBE38'):
            self.setModeNormal()
        self.send_commands(['connect38'])
        self.setMode('SBE38')

    def Wakeup_SBE45(self):
        self.wakeup()
        self.setSBE45()

    def setStop(self):
        self.send_commands(['Stop'])

    def setStart(self):
        if not(self.Mode == 'Box'):
            self.setModeNormal()
        self.send_commands(['Start'], wait=False)

    def Wakeup_SBE38(self):
        self.wakeup()
        self.send_commands(['connect38'])
        self.setMode('SBE38')

    def Start_45(self):
        if not(self.Mode == 'SBE45'):
            self.setSBE45()
        self.send_commands(['Start'], wait=False)

    def Start_38(self):
        if not(self.Mode == 'SBE38'):
            self.setSBE38()
        self.send_commands(['Go'], wait=False)