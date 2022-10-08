import configparser
import sys, os

"""_summary_

    Returns:
        _type_: _description_
"""

class cfg():
    def __init__(self, file='config.ini'):
        self.file = file
        self.dir_file = os.getcwd() + os.sep + file
        self._cfg = configparser.ConfigParser()
        self._cfg.read(self.dir_file, encoding='latin-1') # encoding='utf-8')
        if not(os.path.isfile(self.dir_file)):
            print('no exite el archivo')

    def Get_cfg(self):
        # Cargo archivo cfg a sus correspondientes variables
        Dir = self._cfg.get('General', 'directorio')
        f_Master = self._cfg.get('General', 'f_master')
        f_Slave = self._cfg.get('General', 'f_slave')
        Status_Slave = self._cfg.get('General', 'slave')

        gps_Com = self._cfg.get('GPS', 'com')
        gps_BR = self._cfg.get('GPS', 'baudrate')

        M_COM = self._cfg.get('Master', 'com')
        M_BR = self._cfg.get('Master', 'baudrate')

        S_COM = self._cfg.get('Slave', 'com')
        S_BR = self._cfg.get('Slave', 'baudrate')

        # Armo el diccionario con cada clave, valor correspondiente
        self._config = {'Dir':Dir, 'LADCP':{'Master': {'file': f_Master, 'COM': M_COM, 'BR':M_BR}, 'Slave':{'file': f_Slave, 'status':Status_Slave, 'COM':S_COM,\
        'BR': S_BR}}, 'GPS':{'COM':gps_Com, 'BR':gps_BR}}
        return self._config

    def Set_cfg(self, cfg):
        #Actualizo los valores de campos
        """
        Por algun motivo se actualiza solo self._config
        Tengo que ver porque ocurre esto.
        """
        self._cfg.set('Campaña','SiglasBuque', self._config['Buque'])
        self._cfg.set('Campaña','Año', self._config['Año'])
        self._cfg.set('Campaña','NroCampaña', self._config['Campaña'])
        self._cfg.set('Campaña','Instrumento', self._config['inst'])
        self._cfg.set('Directorios','CNV', self._config['cnv_dir'])
        self._cfg.set('Directorios','Virgenes', self._config['hex_dir'])
        self._cfg.set('Directorios','Varios', self._config['varios_dir'])
        self._cfg.set('Directorios','Surfer', self._config['Surfer'])
        self._cfg.set('Climatologia', 'sup', self._config['Sup'])
        self._cfg.set('Climatologia', 'fdo', self._config['Fdo'])
        self._cfg.set('Climatologia', 'horiz', self._config['Horiz'])
        #Salvo el archivo
        with open(self.file, 'w') as f:
            self._cfg.write(f)
