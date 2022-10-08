import serial
import json
import re
import os, time
import datetime

try:
    unicode
except (NameError, AttributeError):
    unicode = str       # for Python 3, pylint: disable=redefined-builtin,invalid-name

# all Python versions prior 3.x convert ``str([17])`` to '[17]' instead of '\x11'
# so a simple ``bytes(sequence)`` doesn't work for all versions
def to_bytes(seq):
    """convert a sequence to a bytes type"""
    if isinstance(seq, bytes):
        return seq
    elif isinstance(seq, bytearray):
        return bytes(seq)
    elif isinstance(seq, memoryview):
        return seq.tobytes()
    elif isinstance(seq, unicode):
        raise TypeError('unicode strings are not supported, please encode to bytes: {!r}'.format(seq))
    else:
        # handle list of integers and bytes (one or more items) for Python 2 and 3
        return bytes(bytearray(seq))

LF = to_bytes([10])

class Timeout(object):
    """\
    Abstraction for timeout operations. Using time.monotonic() if available
    or time.time() in all other cases.

    The class can also be initialized with 0 or None, in order to support
    non-blocking and fully blocking I/O operations. The attributes
    is_non_blocking and is_infinite are set accordingly.
    """
    if hasattr(time, 'monotonic'):
        # Timeout implementation with time.monotonic(). This function is only
        # supported by Python 3.3 and above. It returns a time in seconds
        # (float) just as time.time(), but is not affected by system clock
        # adjustments.
        TIME = time.monotonic
    else:
        # Timeout implementation with time.time(). This is compatible with all
        # Python versions but has issues if the clock is adjusted while the
        # timeout is running.
        TIME = time.time

    def __init__(self, duration):
        """Initialize a timeout with given duration"""
        self.is_infinite = (duration is None)
        self.is_non_blocking = (duration == 0)
        self.duration = duration
        if duration is not None:
            self.target_time = self.TIME() + duration
        else:
            self.target_time = None

    def expired(self):
        """Return a boolean, telling if the timeout has expired"""
        return self.target_time is not None and self.time_left() <= 0

    def time_left(self):
        """Return how many seconds are left until the timeout expires"""
        if self.is_non_blocking:
            return 0
        elif self.is_infinite:
            return None
        else:
            delta = self.target_time - self.TIME()
            if delta > self.duration:
                # clock jumped, recalculate
                self.target_time = self.TIME() + self.duration
                return self.duration
            else:
                return max(0, delta)

    def restart(self, duration):
        """\
        Restart a timeout, only supported if a timeout was already set up
        before.
        """
        self.duration = duration
        self.target_time = self.TIME() + duration

class NMEA(object):
    """
    Abre el puerto seleccionado y busca la sentencia NMEA seleccionada. Luego devuelve los valores
    correspondientes de la sentencia. Siempre debe ir acompañado por el archivo NMEA.json.
    Los parametros a ingresar son:
        - port: número del puerto serie (COM1 por defecto)
        - BR: Baud rate del puerto (4800 por defecto)
        - timeout: tiempo de espera del puerto (2 segundos por defecto)
        - sts: sentencia de NMEA a decodificar (RMC por defecto)
        - nmeajson: archivo de expresiones regulares de sentencias NMEA (archivo NMEA.json por defecto)
    Funciones a utilizar:
        - detect: busca en los puertos series que contengan sentencia de NMEA (usa "sts" para buscar)
    """
    __autor__ = 'Alvaro Cubiella'
    __version__ = 'V1.0'

    def __init__(self, port= 'COM1', BR = 4800, timeout = 2, sts = 'RMC', expreg_nmea = None):
        self.port = port
        self.BR = BR
        self.timeout = timeout
        self.sts = sts
        self.expreg_nmea = expreg_nmea
        #self.listport = self.detect()      # Detecta los puertos con la sentencia seleccionada

    def scan_ports(self):
        self.__listPort = list()
        for i in range(0,50):
            try:
                comm_NMEA = serial.Serial('COM'+str(i),self.BR,8, timeout = 0.5);
                comm_NMEA.close()
                self.__listPort.append('COM' + str(i))
            except:
                pass
        self.list_ports = self.__listPort

    def detect(self):
        """ Recorreo los puertos disponibles con sentencias NMEA.
        Devuelte una tupla con los numeros de puertos con NMEA,
        de lo contrario regresa una tupla vacia.
        """
        self.scan_ports()
        self.__nmea_port = list()
        for port in self.__listPort:
            try:
                comm_NMEA = serial.Serial(str(port),self.BR,8, timeout = 1);
                comm_NMEA.portstr;
                comm_NMEA.reset_input_buffer()               #Borro buffer del puerto serie
#                dato = comm_NMEA.read_until().decode('ASCII')
#Uso para probar en consola
                dato = comm_NMEA.read(500)
                if self.sts in str(dato):
                    self.__nmea_port.append(port)
                comm_NMEA.close()
            except serial.SerialException:
                pass
        if len(self.__nmea_port) == 0:
            return tuple()
        else:
            return tuple(self.__nmea_port)

    def Read(self):
        """
        Busca la sentencia seleccionada en el puerto serie ingresado y devuelve los respectivos valores.
        """
        patron = re.compile(self.expreg_nmea)
        dato = None
#        if self.listport.count(str(self.port)) == 0:
#            raise IOError()
        try:
            self._comm_NMEA = serial.Serial(str(self.port),self.BR,8, timeout = self.timeout);
            self._comm_NMEA.portstr;
            self._comm_NMEA.reset_input_buffer()               #Borro buffer del puerto serie
            self._comm_NMEA.reset_input_buffer()               #Borro buffer del puerto serie
            #dato = comm_NMEA.read_until().decode('ASCII')
            dato = self.Read_until().decode('ASCII')
            while re.search(patron, dato) is None:
#                comm_NMEA.reset_input_buffer()               #Borro buffer del puerto serie
                #datos = self._comm_NMEA.Read_until().decode('ASCII')
                dato = self.Read_until().decode('ASCII')
            dato = re.search(patron, dato)
            self._comm_NMEA.close()
        except TimeoutError:
            self._comm_NMEA.close()
            raise TimeoutError
        except serial.SerialException:
        #-- Error al abrir el puerto serie
            print ('Ocurrio un error al intentar de abrir el puerto serie seleccionado.\r\n \
                    No se pudo completar la operacion. Puerto %s' %(str(self.port)))
        self.NMEA_data = dato
        #print (self.sts + ':' + str(self.NMEA_data) )

    def Read_until(self, expected=LF, size=None):
        """\
        Read until an expected sequence is found ('\n' by default), the size
        is exceeded or until timeout occurs.
        """
        lenterm = len(expected)
        line = bytearray()
        timeout = Timeout(self.timeout)
        while True:
            c = self._comm_NMEA.read(1)
            if c:
                line += c
                if line[-lenterm:] == expected:
                    break
                if size is not None and len(line) >= size:
                    break
            else:
                raise TimeoutError
            if timeout.expired():
                break
        return bytes(line)

class RMC(NMEA):
    def __init__(self, port = 'COM1', BR = 4800, timeout = 2, sts = 'RMC'):
        #expreg_nmea = "\\$??(?P<sentencia>.*?)[\\,|\\, ](?P<hour>\\d{1,2})(?P<min>\\d{1,2})(?P<sec>\\d{1,2})" +\
        #"\\.(?P<msec>\\d{1,3})[\\,|\\, ](?P<status>.*?)[\\,|\\, ](?P<Lat>\\d{1,2})(?P<Lat_min>\\d{1,2}[\\.|\\,]"+\
        #"\\d{1,6})[\\,|\\, ](?P<Lat_cuadrante>[N|n|S|s])[\\,|\\, ](?P<Lon>\\d{1,3})(?P<Lon_min>\\d{1,2}[\\.|\\,]"+\
        #"\\d{1,6})[\\,|\\, ](?P<Lon_cuadrante>[W|w|E|e])[\\,|\\, ](?P<Speed>\\d{1,3}\\.\\d{1,2})[\\,|\\, ](?P<Dir>"+\
        #"\\d{1,3}\\.\\d{1,2})[\\,|\\, ](?P<dia>\\d{1,2})(?P<Mes>\\d{1,2})(?P<Año>\\d{1,4})[\\,|\\, ](?P<value>.*?)\\r?\\n"

        expreg_nmea = "\\$??(?P<sentencia>.*?)[\\,|\\, ](?P<hour>\\d{1,2})(?P<min>\\d{1,2})(?P<sec>\\d{1,2})" +\
        "[\\.(?P<msec>\\d{1,3})|\\][\\,|\\, ](?P<status>.*?)[\\,|\\, ](?P<Lat>\\d{1,2})(?P<Lat_min>\\d{1,2}[\\.|\\,]"+\
        "\\d{1,6})[\\,|\\, ](?P<Lat_cuadrante>[N|n|S|s])[\\,|\\, ](?P<Lon>\\d{1,3})(?P<Lon_min>\\d{1,2}[\\.|\\,]"+\
        "\\d{1,6})[\\,|\\, ](?P<Lon_cuadrante>[W|w|E|e])[\\,|\\, ](?P<Speed>\\d{1,3}\\.\\d{1,2})[\\,|\\, ](?P<Dir>"+\
        "\\d{1,3}\\.\\d{1,2})[\\,|\\, ](?P<dia>\\d{1,2})(?P<Mes>\\d{1,2})(?P<Año>\\d{1,4})[\\,|\\, ](?P<value>.*?)\\r?\\n"

        NMEA.__init__(self, port, BR, timeout, sts, expreg_nmea)

    def Get_Time(self, sep=':'):
        """ Regresa la hora de NMEA HH:MM:SS
        -sep = separador para formato de hora. Por defecto ':'
        """
        try:
            time = self.NMEA_data['hour'].zfill(2)+str(sep)+self.NMEA_data['min'].zfill(2)+str(sep)+self.NMEA_data['sec'].zfill(2)
            return (time)
        except AttributeError:
            return None

    def Get_Date(self, sep='/'):
        """ Regresa la fecha de NMEA DD/MM/YY
        -sep = separador para formato de fecha. Por defecto '/'
        """
        try:
            date = self.NMEA_data['dia'].zfill(2)+str(sep)+self.NMEA_data['Mes'].zfill(2)+str(sep)+self.NMEA_data['Año'].zfill(2)
            return (date)
        except AttributeError:
            return None

    def Get_DateTime(self):
        """ Regresa la fecha y hora de NMEA como clase datetime.datetime, luego dar el formato desea"""
        try:
            fechahora = datetime.datetime(int('20'+self.NMEA_data['Año']),int(self.NMEA_data['Mes']),int(self.NMEA_data['dia']),int(self.NMEA_data['hour']),\
            int(self.NMEA_data['min']),int(self.NMEA_data['sec']))
            return (fechahora)
        except:
            return None

    def Get_Latitud_Grados(self):
        """Regresa el valor de latitud expresado en grados y decimas de grado DD.DDDD"""
        try:
            lat = round(float(self.NMEA_data['Lat']) + float(self.NMEA_data['Lat_min'])/60, 6)
            if 's' in self.NMEA_data['Lat_cuadrante'].lower():
                return str(lat * -1)
            else:
                return str(lat)
        except AttributeError:
            return None

    def Get_Longitud_Grados(self):
        """Regresa el valor de longitud expresado en grados y decimas de grado DDD.DDDD"""
        try:
            lon = round(float(self.NMEA_data['Lon']) + float(self.NMEA_data['Lon_min'])/60, 6)
            if 'w' in self.NMEA_data['Lon_cuadrante'].lower():
                return str(lon * -1)
            else:
                return str(lon)
        except AttributeError:
            return None

    def Get_Lat_GradosMinutos(self):
        """Regresa el valor de Latitud en grados y minutos"""
        try:
            lat = (self.NMEA_data['Lat'] + ' ' + self.NMEA_data['Lat_min'] + ' ' +\
                self.NMEA_data['Lat_cuadrante'])
            return lat
        except AttributeError:
            return None

    def Get_Lon_GradosMinutos(self):
        """Regresa el valor de longitud en grados y minutos"""
        try:
            lon = (self.NMEA_data['Lon'] + ' ' + self.NMEA_data['Lon_min'] + ' ' +\
                self.NMEA_data['Lon_cuadrante'])
            return lon
        except AttributeError:
            return None

class DBS(NMEA):
    def __init__(self, port = 'COM1', BR = 4800, timeout = 2, sts = 'DBS'):
        expreg_nmea = '\\$??(?P<sentencia>.*?)[\\,|\\, ](?P<ZF>\\d{1,})[\\.|\\. ](?P<ZFdec>\\d{1,})[\\,|\\, ]'+\
        '(?P<ZunF>[f])[\\,|\\, ](?P<ZM>\\d{1,})[\\.|\\. ](?P<ZMdec>\\d{1,})[\\,|\\, ](?P<ZunM>[M])[\\,|\\, ]' +\
        '(?P<ZFa>\\d{1,})[\\.|\\. ](?P<ZFadec>\\d{1,})[\\,|\\, ](?P<ZunFa>[F])'+\
        '(?P<value>.*?)\\r?\\n?'
        NMEA.__init__(self, port, BR, timeout, sts, expreg_nmea)

#        self.day = self.__dato['dia'].zfill(2)
#        self.month = self.__dato['Mes'].zfill(2)
#        self.year = self.__dato['Año'].zfill(2)
#        self.hour = self.__dato['hour'].zfill(2)
#        self.min = self.__dato['min'].zfill(2)
#        self.sec = self.__dato['sec'].zfill(2)

    def Get_Z_Metros(self):
        """ Regresa la profundidad en metros
        """
        try:
            prof = str(int(self.NMEA_data['ZM']) + int(self.NMEA_data['ZMdec']) / 100)
            return (prof)
        except AttributeError:
            return 'NaN'

    def Get_Z_Pies(self):
        """ Regresa la profundidad en pies
        """
        try:
            date = str(int(self.NMEA_data['ZF']) + int(self.NMEA_data['ZFdec']) / 100)
            return (date)
        except AttributeError:
            return 'NaN'