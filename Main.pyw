#-------------------------------------------------------------------------------
# Name:        módulo1
# Purpose:
#
# Author:      Morochos
#
# Created:     21/11/2019
# Copyright:   (c) Morochos 2019
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import sys, os
import time
import wmi
import re
import cfg
import serial, serial.tools.list_ports, warnings
from SBE import Interface_Box
import NMEA

from Main_ui import *
from PyQt5.QtWidgets import QApplication, QMessageBox, QMainWindow, QAction, QInputDialog, QLineEdit, QFileDialog
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import sys, serial, serial.tools.list_ports, warnings
from PyQt5.QtCore import QSize, QRect, QObject, pyqtSignal, QThread, pyqtSignal, pyqtSlot
import time
from PyQt5.QtWidgets import QApplication, QComboBox, QDialog, QMainWindow, QWidget, QLabel, QTextEdit, QListWidget, \
    QListView, QTableWidget,QTableWidgetItem, QMessageBox

from datetime import datetime
#from Instrumentos import sbeterminal

# Variable global
_Config = []


__autor__ = 'Alvaro Cubiella'
__version__ = 'V1.90'

# Corroborando que el soft no sea pirata
############################################################
# Para conseguir el Numero de serie del HDD, ejecutar
# PowerShell de windows e ingresar:
#   wmic diskdrive get serialnumber
# Devuelve:
#   SerialNumber
#   [lista de los numeros de serie de los discos]
############################################################
# Mi PC
#SN_HHD = 'S0MUJ1KQA21853'
# Mi Notebook
SN_HHD = '3635_5A31_5254_1999_0025_3845_0000_0001.'
# METEO-TSF
#SN_HHD = 'Z4YEVSCG'
#Pen Verbatim
#SN_HHD = '9F0701047'
#Escritorio INIDEP
#SN_HHD = 'WCC6Y4TPXF70'
# METEO MA
#SN_HHD = 'WD-WCC6Y7SYAA3Z'

"""
#Escaneo HDD
HDD = list()
c = wmi.WMI()
for item in c.Win32_PhysicalMedia():
    HDD.append(str(item.SerialNumber).strip())

if not(SN_HHD in HDD):
    sys.exit(1)
"""

#########################################################################################
###     Hilo para leer la señal NMEA
#########################################################################################
class NMEA_Ext(QObject):
    finished = pyqtSignal()
    intReady = pyqtSignal(dict)                             # le digo que la señal a enviar es un diccionario

    @pyqtSlot()
    def __init__(self, ser):
        super(NMEA_Ext, self).__init__()
        self.working = True
        self.ser = NMEA.RMC(port=ser.port, BR=ser.baudrate, timeout=5)
        """
        line = self.ser.Read()
        print('iniciando hilo NMEA')
        line = {'latD':self.ser.Get_Latitud_Grados(),
                'lonD':self.ser.Get_Longitud_Grados(),
                'lat': self.ser.Get_Lat_GradosMinutos(),
                'lon': self.ser.Get_Lon_GradosMinutos(),
                'hora': self.ser.Get_Time(),
                'fecha': self.ser.Get_Date(sep='')}
        print(line)
        """

    def work(self):
        while self.working:
            try:
                #line=''
                line = self.ser.Read()
                line = {'latD':self.ser.Get_Latitud_Grados(),
                        'lonD':self.ser.Get_Longitud_Grados(),
                        'lat': self.ser.Get_Lat_GradosMinutos(),
                        'lon': self.ser.Get_Lon_GradosMinutos(),
                        'hora': self.ser.Get_Time(),
                        'fecha': self.ser.Get_Date(sep='')
                        }
                #print(line)
                self.intReady.emit(line)
            except TimeoutError:
                print ('timeout')
                self.intReady.emit(None)
            time.sleep(0.05)
        self.finished.emit()

#########################################################################################
###     Hilo para leer las cadenas del TSG y Fluorometro
#########################################################################################
class Opto_Box(QObject):
    finished = pyqtSignal()
    intReady = pyqtSignal(str)

    @pyqtSlot()
    def __init__(self, ser):
        super(Opto_Box, self).__init__()
        self.working = True
        self.ser = ser

    def work(self):
        time.sleep(2)
        if not(self.ser.isOpen()):
            self.ser.open()
        while self.working:
            #line = ser.readline().decode('utf-8')
            line=''
            self.ser.reset_input_buffer()
            line = self.ser.read_until().decode('ASCII').replace('\r\n','')
            self.intReady.emit(line)
            time.sleep(0.05)
        self.ser.close()
        self.finished.emit()

#########################################################################################
###     Menu principal
#########################################################################################

class AuxSensor(QObject):
    finished = pyqtSignal()
    intReady = pyqtSignal(str)

    @pyqtSlot()
    def __init__(self, ser, sep = '\r\n', pos = -2):
        super(AuxSensor, self).__init__()
        self.working = True
        self.ser = ser
        self.sep = sep
        self.pos = pos

    def work(self):
        if not(self.ser.isOpen()):
            self.ser.open()
        while self.working:
            line=''
            self.ser.reset_input_buffer()                                           #Vacio el buffer del puerto serie
            time.sleep(0.5)                                                                 
            line = self.ser.read_all().decode('ASCII').split(self.sep)[self.pos]    # Luego de la espera, leo todo lo que contiene el 
                                                                                    #puerto y extraigo el ultimo valor            
            self.intReady.emit(line)
            time.sleep(0.05)
            #print(line)
        self.ser.close()
        self.finished.emit()

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    #Aca heredo la clase de la ventana, si no hay nada simplemente aparece una ventana vacia
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__()
        self._Config = cfg.cfg()
        self.cfg = self._Config.Get_cfg()
        QtWidgets.QMainWindow.__init__(self, *args, **kwargs)
        self.setupUi(self)
#        self.setWindowFlag(QtCore.Qt.WindowMaximizeButtonHint)
        self.setWindowFlags(QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMinimizeButtonHint)
        self.setWindowTitle('TSX %s' %(__version__))
        self.thread = None
        self.worker = None

        #Activo el seguimiento del mouse
        self.setMouseTracking(True)

        # Configuro opciones de los botones de la barra de menu
        self.archivo_Salir.setShortcut('Alt+S')

        #Configuro cadenas de barra de estado
        self.archivo_Salir.setStatusTip('Cierra la Aplicacion')
        self.txt_Camp.setStatusTip('Codigo de campaña')
        self.txt_Inst_Modelo.setStatusTip('Modelo del instrumento seleccionado')
        self.txt_Inst_Intervalo.setStatusTip('Intervalo de muestreo de adquisicion')
        self.txt_Inst_SN.setStatusTip('Numero de serie del instrumento')

        #Configuro eventos de cuadros y botones de control
        self.btn_Iniciar.clicked.connect(self.setAdquisicion)
        self.btn_SBE38.clicked.connect(self.close)
        self.btn_TSG.clicked.connect(self.close)
        self.btn_cmd.clicked.connect(self.load_cmd)
        self.btn_NMEAExt_Refresh.clicked.connect(self.list_COM)
        self.btn_Mrk.clicked.connect(self.add_Mrk)

        #Configuro el evento de cambio de pestaña
        self.tabWidget.currentChanged.connect(self.tab)

        #Configuro los cuadros de la pestaña de instrumentos
        self.chkbox_NMEA_Ext.stateChanged.connect(self.up_NMEA_Ext)
        self.chkbox_Opto_NMEA.stateChanged.connect(self.up_NMEA_Opto)
        self.chkbox_Opto_SBE38.stateChanged.connect(self.up_Disp_Ext)
        self.chkbox_Fl_Ext.stateChanged.connect(self.up_Disp_Ext)
        self.chkbox_Ox_Ext.stateChanged.connect(self.up_Disp_Ext)
        self.chkbox_SeaSave.stateChanged.connect(self.up_SeaSave)

        # Funciones del Menu
        self.archivo_Salir.triggered.connect(self.close)

        #Configuro cuadros a condiciones iniciales del codigo
        self.box_NMEA_Opto.setVisible(False)
        self.box_Ox.setVisible(False)
        self.box_Fl.setVisible(False)
        self.lbl_Menu.setText('Visualización de datos adquiridos')
        self.lbl_Menu.setStyleSheet("background-color: rgb(0, 120, 215);" "color: #fff\n" "")
        self.btn_Detener.setVisible(False)
        self.tabWidget.setTabVisible(2,False)

        self.flag = False
        #self.cbox_NMEAExt_COM.clear()

        ports = NMEA.NMEA(timeout = 0.1, sts = self.cbox_NMEAExt_Sentencia.currentText())
        ports.scan_ports()
        self.cbox_NMEAExt_COM.addItems(ports.list_ports)
        self.cbox_Opto_COM.addItems(ports.list_ports)
        self.cbox_Fl_COM.addItems(ports.list_ports)
        self.cbox_SeaSave_COM.addItems(ports.list_ports)


        #Escaneo HDD
        HDD = list()
        c = wmi.WMI()
        for item in c.Win32_PhysicalMedia():
            HDD.append(str(item.SerialNumber).strip())

        if not(SN_HHD in HDD):
            ### Queda para una version nueva
            self.lcd_Timer = QTimer(self)
            self.lcd_Timer.timeout.connect(self.showTime)
            self.count = 180
            self.flag = True
            self.lcd_Timer.start(1000)
        ########################################################################
        ###     Establezco los parametro de CMD por defecto
        ########################################################################
        self.__Config = {   'Opto': {   'AutoRun':True,
                                        'SBE38': True,
                                        'NMEA': False,
                                        'COM':'COM14',
                                        'BR':'9600'
                                    },
                            'TSG':  {   'Model':'SBE45',
                                        'SN': '0000',
                                        'Intervalo': 30,
                                        'Cond': True,
                                        'Sal': True,
                                        'SV': True,
                                        'BR':'4800'
                                    },
                            'SBE38':{   'Status':True,
                                        'SN': '0000',
                                        'Digitos':3,
                                        'BR':'4800'
                                    },
                            'Fl':   {   'Model':'',
                                        'Status':True,
                                        'SN': '0000',
                                        'Count': 0,
                                        'SF': 0,
                                        'COM':'COM1',
                                        'BR':'4800'
                                    },
                            'Ox':   {   'Status':False
                                    },
                            'NMEA_Ext':   { 'Status':True,
                                            'Sentencia': 'RMC',
                                            'COM':'COM10',
                                            'BR':'4800'
                                    },
                            'NMEA_Opto':   {'Status':False,
                                            'Sentencia': 'RMC',
                                            'BR':'4800'
                                    },
                            'Campaña':     {'Buque':'',
                                            'Sigla_Buque':'',
                                            'Año':'2022',
                                            'Nro_Camp':'001'
                                           }

                        }

    def showTime(self):
        ## Corre el programa por X segundos y se cierra automaticamente (para versiones DEMO)
        if self.flag:
            self.count -= 1
            self.setWindowTitle('TSX %s DEMO (%.0f)' %(__version__, self.count))
            #text = str(self.count / 10)
            if self.count < 0:
                sys.exit(1)


    def reset_Count(self):
        self.count = round(int(self.instrumento.SBE45.getInterval()) * 2) * 10

    def list_COM(self):
        self.statusBar.setStyleSheet("font: 10pt \"Times New Roman\";\n"
"color: rgb(0, 0, 0);")
        self.statusBar.showMessage('Buscando NMEA con sentencia %s' %(self.cbox_NMEAExt_Sentencia.currentText()))
        self.btn_NMEAExt_Refresh.setEnabled(False)
        self.repaint()
        ports = NMEA.NMEA(timeout = 1, sts = self.cbox_NMEAExt_Sentencia.currentText())
        self.cbox_NMEAExt_COM.clear()
        self.cbox_NMEAExt_COM.addItems(ports.detect())
        self.btn_NMEAExt_Refresh.setEnabled(True)
        self.statusBar.showMessage('')

    def tab(self):
        if self.tabWidget.currentIndex() == 1:
            #tab Instrumentos
            self.lbl_Menu.setText('Configurar parametros intrumentos de adquisición')
        elif self.tabWidget.currentIndex() == 0:
            #tab Datos
            self.lbl_Menu.setText('Visualización de datos adquiridos')
        elif self.tabWidget.currentIndex() == 2:
            #tab cmd
            self.lbl_Menu.setText('dd')
        elif self.tabWidget.currentIndex() == 3:
            #tab cmd
            self.lbl_Menu.setText('Enviando comandos al sistema')

    ########################################################################
    ###     Finalizo el programa
    ########################################################################
    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Salir', 'Realmente desea salir de la aplicación? ',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                if ser.isOpen():
                    self.stop_loop()
                    ser.close()
                    time.sleep(1)
            except NameError:
                pass
            finally:
                event.accept()
        else:
            event.ignore()

    ########################################################################
    ###     Configuro la visualización de los Box
    ########################################################################
    def up_NMEA_Ext(self):
        # # Actualizo el cuadro de NMEA Externo
        if self.chkbox_NMEA_Ext.isChecked():
            self.box_NMEA_Ext.setVisible(True)
            self.chkbox_Opto_NMEA.setChecked(False)
        else:
            self.box_NMEA_Ext.setVisible(False)
            self.chkbox_Opto_NMEA.setChecked(True)

    def up_NMEA_Opto(self):
        # Actualizo el cuadro de NMEA Opto
        if self.chkbox_Opto_NMEA.isChecked():
            self.box_NMEA_Opto.setVisible(True)
            self.chkbox_NMEA_Ext.setChecked(False)
        else:
            self.box_NMEA_Opto.setVisible(False)
            self.chkbox_NMEA_Ext.setChecked(True)

    def up_Disp_Ext(self):
        ## Actualizo el cuadro de el SBE38
        if self.chkbox_Opto_SBE38.isChecked():
            self.box_SBE38.setVisible(True)
            self.btn_SBE38.setVisible(True)
            if self.chkbox_Fl_Ext.isChecked():
                self.box_Fl.setVisible(True)
                self.box_Fl.setGeometry(QtCore.QRect(380, 190, 361, 181))
                if self.chkbox_Ox_Ext.isChecked():
                    self.box_Ox.setVisible(True)
                    self.box_Ox.setGeometry(QtCore.QRect(380, 370, 361, 71))
                else:
                    self.box_Ox.setVisible(False)
            else:
                self.box_Fl.setVisible(False)
                if self.chkbox_Ox_Ext.isChecked():
                    self.box_Ox.setVisible(True)
                    self.box_Ox.setGeometry(QtCore.QRect(380, 190, 361, 71))
                else:
                    self.box_Ox.setVisible(False)
        else:
            self.box_SBE38.setVisible(False)
            self.btn_SBE38.setVisible(False)
            if self.chkbox_Fl_Ext.isChecked():
                self.box_Fl.setVisible(True)
                self.box_Fl.setGeometry(QtCore.QRect(380, 110, 361, 181))
                if self.chkbox_Ox_Ext.isChecked():
                    self.box_Ox.setVisible(True)
                    self.box_Ox.setGeometry(QtCore.QRect(380, 290, 361, 71))
                else:
                    self.box_Ox.setVisible(False)
            else:
                self.box_Fl.setVisible(False)
                if self.chkbox_Ox_Ext.isChecked():
                    self.box_Ox.setVisible(True)
                    self.box_Ox.setGeometry(QtCore.QRect(380, 110, 361, 71))
                else:
                    self.box_Ox.setVisible(False)
                    self.box_Ox.setGeometry(QtCore.QRect(380, 190, 361, 71))

    def up_SeaSave(self):
        if self.chkbox_SeaSave.isChecked():
            self.cbox_SeaSave_COM.setEnabled(True)
            self.cbox_SeaSave_BR.setEnabled(True)
        else:
            self.cbox_SeaSave_COM.setEnabled(False)
            self.cbox_SeaSave_BR.setEnabled(False)

    ########################################################################
    ###     Cargo los parametros de los cuadros en la variable reservada
    ########################################################################
    def __setConfig(self):
        #Establezco los parametro de CMD configurados por usuario
        self.__Config['Opto']['AutoRun'] = self.chkbox_Opto_AutoPWR.isChecked()
        self.__Config['Opto']['SBE38'] = self.chkbox_Opto_SBE38.isChecked()
        self.__Config['Opto']['NMEA'] = self.chkbox_Opto_NMEA.isChecked()
        self.__Config['Opto']['COM'] =  self.cbox_Opto_COM.currentText()
        self.__Config['Opto']['BR'] = self.cbox_Opto_BR.currentText()

        self.__Config['TSG']['Model'] = self.cbox_TSG_COM.currentText()
        self.__Config['TSG']['SN'] = self.txt_TSG_SN.text()
        self.__Config['TSG']['Intervalo'] =  self.spn_TSG_Interval.value()
        self.__Config['TSG']['Cond'] = self.chkbox_TSG_Cond.isChecked()
        self.__Config['TSG']['Sal'] = self.chkbox_TSG_Sal.isChecked()
        self.__Config['TSG']['SV'] = self.chkbox_TSG_SV.isChecked()
        self.__Config['TSG']['BR'] = self.cbox_TSG_BR.currentText()


        self.__Config['SBE38']['SN'] = '0000'
        self.__Config['SBE38']['Digitos'] = self.spn_SBE38_Digitos.value()
        self.__Config['SBE38']['BR'] = self.cbox_SBE38_BR.currentText()

        self.__Config['Fl']['Status'] = self.chkbox_Fl_Ext.isChecked()
        self.__Config['Fl']['SN'] = self.txt_Fl_SN.text()
        self.__Config['Fl']['Count'] = self.spn_Fl_Counts.value()
        self.__Config['Fl']['SF'] =  self.spn_Fl_Factor.value()
        self.__Config['Fl']['COM'] = self.cbox_Fl_COM.currentText()
        self.__Config['Fl']['BR'] = self.cbox_Fl_BR.currentText()
        self.__Config['Fl']['Model'] = self.cbox_Fl_Modelo.currentText()

        self.__Config['Ox']['Status'] = self.chkbox_Ox_Ext.isChecked()

        self.__Config['NMEA_Ext']['Status'] = self.chkbox_NMEA_Ext.isChecked()
        self.__Config['NMEA_Ext']['Sentencia'] = self.cbox_NMEA_Sentencia.currentText()
        self.__Config['NMEA_Ext']['COM'] = self.cbox_NMEAExt_COM.currentText()
        self.__Config['NMEA_Ext']['BR']  = self.cbox_NMEA_BR.currentText()

        self.__Config['NMEA_Opto']['Status'] = self.chkbox_Opto_NMEA.isChecked()
        self.__Config['NMEA_Opto']['Sentencia'] =  self.cbox_NMEA_Sentencia.currentText()
        self.__Config['NMEA_Opto']['BR'] = self.cbox_NMEA_BR.currentText()

        self.__Config['Campaña']['Buque'] = self.txt_Buque.text()
        self.__Config['Campaña']['Sigla_Buque'] = self.txt_SiglasBuque.text()
        self.__Config['Campaña']['Año'] = self.spn_Year.value()
        self.__Config['Campaña']['Nro_Camp'] = self.spn_Nro_Camp.value()

    ########################################################################
    ###  Inicio el sistema de instrumentos y la adquisicion
    ########################################################################
    def setAdquisicion(self):
        self.NMEA_Str = ''
        self.__setConfig()
        self.instrumento = Interface_Box(port=self.__Config['Opto']['COM'], BR= self.__Config['Opto']['BR'])
        self.btn_Iniciar.setVisible(False)
        self.btn_Detener.setVisible(True)
        self.btn_Detener.setEnabled(False)
        self.tabWidget.setCurrentIndex(2)
        self.tabWidget.setTabVisible(2, True)
        self.chkbox_Temp.setChecked(False)
        self.chkbox_Fl.setChecked(False)
        self.chkbox_Ox.setChecked(False)
        self.textEdit_4.clear()
        self.repaint()
        self.init_TSG()                             # Inicio el com del TSG

        ########################################################################
        ### Configuro SBE45
        ########################################################################
        try:
            self.textEdit_4.append('Iniciando comunicación...')
            time.sleep(0.5)
            self.repaint()
            self.instrumento.setStop()
            self.textEdit_4.append('Configurando intervalo SBE45 a %s segundos' %(str(self.spn_TSG_Interval.value()))); self.repaint()
            self.instrumento.setSBE45()
            time.sleep(0.5)
            self.eco_serial(); self.repaint()
            self.instrumento.SBE45.setStop()
            self.instrumento.SBE45.setInterval(self.__Config['TSG']['Intervalo'])
            time.sleep(0.5)
            self.eco_serial(); self.repaint()
            self.textEdit_4.append('Configurando variable de Conductividad'); self.repaint()
            self.instrumento.SBE45.setConductividad(self.__Config['TSG']['Cond'])
            self.eco_serial(); self.repaint()
            time.sleep(0.5)
            self.textEdit_4.append('Configurando variable de Salinidad'); self.repaint()
            self.instrumento.SBE45.setSalinidad(self.__Config['TSG']['Sal'])
            self.eco_serial(); self.repaint()
            time.sleep(0.5)
            self.textEdit_4.append('Configurando variable de Velocidad del Sonido'); self.repaint()
            self.instrumento.SBE45.setVelocidadSonido(self.__Config['TSG']['SV'])
            self.eco_serial(); self.repaint()
            time.sleep(0.5)
            self.textEdit_4.append('Leyendo Status...'); self.repaint()
            self.instrumento.SBE45.readStatus()
            self.eco_serial()
            time.sleep(0.5)
            self.textEdit_4.append('Leyendo Coeficientes de calibración...'); self.repaint()
            self.instrumento.SBE45.readCoeficient()
            self.eco_serial()
            time.sleep(0.5)
        except IOError:
            #print('Puerto COM seleccionado no disponible')
            self.statusBar.showMessage('ERROR al intentar de iniciar el SBE45'); self.repaint()
            self.loop_finished()
            return
        except TimeoutError:
            self.msg_Box(mensaje = 'Error de comunicación con el TSG.\rTimeout', titulo = 'Error TSG', icono = QMessageBox.Critical)
            #print('No se encontro TSG disponible')
            return

        # Configuro cadena para salida de datos y la exprecion regular
        ### Cadena de ejemplo
        #t1= (?P<Temp1>\d{1,2}[\.]\d{1,6}) c1= (?P<Cond>\d{1,2}[\.]\d{1,6}) s= (?P<Sal>\d{1,2}[\.]\d{1,6}) t2= (?P<Temp2>\d{1,2}[\.]\d{1,6}), fl=(?P<Fl>\d{0,4}), lat=(?P<LatD>\d{1,3}) (?P<LatM>\d{1,2}[\.]\d{1,6}[\ ])(?P<Lat_cuadrante>[N|n|S|s]), lon=(?P<LonD>\d{1,3}) (?P<LonM>\d{1,2}[\.]\d{1,6}[\ ])(?P<Lon_cuadrante>[W|w|E|e]), hms=(?P<Hora>\d{1,6}), dmy=(?P<Fecha>\d{1,6})\r?\n'
        #########################################################################################
        ###     Creo la cadena de la expresion regular a partir de la configuracion del sistema
        #########################################################################################
        self.statusBar.showMessage('')
        self.repaint()
        self.statusBar.showMessage('Creando cadena de datos...')
        self.repaint()
        columns = list()
        columns.append('Temp_TSG')
        re_exp_TSG = 't1=\s{0,2}(?P<Temp_TSG>\d{1,2}[\.]\d{1,6})'
        re_exp_NMEA = ''
        if self.__Config['TSG']['Cond']:
            columns.append('Cond')
            re_exp_TSG = re_exp_TSG + ', c1=\s{0,2}(?P<Cond>\d{1,2}[\.]\d{1,5})'
        if self.__Config['TSG']['Sal']:
            columns.append('Sal')
            re_exp_TSG = re_exp_TSG + ', s=\s{0,2}(?P<Sal>\d{1,3}[\\.]\d{1,4})'
        if self.__Config['TSG']['SV']:
            columns.append('SV')
            re_exp_TSG = re_exp_TSG + ', sv=\s{0,2}(?P<SV>\d{1,4}[\.]\d{1,3})'
        # Pongo a adquirir TSG
        self.textEdit_4.append('Iniciando %s' %(self.instrumento.getMode()))
        self.instrumento.Start_45()
        ########################################################################
        ### Configuro SBE38
        ########################################################################
        if self.__Config['Opto']['SBE38']:
            self.textEdit_4.append('Configurando SBE38...')
            self.repaint()
            self.instrumento.setSBE38()
            self.eco_serial()
            self.instrumento.SBE38.setStop()
            self.eco_serial()
            self.textEdit_4.append('Configurando dígitos')
            self.repaint()
            self.instrumento.SBE38.setDigits(self.__Config['SBE38']['Digitos'])
            self.eco_serial()
            self.textEdit_4.append('Leyendo Status...'); self.repaint()
            self.instrumento.SBE38.readStatus()
            self.eco_serial()
            self.textEdit_4.append('Leyendo Coeficientes de calibración...'); self.repaint()
            self.instrumento.SBE38.readCoeficient()
            self.eco_serial()
            self.textEdit_4.append('Iniciando %s' %(self.instrumento.getMode()))
            self.repaint()
            self.instrumento.Start_38()
            columns.append('SBE38')
            re_exp_TSG = re_exp_TSG + ', t2= (?P<SBE38>\d{1,2}[\.]\d{1,6})'
            self.chkbox_Temp.setChecked(True)

        ########################################################################
        ### Configuro Fluorometro
        ########################################################################
        #Queda pendiente crear la clase para leer el com. Lo mismo que el TSG
        if self.__Config['Fl']['Status']:
            columns.append('Counts')
            if self.checkBox_15.isChecked():
                columns.append('CHL')
            re_exp_Fl = 'fl=(?P<Fl>\d{1,4})'
            self.chkbox_Fl.setChecked(True)
            # Inicio el com del Fluorometro
            self.init_Fluorometro()
            #self.NMEA.work()
            self.thread_Fl.start()

        ########################################################################
        ### Configuro oximetro AAnderAA  PENDIENTE PARA OTRA ACTUALIZACIóN
        ########################################################################
        if self.__Config['Ox']['Status']:
            columns.append('Oxigeno')
            re_exp_Ox = 'ox=(?P<Ox>\d{0,4})'
            self.chkbox_Ox.setChecked(True)

        ########################################################################
        ### Armo cadena de exprecion regular del NMEA. EXCLUSIVA para el RMC
        ########################################################################
        if self.__Config['NMEA_Ext']['Status'] or self.__Config['Opto']['NMEA']:
            columns.append('Lat')
            columns.append('Lon')
            columns.append('Hora')
            columns.append('Fecha')
            re_exp_NMEA = 'lat= (?P<Lat>[\-]?\d{1,2}[\.]\d{1,6}), lon= (?P<Lon>[\-]?\d{1,3}[\.]\d{1,6}), hms= (?P<Hora>\d{1,2}[\\:]\d{1,2}[\\:]\d{1,2}), dmy= (?P<Fecha>\d{0,6})'
            if self.__Config['Opto']['NMEA']:
                re_exp_TSG = re_exp_TSG + re_exp_NMEA
        self.columns = columns
        self.re_exp_TSG = re.compile(re_exp_TSG)
        self.re_exp_NMEA = re.compile(re_exp_NMEA)

        ########################################################################
        ### Inicia la adquisicion de la caja Optoacoplada
        ########################################################################
        self.statusBar.showMessage('')
        self.repaint()
        self.textEdit_4.append('Iniciando sistema de adquisición.')
        self.statusBar.showMessage('Iniciando sistema de adquisición.')
        self.repaint()
        self.instrumento.setStart()
        self.tbl_Data.setRowCount(0)
        self.tbl_Data.setColumnCount(len(self.columns))
        self.tbl_Data.setHorizontalHeaderLabels(self.columns)
        self.tbl_Data.horizontalHeader().setVisible(True)
        self.row = 0

        ########################################################################
        ###     Inicializo las clases de los hilos correspondientes
        ########################################################################
        self.init_NMEA()

        self.btn_Detener.clicked.connect(self.stop_loop)                # stop the loop on the stop button click
        try:
            #self.NMEA.work()
            self.thread_NMEA.start()
        except:
            print('error start NMEA')

        try:
            self.thread_Opto.start()
            time.sleep(0.25)
        except:
            print('error start opto')

        self.statusBar.showMessage('')
        self.repaint()
        self.statusBar.setStyleSheet("font: 10pt \"Times New Roman\";\n"
"color: rgb(0, 255, 0);")
        self.statusBar.showMessage('Sistema ON-Line')
        self.txt_Camp.setText('%s%s%s' %(self.txt_SiglasBuque.text().upper(),str(self.spn_Year.value()), str(self.spn_Nro_Camp.value()).zfill(2)))
        self.txt_Inst_Modelo.setText('%s' %(self.instrumento.SBE45.getModelo()))
        self.txt_Inst_Intervalo.setText('%s' %(self.instrumento.SBE45.getInterval()))
        self.txt_Inst_SN.setText('%s' %(self.instrumento.SBE45.getSerialNumber()))

        ## Queda para una próxima versión
        #self.reset_Count()
        #self.lcd_Timer.start(1000)
        #self.flag = True
        self.tabWidget.setCurrentIndex(0)
        self.btn_Detener.setEnabled(True)
        self.tabWidget.setTabVisible(2, False)

    ########################################################################
    ### Inicializo el com del TSG
    ########################################################################
    def init_TSG(self):
        try:
            ser = serial.Serial(self.cbox_Opto_COM.currentText(), self.cbox_Opto_BR.currentText())
            ser.timeout = self.__Config['TSG']['Intervalo'] + 1
            ser.close()
            self.Opto = Opto_Box(ser)                                       # a new worker to perform those tasks
            self.thread_Opto = QThread()                                    # a new thread to run our background tasks in
            self.Opto.moveToThread(self.thread_Opto)                        # move the worker into the thread, do this first before connecting the signals
            self.thread_Opto.started.connect(self.Opto.work)                # begin our worker object's loop when the thread starts running
            self.Opto.intReady.connect(self.onIntReady)
            self.Opto.finished.connect(self.loop_finished)                  # do something in the gui when the worker loop ends
            self.Opto.finished.connect(self.thread_Opto.quit)               # tell the thread it's time to stop running
            self.Opto.finished.connect(self.Opto.deleteLater)               # have worker mark itself for deletion
            self.thread_Opto.finished.connect(self.thread_Opto.deleteLater)  # have thread mark itself for deletion
        except IOError:
            self.loop_finished()                                # Vuelen boton iniciar y detener a condiciones iniciales
            self.msg_Box(mensaje = 'Error al inicializar el puerto seleccionado!!!\r', titulo = 'I/O Error TSG', icono = QMessageBox.Critical)
            return
        self.statusBar.setStyleSheet("font: 10pt \"Times New Roman\";\n"
"color: rgb(0, 0, 0);")

    ############################################################################
    ###     Inicio el hilo del fluorometro
    ############################################################################
    def init_Fluorometro(self):
        try:
            ser = serial.Serial(self.cbox_Fl_COM.currentText(), self.cbox_Fl_BR.currentText(), timeout = 2)
            ser.close()
            self.Fluor = AuxSensor(ser)
            #self.Fluor.work()
            self.thread_Fl = QThread()                                          # a new thread to run our background tasks in
            self.Fluor.moveToThread(self.thread_Fl)                             # move the worker into the thread, do this first before connecting the signals
            self.thread_Fl.started.connect(self.Fluor.work)                     # begin our worker object's loop when the thread starts running
            self.Fluor.intReady.connect(self.on_FlReady)
            self.Fluor.finished.connect(self.loop_finished)                     # do something in the gui when the worker loop ends
            self.Fluor.finished.connect(self.thread_Fl.quit)                    # tell the thread it's time to stop running
            self.Fluor.finished.connect(self.Fluor.deleteLater)                 # have worker mark itself for deletion
            self.thread_Fl.finished.connect(self.thread_Fl.deleteLater)         # have thread mark itself for deletion
        except IOError:
            self.loop_finished()    # Vuelen boton iniciar y detener a condiciones iniciales
            self.msg_Box(mensaje = 'Error al inicializar el puerto seleccionado!!!\r', titulo = 'I/O Error Fluorómetro', icono = QMessageBox.Critical)
        return

    def loop_finished(self):
        self.flag = False
        self.btn_Iniciar.setVisible(True)
        self.btn_Detener.setVisible(False)
        self.statusBar.showMessage('Sistema OFF-Line')
        self.statusBar.setStyleSheet("font: 10pt \"Times New Roman\";\n"
"color: rgb(255, 0, 0);")

    def init_NMEA(self):
        # Inicializo el com del NMEA
        try:
            ser = serial.Serial(self.cbox_NMEAExt_COM.currentText(), self.cbox_NMEAExt_BR.currentText(), timeout = 5)
            ser.close()
            self.NMEA = NMEA_Ext(ser)
            #self.NMEA.work()
            self.thread_NMEA = QThread()
            self.NMEA.moveToThread(self.thread_NMEA)
            self.thread_NMEA.started.connect(self.NMEA.work)
            self.NMEA.intReady.connect(self.onIntReadyNMEA)
            self.NMEA.finished.connect(self.loop_finished)
            self.NMEA.finished.connect(self.thread_NMEA.quit)
            self.NMEA.finished.connect(self.NMEA.deleteLater)
            self.thread_NMEA.finished.connect(self.thread_NMEA.deleteLater)

        except IOError:
            self.loop_finished()                                # Vuelen boton iniciar y detener a condiciones iniciales
            self.msg_Box(mensaje = 'Error al inicializar el puerto seleccionado!!!\r',
                        titulo = 'I/O Error NMEA', icono = QMessageBox.Critical)
            return

    ########################################################################
    ###     Atiendo la señal generada a partir del hilo del Opto_Box
    ########################################################################
    # Se encarga de interpretar las cadenas del TSG y NMEA a partir de las expresiones
    # regulares que se generaron por la seleccion del usuario.
    # Los datos son escritos en la tabla en su respectiva columna
    def onIntReady(self, i):
        #self.textEdit.append("{}".format(i))
        str_TSG_Vrg = i
        try:
            str_NMEA = 'lat= %s, lon= %s, hms= %s, dmy= %s' %(self.NMEA_Str['latD'], self.NMEA_Str['lonD'], self.NMEA_Str['hora'], self.NMEA_Str['fecha'])
        except:
            str_NMEA = None

        self.row = self.tbl_Data.rowCount()
        self.tbl_Data.insertRow(self.row)
        var_TSG = re.search(self.re_exp_TSG, str_TSG_Vrg)
        var_TSG_vrg = var_TSG.groupdict()
        var_TSG = var_TSG.groupdict()

        if self.__Config['Fl']['Status']:
            var_TSG.update(self.Fl_Str)
            str_TSG = str_TSG_Vrg
            for label, value in self.Fl_Str.items():
                str_TSG = '%s, %s = %s' %(str_TSG, label, value)

        if self.__Config['NMEA_Ext']['Status']:
            var_NMEA = re.search(self.re_exp_NMEA, str_NMEA)
            self.setRow(tsg= var_TSG, nmea= var_NMEA.groupdict())
            self.textEdit_3.setText(('%s, %s' %(str_TSG, str_NMEA)))
            #Armo cadena para almecenar en archivo
            if self.__Config['Fl']['Status']:
                cadena = '%s, %s' %(str_TSG, str_NMEA)
            else:
                cadena = '%s, %s' %(str_TSG_Vrg, str_NMEA)
        else:
            ### Falta terminar esta parte, es para GPS incorporado a la BOX
            var_TSG = re.search(self.re_exp_TSG, str_TSG)
            self.setRow(tsg= var_TSG.groupdict())
            self.textEdit_3.setText(('%s' %(str_TSG)))
            cadena = '%s' %(str_TSG)
            str_SeaSave = cadena
        # Verifico SI la salida a SeaSave este habilitada y envio la cadena.
        if self.chkbox_SeaSave.isChecked():
            #Armo cadena para enviar al SeaSave
            str_SeaSave = '%s, lat=%s, lon=%s, hms=%s, dmy=%s' %(str_TSG_Vrg, self.NMEA_Str['lat'], self.NMEA_Str['lon'], self.NMEA_Str['hora'].replace(':',''), self.NMEA_Str['fecha'])
            self.send_SeaSave(str_SeaSave)
        self.file = '%s.dat' %(var_NMEA.groupdict()['Fecha'])
        self.w_File(self.file, cadena)
        #self.reset_Count()

    ########################################################################
    ###     Atiendo la señal generada a partir del hilo del NMEA
    ########################################################################
    # Paso el valor a la variable para que quede a disposicion del dato del TSG
    def onIntReadyNMEA(self, i):
        self.NMEA_Str = i
        #print (i)

    ########################################################################
    ###     Atiendo la señal generada a partir del hilo del Fluorometro
    ########################################################################
    # Paso el valor a la variable para que quede a disposicion del dato del TSG
    def on_FlReady (self, count):
        count = count.replace('\r','').replace('\n','')
        self.Fl_Str = dict()                                            #Creo el diccionario para los valores del fluorometro
        if self.checkBox_15.isChecked() and count.isdecimal():
            value = float(self.spn_Fl_Factor.value())*(int(count) - int(self.spn_Fl_Counts.value()))
            self.Fl_Str['CHL'] = '%.4f' %(value)
        elif self.checkBox_15.isChecked() and count == '':
            self.Fl_Str['CHL'] = 'NaN'
            count = 'NaN'
        elif count == '':
            count = 'NaN'
            self.Fl_Str['CHL'] = 'NaN'
        self.Fl_Str['Counts'] = count
        print(self.Fl_Str)


    ########################################################################
    ###     Crea la cabecera del archivo de datos
    ########################################################################
    def cabecera(self, file):
        # Creo cadena de fecha hora en el formato tipo "Mar 30 2022 12:36:31"
        fecha = datetime.strptime(('%s %s') %(self.NMEA_Str['fecha'], self.NMEA_Str['hora']), '%d%m%y %H:%M:%S')
        with open(file, mode='w', encoding='utf-8') as f:
            f.write("* Sea-Bird %s Data File:\n" %(self.instrumento.SBE45.getModelo()))
            f.write("* FileName = %s\n" %(os.getcwd() + os.sep + file))
            f.write("* Software Version TSX %s\n" %(__version__))
            f.write("* Campaña = %s\n" %(self.txt_Camp.text()))
            f.write("* NMEA Latitude = %s\n" %(self.NMEA_Str['lat']))
            f.write("* NMEA Longitude  = %s\n" %(self.NMEA_Str['lon']))
            f.write("* NMEA UTC (Time) = %s\n" %(fecha.strftime("%b %d %Y %H:%M:%S")))
            f.write("* Real-Time Sample Interval = %s\n" %(self.instrumento.SBE45.getInterval()))
            f.write("** Calibration coefficients %s\n" %(self.instrumento.SBE45.getModelo()))
            for i in self.instrumento.SBE45.getCoefficients().keys():
                f.write("** %s\n" %(i))
                for var, value in self.instrumento.SBE45.getCoefficients()[i].items():
                    #print("**\t %s = %s" %(var, value))
                    f.write("**\t %s = %s\n" %(var, value))
            if self.__Config['Opto']['SBE38']:
                f.write("** Calibration coefficients SBE38\n")
                for var, value in self.instrumento.SBE38.getCoefficients().items():
                    f.write("**\t %s = %s\n" %(var, value))
            if self.__Config['Fl']['Status']:
                f.write("** Calibration coefficients %s\n" %(self.cbox_Fl_Modelo.currentText()))
                f.write("**\t SN = %s\n" %(self.txt_Fl_SN.text()))
                f.write("**\t SF = %.4f\n" %(self.spn_Fl_Factor.value()))
                f.write("**\t CWO = %.0f\n" %(self.spn_Fl_Counts.value()))
            if self.__Config['Ox']['Status']:
                f.write("** Version en desarrollo para Optode AAnderAA")
            f.write("*END*\n\n")
        f.close()

    ########################################################################
    ###     Escribo la cadena ingresada en el archivo diario
    ########################################################################
    def w_File(self, file, cadena):
        # Compruebo si el archivo no existe, entonces lo creo....
        if not(os.path.exists(os.getcwd() + os.sep + file)):
            self.cabecera(file)
        # Luego, escribo el scan de datos
        f = open(os.getcwd() + os.sep + file, mode='a', encoding='utf-8')
        f.writelines('%s\n' %(cadena))
        f.close()

    ########################################################################
    ###     Crea la lista de los datos para escribir en la tabla
    ########################################################################
    def setRow(self, tsg = {}, nmea = {}):
        row = list()
        if nmea != {}:
            tsg.update(nmea)
            for i in self.columns:
                try:
                    row.append(tsg[i])
                except:
                    pass
        else:
            for i in self.columns:
                row.append(tsg[i])
        col = 0
        for item in row:
            cell = QTableWidgetItem(str(item))
            self.tbl_Data.setItem(self.row, col, cell)
            col += 1
        self.row += 1
        self.tbl_Data.scrollToBottom()
        self.tbl_Data.setHorizontalHeaderLabels(self.columns)

    ########################################################################
    ###     Envio cadena de datos al SeaSave por el RS232 seleccionado
    ########################################################################
    def send_SeaSave(self, cadena):
        ser = serial.Serial(port=self.cbox_SeaSave_COM.currentText(), baudrate=self.cbox_SeaSave_BR.currentText())
        for cmd in cadena:
            ser.reset_input_buffer()
            ser.write(cmd.encode('ascii', 'ignore'))
            ser.flush()
        ser.write(b'\r\n')
        ser.close()

    ########################################################################
    ###     Detengo el trabajo de los hilos
    ########################################################################
    def stop_loop(self):
        self.NMEA.working = False
        time.sleep(1)
        self.Opto.working = False
        time.sleep(0.5)
        self.Fluor.working = False

    ########################################################################
    ###  Muestro un mensaje con la lista de parametros a enviar al sistema
    ########################################################################
    def load_cmd (self):
        self.__setConfig()
        mensaje = 'Version aún en desarrollo\nGracias!!!'
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setText(mensaje)
        msgBox.setWindowTitle("Lista de CMD")
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.exec()

    ########################################################################
    ###     Escribo la marca realizada en un archivo mrk
    ########################################################################
    def add_Mrk(self, file):
        # Compruebo si el archivo no existe, entonces lo creo....
        self.btn_Mrk.setEnabled(False)
        file = self.file.replace('dat', 'mrk')
        if not(os.path.exists(os.getcwd() + os.sep + file)):
            self.cabecera_mrk(file)
        # Luego, escribo el scan de datos
        f_hdr = open(os.getcwd() + os.sep + file, mode='a', encoding='utf-8')
        cadena = self.textEdit_3.text()
        f_hdr.writelines('%s\n' %(cadena))
        f_hdr.close()
        self.btn_Mrk.setEnabled(True)

    ########################################################################
    ###     Crea la cabecera del archivo de marcas
    ########################################################################
    def cabecera_mrk(self, file):
        # Creo cadena de fecha hora en el formato tipo "Mar 30 2022 12:36:31"
        fecha = datetime.strptime(('%s %s') %(self.NMEA_Str['fecha'], self.NMEA_Str['hora']), '%d%m%y %H:%M:%S')
        with open(file, mode='w', encoding='utf-8') as f_hdr:
            f_hdr.write("* Sea-Bird %s Data File:\n" %(self.instrumento.SBE45.getModelo()))
            f_hdr.write("* FileName = %s\n" %(os.getcwd() + os.sep + file))
            f_hdr.write("* Software Version TSX %s\n" %(__version__))
            f_hdr.write("* Campaña = %s\n" %(self.txt_Camp.text()))
            f_hdr.write("*END*\n\n")
        f_hdr.close()

    ########################################################################
    ###     Muestro mensaje emergente
    ########################################################################
    def msg_Box(self, mensaje='', titulo = '', icono = QMessageBox.Information):
        msgBox = QMessageBox()
        msgBox.setIcon(icono)
        msgBox.setText(mensaje)
        msgBox.setWindowTitle(titulo)
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.exec()

    def eco_serial(self, device = 'opto'):
        if self.instrumento.Mode == 'SBE45':
            cadena = self.instrumento.SBE45.buffer.decode('utf-8')
        elif self.instrumento.Mode == 'SBE38':
            cadena = self.instrumento.SBE38.buffer.decode('utf-8')
        elif self.instrumento.Mode == 'Box':
            cadena = self.instrumento.buffer.decode('utf-8')
        self.repaint()
        self.textEdit_4.append(('%s' %(cadena)))
        self.repaint()

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    app.installEventFilter(window)
    app.exec_()